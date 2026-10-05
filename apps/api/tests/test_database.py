"""PostgreSQL contracts; opt in only against a dedicated, migrated, seeded test DB.

No runtime or migration environment variable is consulted here. All mutations run in
rolled-back transactions, so the same fixture database can be inspected after a run.
"""

import os
from collections.abc import Iterator
from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import Cursor, sql
from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.bootstrap import _check_existing_access
from app.models import Base
from seeds.dataset import PRIMARY_TENANT_ID, SECONDARY_TENANT_ID
from seeds.loader import seed_database

ERP_TABLES = {
    "customers",
    "suppliers",
    "product_categories",
    "products",
    "purchase_orders",
    "purchase_order_items",
    "sales_orders",
    "sales_order_items",
    "purchase_invoices",
    "sales_invoices",
    "payments",
    "stock",
}


def _test_url(variable: str) -> URL:
    raw = os.environ.get(variable)
    if not raw:
        pytest.skip(f"Set {variable} to an isolated nlq_test* PostgreSQL database")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("nlq_test"):
        pytest.fail(f"{variable} must target a PostgreSQL database named nlq_test*")
    return url.set(drivername="postgresql+psycopg")


def _engine(variable: str, role: str, primary_url: URL | None = None) -> Engine:
    url = _test_url(variable)
    if primary_url is not None:
        assert (url.host, url.port, url.database) == (
            primary_url.host,
            primary_url.port,
            primary_url.database,
        ), f"{variable} must target the same isolated database as TEST_DATABASE_URL"
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT session_user")) == role
    return engine


@pytest.fixture(scope="module")
def database_engine() -> Iterator[Engine]:
    engine = _engine("TEST_DATABASE_URL", "nlq_migrator")
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def reader_engine(database_engine: Engine) -> Iterator[Engine]:
    engine = _engine("TEST_READER_DATABASE_URL", "nlq_reader", database_engine.url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def app_engine(database_engine: Engine) -> Iterator[Engine]:
    engine = _engine("TEST_APP_DATABASE_URL", "nlq_app", database_engine.url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def admin_engine(database_engine: Engine) -> Iterator[Engine]:
    engine = _engine("TEST_ADMIN_DATABASE_URL", "nlq_bootstrap", database_engine.url)
    yield engine
    engine.dispose()


@pytest.fixture
def admin_cursor(admin_engine: Engine) -> Iterator[Cursor]:
    with admin_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with connection.connection.driver_connection.cursor() as cursor:
                yield cursor
        finally:
            transaction.rollback()


@pytest.fixture
def db(database_engine: Engine) -> Iterator[Connection]:
    with database_engine.connect() as connection, connection.begin():
        transaction = connection.get_transaction()
        yield connection
        transaction.rollback()


def test_metadata_registers_requested_erp_relations() -> None:
    tables = {table.name: table for table in Base.metadata.tables.values() if table.schema == "erp"}
    assert set(tables) == ERP_TABLES
    for table in tables.values():
        assert {"id", "tenant_id", "created_at", "updated_at"} <= set(table.c.keys())
        assert "id" in table.primary_key.columns
        for foreign_key in table.foreign_key_constraints:
            if foreign_key.referred_table.schema == "erp":
                assert "tenant_id" in foreign_key.column_keys, table.name


@pytest.mark.integration
def test_migration_created_tables_and_rls(database_engine: Engine) -> None:
    inspector = inspect(database_engine)
    assert set(inspector.get_table_names(schema="erp")) == ERP_TABLES
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM app.alembic_version"))
        protected = connection.execute(
            text(
                "SELECT c.relname, c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'erp' AND c.relkind = 'r'"
            )
        ).all()
    assert {name for name, enabled in protected if enabled} == ERP_TABLES


@pytest.mark.integration
def test_foreign_keys_reject_missing_and_cross_tenant_customer(db: Connection) -> None:
    orders = Base.metadata.tables["erp.sales_orders"]
    customers = Base.metadata.tables["erp.customers"]
    order_id = db.scalar(
        select(orders.c.id).where(orders.c.tenant_id == PRIMARY_TENANT_ID).limit(1)
    )
    foreign_customer = db.scalar(
        select(customers.c.id).where(customers.c.tenant_id == SECONDARY_TENANT_ID).limit(1)
    )
    assert order_id is not None and foreign_customer is not None
    for invalid_customer in (uuid4(), foreign_customer):
        with pytest.raises(IntegrityError) as error, db.begin_nested():
            db.execute(
                orders.update().where(orders.c.id == order_id).values(customer_id=invalid_customer)
            )
        assert error.value.orig.sqlstate == "23503"


@pytest.mark.integration
def test_customer_code_is_unique_within_each_tenant(db: Connection) -> None:
    customers = Base.metadata.tables["erp.customers"]
    first, second = db.execute(
        select(customers.c.id, customers.c.code)
        .where(customers.c.tenant_id == PRIMARY_TENANT_ID)
        .limit(2)
    ).all()
    with pytest.raises(IntegrityError) as error, db.begin_nested():
        db.execute(customers.update().where(customers.c.id == second.id).values(code=first.code))
    assert error.value.orig.sqlstate == "23505"


@pytest.mark.integration
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE erp.sales_order_items SET quantity = 0",
        "UPDATE erp.purchase_order_items SET unit_price = -1",
        "UPDATE erp.sales_order_items SET tax_rate = 101",
        "UPDATE erp.sales_orders SET total_amount = subtotal + tax_amount + 1",
        "UPDATE erp.purchase_orders SET status = 'made_up_status'",
        "UPDATE erp.sales_invoices SET due_date = invoice_date - 1",
        "UPDATE erp.payments SET purchase_invoice_id = NULL, sales_invoice_id = NULL",
        "UPDATE erp.payments SET amount = 0",
        "UPDATE erp.stock SET reserved_quantity = quantity + 1",
    ],
)
def test_business_constraints_are_enforced_by_postgresql(db: Connection, statement: str) -> None:
    with pytest.raises(IntegrityError) as error, db.begin_nested():
        db.execute(text(statement))
    assert error.value.orig.sqlstate == "23514"


