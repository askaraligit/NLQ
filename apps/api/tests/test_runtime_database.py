import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.runtime import (
    DatabaseConfigurationError,
    DatabaseRuntime,
    _runtime_url,
    create_database_runtime,
    database_status,
)


class FakeConnection:
    def __init__(self, identity: str, readonly: str = "on") -> None:
        self.identity = identity
        self.readonly = readonly

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def scalar(self, statement: object) -> str:
        query = str(statement)
        if "current_user" in query:
            return self.identity
        if "default_transaction_read_only" in query:
            return self.readonly
        return "1"

    def execute(self, _: object) -> None:
        return None


class FakeEngine:
    def __init__(self, identity: str, readonly: str = "on", available: bool = True) -> None:
        self.connection = FakeConnection(identity, readonly)
        self.available = available
        self.disposed = False

    def connect(self) -> FakeConnection:
        if not self.available:
            from sqlalchemy.exc import OperationalError

            raise OperationalError("SELECT 1", {}, Exception("not reachable"))
        return self.connection

    def dispose(self) -> None:
        self.disposed = True


def test_runtime_url_requires_expected_restricted_identity() -> None:
    with pytest.raises(DatabaseConfigurationError, match="nlq_app"):
        _runtime_url("postgresql://nlq_migrator:secret@db/nlq", "nlq_app", None, None, "DATABASE")
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is not configured"):
        _runtime_url(None, "nlq_app", None, None, "DATABASE")


def test_runtime_url_uses_container_host_override_without_losing_encoded_password() -> None:
    url = _runtime_url(
        "postgresql+psycopg://nlq_reader:p%40ss%25word@127.0.0.1:55432/nlq",
        "nlq_reader",
        "postgres",
        5432,
        "ANALYTICS_DATABASE",
    )
    assert (url.host, url.port, url.username, url.password) == (
        "postgres",
        5432,
        "nlq_reader",
        "p@ss%word",
    )


def test_create_runtime_uses_two_distinct_pool_backed_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []

    def fake_create_engine(url: object, **options: object) -> FakeEngine:
        calls.append((url, options))
        identity = make_url(str(url)).username
        return FakeEngine(identity or "")

    monkeypatch.setattr("app.db.runtime.create_engine", fake_create_engine)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://nlq_app:app-secret@localhost/nlq",
        analytics_database_url="postgresql://nlq_reader:reader-secret@localhost/nlq",
        database_pool_size=3,
        database_max_overflow=2,
        database_pool_timeout_seconds=4,
    )
    runtime = create_database_runtime(settings)
    assert len(calls) == 2
    assert calls[0][0].username == "nlq_app"
    assert calls[1][0].username == "nlq_reader"
    assert calls[0][1]["pool_size"] == 3
    runtime.dispose()
    assert runtime.application_engine.disposed
    assert runtime.analytics_engine.disposed


@pytest.mark.parametrize(
    ("app_identity", "analytics_identity", "analytics_readonly", "expected"),
    [
        ("nlq_app", "nlq_reader", "on", {"application_database": "ok", "analytics_database": "ok"}),
        (
            "nlq_app",
            "nlq_reader",
            "off",
            {"application_database": "ok", "analytics_database": "unavailable"},
        ),
        (
            "wrong_role",
            "nlq_reader",
            "on",
            {"application_database": "unavailable", "analytics_database": "ok"},
        ),
    ],
)
def test_database_status_checks_identity_and_readonly_defaults(
    app_identity: str, analytics_identity: str, analytics_readonly: str, expected: dict[str, str]
) -> None:
    app = FakeEngine(app_identity)
    analytics = FakeEngine(analytics_identity, analytics_readonly)
    runtime = DatabaseRuntime(app, analytics, object(), object())  # type: ignore[arg-type]
    assert database_status(runtime) == expected


def test_database_status_is_safe_when_configured_connection_is_unavailable() -> None:
    runtime = DatabaseRuntime(
        FakeEngine("nlq_app", available=False), FakeEngine("nlq_reader"), object(), object()
    )  # type: ignore[arg-type]
    assert database_status(runtime) == {
        "application_database": "unavailable",
        "analytics_database": "ok",
    }
