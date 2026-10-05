"""Live readiness coverage using only explicit isolated PostgreSQL credentials."""

import os

import httpx
import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.main import create_app


def _test_connection(variable: str, expected_identity: str) -> str:
    raw_url = os.environ.get(variable)
    if not raw_url:
        pytest.skip(f"Set {variable} to an isolated nlq_test* PostgreSQL database")
    url = make_url(raw_url)
    if (
        url.get_backend_name() != "postgresql"
        or not (url.database or "").startswith("nlq_test")
        or url.username != expected_identity
    ):
        pytest.fail(
            f"{variable} must target a nlq_test* PostgreSQL database as {expected_identity}"
        )
    return raw_url


@pytest.mark.anyio
@pytest.mark.integration
async def test_readiness_uses_both_restricted_runtime_connections() -> None:
    settings = Settings(
        _env_file=None,
        database_url=_test_connection("TEST_APP_DATABASE_URL", "nlq_app"),
        analytics_database_url=_test_connection("TEST_READER_DATABASE_URL", "nlq_reader"),
    )
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"application_database": "ok", "analytics_database": "ok"},
    }
