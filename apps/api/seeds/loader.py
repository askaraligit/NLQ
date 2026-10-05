"""All-or-nothing sample loading; existing business records are never replaced."""

from sqlalchemy import Engine, insert, or_, select, text

from app.models import AnalyticsPrincipal, Base, SeedRun, Tenant
from seeds.dataset import PRIMARY_TENANT_ID, SEED_VERSION, TABLE_ORDER, generate_datasets

SEED_LOCK_ID = 2_026_093_002


def seed_database(engine: Engine) -> dict[str, str]:
    """Create both demo tenants once, or skip their committed version markers.

    The caller supplies a migration-only engine. A shared transaction-level advisory
    lock serializes competing seed commands; rollback includes both tenant markers.
    """
    if engine.dialect.name != "postgresql":
        raise ValueError("Sample loading requires PostgreSQL")
    datasets = generate_datasets()
    statuses = {}
    tenant_table = Tenant.__table__
    marker_table = SeedRun.__table__
    principal_table = AnalyticsPrincipal.__table__
    with engine.begin() as connection:
        if connection.scalar(text("SELECT current_user")) != "nlq_migrator":
            raise ValueError("Sample loading requires the nlq_migrator identity")
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))
        connection.execute(text("SET LOCAL statement_timeout = '120s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SEED_LOCK_ID})
        mapping = connection.scalar(
            select(principal_table.c.tenant_id).where(principal_table.c.db_role == "nlq_reader")
        )
        if mapping is not None and mapping != PRIMARY_TENANT_ID:
            raise ValueError(
                "nlq_reader is already assigned to a different tenant; no data changed"
            )

        for dataset in datasets:
            tenant_id, slug = dataset.tenant["id"], dataset.tenant["slug"]
            marker = connection.scalar(
                select(marker_table.c.version).where(
                    marker_table.c.tenant_id == tenant_id,
                    marker_table.c.version == SEED_VERSION,
                )
            )
            if marker is not None:
                statuses[slug] = "already_seeded"
                continue
            collision = connection.scalar(
                select(tenant_table.c.id).where(
                    or_(tenant_table.c.id == tenant_id, tenant_table.c.slug == slug)
                )
            )
            if collision is not None:
                raise ValueError(
                    f"Tenant {slug} already exists without this seed marker; no data changed"
                )
            connection.execute(insert(tenant_table), [dataset.tenant])
            for name in TABLE_ORDER:
                rows = dataset.tables[name]
                if rows:
                    connection.execute(insert(Base.metadata.tables[f"erp.{name}"]), rows)
            connection.execute(
                insert(marker_table), [{"tenant_id": tenant_id, "version": SEED_VERSION}]
            )
            statuses[slug] = "created"

        if mapping is None:
            connection.execute(
                insert(principal_table), [{"db_role": "nlq_reader", "tenant_id": PRIMARY_TENANT_ID}]
            )
    return statuses
