"""Alembic entry point using the isolated migration identity only."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.config import get_migration_url
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """Inspect only owned application schemas, never public or extensions."""
    if type_ == "schema":
        return name in {"app", "erp"}
    if type_ == "table":
        return parent_names.get("schema_name") in {"app", "erp"}
    return True


def migration_options():
    return {
        "target_metadata": target_metadata,
        "version_table_schema": "app",
        "include_schemas": True,
        "include_name": include_name,
        "compare_type": True,
        "compare_server_default": True,
    }


def run_migrations_offline() -> None:
    context.configure(
        url=get_migration_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **migration_options(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Credentials are never put in Alembic's interpolated config or logged SQL parameters.
    engine = create_engine(get_migration_url(), poolclass=pool.NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, **migration_options())
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
