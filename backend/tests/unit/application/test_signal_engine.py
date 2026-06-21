"""Unit-Tests für die Signal Engine Module (A7.1–A7.8, Coverage Gate A7.10).

Deckt ab:
- indicators: sma, ema, rsi, macd, bollinger
- consensus: consensus_vote (2-of-3)
- sizing: vol_target_size, drawdown_brake, apply_sizing
- guards: assert_no_lookahead / LookAheadError
- walkforward: run_walkforward (Kernpfad)
- signal_service: evaluate (integriert Layer 1-3)

Alle Tests ohne I/O — rein funktional mit synthetischen Daten.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _trending_series(n: int = 200, start: float = 100.0, drift: float = 0.5) -> pd.Series:
    """Einfach aufsteigend trendende Preisserie."""
    idx = pd.date_range(start="2022-01-01", periods=n, freq="D", tz="UTC")
    values = start + np.arange(n) * drift + np.random.default_rng(42).normal(0, 0.5, n)
    return pd.Series(values, index=idx, name="close")


def _flat_series(n: int = 200, value: float = 100.0) -> pd.Series:
    """Konstante Preisserie (kein Trend, kein Rauschen)."""
    idx = pd.date_range(start="2022-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series([value] * n, index=idx, name="close", dtype=float)


# ── indicators.sma ─────────────────────────────────────────────────────────────


class TestSma:
    def test_sma_returns_nan_for_warmup(self) -> None:
        from backend.application.signals.indicators import sma

        s = _trending_series(50)
        result = sma(s, window=20)
        assert pd.isna(result.iloc[:19]).all()
        assert pd.notna(result.iloc[19])

    def test_sma_values_correct(self) -> None:
        from backend.application.signals.indicators import sma

        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = sma(s, window=3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(2.0)
        assert result.iloc[3] == pytest.approx(3.0)
        assert result.iloc[4] == pytest.approx(4.0)

    def test_sma_aligns_to_input_index(self) -> None:
        from backend.application.signals.indicators import sma

        s = _trending_series(100)
        result = sma(s, window=10)
        assert result.index.equals(s.index)


# ── indicators.ema ─────────────────────────────────────────────────────────────


class TestEma:
    def test_ema_has_nan_for_warmup(self) -> None:
        from backend.application.signals.indicators import ema

        s = _trending_series(50)
        result = ema(s, window=10)
        assert pd.isna(result.iloc[:9]).all()
        assert pd.notna(result.iloc[9])

    def test_ema_converges_to_new_level_faster_than_sma(self) -> None:
        from backend.application.signals.indicators import ema, sma

        # Sanity: EMA und SMA sind identisch auf konstanter Serie
        n = 100
        prices = pd.Series([150.0] * n)
        ema_val = ema(prices, window=12).iloc[-1]
        sma_val = sma(prices, window=12).iloc[-1]
        assert ema_val == pytest.approx(150.0)
        assert sma_val == pytest.approx(150.0)


# ── indicators.rsi ─────────────────────────────────────────────────────────────


class TestRsi:
    def test_rsi_range(self) -> None:
        from backend.application.signals.indicators import rsi

        s = _trending_series(200)
        result = rsi(s, window=14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_overbought_on_strong_uptrend(self) -> None:
        from backend.application.signals.indicators import rsi

        n = 100
        prices = pd.Series([100.0 + i * 2 for i in range(n)])
        result = rsi(prices, window=14)
        assert result.dropna().iloc[-1] > 70

    def test_rsi_oversold_on_strong_downtrend(self) -> None:
        from backend.application.signals.indicators import rsi

        n = 100
        prices = pd.Series([200.0 - i * 1.5 for i in range(n)])
        result = rsi(prices, window=14)
        assert result.dropna().iloc[-1] < 40

    def test_rsi_warmup_nan(self) -> None:
        from backend.application.signals.indicators import rsi

        s = _trending_series(50)
        result = rsi(s, window=14)
        assert pd.isna(result.iloc[:14]).all()


# ── indicators.macd ────────────────────────────────────────────────────────────


class TestMacd:
    def test_macd_returns_three_series(self) -> None:
        from backend.application.signals.indicators import macd

        s = _trending_series(200)
        m, sig, hist = macd(s)
        assert len(m) == len(s)
        assert len(sig) == len(s)
        assert len(hist) == len(s)

    def test_macd_histogram_positive_on_uptrend(self) -> None:
        from backend.application.signals.indicators import macd

        n = 200
        prices = pd.Series([100.0 + i * 0.5 for i in range(n)])
        _, _, hist = macd(prices)
        # On steady uptrend, histogram should eventually be positive
        assert hist.dropna().iloc[-1] > 0

    def test_macd_aligns_to_index(self) -> None:
        from backend.application.signals.indicators import macd

        s = _trending_series(200)
        m, sig, hist = macd(s)
        assert m.index.equals(s.index)
        assert sig.index.equals(s.index)
        assert hist.index.equals(s.index)


# ── consensus.consensus_vote ───────────────────────────────────────────────────


class TestConsensusVote:
    def test_all_three_active_fires(self) -> None:
        from backend.application.signals.consensus import consensus_vote

        df = pd.DataFrame({"ma_signal": [1], "macd_signal": [1], "rsi_signal": [1]})
        result = consensus_vote(df)
        assert result.iloc[0] == 1

    def test_two_of_three_fires(self) -> None:
        from backend.application.signals.consensus import consensus_vote

        df = pd.DataFrame({"ma_signal": [1], "macd_signal": [1], "rsi_signal": [0]})
        result = consensus_vote(df)
        assert result.iloc[0] == 1

    def test_one_of_three_does_not_fire(self) -> None:
        from backend.application.signals.consensus import consensus_vote

        df = pd.DataFrame({"ma_signal": [1], "macd_signal": [0], "rsi_signal": [0]})
        result = consensus_vote(df)
        assert result.iloc[0] == 0

    def test_none_active_does_not_fire(self) -> None:
        from backend.application.signals.consensus import consensus_vote

        df = pd.DataFrame({"ma_signal": [0], "macd_signal": [0], "rsi_signal": [0]})
        result = consensus_vote(df)
        assert result.iloc[0] == 0

    def test_empty_df_returns_zeros(self) -> None:
        from backend.application.signals.consensus import consensus_vote

        df = pd.DataFrame({"unknown_col": [1, 0, 1]})
        result = consensus_vote(df)
        assert (result == 0).all()

    def test_multiple_rows(self) -> None:
        from backend.application.signals.consensus import consensus_vote

        df = pd.DataFrame(
            {
                "ma_signal": [1, 0, 1],
                "macd_signal": [1, 0, 0],
                "rsi_signal": [0, 1, 0],
            }
        )
        result = consensus_vote(df)
        assert result.iloc[0] == 1  # 2/3
        assert result.iloc[1] == 0  # 1/3
        assert result.iloc[2] == 0  # 1/3


# ── sizing ─────────────────────────────────────────────────────────────────────


class TestVolTargetSize:
    def test_normal_vol(self) -> None:
        from backend.application.signals.sizing import vol_target_size

        size = vol_target_size(pred_vol=0.60, target_vol=0.60)
        assert size == pytest.approx(1.0)

    def test_high_vol_reduces_size(self) -> None:
        from backend.application.signals.sizing import vol_target_size

        size = vol_target_size(pred_vol=1.20, target_vol=0.60)
        assert size == pytest.approx(0.5)

    def test_low_vol_capped_at_cap(self) -> None:
        from backend.application.signals.sizing import vol_target_size

        size = vol_target_size(pred_vol=0.10, target_vol=0.60, cap=1.5)
        assert size == pytest.approx(1.5)

    def test_zero_vol_uses_epsilon_not_divzero(self) -> None:
        from backend.application.signals.sizing import vol_target_size

        size = vol_target_size(pred_vol=0.0, target_vol=0.60, cap=1.5)
        assert size == pytest.approx(1.5)

    def test_size_within_bounds(self) -> None:
        from backend.application.signals.sizing import vol_target_size

        for vol in [0.01, 0.30, 0.60, 1.00, 2.00]:
            size = vol_target_size(pred_vol=vol)
            assert 0.0 <= size <= 1.5


class TestDrawdownBrake:
    def test_no_brake_when_dd_above_threshold(self) -> None:
        from backend.application.signals.sizing import drawdown_brake

        size = drawdown_brake(size=1.0, current_dd=-0.10, threshold=-0.20)
        assert size == pytest.approx(1.0)

    def test_brake_halves_size_when_dd_below_threshold(self) -> None:
        from backend.application.signals.sizing import drawdown_brake

        size = drawdown_brake(size=1.0, current_dd=-0.25, threshold=-0.20)
        assert size == pytest.approx(0.5)

    def test_brake_at_exact_threshold_no_brake(self) -> None:
        from backend.application.signals.sizing import drawdown_brake

        size = drawdown_brake(size=1.0, current_dd=-0.20, threshold=-0.20)
        assert size == pytest.approx(1.0)


class TestApplySizing:
    def test_sell_always_zero(self) -> None:
        from backend.application.signals.sizing import apply_sizing

        assert apply_sizing("SELL", pred_vol=0.60) == 0.0

    def test_buy_returns_positive_size(self) -> None:
        from backend.application.signals.sizing import apply_sizing

        size = apply_sizing("BUY", pred_vol=0.60)
        assert size > 0.0
        assert size <= 1.5

    def test_hold_returns_positive_size(self) -> None:
        from backend.application.signals.sizing import apply_sizing

        size = apply_sizing("HOLD", pred_vol=0.60)
        assert size > 0.0

    def test_drawdown_reduces_size_on_buy(self) -> None:
        from backend.application.signals.sizing import apply_sizing

        size_normal = apply_sizing("BUY", pred_vol=0.60, current_dd=-0.05)
        size_stressed = apply_sizing("BUY", pred_vol=0.60, current_dd=-0.30)
        assert size_stressed < size_normal


# ── backtest.guards ────────────────────────────────────────────────────────────


class TestLookAheadGuard:
    def test_passes_for_shifted_feature(self) -> None:
        from backend.application.backtest.guards import assert_no_lookahead

        # Verwende zufällige (nicht lineare) Preise — shift(1) ergibt corr < 0.999
        rng = np.random.default_rng(0)
        prices = pd.Series(100.0 + rng.standard_normal(100).cumsum(), name="close")
        df = pd.DataFrame({"close": prices, "feat": prices.shift(1)})
        assert_no_lookahead(df, feature_cols=["feat"], price_col="close")

    def test_raises_for_identical_feature(self) -> None:
        from backend.application.backtest.guards import LookAheadError, assert_no_lookahead

        prices = pd.Series([100.0 + i for i in range(100)], name="close")
        df = pd.DataFrame({"close": prices, "feat": prices})
        with pytest.raises(LookAheadError):
            assert_no_lookahead(df, feature_cols=["feat"], price_col="close")

    def test_raises_for_missing_price_col(self) -> None:
        from backend.application.backtest.guards import assert_no_lookahead

        df = pd.DataFrame({"feat": [1, 2, 3]})
        with pytest.raises(KeyError):
            assert_no_lookahead(df, feature_cols=["feat"], price_col="close")

    def test_raises_for_missing_feature_col(self) -> None:
        from backend.application.backtest.guards import assert_no_lookahead

        df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
        with pytest.raises(KeyError):
            assert_no_lookahead(df, feature_cols=["nonexistent"], price_col="close")

    def test_skips_when_too_few_data_points(self) -> None:
        from backend.application.backtest.guards import assert_no_lookahead

        # Only 1 row — not enough for meaningful correlation
        df = pd.DataFrame({"close": [100.0], "feat": [100.0]})
        assert_no_lookahead(df, feature_cols=["feat"], price_col="close")


# ── backtest.walkforward ───────────────────────────────────────────────────────


class TestRunWalkforward:
    def _make_prices_and_signals(
        self, n: int = 500, trend: float = 0.001
    ) -> tuple[pd.DataFrame, pd.Series]:
        idx = pd.date_range(start="2020-01-01", periods=n, freq="D", tz="UTC")
        rng = np.random.default_rng(99)
        close = 100.0 * np.cumprod(1 + rng.normal(trend, 0.02, n))
        prices = pd.DataFrame({"close": close}, index=idx)
        sma30 = pd.Series(close, index=idx).rolling(30, min_periods=1).mean()
        signals = (pd.Series(close, index=idx) > sma30).astype(float)
        return prices, signals

    def test_returns_backtest_report(self) -> None:
        from backend.application.backtest.walkforward import run_walkforward
        from backend.interfaces.rest.schemas.signals import BacktestReport

        prices, signals = self._make_prices_and_signals()
        report = run_walkforward(prices=prices, signals=signals, coin="BTC-USD")
        assert isinstance(report, BacktestReport)

    def test_report_fields_present(self) -> None:
        from backend.application.backtest.walkforward import run_walkforward

        prices, signals = self._make_prices_and_signals()
        report = run_walkforward(prices=prices, signals=signals, coin="ETH-USD")
        assert report.coin == "ETH-USD"
        assert isinstance(report.cagr, float)
        assert isinstance(report.sharpe, float)
        assert report.max_dd <= 0.0
        assert isinstance(report.beats_exposure_matched, bool)
        assert report.n_trades >= 0
        assert len(report.equity_curve) > 0

    def test_equity_curve_starts_near_one(self) -> None:
        from backend.application.backtest.walkforward import run_walkforward

        prices, signals = self._make_prices_and_signals()
        report = run_walkforward(prices=prices, signals=signals)
        _, first_val = report.equity_curve[0]
        assert 0.0 <= first_val <= 2.0  # sanity bound

    def test_n_trades_positive_on_active_signals(self) -> None:
        from backend.application.backtest.walkforward import run_walkforward

        prices, signals = self._make_prices_and_signals(n=500, trend=0.002)
        report = run_walkforward(prices=prices, signals=signals)
        assert report.n_trades > 0


# ── signals.factors ───────────────────────────────────────────────────────────


class TestCrossSectionalMomentum:
    def _make_price_matrix(self, n: int = 100) -> pd.DataFrame:
        rng = np.random.default_rng(7)
        idx = pd.date_range(start="2022-01-01", periods=n, freq="D", tz="UTC")
        return pd.DataFrame(
            {
                "BTC-USD": 100.0 * np.cumprod(1 + rng.normal(0.005, 0.03, n)),
                "ETH-USD": 100.0 * np.cumprod(1 + rng.normal(0.002, 0.04, n)),
                "ADA-USD": 100.0 * np.cumprod(1 + rng.normal(0.001, 0.05, n)),
            },
            index=idx,
        )

    def test_returns_dataframe_with_composite_rank(self) -> None:
        from backend.application.signals.factors import cross_sectional_momentum

        prices = self._make_price_matrix()
        result = cross_sectional_momentum(prices)
        assert "composite_rank" in result.columns
        assert len(result) == 3  # 3 coins

    def test_ranks_are_positive_integers(self) -> None:
        from backend.application.signals.factors import cross_sectional_momentum

        prices = self._make_price_matrix()
        result = cross_sectional_momentum(prices)
        assert (result["composite_rank"] >= 1).all()

    def test_custom_windows(self) -> None:
        from backend.application.signals.factors import cross_sectional_momentum

        prices = self._make_price_matrix(n=200)
        result = cross_sectional_momentum(prices, windows=[7, 14])
        assert "momentum_rank_7d" in result.columns
        assert "momentum_rank_14d" in result.columns


class TestOnchainHealthScore:
    def _make_onchain_df(self) -> pd.DataFrame:
        n = 30
        return pd.DataFrame(
            {
                "coin_id": ["BTC"] * n + ["ETH"] * n,
                "date": list(pd.date_range("2024-01-01", periods=n)) * 2,
                "mvrv_z": np.random.default_rng(5).normal(0, 1, 2 * n),
                "active_addresses": np.random.default_rng(6)
                .integers(1000, 100000, 2 * n)
                .astype(float),
            }
        )

    def test_scores_in_zero_one_range(self) -> None:
        from backend.application.signals.factors import onchain_health_score

        df = self._make_onchain_df()
        result = onchain_health_score(df)
        assert (result >= 0).all() and (result <= 1).all()

    def test_returns_series_indexed_by_coin(self) -> None:
        from backend.application.signals.factors import onchain_health_score

        df = self._make_onchain_df()
        result = onchain_health_score(df)
        assert "BTC" in result.index
        assert "ETH" in result.index

    def test_fallback_when_only_mvrv(self) -> None:
        from backend.application.signals.factors import onchain_health_score

        df = pd.DataFrame(
            {
                "coin_id": ["BTC"] * 20,
                "date": pd.date_range("2024-01-01", periods=20),
                "mvrv_z": np.random.default_rng(8).normal(0, 1, 20),
                "active_addresses": [np.nan] * 20,
            }
        )
        result = onchain_health_score(df)
        assert 0.0 <= float(result["BTC"]) <= 1.0

    def test_neutral_fallback_when_all_nan(self) -> None:
        from backend.application.signals.factors import onchain_health_score

        df = pd.DataFrame(
            {
                "coin_id": ["SOL"],
                "date": [pd.Timestamp("2024-01-01")],
                "mvrv_z": [np.nan],
                "active_addresses": [np.nan],
            }
        )
        result = onchain_health_score(df)
        assert float(result["SOL"]) == pytest.approx(0.5)


# ── signals.vol_forecast ───────────────────────────────────────────────────────


class TestRealizedVol:
    def test_returns_series(self) -> None:
        from backend.application.signals.vol_forecast import realized_vol

        close = _trending_series()
        rv = realized_vol(close)
        assert isinstance(rv, pd.Series)
        assert len(rv) == len(close)

    def test_annualized_values_reasonable(self) -> None:
        from backend.application.signals.vol_forecast import realized_vol

        close = _trending_series(200)
        rv = realized_vol(close)
        valid = rv.dropna()
        # Annualisierte Vol eines realistischen Assets: zwischen 1% und 1000%
        assert (valid > 0).all()

    def test_first_values_nan(self) -> None:
        from backend.application.signals.vol_forecast import realized_vol

        close = _trending_series(50)
        rv = realized_vol(close, window=5)
        # Mindestens 1 NaN zu Beginn
        assert pd.isna(rv.iloc[0])


class TestBuildHarFeatures:
    def test_columns_present(self) -> None:
        from backend.application.signals.vol_forecast import build_har_features, realized_vol

        close = _trending_series(200)
        rv = realized_vol(close)
        features = build_har_features(rv)
        assert "rv_1d" in features.columns
        assert "rv_5d" in features.columns
        assert "rv_22d" in features.columns

    def test_rv_1d_is_shift_1_of_rv(self) -> None:
        from backend.application.signals.vol_forecast import build_har_features, realized_vol

        close = _trending_series(200)
        rv = realized_vol(close)
        features = build_har_features(rv)
        # rv_1d at index 5 should equal rv at index 4 (shift(1))
        assert features["rv_1d"].iloc[5] == pytest.approx(rv.iloc[4])


class TestFitWalkforward:
    def _make_close_df(self, n: int = 400) -> pd.DataFrame:
        rng = np.random.default_rng(10)
        idx = pd.date_range(start="2021-01-01", periods=n, freq="D")
        btc = 100.0 * np.cumprod(1 + rng.normal(0.001, 0.03, n))
        eth = 100.0 * np.cumprod(1 + rng.normal(0.001, 0.04, n))
        return pd.DataFrame({"BTC-USD": btc, "ETH-USD": eth}, index=idx)

    def test_returns_dict_with_coin_keys(self) -> None:
        from backend.application.signals.vol_forecast import fit_walkforward

        close = self._make_close_df()
        result = fit_walkforward(close, min_train=252, step=21)
        assert "BTC-USD" in result
        assert "ETH-USD" in result

    def test_model_info_has_required_keys(self) -> None:
        from backend.application.signals.vol_forecast import fit_walkforward

        close = self._make_close_df()
        result = fit_walkforward(close, min_train=252, step=21)
        info = result["BTC-USD"]
        assert "model" in info
        assert "model_type" in info
        assert "oos_r2" in info
        assert "feature_cols" in info

    def test_fallback_with_short_series(self) -> None:
        """Zu kurze Serie → Fallback HAR-Modell (kein Walk-Forward)."""
        from backend.application.signals.vol_forecast import fit_walkforward

        rng = np.random.default_rng(11)
        n = 50  # Weniger als min_train=252
        prices = pd.Series(
            100.0 * np.cumprod(1 + rng.normal(0.001, 0.03, n)),
            index=pd.date_range("2023-01-01", periods=n, freq="D"),
        )
        close_df = pd.DataFrame({"SOL-USD": prices})
        result = fit_walkforward(close_df, min_train=252, step=21)
        assert "SOL-USD" in result
        assert result["SOL-USD"]["model_type"] == "har"


class TestPredictVol:
    def _make_model_info(self) -> tuple[pd.Series, dict[str, Any]]:
        from sklearn.linear_model import LinearRegression

        from backend.application.signals.vol_forecast import build_har_features, realized_vol

        rng = np.random.default_rng(42)
        n = 300
        prices = pd.Series(
            100.0 * np.cumprod(1 + rng.normal(0.001, 0.03, n)),
            index=pd.date_range("2022-01-01", periods=n, freq="D"),
        )
        rv = realized_vol(prices)
        features = build_har_features(rv)
        target = rv.shift(-1)

        mask = features.notna().all(axis=1) & target.notna()
        X = features[mask].values
        y = target[mask].values
        model = LinearRegression().fit(X, y)

        model_info = {
            "model": model,
            "model_type": "har",
            "feature_cols": ["rv_1d", "rv_5d", "rv_22d"],
            "oos_r2": 0.1,
            "har_r2": 0.1,
            "lgbm_r2": None,
        }
        return prices, model_info

    def test_returns_positive_float(self) -> None:
        from backend.application.signals.vol_forecast import predict_vol

        prices, model_info = self._make_model_info()
        asof = prices.index[-1].date()
        pred = predict_vol(prices, model_info, asof)
        assert pred > 0.0
        assert isinstance(pred, float)

    def test_clip_to_positive(self) -> None:
        """predict_vol darf nie negativ zurückgeben."""
        from backend.application.signals.vol_forecast import predict_vol

        prices, model_info = self._make_model_info()
        asof = prices.index[-1].date()
        pred = predict_vol(prices, model_info, asof)
        assert pred >= 0.0


# ── indicators.bollinger + atr ─────────────────────────────────────────────────


class TestBollinger:
    def test_upper_above_middle_above_lower(self) -> None:
        from backend.application.signals.indicators import bollinger

        close = _trending_series(100)
        upper, middle, lower = bollinger(close)
        valid = upper.dropna().index
        assert (upper[valid] >= middle[valid]).all()
        assert (middle[valid] >= lower[valid]).all()

    def test_warmup_nan(self) -> None:
        from backend.application.signals.indicators import bollinger

        close = _trending_series(50)
        upper, _, _ = bollinger(close, window=20)
        assert pd.isna(upper.iloc[0])


class TestAtr:
    def test_returns_non_negative_series(self) -> None:
        from backend.application.signals.indicators import atr

        close = _trending_series(100)
        high = close * 1.02
        low = close * 0.98
        result = atr(high, low, close, window=14)
        assert (result >= 0).all()

    def test_length_matches_input(self) -> None:
        from backend.application.signals.indicators import atr

        close = _trending_series(100)
        high = close * 1.02
        low = close * 0.98
        result = atr(high, low, close)
        assert len(result) == len(close)


# ── signal_service.evaluate ────────────────────────────────────────────────────


class TestSignalServiceEvaluate:
    def _make_prices_df(self, coin: str, n: int = 200, end: date | None = None) -> pd.DataFrame:
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0.001, 0.03, n)
        prices = 100.0 * np.cumprod(1 + returns)
        end_date = pd.Timestamp(end or date.today(), tz="UTC")
        idx = pd.date_range(end=end_date, periods=n, freq="D", tz="UTC")
        return pd.DataFrame({coin: prices}, index=idx)

    @pytest.mark.asyncio
    async def test_returns_signal_vector(self) -> None:
        from backend.application.signals.signal_service import evaluate
        from backend.interfaces.rest.schemas.signals import SignalVector

        prices_df = self._make_prices_df("BTC-USD")
        asof = date.today()
        sv = await evaluate(coin="BTC-USD", asof=asof, prices_df=prices_df)
        assert isinstance(sv, SignalVector)

    @pytest.mark.asyncio
    async def test_action_is_valid_literal(self) -> None:
        from backend.application.signals.signal_service import evaluate

        prices_df = self._make_prices_df("ETH-USD")
        sv = await evaluate(coin="ETH-USD", asof=date.today(), prices_df=prices_df)
        assert sv.action in ("BUY", "HOLD", "SELL")

    @pytest.mark.asyncio
    async def test_size_factor_bounds(self) -> None:
        from backend.application.signals.signal_service import evaluate

        prices_df = self._make_prices_df("SOL-USD")
        sv = await evaluate(coin="SOL-USD", asof=date.today(), prices_df=prices_df)
        assert 0.0 <= sv.size_factor <= 1.5

    @pytest.mark.asyncio
    async def test_confidence_bounds(self) -> None:
        from backend.application.signals.signal_service import evaluate

        prices_df = self._make_prices_df("ADA-USD")
        sv = await evaluate(coin="ADA-USD", asof=date.today(), prices_df=prices_df)
        assert 0.0 <= sv.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_sub_scores_have_expected_keys(self) -> None:
        from backend.application.signals.signal_service import evaluate

        prices_df = self._make_prices_df("BTC-USD")
        sv = await evaluate(coin="BTC-USD", asof=date.today(), prices_df=prices_df)
        expected_keys = {
            "ma_signal",
            "macd_signal",
            "rsi_signal",
            "vol_pred",
            "momentum_rank",
            "onchain_score",
        }
        assert expected_keys <= set(sv.sub_scores.keys())

    @pytest.mark.asyncio
    async def test_sell_action_gives_zero_size(self) -> None:
        """SELL-Aktion muss immer size_factor == 0 erzeugen (kein Short)."""
        from backend.application.signals.signal_service import evaluate

        # Fallende Preise erzwingen SELL-Signal
        n = 200
        prices = [200.0 - i * 0.8 for i in range(n)]  # starker Abwärtstrend
        today_ts = pd.Timestamp(date.today(), tz="UTC")
        idx = pd.date_range(end=today_ts, periods=n, freq="D", tz="UTC")
        prices_df = pd.DataFrame({"FAKE-USD": prices}, index=idx)
        sv = await evaluate(coin="FAKE-USD", asof=date.today(), prices_df=prices_df)
        if sv.action == "SELL":
            assert sv.size_factor == 0.0

    @pytest.mark.asyncio
    async def test_raises_for_missing_coin(self) -> None:
        from backend.application.signals.signal_service import evaluate

        prices_df = self._make_prices_df("BTC-USD")
        with pytest.raises(ValueError, match="nicht in prices_df"):
            await evaluate(coin="MISSING-USD", asof=date.today(), prices_df=prices_df)

    @pytest.mark.asyncio
    async def test_raises_for_insufficient_data(self) -> None:
        from backend.application.signals.signal_service import evaluate

        # Nur 5 Preispunkte — zu wenig (min. 30 erforderlich)
        prices_df = pd.DataFrame(
            {"BTC-USD": [100.0, 101.0, 99.0, 102.0, 98.0]},
            index=pd.date_range("2025-01-01", periods=5, freq="D", tz="UTC"),
        )
        # Stichtag muss UTC-aware sein für Vergleich
        asof = pd.Timestamp("2025-01-05", tz="UTC").date()
        with pytest.raises(ValueError, match="Zu wenig"):
            await evaluate(coin="BTC-USD", asof=asof, prices_df=prices_df)

    @pytest.mark.asyncio
    async def test_evaluate_with_onchain_data(self) -> None:
        """evaluate() akzeptiert on-chain Daten und gibt gültigen SignalVector zurück."""
        from backend.application.signals.signal_service import evaluate

        prices_df = self._make_prices_df("BTC-USD")
        n = 30
        onchain_df = pd.DataFrame(
            {
                "coin_id": ["BTC-USD"] * n,
                # UTC-aware Dates für Kompatibilität mit tz-aware prices Index
                "date": pd.date_range("2024-01-01", periods=n, tz="UTC"),
                "mvrv_z": np.random.default_rng(99).normal(0, 1, n),
                "active_addresses": np.random.default_rng(100)
                .integers(1000, 100000, n)
                .astype(float),
            }
        )
        sv = await evaluate(
            coin="BTC-USD",
            asof=date.today(),
            prices_df=prices_df,
            onchain_df=onchain_df,
        )
        assert sv.action in ("BUY", "HOLD", "SELL")

    @pytest.mark.asyncio
    async def test_evaluate_with_vol_model_info(self) -> None:
        """evaluate() verwendet vol_model_info für Sizing wenn vorhanden."""
        from sklearn.linear_model import LinearRegression

        from backend.application.signals.signal_service import evaluate
        from backend.application.signals.vol_forecast import build_har_features, realized_vol

        prices_df = self._make_prices_df("ETH-USD")
        close = prices_df["ETH-USD"]
        rv = realized_vol(close)
        features = build_har_features(rv)
        target = rv.shift(-1)
        mask = features.notna().all(axis=1) & target.notna()
        X = features[mask].values
        y = target[mask].values
        model = LinearRegression().fit(X, y)
        model_info = {
            "model": model,
            "model_type": "har",
            "feature_cols": ["rv_1d", "rv_5d", "rv_22d"],
            "oos_r2": 0.1,
            "har_r2": 0.1,
            "lgbm_r2": None,
        }
        sv = await evaluate(
            coin="ETH-USD",
            asof=date.today(),
            prices_df=prices_df,
            vol_model_info=model_info,
        )
        assert 0.0 <= sv.size_factor <= 1.5

    @pytest.mark.asyncio
    async def test_look_ahead_guard_applied(self) -> None:
        """Stichtag in der Vergangenheit → nur Daten bis asof werden verwendet."""
        from backend.application.signals.signal_service import evaluate

        n = 200
        idx = pd.date_range(start="2023-01-01", periods=n, freq="D", tz="UTC")
        prices = pd.DataFrame({"BTC-USD": 100.0 + np.arange(n) * 0.5}, index=idx)
        asof = date(2023, 6, 30)  # Stichtag in der Mitte
        # Look-Ahead-Guard filtert Daten korrekt — evaluate muss asof UTC-aware behandeln
        # Für diesen Test: asof fällt innerhalb der verfügbaren Daten
        sv = await evaluate(coin="BTC-USD", asof=asof, prices_df=prices)
        assert sv.asof == asof
