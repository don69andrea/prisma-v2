"""Unit-Tests für backend.application.backtest.walkforward.

A7.3 — PoC-Reproduktion: Signal > Baseline auf synthetischen Trenddaten
A7.6 — Exposure-Matched Baseline wird immer berechnet
A7.7 — Netto-Kosten werden von Brutto-Rendite abgezogen

RED-Phase: Tests müssen fehlschlagen, bis walkforward.py implementiert ist.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Hilfsfunktionen für synthetische Testdaten
# ---------------------------------------------------------------------------


def _make_trending_prices(n: int = 600, seed: int = 0) -> pd.DataFrame:
    """Synthetische Preisserie mit deutlichem Aufwärtstrend + Volatilitätsclustering."""
    rng = np.random.default_rng(seed)
    # Trend-Komponente: leicht positiver Drift
    drift = 0.0008
    vol = 0.018
    returns = rng.normal(drift, vol, n)
    prices = 1000.0 * np.cumprod(1 + returns)
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    return pd.DataFrame({"close": prices}, index=idx)


def _make_signals_from_ma(prices: pd.DataFrame, window: int = 100) -> pd.Series:
    """100-Tage-MA-Signal: 1 wenn Preis über MA, sonst 0. Shift(1) verhindert Look-Ahead."""
    ma = prices["close"].rolling(window).mean()
    sig = (prices["close"] > ma).astype(float)
    return sig  # BacktestEngine wendet intern shift(1) an


def _make_always_invested_signal(prices: pd.DataFrame) -> pd.Series:
    """Immer investiert (Signal = 1) — nützlich für Kosten-Tests."""
    return pd.Series(1.0, index=prices.index)


# ---------------------------------------------------------------------------
# T01 — BacktestReport-Schema-Validität
# ---------------------------------------------------------------------------


class TestBacktestReportSchema:
    def test_report_is_pydantic_valid(self) -> None:
        """run_walkforward gibt ein gültiges BacktestReport zurück."""
        from backend.application.backtest.walkforward import run_walkforward

        prices = _make_trending_prices(600)
        signals = _make_signals_from_ma(prices)
        report = run_walkforward(prices, signals, coin="SYN-TEST")

        # Pflichtfelder vorhanden
        assert report.coin == "SYN-TEST"
        assert isinstance(report.cagr, float)
        assert isinstance(report.sharpe, float)
        assert isinstance(report.max_dd, float)
        assert isinstance(report.calmar, float)
        assert isinstance(report.beats_exposure_matched, bool)
        assert isinstance(report.n_trades, int)
        assert len(report.equity_curve) > 0


# ---------------------------------------------------------------------------
# T02 — A7.7: Netto-Kosten werden abgezogen
# ---------------------------------------------------------------------------


class TestNetCosts:
    def test_backtest_deducts_costs_on_trade_days(self) -> None:
        """Strategie-Rendite muss kleiner als Brutto-Rendite an Trade-Tagen sein (A7.7)."""
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices = _make_trending_prices(500)
        signals = _make_signals_from_ma(prices, window=50)
        details = run_walkforward_with_details(prices, signals, costs=0.001)

        # An Trade-Tagen (Positionswechsel) muss net < gross
        net = details["net_returns"]
        gross = details["gross_returns"]
        trade_days = details["trade_mask"]  # Boolean-Series, True an Trade-Tagen

        if trade_days.sum() > 0:
            net_on_trade = net[trade_days]
            gross_on_trade = gross[trade_days]
            # Netto muss im Schnitt kleiner als brutto sein (Kosten reduzieren Rendite)
            assert net_on_trade.mean() < gross_on_trade.mean()

    def test_zero_costs_equals_gross(self) -> None:
        """Bei costs=0 ist netto = brutto."""
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices = _make_trending_prices(400)
        signals = _make_always_invested_signal(prices)
        details = run_walkforward_with_details(prices, signals, costs=0.0)

        net = details["net_returns"]
        gross = details["gross_returns"]
        pd.testing.assert_series_equal(net, gross, check_names=False)


# ---------------------------------------------------------------------------
# T03 — A7.6: Exposure-Matched Baseline immer berechnet
# ---------------------------------------------------------------------------


class TestExposureMatchedBaseline:
    def test_beats_exposure_matched_is_bool_not_none(self) -> None:
        """beats_exposure_matched muss ein bool sein, nie None (A7.6)."""
        from backend.application.backtest.walkforward import run_walkforward

        prices = _make_trending_prices(500)
        signals = _make_signals_from_ma(prices)
        report = run_walkforward(prices, signals, coin="TEST")

        assert report.beats_exposure_matched is not None
        assert isinstance(report.beats_exposure_matched, bool)

    def test_baseline_uses_average_exposure(self) -> None:
        """Exposure-Matched Baseline muss Ø-Exposure der Strategie nutzen."""
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices = _make_trending_prices(500)
        signals = _make_signals_from_ma(prices, window=50)
        details = run_walkforward_with_details(prices, signals)

        avg_exp = details["avg_exposure"]
        baseline = details["baseline_returns"]
        gross = details["gross_returns"]

        # Baseline = avg_exposure * market_return; gross = signal * market_return
        # Also: baseline.mean() / gross.mean() ≈ avg_exp / signal_avg (wenn Vorzeichen übereinstimmen)
        assert 0.0 <= avg_exp <= 1.5, f"Ø-Exposure {avg_exp} ausserhalb sinnvollem Bereich"
        assert len(baseline) == len(gross)

    def test_beats_exposure_matched_true_requires_both_sharpe_and_calmar(self) -> None:
        """beats_exposure_matched=True nur wenn BEIDE Sharpe UND Calmar > Baseline."""
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices = _make_trending_prices(600)
        signals = _make_signals_from_ma(prices)
        details = run_walkforward_with_details(prices, signals)

        beats = details["beats_exposure_matched"]
        strat_sharpe = details["strategy_sharpe"]
        strat_calmar = details["strategy_calmar"]
        base_sharpe = details["baseline_sharpe"]
        base_calmar = details["baseline_calmar"]

        # Wenn beats=True, dann müssen beide Bedingungen erfüllt sein
        if beats:
            assert strat_sharpe > base_sharpe
            assert strat_calmar > base_calmar
        else:
            # Wenn beats=False, dann muss mindestens eine Bedingung nicht erfüllt sein
            assert not (strat_sharpe > base_sharpe and strat_calmar > base_calmar)


# ---------------------------------------------------------------------------
# T04 — A7.3: PoC-Reproduktion (Signal > Baseline auf synthetischen Trenddaten)
# ---------------------------------------------------------------------------


class TestPoCReproduction:
    def test_strategy_beats_baseline_on_trending_data(self) -> None:
        """Auf klar trendigem Markt muss MA-Signal die Exposure-Baseline schlagen (A7.3).

        Reproduziert das PoC-Ergebnis: BTC Calmar 1.31 > Baseline 0.60.
        Synthetic: starker Trend + hohe Volatilität → MA-Signal reduziert MaxDD.
        """
        from backend.application.backtest.walkforward import run_walkforward

        # Stark trendigende Daten mit deutlichen Drawdown-Phasen
        rng = np.random.default_rng(7)
        n = 800
        # Bullischer Trend mit Crash-Phasen (MA-Signal schützt davor)
        returns = np.concatenate(
            [
                rng.normal(0.002, 0.015, 300),  # Bull
                rng.normal(-0.004, 0.030, 100),  # Crash
                rng.normal(0.002, 0.015, 300),  # Bull
                rng.normal(-0.005, 0.030, 100),  # Crash
            ]
        )
        prices = 1000.0 * np.cumprod(1 + returns)
        idx = pd.date_range("2018-01-01", periods=n, freq="D")
        df = pd.DataFrame({"close": prices}, index=idx)

        signals = _make_signals_from_ma(df, window=50)
        report = run_walkforward(df, signals, coin="SYN-BTC", min_train=100)

        # Strategie muss Baseline auf diesem Datensatz schlagen (PoC-Reproduktion)
        assert report.beats_exposure_matched is True, (
            f"Erwartet beats_exposure_matched=True, "
            f"aber Strategie Calmar={report.calmar:.2f} vs kein Zugriff auf Baseline"
        )

    def test_equity_curve_non_negative(self) -> None:
        """Equity-Kurve darf nie negativ werden (kein Short, kein negativer Faktor)."""
        from backend.application.backtest.walkforward import run_walkforward

        prices = _make_trending_prices(500)
        signals = _make_signals_from_ma(prices)
        report = run_walkforward(prices, signals, coin="TEST")

        for dt, val in report.equity_curve:
            assert val >= 0.0, f"Negative Equity am {dt}: {val}"

    def test_n_trades_positive_with_changing_signal(self) -> None:
        """n_trades muss positiv sein wenn das Signal wechselt."""
        from backend.application.backtest.walkforward import run_walkforward

        prices = _make_trending_prices(500)
        signals = _make_signals_from_ma(prices, window=20)  # schnelleres Signal → mehr Trades
        report = run_walkforward(prices, signals, coin="TEST")

        assert report.n_trades > 0


# ---------------------------------------------------------------------------
# T05 — meta_filter Integration (ML-07, ML-08)
# ---------------------------------------------------------------------------


class TestMetaFilter:
    def test_meta_filter_backward_compat(self) -> None:
        """ML-08: Kein meta_filter-Arg → identische Metriken; all-ones Filter = kein Filter.

        Beide Varianten müssen bit-identische Ergebnisse liefern (atol 1e-12).
        """
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices = _make_trending_prices(600)
        signals = _make_signals_from_ma(prices)

        # Baseline: keine meta_filter (Default None)
        no_filter = run_walkforward_with_details(prices, signals, costs=0.001)

        # all-ones Filter: Position bleibt unverändert → identisch
        all_ones = pd.Series(1.0, index=prices.index)
        with_ones = run_walkforward_with_details(prices, signals, costs=0.001, meta_filter=all_ones)

        # Metriken müssen bit-identisch sein
        np.testing.assert_allclose(
            no_filter["strategy_sharpe"],
            with_ones["strategy_sharpe"],
            atol=1e-12,
            err_msg="strategy_sharpe weicht mit all-ones Filter ab",
        )
        np.testing.assert_allclose(
            no_filter["strategy_calmar"],
            with_ones["strategy_calmar"],
            atol=1e-12,
            err_msg="strategy_calmar weicht mit all-ones Filter ab",
        )
        np.testing.assert_allclose(
            no_filter["n_trades"],
            with_ones["n_trades"],
            atol=1e-12,
            err_msg="n_trades weicht mit all-ones Filter ab",
        )

    def test_meta_filter_masks_positions(self) -> None:
        """Positionen müssen auf 0 gesetzt werden wo meta_filter == 0.

        Ein Block von Null-Werten im Filter muss n_trades und Exposure reduzieren.
        """
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices = _make_trending_prices(600)
        signals = _make_signals_from_ma(prices)

        # Ungefilterter Lauf (Referenz)
        unfiltered = run_walkforward_with_details(prices, signals, costs=0.001)

        # Filter mit einem grossen Null-Block (50% der Daten = 0)
        meta_filter = pd.Series(1.0, index=prices.index)
        mid = len(prices) // 2
        meta_filter.iloc[:mid] = 0.0  # erste Hälfte: keine Trades

        filtered = run_walkforward_with_details(
            prices, signals, costs=0.001, meta_filter=meta_filter
        )

        # Exposure muss gesunken sein (weniger investierte Tage)
        assert filtered["avg_exposure"] < unfiltered["avg_exposure"], (
            f"Erwartet avg_exposure < {unfiltered['avg_exposure']:.4f}, "
            f"got {filtered['avg_exposure']:.4f}"
        )

        # n_trades muss kleiner oder gleich sein
        assert filtered["n_trades"] <= unfiltered["n_trades"], (
            f"Erwartet n_trades <= {unfiltered['n_trades']}, got {filtered['n_trades']}"
        )

    def test_baseline_same_oos_period(self) -> None:
        """ML-07: Always-trade und meta-filtered müssen über denselben OOS-Zeitraum verglichen werden.

        Index-Gleichheit der return-Serien muss gegeben sein (identische Daten-Datumsabdeckung).
        """
        from backend.application.backtest.walkforward import run_walkforward_with_details

        prices = _make_trending_prices(600)
        signals = _make_signals_from_ma(prices)

        # always-trade: kein Filter
        always = run_walkforward_with_details(prices, signals, costs=0.001)

        # meta-filtered: partieller Filter
        meta_filter = pd.Series(1.0, index=prices.index)
        meta_filter.iloc[::3] = 0.0  # jeden dritten Tag: kein Trade

        filtered = run_walkforward_with_details(
            prices, signals, costs=0.001, meta_filter=meta_filter
        )

        # Beide net_returns müssen denselben DatetimeIndex teilen (ML-07)
        pd.testing.assert_index_equal(
            always["net_returns"].index,
            filtered["net_returns"].index,
            check_names=False,
            obj="OOS-Datumsabdeckung muss identisch sein (ML-07)",
        )


# ---------------------------------------------------------------------------
# T06 — Edge-branch coverage for walkforward private metric helpers
# ---------------------------------------------------------------------------


class TestPrivateMetricEdgeCases:
    """Cover edge-case branches in _sharpe, _cagr, _max_drawdown, _calmar."""

    def test_sharpe_empty_returns(self) -> None:
        """_sharpe returns 0.0 for empty series (line 38 branch)."""
        from backend.application.backtest.walkforward import _sharpe  # noqa: PLC0415

        assert _sharpe(pd.Series([], dtype=float)) == 0.0

    def test_sharpe_zero_std(self) -> None:
        """_sharpe returns 0.0 when std == 0 (constant returns, line 38 branch)."""
        from backend.application.backtest.walkforward import _sharpe  # noqa: PLC0415

        assert _sharpe(pd.Series([0.01, 0.01, 0.01])) == 0.0

    def test_cagr_empty_returns(self) -> None:
        """_cagr returns 0.0 for empty series (line 45 branch)."""
        from backend.application.backtest.walkforward import _cagr  # noqa: PLC0415

        assert _cagr(pd.Series([], dtype=float)) == 0.0

    def test_cagr_total_zero_or_negative(self) -> None:
        """_cagr returns -1.0 when cumulative product <= 0 (line 48 branch)."""
        from backend.application.backtest.walkforward import _cagr  # noqa: PLC0415

        # Returns that produce total <= 0: -100% loss
        assert _cagr(pd.Series([-1.0])) == -1.0

    def test_max_drawdown_empty_returns(self) -> None:
        """_max_drawdown returns 0.0 for empty series (line 55 branch)."""
        from backend.application.backtest.walkforward import _max_drawdown  # noqa: PLC0415

        assert _max_drawdown(pd.Series([], dtype=float)) == 0.0

    def test_calmar_zero_drawdown(self) -> None:
        """_calmar returns 0.0 when max_drawdown == 0 (line 67 branch)."""
        from backend.application.backtest.walkforward import _calmar  # noqa: PLC0415

        # Monotonically increasing returns → no drawdown
        returns = pd.Series([0.01, 0.01, 0.01, 0.01, 0.01])
        assert _calmar(returns) == 0.0
