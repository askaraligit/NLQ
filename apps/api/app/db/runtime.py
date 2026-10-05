"""Runtime database engines, isolated from migration and administrator connections."""

from collections.abc import Generator
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


class DatabaseConfigurationError(ValueError):
    """A runtime connection URL is missing or uses a credential outside its scope."""


class DatabaseUnavailableError(RuntimeError):
    """A configured database cannot currently serve a runtime request."""


@dataclass(frozen=True)
class DatabaseRuntime:
    """Dedicated engine/session factories for application and generated-SQL paths."""

    application_engine: Engine
    analytics_engine: Engine
    application_sessions: sessionmaker[Session]
    analytics_sessions: sessionmaker[Session]

    def dispose(self) -> None:
        self.application_engine.dispose()
        self.analytics_engine.dispose()


def _runtime_url(
    raw_url: str | None,
    expected_username: str,
    host_override: str | None,
    port_override: int | None,
    label: str,
) -> URL:
    if not raw_url:
        raise DatabaseConfigurationError(f"{label}_URL is not configured")
    try:
        url = make_url(raw_url)
    except ArgumentError:
        raise DatabaseConfigurationError(f"{label}_URL must be a valid PostgreSQL URL") from None
    if (
        url.get_backend_name() != "postgresql"
        or url.username != expected_username
        or not url.password
        or not url.host
        or not url.database
    ):
        raise DatabaseConfigurationError(
            f"{label}_URL must use the restricted {expected_username} PostgreSQL identity"
        )
    return url.set(
        drivername="postgresql+psycopg",
        host=host_override or url.host,
        port=port_override or url.port,
    )


def create_database_runtime(settings: Settings) -> DatabaseRuntime:
    """Create pool-backed engines without opening a connection during app startup."""
    application_url = _runtime_url(
        settings.database_url.get_secret_value() if settings.database_url else None,
        "nlq_app",
        settings.database_host,
        settings.database_port,
        "DATABASE",
    )
    analytics_url = _runtime_url(
        settings.analytics_database_url.get_secret_value()
        if settings.analytics_database_url
        else None,
        "nlq_reader",
        settings.analytics_database_host,
        settings.analytics_database_port,
        "ANALYTICS_DATABASE",
    )
    options = {
        "pool_pre_ping": True,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout": settings.database_pool_timeout_seconds,
        "pool_recycle": 1_800,
        "hide_parameters": True,
        "connect_args": {"connect_timeout": settings.database_pool_timeout_seconds},
    }
    application_engine = create_engine(application_url, **options)
    analytics_engine = create_engine(analytics_url, **options)
    return DatabaseRuntime(
        application_engine=application_engine,
        analytics_engine=analytics_engine,
        application_sessions=sessionmaker(
            application_engine, autoflush=False, expire_on_commit=False
        ),
        analytics_sessions=sessionmaker(analytics_engine, autoflush=False, expire_on_commit=False),
    )


def database_status(runtime: DatabaseRuntime | None) -> dict[str, str]:
    """Return non-sensitive connectivity results for readiness probes."""
    if runtime is None:
        return {"application_database": "unconfigured", "analytics_database": "unconfigured"}
    checks: dict[str, str] = {}
    for name, engine, expected_identity in (
        ("application_database", runtime.application_engine, "nlq_app"),
        ("analytics_database", runtime.analytics_engine, "nlq_reader"),
    ):
        try:
            with engine.connect() as connection:
                if connection.scalar(text("SELECT current_user")) != expected_identity:
                    raise DatabaseUnavailableError("Database identity mismatch")
                connection.execute(text("SELECT 1"))
                if (
                    name == "analytics_database"
                    and connection.scalar(text("SHOW default_transaction_read_only")) != "on"
                ):
                    raise DatabaseUnavailableError(
                        "Analytics connection is not read-only by default"
                    )
        except (DatabaseUnavailableError, SQLAlchemyError):
            checks[name] = "unavailable"
        else:
            checks[name] = "ok"
    return checks


def application_session(runtime: DatabaseRuntime) -> Generator[Session, None, None]:
    """Dependency for future application repositories; commits remain service-owned."""
    with runtime.application_sessions() as session:
        yield session


def analytics_session(runtime: DatabaseRuntime) -> Generator[Session, None, None]:
    """Dependency for future validated NLQ execution only."""
    with runtime.analytics_sessions() as session:
        yield session
