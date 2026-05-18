"""Unit-Tests fuer FastAPI-Dependency-Factories."""

from typing import Any
from unittest.mock import patch

import pytest

from backend.config import Settings
from backend.infrastructure.providers.stub_fundamentals import StubFundamentalsProvider
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider
from backend.interfaces.rest.dependencies import (
    get_anthropic_client,
    get_fundamentals_provider,
    get_market_data_provider,
)

pytestmark = pytest.mark.unit


def test_get_anthropic_client_uses_timeout_30s_and_max_retries_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # get_anthropic_client is @lru_cache — clear before and after to avoid
    # cross-test contamination.
    get_anthropic_client.cache_clear()
    captured: dict[str, Any] = {}

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        "backend.interfaces.rest.dependencies.anthropic.AsyncAnthropic",
        FakeAsyncAnthropic,
    )
    with patch(
        "backend.interfaces.rest.dependencies.get_settings",
        return_value=Settings(anthropic_api_key="test-key"),
    ):
        get_anthropic_client()

    get_anthropic_client.cache_clear()

    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 30.0
    assert captured["max_retries"] == 3


@pytest.mark.asyncio
async def test_get_fundamentals_provider_dev_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(environment="development")
    provider = await get_fundamentals_provider(settings=settings)
    assert isinstance(provider, StubFundamentalsProvider)
    assert "production" not in caplog.text


@pytest.mark.asyncio
async def test_get_fundamentals_provider_production_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    settings = Settings(environment="production", api_key="test-key")
    with caplog.at_level(logging.WARNING, logger="backend.interfaces.rest.dependencies"):
        await get_fundamentals_provider(settings=settings)
    assert "StubFundamentalsProvider" in caplog.text
    assert "production" in caplog.text


@pytest.mark.asyncio
async def test_get_market_data_provider_production_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    settings = Settings(environment="production", api_key="test-key")
    with caplog.at_level(logging.WARNING, logger="backend.interfaces.rest.dependencies"):
        await get_market_data_provider(settings=settings)
    assert "StubMarketDataProvider" in caplog.text
    assert "production" in caplog.text


@pytest.mark.asyncio
async def test_get_market_data_provider_dev_returns_stub(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(environment="development")
    provider = await get_market_data_provider(settings=settings)
    assert isinstance(provider, StubMarketDataProvider)
    assert "production" not in caplog.text
