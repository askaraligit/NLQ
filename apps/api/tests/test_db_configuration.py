from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from app.db.config import MigrationSettings, get_migration_url
from app.db.configure import configure_environment


def test_database_environment_generation_keeps_credentials_in_their_scopes(tmp_path: Path) -> None:
    api = tmp_path / "apps/api"
    api.mkdir(parents=True)
    (api / "pyproject.toml").touch()
    (tmp_path / ".env.example").touch()
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=existing-admin-password\n", encoding="utf-8")
    (api / ".env").write_text("LOG_LEVEL=WARNING\nDATABASE_URL=\n", encoding="utf-8")

    configure_environment(tmp_path)
    root_values = dotenv_values(tmp_path / ".env", interpolate=False)
    runtime = dotenv_values(api / ".env", interpolate=False)
    migration = dotenv_values(api / "migrations/.env", interpolate=False)
    assert runtime["LOG_LEVEL"] == "WARNING"
    assert root_values["POSTGRES_PASSWORD"] == "existing-admin-password"
    assert make_url(runtime["DATABASE_URL"]).username == "nlq_app"
    assert make_url(runtime["ANALYTICS_DATABASE_URL"]).username == "nlq_reader"
    assert make_url(migration["MIGRATION_DATABASE_URL"]).username == "nlq_migrator"
    assert "MIGRATION_DATABASE_URL" not in runtime
    assert "POSTGRES_PASSWORD" not in runtime
    paths = [tmp_path / ".env", api / ".env", api / "migrations/.env"]
    before = [path.read_bytes() for path in paths]
    assert configure_environment(tmp_path) == []
    assert before == [path.read_bytes() for path in paths]


def test_database_environment_refuses_non_repository_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository root"):
        configure_environment(tmp_path)


def test_migration_settings_never_fall_back_to_runtime_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(MigrationSettings.model_config, "env_file", None)
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://nlq_app:private-secret@localhost/nlq")
    with pytest.raises(ValueError, match="MIGRATION_DATABASE_URL") as error:
        get_migration_url()
    assert "private-secret" not in str(error.value)


@pytest.mark.parametrize("user", ["nlq_app", "nlq_reader", "postgres"])
def test_migrations_reject_other_database_identities(
    user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(MigrationSettings.model_config, "env_file", None)
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL", f"postgresql://{user}:private-secret@localhost/nlq"
    )
    with pytest.raises(ValueError, match="nlq_migrator") as error:
        get_migration_url()
    assert "private-secret" not in str(error.value)


def test_container_migration_host_override_preserves_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(MigrationSettings.model_config, "env_file", None)
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL",
        "postgresql+psycopg://nlq_migrator:p%40ss%25word@127.0.0.1:55432/nlq",
    )
    monkeypatch.setenv("MIGRATION_DATABASE_HOST", "postgres")
    monkeypatch.setenv("MIGRATION_DATABASE_PORT", "5432")
    url = get_migration_url()
    assert (url.host, url.port, url.username, url.database) == (
        "postgres",
        5432,
        "nlq_migrator",
        "nlq",
    )
    assert url.password == "p@ss%word"
