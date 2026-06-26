"""Unit-Tests fuer FastAPI-Dependency-Factories."""

from typing import Any
from unittest.mock import patch

import pytest

from backend.config import Settings
from backend.infrastructure.adapters.yfinance_fundamentals_adapter import (
    YFinanceFundamentalsAdapter,
)
from backend.infrastructure.adapters.yfinance_market_data_adapter import YFinanceMarketDataAdapter
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
async def test_get_fundamentals_provider_returns_yfinance_adapter() -> None:
    provider = await get_fundamentals_provider()
    assert isinstance(provider, YFinanceFundamentalsAdapter)


@pytest.mark.asyncio
async def test_get_market_data_provider_returns_yfinance_adapter() -> None:
    provider = await get_market_data_provider()
    assert isinstance(provider, YFinanceMarketDataAdapter)
