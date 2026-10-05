"""Provision database roles and schemas using a separate administrator connection."""

import sys

import psycopg
from psycopg import sql
from pydantic import ValidationError

from app.db.config import BootstrapSettings

ERP_RELATIONS = {
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


def _check_existing_access(cursor: psycopg.Cursor) -> None:
    # Ownership bypasses ordinary grants and RLS. Never take over existing runtime-owned data.
    cursor.execute(
        "SELECT 1 FROM ("
        "SELECT relowner AS owner FROM pg_class UNION ALL "
        "SELECT proowner FROM pg_proc UNION ALL SELECT nspowner FROM pg_namespace UNION ALL "
        "SELECT datdba FROM pg_database WHERE datname = current_database()"
        ") objects JOIN pg_roles r ON r.oid = objects.owner "
        "WHERE r.rolname IN ('nlq_reader', 'nlq_app') LIMIT 1"
    )
    if cursor.fetchone():
        raise ValueError("A runtime role owns database objects; provisioning refused")
    cursor.execute(
        "SELECT n.nspname, c.relname, "
        "(has_table_privilege('nlq_reader', c.oid, 'SELECT') OR "
        "has_any_column_privilege('nlq_reader', c.oid, 'SELECT')), "
        "has_table_privilege('nlq_reader', c.oid, "
        "'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN') OR "
        "has_any_column_privilege('nlq_reader', c.oid, 'INSERT, UPDATE, REFERENCES'), "
        "has_table_privilege('nlq_reader', c.oid, 'SELECT WITH GRANT OPTION') OR "
        "has_any_column_privilege('nlq_reader', c.oid, 'SELECT WITH GRANT OPTION'), "
        "has_table_privilege('nlq_app', c.oid, "
        "'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN') OR "
        "has_any_column_privilege('nlq_app', c.oid, 'SELECT, INSERT, UPDATE, REFERENCES') "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname IN ('app', 'erp', 'public') AND c.relkind IN ('r', 'p', 'v', 'm', 'f')"
    )
    for schema, table, reader_select, reader_write, reader_grant, app_access in cursor.fetchall():
        if reader_write or reader_grant:
            raise ValueError(
                "An analytics role has unsafe existing table grants; provisioning refused"
            )
        if reader_select and (schema != "erp" or table not in ERP_RELATIONS):
            raise ValueError("An analytics role has unexpected data access; provisioning refused")
        if app_access and schema == "erp":
            raise ValueError("The app role has existing ERP grants; provisioning refused")


def provision(settings: BootstrapSettings) -> None:
    passwords = {
        "nlq_migrator": settings.nlq_migrator_password,
        "nlq_app": settings.nlq_app_password,
        "nlq_reader": settings.nlq_reader_password,
    }
    with psycopg.connect(**settings.connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            # A concurrent maintenance command must not race role/schema creation.
            cursor.execute("SELECT pg_advisory_xact_lock(715602001)")
            for name, password in passwords.items():
                cursor.execute(
                    "SELECT rolsuper OR rolcreatedb OR rolcreaterole "
                    "OR rolreplication OR rolbypassrls "
                    "FROM pg_roles WHERE rolname = %s",
                    (name,),
                )
                existing = cursor.fetchone()
                if existing is not None and existing[0]:
                    raise ValueError(
                        "A managed role has privileged attributes; provisioning refused"
                    )
                cursor.execute(
                    "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member "
                    "WHERE r.rolname = %s",
                    (name,),
                )
                if cursor.fetchone():
                    raise ValueError(
                        "A managed role has unexpected memberships; provisioning refused"
                    )
                operation = sql.SQL("CREATE ROLE") if existing is None else sql.SQL("ALTER ROLE")
                cursor.execute(
                    sql.SQL(
                        "{} {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(
                        operation, sql.Identifier(name), sql.Literal(password.get_secret_value())
                    )
                )

            _check_existing_access(cursor)
            database = sql.Identifier(settings.postgres_db)
            cursor.execute(
                sql.SQL(
                    "REVOKE ALL ON DATABASE {} FROM PUBLIC, nlq_app, nlq_reader, nlq_migrator"
                ).format(database)
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO nlq_migrator, nlq_app, nlq_reader").format(
                    database
                )
            )
            cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC, nlq_app, nlq_reader")
            cursor.execute(sql.SQL("ALTER DATABASE {} SET timezone = 'UTC'").format(database))
            for schema in ("app", "erp"):
                cursor.execute(
                    "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = %s",
                    (schema,),
                )
                owner = cursor.fetchone()
                if owner is not None and owner[0] != "nlq_migrator":
                    raise ValueError(
                        "An application schema has an unexpected owner; provisioning refused"
                    )
                if owner is None:
                    cursor.execute(
                        sql.SQL("CREATE SCHEMA {} AUTHORIZATION nlq_migrator").format(
                            sql.Identifier(schema)
                        )
                    )
                cursor.execute(
                    sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC, nlq_app, nlq_reader").format(
                        sql.Identifier(schema)
                    )
                )

            cursor.execute("GRANT USAGE ON SCHEMA app TO nlq_app")
            cursor.execute("GRANT USAGE ON SCHEMA erp TO nlq_reader")

            # Explicit schema qualification also keeps Alembic's reflected FK schemas stable.
            cursor.execute("ALTER ROLE nlq_migrator SET search_path = pg_catalog")
            cursor.execute("ALTER ROLE nlq_app SET search_path = pg_catalog, app")
            cursor.execute("ALTER ROLE nlq_reader SET search_path = pg_catalog, erp")
            cursor.execute("ALTER ROLE nlq_reader SET default_transaction_read_only = on")
            cursor.execute("ALTER ROLE nlq_reader SET statement_timeout = '10s'")
            cursor.execute("ALTER ROLE nlq_reader SET lock_timeout = '1s'")
            cursor.execute("ALTER ROLE nlq_reader SET idle_in_transaction_session_timeout = '10s'")
            cursor.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE nlq_migrator "
                "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
            )


def main() -> int:
    try:
        provision(BootstrapSettings())
    except (psycopg.Error, ValidationError, ValueError):
        print(
            "Database provisioning failed. Check administrator connectivity, settings, "
            "role memberships, and schema ownership. Credentials were not printed.",
            file=sys.stderr,
        )
        return 1
    print("Database roles and schemas provisioned. Run Alembic migrations next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
