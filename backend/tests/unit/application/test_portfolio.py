"""Unit tests for backend.application.backtest.portfolio (Phase 06-02).

Covers:
- allocate_portfolio() returns PortfolioWeights with correct structure
- Vol-based weighting: higher vol → lower weight
- Per-coin cap enforced (max 40%)
- Max total exposure enforced (80%)
- SELL signals → weight = 0
- Drawdown brake halves all weights when portfolio_dd < threshold
- Empty / single-coin edge cases
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_TARGET_VOL = 0.20
_MAX_WEIGHT = 0.40
_MAX_EXPOSURE = 0.80
_DD_THRESHOLD = -0.15


class TestPortfolioWeightsSchema:
    def test_returns_portfolio_weights(self) -> None:
        from backend.application.backtest.portfolio import PortfolioWeights, allocate_portfolio
        signals = {"BTC-USD": ("BUY", 0.8), "ETH-USD": ("BUY", 0.6)}
        vols = {"BTC-USD": 0.60, "ETH-USD": 0.70}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        assert isinstance(result, PortfolioWeights)
        assert isinstance(result.weights, dict)
        assert isinstance(result.total_exposure, float)

    def test_total_exposure_in_range(self) -> None:
        """Total exposure ≤ max_exposure."""
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {f"COIN{i}-USD": ("BUY", 0.8) for i in range(10)}
        vols = {k: 0.50 for k in signals}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        assert result.total_exposure <= _MAX_EXPOSURE + 1e-9

    def test_weights_sum_equals_total_exposure(self) -> None:
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("BUY", 0.8), "ETH-USD": ("BUY", 0.6)}
        vols = {"BTC-USD": 0.60, "ETH-USD": 0.70}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        assert sum(result.weights.values()) == pytest.approx(result.total_exposure, abs=1e-9)


class TestSellSignals:
    def test_sell_signal_zero_weight(self) -> None:
        """SELL action → weight = 0, no exposure."""
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("SELL", 0.0), "ETH-USD": ("BUY", 0.8)}
        vols = {"BTC-USD": 0.60, "ETH-USD": 0.70}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        assert result.weights.get("BTC-USD", 0.0) == pytest.approx(0.0)

    def test_all_sell_zero_exposure(self) -> None:
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("SELL", 0.0), "ETH-USD": ("SELL", 0.0)}
        vols = {"BTC-USD": 0.60, "ETH-USD": 0.70}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        assert result.total_exposure == pytest.approx(0.0)


class TestPerCoinCap:
    def test_single_coin_capped_at_max_weight(self) -> None:
        """Single BUY coin → capped at max_weight (default 40%)."""
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("BUY", 1.5)}
        vols = {"BTC-USD": 0.10}  # low vol → large raw weight; must be capped
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        assert result.weights.get("BTC-USD", 0.0) <= _MAX_WEIGHT + 1e-9

    def test_no_weight_exceeds_cap(self) -> None:
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {f"COIN{i}-USD": ("BUY", 1.0) for i in range(5)}
        vols = {k: 0.10 for k in signals}  # low vol → large raw weights
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        for coin, w in result.weights.items():
            assert w <= _MAX_WEIGHT + 1e-9, f"{coin}: {w} > {_MAX_WEIGHT}"


class TestVolTargeting:
    def test_higher_vol_gets_lower_weight(self) -> None:
        """Coin with higher vol should receive ≤ weight of low-vol coin (ceteris paribus)."""
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"LOW-USD": ("BUY", 1.0), "HIGH-USD": ("BUY", 1.0)}
        vols = {"LOW-USD": 0.30, "HIGH-USD": 0.90}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        assert result.weights.get("LOW-USD", 0.0) >= result.weights.get("HIGH-USD", 0.0)


class TestDrawdownBrake:
    def test_drawdown_brake_halves_exposure(self) -> None:
        """When portfolio_dd < threshold, all weights are halved."""
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("BUY", 0.8)}
        vols = {"BTC-USD": 0.60}
        normal = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals), portfolio_dd=0.0)
        braked = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals), portfolio_dd=-0.20)
        assert braked.total_exposure == pytest.approx(normal.total_exposure * 0.5, rel=1e-6)

    def test_no_brake_within_threshold(self) -> None:
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("BUY", 0.8)}
        vols = {"BTC-USD": 0.60}
        normal = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals), portfolio_dd=0.0)
        just_ok = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals), portfolio_dd=-0.14)
        assert just_ok.total_exposure == pytest.approx(normal.total_exposure, rel=1e-6)


class TestEligibilityFilter:
    def test_ineligible_coin_excluded(self) -> None:
        """Coins not in eligible_coins are excluded regardless of signal."""
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("BUY", 0.8), "SOL-USD": ("BUY", 0.8)}
        vols = {"BTC-USD": 0.60, "SOL-USD": 0.70}
        # SOL not in eligible set
        result = allocate_portfolio(
            signals, vols, eligible_coins=frozenset({"BTC-USD"})
        )
        assert "SOL-USD" not in result.weights or result.weights["SOL-USD"] == pytest.approx(0.0)
        assert "BTC-USD" in result.weights

    def test_empty_eligible_coins_zero_exposure(self) -> None:
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("BUY", 0.8)}
        vols = {"BTC-USD": 0.60}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset())
        assert result.total_exposure == pytest.approx(0.0)


class TestEdgeCases:
    def test_empty_signals_zero_exposure(self) -> None:
        from backend.application.backtest.portfolio import allocate_portfolio
        result = allocate_portfolio({}, {}, eligible_coins=frozenset())
        assert result.total_exposure == pytest.approx(0.0)
        assert result.weights == {}

    def test_weights_non_negative(self) -> None:
        from backend.application.backtest.portfolio import allocate_portfolio
        signals = {"BTC-USD": ("BUY", 0.8), "ETH-USD": ("SELL", 0.0)}
        vols = {"BTC-USD": 0.60, "ETH-USD": 0.70}
        result = allocate_portfolio(signals, vols, eligible_coins=frozenset(signals))
        for w in result.weights.values():
            assert w >= 0.0