@pytest.mark.integration
def test_item_totals_use_exact_decimal_rounding(db: Connection) -> None:
    items = Base.metadata.tables["erp.sales_order_items"]
    item_id = db.scalar(select(items.c.id).limit(1))
    actual = db.execute(
        items.update()
        .where(items.c.id == item_id)
        .values(quantity=Decimal("1.25"), unit_price=Decimal("19.99"), tax_rate=Decimal("18"))
        .returning(items.c.line_subtotal, items.c.tax_amount, items.c.line_total)
    ).one()
    assert tuple(actual) == (Decimal("24.99"), Decimal("4.50"), Decimal("29.49"))


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["purchase", "sales"])
def test_seeded_headers_invoices_and_payments_reconcile(db: Connection, kind: str) -> None:
    # The PostgreSQL-generated line values are checked against seeded header snapshots.
    assert (
        db.scalar(
            text(
                f"SELECT count(*) FROM erp.{kind}_orders o LEFT JOIN ("
                f"SELECT tenant_id, order_id, sum(line_subtotal) subtotal, sum(tax_amount) tax, "
                f"sum(line_total) total FROM erp.{kind}_order_items GROUP BY tenant_id, order_id"
                ") i ON i.tenant_id = o.tenant_id AND i.order_id = o.id "
                "WHERE (o.subtotal, o.tax_amount, o.total_amount) "
                "IS DISTINCT FROM (i.subtotal, i.tax, i.total)"
            )
        )
        == 0
    )
    assert (
        db.scalar(
            text(
                f"SELECT count(*) FROM erp.{kind}_invoices i "
                f"JOIN erp.{kind}_orders o ON o.tenant_id = i.tenant_id AND o.id = i.order_id "
                "WHERE (i.subtotal, i.tax_amount, i.total_amount) <> "
                "(o.subtotal, o.tax_amount, o.total_amount)"
            )
        )
        == 0
    )
    assert (
        db.scalar(
            text(
                f"SELECT count(*) FROM erp.{kind}_invoices i LEFT JOIN ("
                f"SELECT tenant_id, {kind}_invoice_id invoice_id, sum(amount) paid "
                f"FROM erp.payments GROUP BY tenant_id, {kind}_invoice_id"
                ") p ON p.tenant_id = i.tenant_id AND p.invoice_id = i.id "
                "WHERE coalesce(p.paid, 0) > i.total_amount "
                "OR (i.status = 'paid' AND coalesce(p.paid, 0) <> i.total_amount) "
                "OR (i.status = 'partially_paid' AND NOT "
                "(coalesce(p.paid, 0) > 0 AND coalesce(p.paid, 0) < i.total_amount)) "
                "OR (i.status IN ('issued', 'overdue') AND coalesce(p.paid, 0) <> 0)"
            )
        )
        == 0
    )


@pytest.mark.integration
def test_seeding_again_preserves_existing_records(database_engine: Engine) -> None:
    def snapshot() -> dict[str, tuple]:
        with database_engine.connect() as connection:
            return {
                name: tuple(
                    connection.execute(
                        text(f"SELECT count(*), max(updated_at) FROM erp.{name}")
                    ).one()
                )
                for name in ERP_TABLES
            }

    before = snapshot()
    result = seed_database(database_engine)
    assert result and set(result.values()) == {"already_seeded"}
    assert snapshot() == before


