"""Validated runtime configuration; external capabilities are inactive in Phase 1."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIRECTORY = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Optional until their capabilities are implemented. SecretStr redacts repr/JSON output.
    database_url: SecretStr | None = None
    analytics_database_url: SecretStr | None = None
    llm_provider: Literal["openai", "anthropic", "local"] = "openai"
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: int = Field(default=30, gt=0)
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "nlq-api"
    jwt_audience: str = "nlq-web"
    redis_url: SecretStr | None = None

    query_timeout_ms: int = Field(default=10_000, gt=0)
    query_max_rows: int = Field(default=1_000, gt=0)
    query_page_size: int = Field(default=100, gt=0)
    query_max_response_bytes: int = Field(default=5 * 1024 * 1024, gt=0)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized = []
        for origin in origins:
            url = TypeAdapter(AnyHttpUrl).validate_python(origin)
            if (
                "*" in (url.host or "")
                or url.username is not None
                or url.password is not None
                or url.path not in (None, "/")
                or url.query is not None
                or url.fragment is not None
            ):
                raise ValueError("CORS_ORIGINS must contain exact HTTP(S) origins without paths")
            normalized.append(str(url).rstrip("/"))
        return list(dict.fromkeys(normalized))

    @field_validator("database_url", "analytics_database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            try:
                TypeAdapter(PostgresDsn).validate_python(value.get_secret_value())
            except ValidationError:
                raise ValueError("Database URL must be a valid PostgreSQL connection URL") from None
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            try:
                TypeAdapter(RedisDsn).validate_python(value.get_secret_value())
            except ValidationError:
                raise ValueError("REDIS_URL must be a valid Redis connection URL") from None
        return value

    @model_validator(mode="after")
    def validate_query_limits(self) -> Self:
        if self.query_page_size > self.query_max_rows:
            raise ValueError("QUERY_PAGE_SIZE must not exceed QUERY_MAX_ROWS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
