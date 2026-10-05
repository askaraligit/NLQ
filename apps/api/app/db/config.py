"""Credential scopes for migration and bootstrap commands."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

API_DIRECTORY = Path(__file__).resolve().parents[2]


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIRECTORY / "migrations" / ".env",
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    migration_database_url: SecretStr
    migration_database_host: str | None = None
    migration_database_port: int | None = Field(default=None, ge=1, le=65535)
    app_env: Literal["development", "test", "staging", "production"] = "development"


def get_migration_settings() -> MigrationSettings:
    return MigrationSettings()


def get_migration_url() -> URL:
    try:
        settings = get_migration_settings()
        url = make_url(settings.migration_database_url.get_secret_value())
    except (ArgumentError, ValidationError, ValueError):
        raise ValueError(
            "Set a valid MIGRATION_DATABASE_URL in migrations/.env or the environment"
        ) from None
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg"}
        or url.username != "nlq_migrator"
        or not url.password
        or not url.host
        or not url.database
    ):
        raise ValueError("MIGRATION_DATABASE_URL must use PostgreSQL and the nlq_migrator identity")
    return url.set(
        drivername="postgresql+psycopg",
        host=settings.migration_database_host or url.host,
        port=settings.migration_database_port or url.port,
    )


class BootstrapSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIRECTORY.parent.parent / ".env",
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "nlq"
    postgres_user: str = "nlq_bootstrap"
    postgres_password: SecretStr
    nlq_app_password: SecretStr = Field(min_length=16)
    nlq_reader_password: SecretStr = Field(min_length=16)
    nlq_migrator_password: SecretStr = Field(min_length=16)

    def connection_kwargs(self) -> dict[str, object]:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password.get_secret_value(),
            "connect_timeout": 10,
        }