@pytest.mark.integration
def test_updated_at_changes_for_direct_sql_writes(db: Connection) -> None:
    customers = Base.metadata.tables["erp.customers"]
    before = db.execute(select(customers).limit(1)).mappings().one()
    db.execute(
        text("UPDATE erp.customers SET updated_at = '2000-01-01T00:00:00Z' WHERE id = :id"),
        {"id": before["id"]},
    )
    after = db.execute(select(customers).where(customers.c.id == before["id"])).mappings().one()
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] > before["updated_at"]


@pytest.mark.integration
def test_reader_rls_cannot_be_changed_using_session_settings(reader_engine: Engine) -> None:
    with reader_engine.connect() as connection, connection.begin():
        assert connection.scalar(text("SHOW default_transaction_read_only")) == "on"
        assert connection.scalar(text("SHOW transaction_read_only")) == "on"
        for table_name in sorted(ERP_TABLES):
            # Identifiers come only from the constant relation allowlist above.
            tenants = set(
                connection.scalars(text(f"SELECT DISTINCT tenant_id FROM erp.{table_name}"))
            )
            assert tenants == {PRIMARY_TENANT_ID}, table_name
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(SECONDARY_TENANT_ID)},
        )
        connection.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
            {"tenant": str(SECONDARY_TENANT_ID)},
        )
        assert set(connection.scalars(text("SELECT DISTINCT tenant_id FROM erp.customers"))) == {
            PRIMARY_TENANT_ID
        }
        assert (
            connection.scalar(
                text("SELECT count(*) FROM erp.customers WHERE tenant_id = :tenant"),
                {"tenant": SECONDARY_TENANT_ID},
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO erp.customers DEFAULT VALUES",
        "UPDATE erp.customers SET updated_at = now()",
        "DELETE FROM erp.payments",
        "DROP TABLE erp.payments",
        "SELECT * FROM app.analytics_principals",
        "SELECT * FROM app.tenants",
        "SET ROLE nlq_migrator",
        "SET SESSION AUTHORIZATION nlq_migrator",
    ],
)
def test_reader_privileges_hold_when_read_only_is_disabled(
    reader_engine: Engine, statement: str
) -> None:
    with reader_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ WRITE"))
            assert connection.scalar(text("SHOW transaction_read_only")) == "off"
            with pytest.raises(DBAPIError) as error:
                connection.execute(text(statement))
            assert error.value.orig.sqlstate == "42501"
        finally:
            # Even a misconfigured database cannot persist a successful test mutation.
            transaction.rollback()


@pytest.mark.integration
def test_app_identity_has_no_erp_access(app_engine: Engine) -> None:
    with app_engine.connect() as connection:
        with pytest.raises(DBAPIError) as error:
            connection.execute(text("SELECT * FROM erp.customers"))
        assert error.value.orig.sqlstate == "42501"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("statement", "message"),
    [
        (
            "GRANT INSERT ON erp.customers TO nlq_reader",
            "unsafe existing table grants",
        ),
        (
            "GRANT UPDATE (name) ON erp.customers TO nlq_reader",
            "unsafe existing table grants",
        ),
        (
            "GRANT SELECT ON erp.customers TO nlq_reader WITH GRANT OPTION",
            "unsafe existing table grants",
        ),
        (
            "GRANT SELECT ON app.tenants TO nlq_reader",
            "unexpected data access",
        ),
        (
            "GRANT SELECT ON erp.customers TO nlq_app",
            "existing ERP grants",
        ),
        (
            "GRANT SELECT (name) ON erp.customers TO nlq_app",
            "existing ERP grants",
        ),
    ],
)
def test_provisioning_rejects_existing_excess_privileges(
    admin_cursor: Cursor, statement: str, message: str
) -> None:
    _check_existing_access(admin_cursor)
    admin_cursor.execute(statement)
    with pytest.raises(ValueError, match=message):
        _check_existing_access(admin_cursor)


@pytest.mark.integration
@pytest.mark.parametrize("role", ["nlq_reader", "nlq_app"])
def test_provisioning_rejects_runtime_object_ownership(admin_cursor: Cursor, role: str) -> None:
    _check_existing_access(admin_cursor)
    probe = sql.Identifier("public", f"nlq_test_ownership_{uuid4().hex}")
    admin_cursor.execute(sql.SQL("CREATE TABLE {} (id integer)").format(probe))
    admin_cursor.execute(sql.SQL("ALTER TABLE {} OWNER TO {}").format(probe, sql.Identifier(role)))
    with pytest.raises(ValueError, match="runtime role owns database objects"):
        _check_existing_access(admin_cursor)
