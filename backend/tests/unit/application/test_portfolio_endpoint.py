"""Unit tests for GET /api/v1/backtest/portfolio endpoint (Phase 06-04).

Tests cover:
- 200 response + valid PortfolioBacktestReport JSON
- CryptoPriceAdapter failure → 503
- Cache: second call does NOT re-invoke the walkforward
- All required schema fields present (Pydantic validation)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

_N = 800


def _make_stub_ohlcv(symbol: str, n: int = _N, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0008, 0.022, n)
    close = 1000.0 * np.cumprod(1 + returns)
    volume = 200_000_000.0 / close  # dollar_vol >> $100M
    idx = pd.date_range("2019-01-01", periods=n, freq="D")
    return pd.DataFrame({"close": close, "volume": volume}, index=idx)


def _stub_report() -> dict[str, Any]:
    """Minimal valid PortfolioBacktestReport JSON."""
    return {
        "coins": ["BTC-USD", "ETH-USD"],
        "sharpe": 1.2,
        "calmar": 0.8,
        "max_dd": -0.35,
        "cagr": 0.25,
        "avg_exposure": 0.45,
        "n_rebalances": 120,
        "beats_equal_weight_bh": True,
        "beats_exposure_matched": True,
        "equity_curve": [["2021-01-01", 1.0], ["2021-01-02", 1.01]],
        "per_coin_stats": {
            "BTC-USD": {"avg_weight": 0.3, "days_in_portfolio": 200},
            "ETH-USD": {"avg_weight": 0.2, "days_in_portfolio": 150},
        },
        "pit_universe": {"BTC-USD": "2019-01-01", "ETH-USD": "2019-01-01"},
        "costs": 0.001,
    }


def _make_test_app_with_mocked_adapter(
    adapter_side_effect: Any = None,
    adapter_return: Any = None,
    wf_return: Any = None,
) -> TestClient:
    """Build a TestClient with monkeypatched adapter and walkforward."""
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from backend.interfaces.rest.routers.signals import backtest_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(backtest_router)
    return TestClient(app)


class TestPortfolioEndpointReturns200:
    def test_returns_200_and_valid_schema(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/backtest/portfolio → 200 + PortfolioBacktestReport."""
        from backend.interfaces.rest.routers import signals as signals_module
        from backend.interfaces.rest.schemas.signals import PortfolioBacktestReport

        # Patch CryptoPriceAdapter.fetch_ohlcv to return stub data
        async def _mock_fetch(
            self_: object, symbol: str, start: str = "2017-01-01"
        ) -> pd.DataFrame:
            return _make_stub_ohlcv(symbol)

        monkeypatch.setattr(
            "backend.infrastructure.adapters.crypto_price_adapter.CryptoPriceAdapter.fetch_ohlcv",
            _mock_fetch,
        )

        # Clear portfolio cache
        signals_module._portfolio_cache.clear()

        app = FastAPI()
        app.include_router(signals_module.backtest_router)
        client = TestClient(app)

        resp = client.get("/api/v1/backtest/portfolio")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        body = resp.json()
        report = PortfolioBacktestReport.model_validate(body)
        assert isinstance(report.sharpe, float)
        assert isinstance(report.beats_equal_weight_bh, bool)
        assert isinstance(report.pit_universe, dict)

    def test_all_required_fields_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All required PortfolioBacktestReport fields present in response."""
        from backend.interfaces.rest.routers import signals as signals_module

        async def _mock_fetch(
            self_: object, symbol: str, start: str = "2017-01-01"
        ) -> pd.DataFrame:
            return _make_stub_ohlcv(symbol)

        monkeypatch.setattr(
            "backend.infrastructure.adapters.crypto_price_adapter.CryptoPriceAdapter.fetch_ohlcv",
            _mock_fetch,
        )
        signals_module._portfolio_cache.clear()

        app = FastAPI()
        app.include_router(signals_module.backtest_router)
        client = TestClient(app)

        resp = client.get("/api/v1/backtest/portfolio")
        assert resp.status_code == 200
        body = resp.json()

        required_fields = {
            "coins",
            "sharpe",
            "calmar",
            "max_dd",
            "cagr",
            "avg_exposure",
            "n_rebalances",
            "beats_equal_weight_bh",
            "beats_exposure_matched",
            "equity_curve",
            "per_coin_stats",
            "pit_universe",
            "costs",
        }
        for field in required_fields:
            assert field in body, f"Missing field: {field}"


class TestPortfolioEndpointErrorHandling:
    def test_adapter_failure_returns_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If CryptoPriceAdapter raises, endpoint must return 503."""
        from backend.interfaces.rest.routers import signals as signals_module

        async def _mock_fetch_fail(
            self_: object, symbol: str, start: str = "2017-01-01"
        ) -> pd.DataFrame:
            raise RuntimeError("yfinance timeout")

        monkeypatch.setattr(
            "backend.infrastructure.adapters.crypto_price_adapter.CryptoPriceAdapter.fetch_ohlcv",
            _mock_fetch_fail,
        )
        signals_module._portfolio_cache.clear()

        app = FastAPI()
        app.include_router(signals_module.backtest_router)
        client = TestClient(app)

        resp = client.get("/api/v1/backtest/portfolio")
        assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.text[:200]}"


class TestPortfolioEndpointCache:
    def test_cache_second_call_skips_walkforward(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Second call within TTL must return cached result without re-fetching."""
        from backend.interfaces.rest.routers import signals as signals_module

        call_count = {"n": 0}

        async def _mock_fetch(
            self_: object, symbol: str, start: str = "2017-01-01"
        ) -> pd.DataFrame:
            call_count["n"] += 1
            return _make_stub_ohlcv(symbol)

        monkeypatch.setattr(
            "backend.infrastructure.adapters.crypto_price_adapter.CryptoPriceAdapter.fetch_ohlcv",
            _mock_fetch,
        )
        signals_module._portfolio_cache.clear()

        app = FastAPI()
        app.include_router(signals_module.backtest_router)
        client = TestClient(app)

        # First call — should fetch
        resp1 = client.get("/api/v1/backtest/portfolio")
        assert resp1.status_code == 200
        count_after_first = call_count["n"]

        # Second call — should be cached
        resp2 = client.get("/api/v1/backtest/portfolio")
        assert resp2.status_code == 200
        assert call_count["n"] == count_after_first, "Second call should use cache and not re-fetch"

        # Both responses should be identical
        assert resp1.json()["sharpe"] == resp2.json()["sharpe"]
