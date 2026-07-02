"""Unit-Tests für TA-Berechnungen in yfinance_crypto — kein yfinance-API-Call nötig.

Testet RSI, MACD, Bollinger Bands und EMA mit synthetischen Preisreihen,
um Korrektheit der nativen pandas/numpy-Implementierungen zu verifizieren.
"""

from __future__ import annotations

import pandas as pd
import pytest


def _series(*prices: float) -> pd.Series:
    return pd.Series(list(prices), dtype=float)


def _make_df(n: int = 300, slope: float = 0.001) -> pd.DataFrame:
    prices = [100.0 * (1 + slope) ** i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": prices,
            "High": [p * 1.005 for p in prices],
            "Low": [p * 0.995 for p in prices],
            "Close": prices,
            "Volume": [1_000_000.0] * n,
        }
    )


# ─────────────────────────── RSI ───────────────────────────


class TestRsi:
    def test_pure_uptrend_rsi_above_90(self) -> None:
        """50 aufeinanderfolgende steigende Perioden → RSI nahe 100."""
        from backend.infrastructure.adapters.yfinance_crypto import _rsi

        close = _series(*[100.0 + i for i in range(50)])
        result = _rsi(close, 14)
        assert result.iloc[-1] > 90.0

    def test_pure_downtrend_rsi_below_10(self) -> None:
        """50 aufeinanderfolgende fallende Perioden → RSI nahe 0."""
        from backend.infrastructure.adapters.yfinance_crypto import _rsi

        close = _series(*[100.0 - i * 0.5 for i in range(50)])
        result = _rsi(close, 14)
        assert result.iloc[-1] < 10.0

    def test_rsi_stays_between_0_and_100(self) -> None:
        """RSI-Werte liegen immer im Bereich [0, 100]."""
        import random

        from backend.infrastructure.adapters.yfinance_crypto import _rsi

        random.seed(42)
        close = _series(*[100.0 + random.gauss(0, 5) for _ in range(100)])
        valid = _rsi(close, 14).dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_all_nan_when_fewer_than_min_periods(self) -> None:
        """Mit < 14 Datenpunkten: alle Werte NaN (min_periods=14)."""
        from backend.infrastructure.adapters.yfinance_crypto import _rsi

        close = _series(*[100.0 + i for i in range(10)])
        result = _rsi(close, 14)
        # 10 Punkte, aber min_periods=14 → diff gibt 9 Werte → alle NaN
        assert result.isna().all()

    def test_rsi_shorter_period_produces_values_sooner(self) -> None:
        """RSI(7) liefert früher Werte als RSI(14)."""
        from backend.infrastructure.adapters.yfinance_crypto import _rsi

        close = _series(*[100.0 + i * 0.1 for i in range(30)])
        rsi7 = _rsi(close, 7)
        rsi14 = _rsi(close, 14)
        assert rsi7.dropna().count() > rsi14.dropna().count()

    def test_rsi_returns_same_length_as_input(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _rsi

        close = _series(*[100.0] * 30)
        assert len(_rsi(close, 14)) == 30

    def test_rsi_exact_boundary_at_30(self) -> None:
        """CryptoScorer.SELL_THRESHOLD liegt bei RSI=30 → boundary-Test."""
        from backend.domain.services.crypto_scorer import CryptoScorer

        scorer = CryptoScorer()
        # RSI 29.9 → oversold tier (10 Pt)
        assert scorer._rsi_score(29.9) == 10.0
        # RSI genau 30 → nächste Stufe (8 Pt)
        assert scorer._rsi_score(30.0) == 8.0

    def test_rsi_exact_boundary_at_70(self) -> None:
        from backend.domain.services.crypto_scorer import CryptoScorer

        scorer = CryptoScorer()
        # RSI 69.9 → 3 Pt
        assert scorer._rsi_score(69.9) == 3.0
        # RSI genau 70 → 0 Pt (overbought)
        assert scorer._rsi_score(70.0) == 0.0


# ─────────────────────────── MACD ───────────────────────────


class TestMacd:
    def test_returns_three_series(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _macd

        close = _series(*[100.0 + i for i in range(50)])
        macd_line, signal_line, hist = _macd(close, 12, 26, 9)
        assert isinstance(macd_line, pd.Series)
        assert isinstance(signal_line, pd.Series)
        assert isinstance(hist, pd.Series)

    def test_histogram_equals_macd_minus_signal(self) -> None:
        """hist = macd_line − signal_line (algebraisch exakt)."""
        from backend.infrastructure.adapters.yfinance_crypto import _macd

        close = _series(*[100.0 + i * 0.5 for i in range(60)])
        macd_line, signal_line, hist = _macd(close, 12, 26, 9)
        pd.testing.assert_series_equal(hist, macd_line - signal_line)

    def test_macd_positive_in_sustained_uptrend(self) -> None:
        """Schnelle EMA > langsame EMA in Aufwärtstrend → MACD > 0."""
        from backend.infrastructure.adapters.yfinance_crypto import _macd

        close = _series(*[100.0 * (1.01**i) for i in range(100)])
        macd_line, _, _ = _macd(close, 12, 26, 9)
        assert macd_line.iloc[-1] > 0

    def test_macd_negative_in_sustained_downtrend(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _macd

        close = _series(*[100.0 * (0.99**i) for i in range(100)])
        macd_line, _, _ = _macd(close, 12, 26, 9)
        assert macd_line.iloc[-1] < 0

    def test_output_length_equals_input_length(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _macd

        close = _series(*[100.0 + i for i in range(50)])
        macd_line, signal_line, hist = _macd(close, 12, 26, 9)
        assert len(macd_line) == len(signal_line) == len(hist) == 50

    def test_signal_line_diverges_from_macd_at_peak(self) -> None:
        """Signal-Line und MACD-Line sind bei Trendwechsel unterschiedlich."""
        from backend.infrastructure.adapters.yfinance_crypto import _macd

        # Stark steigend dann stark fallend
        up = [100.0 * (1.02**i) for i in range(50)]
        down = [up[-1] * (0.98**i) for i in range(50)]
        close = _series(*(up + down))
        macd_line, signal_line, _ = _macd(close, 12, 26, 9)
        # MACD und Signal-Line sollten am Trendwechsel voneinander abweichen
        assert macd_line.iloc[-1] != signal_line.iloc[-1]


# ─────────────────────────── BBands ───────────────────────────


class TestBbands:
    def test_returns_three_series(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _bbands

        close = _series(*[100.0 + i * 0.1 for i in range(30)])
        upper, mid, lower = _bbands(close, 20, 2.0)
        assert isinstance(upper, pd.Series)
        assert isinstance(mid, pd.Series)
        assert isinstance(lower, pd.Series)

    def test_upper_geq_mid_geq_lower(self) -> None:
        """upper >= mid >= lower für Serien mit Varianz."""
        import random

        from backend.infrastructure.adapters.yfinance_crypto import _bbands

        random.seed(1)
        close = _series(*[100.0 + random.gauss(0, 2) for _ in range(30)])
        upper, mid, lower = _bbands(close, 20, 2.0)
        valid = ~(upper.isna() | lower.isna())
        assert (upper[valid] >= mid[valid]).all()
        assert (mid[valid] >= lower[valid]).all()

    def test_mid_equals_rolling_sma(self) -> None:
        """Mittleres Band == SMA(20)."""
        from backend.infrastructure.adapters.yfinance_crypto import _bbands

        close = _series(*[100.0 + i for i in range(30)])
        _, mid, _ = _bbands(close, 20, 2.0)
        expected = close.rolling(20).mean()
        pd.testing.assert_series_equal(mid, expected)

    def test_bands_symmetric_around_mid(self) -> None:
        """Upper − Mid == Mid − Lower (symmetrisch)."""
        from backend.infrastructure.adapters.yfinance_crypto import _bbands

        close = _series(*[100.0 + i * 0.5 for i in range(30)])
        upper, mid, lower = _bbands(close, 20, 2.0)
        valid = ~upper.isna()
        pd.testing.assert_series_equal((upper - mid)[valid], (mid - lower)[valid])

    def test_nan_before_period_length(self) -> None:
        """Erste 19 Werte NaN, ab Index 19 definiert."""
        from backend.infrastructure.adapters.yfinance_crypto import _bbands

        close = _series(*[100.0 + i for i in range(30)])
        upper, _, _ = _bbands(close, 20, 2.0)
        assert upper.iloc[:19].isna().all()
        assert upper.iloc[19:].notna().all()

    def test_flat_series_has_zero_bandwidth(self) -> None:
        """Konstante Preisreihe: Bandbreite = 0 (kein Rauschen)."""
        from backend.infrastructure.adapters.yfinance_crypto import _bbands

        close = _series(*[50.0] * 30)
        upper, mid, lower = _bbands(close, 20, 2.0)
        valid = ~upper.isna()
        assert ((upper - lower)[valid].abs() < 1e-6).all()


# ─────────────────────────── EMA ───────────────────────────


class TestEma:
    def test_returns_same_length_as_input(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _ema

        close = _series(*[100.0] * 30)
        assert len(_ema(close, 20)) == 30

    def test_constant_series_returns_constant(self) -> None:
        """Flache Preisreihe: EMA == Preis."""
        from backend.infrastructure.adapters.yfinance_crypto import _ema

        close = _series(*[50.0] * 50)
        result = _ema(close, 20)
        assert (result - 50.0).abs().max() < 1e-6

    def test_ema20_converges_faster_than_ema50(self) -> None:
        """Nach Kurssprung: EMA(20) näher am neuen Kurs als EMA(50)."""
        from backend.infrastructure.adapters.yfinance_crypto import _ema

        prices = [100.0] * 50 + [200.0] * 50
        close = _series(*prices)
        ema20 = _ema(close, 20)
        ema50 = _ema(close, 50)
        assert ema20.iloc[-1] > ema50.iloc[-1]

    def test_no_nan_values(self) -> None:
        """EWM ohne min_periods: kein NaN-Wert."""
        from backend.infrastructure.adapters.yfinance_crypto import _ema

        close = _series(100.0, 101.0, 99.0, 102.0)
        assert _ema(close, 20).notna().all()

    def test_ema_above_mid_in_uptrend(self) -> None:
        """In Aufwärtstrend: EMA(20) > EMA(50)."""
        from backend.infrastructure.adapters.yfinance_crypto import _ema

        close = _series(*[100.0 + i * 0.5 for i in range(200)])
        ema20 = _ema(close, 20)
        ema50 = _ema(close, 50)
        # Nach 200 Perioden eindeutig etabliert
        assert ema20.iloc[-1] > ema50.iloc[-1]


# ─────────────────────────── _add_indicators ───────────────────────────


class TestAddIndicators:
    """Testet die gesamte Indikator-Pipeline auf exakte Spaltennamen und Wertebereiche."""

    def test_all_nine_ta_columns_present(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df()
        result = _add_indicators(df)
        expected = [
            "RSI_14",
            "MACD_12_26_9",
            "MACDs_12_26_9",
            "MACDh_12_26_9",
            "EMA_20",
            "EMA_50",
            "BBU_20_2.0",
            "BBM_20_2.0",
            "BBL_20_2.0",
        ]
        for col in expected:
            assert col in result.columns, f"Spalte fehlt: {col}"

    def test_ohlcv_columns_preserved(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df()
        result = _add_indicators(df)
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert col in result.columns

    def test_rsi_column_name_exact(self) -> None:
        """CryptoScorer greift per String-Key auf 'RSI_14' zu."""
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df()
        result = _add_indicators(df)
        assert "RSI_14" in result.columns
        assert "rsi_14" not in result.columns  # kein Lowercase-Alias

    def test_macd_column_names_exact(self) -> None:
        """CryptoScorer erwartet exakt 'MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9'."""
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df()
        result = _add_indicators(df)
        assert "MACD_12_26_9" in result.columns
        assert "MACDs_12_26_9" in result.columns
        assert "MACDh_12_26_9" in result.columns

    def test_bbands_column_names_with_period(self) -> None:
        """BBands-Spalten haben Dezimalpunkt: BBU_20_2.0 (nicht BBU_20_2)."""
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df()
        result = _add_indicators(df)
        assert "BBU_20_2.0" in result.columns
        assert "BBM_20_2.0" in result.columns
        assert "BBL_20_2.0" in result.columns

    def test_rsi_values_in_valid_range(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df(300)
        result = _add_indicators(df)
        valid = result["RSI_14"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_bbu_always_geq_bbl(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df(300)
        result = _add_indicators(df)
        valid = result.dropna(subset=["BBU_20_2.0", "BBL_20_2.0"])
        assert (valid["BBU_20_2.0"] >= valid["BBL_20_2.0"]).all()

    def test_ema20_above_ema50_in_uptrend(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df(300, slope=0.002)
        result = _add_indicators(df)
        assert result["EMA_20"].iloc[-1] > result["EMA_50"].iloc[-1]

    def test_macd_histogram_consistent(self) -> None:
        """MACDh_12_26_9 == MACD_12_26_9 − MACDs_12_26_9."""
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df(200)
        result = _add_indicators(df)
        diff = (result["MACD_12_26_9"] - result["MACDs_12_26_9"] - result["MACDh_12_26_9"]).abs()
        assert diff.max() < 1e-9

    def test_downtrend_ema20_below_ema50(self) -> None:
        from backend.infrastructure.adapters.yfinance_crypto import _add_indicators

        df = _make_df(300, slope=-0.002)
        result = _add_indicators(df)
        assert result["EMA_20"].iloc[-1] < result["EMA_50"].iloc[-1]


# ─────────────────────────── get_ohlcv ───────────────────────────


class TestGetOhlcv:
    async def test_returns_dataframe_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.infrastructure.adapters import yfinance_crypto as mod

        df = _make_df(300)

        async def _fake_to_thread(func, *args, **kwargs):
            return df

        monkeypatch.setattr(mod.asyncio, "to_thread", _fake_to_thread)  # type: ignore[attr-defined]
        adapter = mod.YFinanceCryptoAdapter()
        result = await adapter.get_ohlcv("BTC-CHF")
        assert result is not None
        assert "Close" in result.columns

    async def test_returns_none_on_empty_download(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.infrastructure.adapters import yfinance_crypto as mod

        async def _fake_to_thread(func, *args, **kwargs):
            return pd.DataFrame()

        monkeypatch.setattr(mod.asyncio, "to_thread", _fake_to_thread)  # type: ignore[attr-defined]
        adapter = mod.YFinanceCryptoAdapter()
        result = await adapter.get_ohlcv("BTC-CHF")
        assert result is None

    async def test_returns_none_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.infrastructure.adapters import yfinance_crypto as mod

        async def _fake_to_thread(func, *args, **kwargs):
            raise RuntimeError("yfinance down")

        monkeypatch.setattr(mod.asyncio, "to_thread", _fake_to_thread)  # type: ignore[attr-defined]
        adapter = mod.YFinanceCryptoAdapter()
        result = await adapter.get_ohlcv("BTC-CHF")
        assert result is None

    async def test_flattens_multiindex_columns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.infrastructure.adapters import yfinance_crypto as mod

        df = _make_df(60)
        df.columns = pd.MultiIndex.from_product([df.columns, ["BTC-CHF"]])

        async def _fake_to_thread(func, *args, **kwargs):
            return df

        monkeypatch.setattr(mod.asyncio, "to_thread", _fake_to_thread)  # type: ignore[attr-defined]
        adapter = mod.YFinanceCryptoAdapter()
        result = await adapter.get_ohlcv("BTC-CHF")
        assert result is not None
        assert "Close" in result.columns


# ─────────────────────────── USD→CHF FX-Umrechnung ───────────────────────────


class TestChfUsdRate:
    """Regression: USD-Krypto-Preise wurden mit CHFUSD=X (~1.12) multipliziert
    statt mit USDCHF=X (~0.90) -> ~22% zu hoch. Richtung + Plausibilitaet."""

    def test_uses_usdchf_ticker_not_chfusd(self) -> None:
        from backend.infrastructure.adapters import yfinance_crypto as mod

        # USDCHF=X = CHF pro USD (~0.90), korrekte Richtung fuer Multiplikation.
        assert mod._CHF_USD_RATE_TICKER == "USDCHF=X"

    async def test_plausible_rate_passed_through(self) -> None:
        from unittest.mock import AsyncMock

        from backend.infrastructure.adapters import yfinance_crypto as mod

        adapter = mod.YFinanceCryptoAdapter()
        adapter._download = AsyncMock(return_value=pd.DataFrame({"Close": [0.89]}))  # type: ignore[method-assign]
        rate = await adapter._get_chf_usd_rate()
        assert rate == pytest.approx(0.89)
        # 100 USD -> ~89 CHF (CHF ist teurer als USD -> weniger CHF pro USD)
        assert 100.0 * rate < 100.0

    async def test_implausible_rate_falls_back(self) -> None:
        from unittest.mock import AsyncMock

        from backend.infrastructure.adapters import yfinance_crypto as mod

        adapter = mod.YFinanceCryptoAdapter()
        # 1.12 = CHFUSD (falsche Richtung) -> ausserhalb [0.5, 1.5]? nein, aber
        # ein grober Ausreisser wie 5.0 muss auf Fallback gehen.
        adapter._download = AsyncMock(return_value=pd.DataFrame({"Close": [5.0]}))  # type: ignore[method-assign]
        rate = await adapter._get_chf_usd_rate()
        assert rate == pytest.approx(mod._CHF_PER_USD_FALLBACK)

    async def test_empty_download_uses_fallback(self) -> None:
        from unittest.mock import AsyncMock

        from backend.infrastructure.adapters import yfinance_crypto as mod

        adapter = mod.YFinanceCryptoAdapter()
        adapter._download = AsyncMock(return_value=pd.DataFrame())  # type: ignore[method-assign]
        rate = await adapter._get_chf_usd_rate()
        assert rate == pytest.approx(mod._CHF_PER_USD_FALLBACK)
