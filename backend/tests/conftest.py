from __future__ import annotations

import pytest

from catalyst.config import Settings, get_settings
from catalyst.providers.factory import build_providers
from catalyst.providers.web import MockReader, render_mock


@pytest.fixture
def mock_settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("CATALYST_MODE", "mock")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.sqlite")
    for var in ("WEB_PROVIDER", "LLM_PROVIDER", "PRICE_PROVIDER_IN", "PRICE_PROVIDER_US"):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture
def providers(mock_settings):
    return build_providers(mock_settings)


@pytest.fixture
def page():
    """Rendered mock page by file name (same formats as the real sites)."""
    reader = MockReader()
    return lambda name: render_mock(reader._file(name))
