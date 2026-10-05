from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import Settings

pytestmark = pytest.mark.anyio


@pytest.fixture
def app_factory(monkeypatch: pytest.MonkeyPatch) -> Callable[[Settings], FastAPI]:
    # Import after environment isolation, and prevent the deployment app from loading local .env.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    from app.main import create_app

    return create_app


async def test_application_bootstraps_without_database_or_provider(
    app_factory: Callable[[Settings], FastAPI],
) -> None:
    transport = httpx.ASGITransport(app=app_factory(Settings(_env_file=None)))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 200
        schema = await client.get("/openapi.json")
        assert schema.status_code == 200
        assert schema.json()["info"]["title"] == "NLQ API"
        assert schema.json()["paths"] == {}


async def test_cors_allows_only_configured_frontend_origins(
    app_factory: Callable[[Settings], FastAPI],
) -> None:
    settings = Settings(_env_file=None, cors_origins=["https://app.example.com"])
    transport = httpx.ASGITransport(app=app_factory(settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.options(
            "/openapi.json",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        rejected = await client.options(
            "/openapi.json",
            headers={
                "Origin": "https://untrusted.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
