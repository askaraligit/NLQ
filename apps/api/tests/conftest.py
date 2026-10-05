import os

import pytest

from app.core.config import Settings, get_settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not let a developer's runtime configuration influence tests."""
    for name in os.environ:
        if name.lower() in Settings.model_fields:
            monkeypatch.delenv(name)
    get_settings.cache_clear()
