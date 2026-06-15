"""Unit-Tests für CryptoScorer — alle Score-Komponenten und Signal-Schwellen."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.domain.entities.crypto_asset import CryptoAsset


def _make_asset(**kwargs) -> CryptoAsset:
    defaults = dict(
        ticker_cg="bitcoin", ticker_yf="BTC-CHF", name="Bitcoin",
        symbol="BTC", kategorie="Layer1", has_six_etp=True,
        price_chf=50000.0, market_cap_chf=1e12, volume_24h_chf=5e9,
        price_change_24h_pct=1.0, price_change_7d_pct=5.0,
        ath_change_pct=-30.0, market_cap_rank=1,
    )
    return CryptoAsset(**{**defaults, **kwargs})


def _make_technicals(
    rsi: float = 50.0,
    macd_above_signal: bool = True,
    close_trend: str = "up",
    volume_trend: str = "flat",
) -> pd.DataFrame:
    n = 300
    close_base = 50000.0
    if close_trend == "up":
        close = [close_base * (1 + i * 0.001) for i in range(n)]
    elif close_trend == "down":
        close = [close_base * (1 - i * 0.001) for i in range(n)]
    else:
        close = [close_base] * n

    if volume_trend == "up":
        volume = [1e6 * (1 + i * 0.002) for i in range(n)]
    else:
        volume = [1e6] * n

    df = pd.DataFrame({
        "Open": close, "High": close, "Low": close, "Close": close, "Volume": volume,
    })
    df["RSI_14"] = rsi
    macd_val = 100.0 if macd_above_signal else -100.0
    df["MACD_12_26_9"] = macd_val
    df["MACDs_12_26_9"] = 0.0
    ema20 = close_base * 0.98
    ema50 = close_base * 0.96
    df["EMA_20"] = ema20
    df["EMA_50"] = ema50
    df["BBU_20_2.0"] = close_base * 1.05
    df["BBL_20_2.0"] = close_base * 0.95
    return df


class TestRsiScore:
    def test_oversold_returns_10(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(25.0) == 10.0

    def test_near_oversold_returns_8(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(40.0) == 8.0

    def test_neutral_returns_5(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(50.0) == 5.0

    def test_near_overbought_returns_3(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(65.0) == 3.0

    def test_overbought_returns_0(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(75.0) == 0.0


class TestFearGreedScore:
    def test_extreme_fear_returns_12(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(20) == 12.0

    def test_fear_returns_9(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(35) == 9.0

    def test_neutral_returns_6(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(50) == 6.0

    def test_greed_returns_3(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(70) == 3.0

    def test_extreme_greed_returns_0(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(85) == 0.0


class TestMomentumScore:
    def test_strong_up_returns_15(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(25.0) == 15.0

    def test_moderate_up_returns_12(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(15.0) == 12.0

    def test_small_up_returns_9(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(7.0) == 9.0

    def test_flat_positive_returns_6(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(2.0) == 6.0

    def test_small_negative_returns_3(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(-3.0) == 3.0

    def test_large_negative_returns_0(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(-10.0) == 0.0


class TestSignalThresholds:
    def setup_method(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        self.scorer = CryptoScorer()

    def _score(self, **asset_kwargs) -> float:
        asset = _make_asset(**asset_kwargs)
        tech = _make_technicals(rsi=28.0, macd_above_signal=True, close_trend="up")
        score, _ = self.scorer.score(asset, tech, fear_greed=20, correlation_smi_1y=0.1)
        return score

    def test_high_score_produces_strong_buy(self):
        score = self._score(price_change_7d_pct=25.0, market_cap_rank=1, ath_change_pct=-20.0)
        assert score >= CryptoScorer.STRONG_BUY_THRESHOLD

    def test_score_is_bounded_0_to_100(self):
        asset = _make_asset(price_change_7d_pct=100.0)
        tech = _make_technicals(rsi=10.0)
        score, _ = self.scorer.score(asset, tech, fear_greed=0, correlation_smi_1y=0.0)
        assert 0.0 <= score <= 100.0

    def test_score_components_sum_matches_total(self):
        asset = _make_asset()
        tech = _make_technicals()
        score, components = self.scorer.score(asset, tech, fear_greed=50, correlation_smi_1y=0.2)
        assert abs(sum(components.values()) - score) < 1.0


class TestSignalReason:
    def test_oversold_rsi_buy_reason_mentions_rsi(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("BUY", "Bitcoin", 65.0, rsi=28.0, fear_greed=50, change_7d=5.0)
        assert "RSI" in reason
        assert "Bitcoin" in reason

    def test_extreme_fear_buy_reason_mentions_angst(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("BUY", "Ethereum", 70.0, rsi=55.0, fear_greed=15, change_7d=2.0)
        assert "Angst" in reason

    def test_hold_reason_mentions_neutral(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("HOLD", "Bitcoin", 50.0, rsi=50.0, fear_greed=50, change_7d=1.0)
        assert "50" in reason

    def test_overbought_sell_reason_mentions_rsi(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("SELL", "Bitcoin", 20.0, rsi=78.0, fear_greed=80, change_7d=-5.0)
        assert "RSI" in reason
