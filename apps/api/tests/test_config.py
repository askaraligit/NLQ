from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import API_DIRECTORY, Settings


def test_bootstrap_does_not_require_external_service_secrets() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url is None
    assert settings.analytics_database_url is None
    assert settings.llm_api_key is None
    assert settings.jwt_secret is None
    assert settings.redis_url is None


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=test\nLOG_LEVEL=warning\n", encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("CORS_ORIGINS", '["https://example.com/", "https://example.com"]')
    monkeypatch.setenv("LLM_API_KEY", "")

    settings = Settings(_env_file=env_file)

    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.cors_origins == ["https://example.com"]
    assert settings.llm_api_key is None


def test_default_dotenv_is_anchored_to_api_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert Settings.model_config["env_file"] == API_DIRECTORY / ".env"
    assert Path(Settings.model_config["env_file"]).is_absolute()

    # Exercise absolute dotenv resolution with fixtures, never the developer's real .env.
    api_directory = tmp_path / "api"
    api_directory.mkdir()
    env_file = api_directory / ".env"
    env_file.write_text("APP_ENV=test\n", encoding="utf-8")
    (tmp_path / ".env").write_text("LOG_LEVEL=NOT_A_LEVEL\n", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", env_file)
    monkeypatch.chdir(tmp_path)

    assert Settings().app_env == "test"


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.com",
        "ftp://example.com",
        "https://example.com/path",
        "https://user:password@example.com",
        "https://example.com?key=value",
    ],
)
def test_cors_rejects_non_origin_urls(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


@pytest.mark.parametrize(
    "values",
    [
        {"app_env": "unknown"},
        {"log_level": "verbose"},
        {"query_timeout_ms": 0},
        {"query_max_rows": -1},
        {"query_page_size": 0},
        {"query_max_response_bytes": 0},
        {"llm_timeout_seconds": 0},
        {"query_max_rows": 10, "query_page_size": 11},
    ],
)
def test_invalid_runtime_settings_fail_early(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_sensitive_settings_are_redacted() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://app:db-password@localhost/nlq",
        analytics_database_url="postgresql://reader:reader-password@localhost/nlq",
        llm_api_key="provider-secret",
        jwt_secret="jwt-secret",
        redis_url="redis://:redis-password@localhost:6379/0",
    )
    serialized = settings.model_dump_json() + repr(settings)

    for secret in [
        "db-password",
        "reader-password",
        "provider-secret",
        "jwt-secret",
        "redis-password",
    ]:
        assert secret not in serialized
    assert settings.database_url.get_secret_value().startswith("postgresql+psycopg://")


@pytest.mark.parametrize("field", ["database_url", "analytics_database_url", "redis_url"])
def test_invalid_secret_urls_do_not_echo_credentials(field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **{field: "invalid://username:private-password@host"})

    assert "private-password" not in str(exc.value)
