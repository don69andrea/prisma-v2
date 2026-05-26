"""Unit-Tests fuer `_simulate_portfolio` und `_monthly_rebalance_dates`.

Spec-Referenz: docs/specs/2026-05-12-backtest-service-light.md §5 + §9.1.

Diese Tests isolieren die zwei static methods der Portfolio-Simulation —
unabhaengig vom restlichen Service-Stack (Repos, MarketDataProvider).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.application.services.backtest_service import BacktestService

pytestmark = pytest.mark.unit


# ── _monthly_rebalance_dates ──────────────────────────────────────────────


def test_monthly_rebalance_dates_picks_last_trading_day_per_month() -> None:
    """Spec §5: Letzter Trading-Day jedes Kalendermonats."""
    idx = pd.bdate_range("2025-01-01", "2025-03-31", tz="UTC")
    dates = BacktestService._monthly_rebalance_dates(idx)

    assert pd.Timestamp("2025-01-31", tz="UTC") in dates
    assert pd.Timestamp("2025-02-28", tz="UTC") in dates
    assert pd.Timestamp("2025-03-31", tz="UTC") in dates
    assert len(dates) == 3


def test_monthly_rebalance_dates_partial_month_returns_last_available_day() -> None:
    """Bei <1 vollem Monat: letzter verfuegbarer Trading-Day im Index."""
    idx = pd.bdate_range("2025-01-06", "2025-01-20", tz="UTC")
    dates = BacktestService._monthly_rebalance_dates(idx)

    assert dates == {pd.Timestamp("2025-01-20", tz="UTC")}


def test_monthly_rebalance_dates_empty_index_returns_empty_set() -> None:
    """Edge-Case: leerer Index → leeres Set, kein Error."""
    idx = pd.DatetimeIndex([], tz="UTC")
    dates = BacktestService._monthly_rebalance_dates(idx)

    assert dates == set()


# ── _simulate_portfolio: Drift + Monthly-Reset (Spec §5) ──────────────────


def test_simulate_portfolio_uses_buy_and_hold_with_drift_within_month() -> None:
    """Spec §5: Innerhalb eines Monats reine Drift (Buy-and-Hold), kein Reset.

    Vergleich:
    - Naive `mean(axis=1)` (alte Impl): rebalanciert taeglich auf 50/50.
      Portfolio-Wert nach 5 Tagen = 1.05^5 = 1.27628 (taeglicher 5%-Return).
    - Spec-konforme Drift (neue Impl): startet 50/50, A's Gewicht waechst.
      Portfolio-Wert nach 5 Tagen = 0.5 * 1.1^5 + 0.5 * 1.0 = 1.305255.

    Die beiden Werte sind klar verschieden → Test faengt naive Impl.
    """
    idx = pd.bdate_range("2025-01-06", periods=6, tz="UTC")  # 6 Tage → 5 Returns, < 1 Monat
    # Asset A: taeglich +10%, Asset B: flat
    prices = pd.DataFrame(
        {
            "A": [100.0 * (1.1**i) for i in range(6)],
            "B": [100.0] * 6,
        },
        index=idx,
    )
    series = BacktestService._simulate_portfolio(prices, ["A", "B"])

    # Buy-and-Hold-Erwartung: 0.5 * (1.1^5) + 0.5 * 1.0 = 1.305255
    expected_final = 0.5 * (1.1**5) + 0.5 * 1.0
    assert abs(float(series.iloc[-1]) - expected_final) < 1e-9, (
        f"Drift falsch: got {series.iloc[-1]}, expected {expected_final}"
    )


def test_simulate_portfolio_within_month_drift_diverges_from_5050() -> None:
    """Spec §5: Innerhalb eines Monats akkumuliert sich Drift.

    Bei monoton steigendem Asset A muss das Gewicht von A im Laufe des Januars > 0.5
    werden. Folglich weicht der Portfolio-Return Mitte Januar von der 50/50-Mischung ab.

    Faengt die naive ``mean(axis=1)``-Impl: die rebalanciert taeglich → Drift gleich Null.
    """
    idx = pd.bdate_range("2025-01-01", periods=15, tz="UTC")  # nur Januar, kein Monatsende
    n = len(idx)
    prices = pd.DataFrame(
        {
            "A": np.linspace(100.0, 200.0, n),  # +100% innerhalb Jan, monoton
            "B": [100.0] * n,                    # flat
        },
        index=idx,
    )
    series = BacktestService._simulate_portfolio(prices, ["A", "B"])

    # An Tag 10 (Mitte Januar) ist A's Gewicht bereits gedriftet.
    pos = 10
    ret_a = float(prices["A"].iloc[pos] / prices["A"].iloc[pos - 1] - 1)
    ret_b = 0.0
    actual = float(series.iloc[pos] / series.iloc[pos - 1] - 1)
    naive_5050 = 0.5 * ret_a + 0.5 * ret_b

    # Bei korrekter Drift: w_a > 0.5 → Portfolio-Return > naive_5050 (positives ret_a).
    assert actual > naive_5050 + 1e-6, (
        f"Drift nicht akkumuliert: actual={actual}, naive_5050={naive_5050}"
    )


def test_simulate_portfolio_resets_to_equal_weight_at_month_end() -> None:
    """Spec §5: nach Monatsende ist der erste Trading-Day-Return wieder 50/50-Mix.

    Indirekter Beweis ueber Vergleich Januar-Drift vs. Februar-Start: am ersten
    Februar-Tag muss der Return exakt 0.5 * ret_a + 0.5 * ret_b sein (Reset auf 1/N),
    waehrend am gleichen Tag im Januar (vor Reset, mit Drift) der Return groesser ist.
    """
    idx = pd.bdate_range("2025-01-01", "2025-02-28", tz="UTC")
    n = len(idx)
    prices = pd.DataFrame(
        {
            "A": np.linspace(100.0, 200.0, n),
            "B": [100.0] * n,
        },
        index=idx,
    )
    series = BacktestService._simulate_portfolio(prices, ["A", "B"])

    feb_first_pos = next(i for i, d in enumerate(idx) if d.month == 2)

    ret_a_feb = float(prices["A"].iloc[feb_first_pos] / prices["A"].iloc[feb_first_pos - 1] - 1)
    expected_feb_ret = 0.5 * ret_a_feb + 0.5 * 0.0

    actual_feb_ret = float(series.iloc[feb_first_pos] / series.iloc[feb_first_pos - 1] - 1)

    # Gleichheit beweist Reset (50/50). Zusaetzlich: dieser Wert muss STRIKT
    # kleiner sein als der gedriftete Januar-Mid-Return → bricht naive Impl
    # (die haette beide Werte gleich, weil sie taeglich rebalanciert).
    assert abs(actual_feb_ret - expected_feb_ret) < 1e-9, (
        f"Reset am Monatsende nicht ausgefuehrt: actual={actual_feb_ret}, "
        f"expected (mit Reset auf 50/50)={expected_feb_ret}"
    )

    # Sanity gegen naive Impl: Januar-Drift sollte sichtbar hoeher sein
    jan_mid_pos = feb_first_pos // 2
    ret_a_jan = float(prices["A"].iloc[jan_mid_pos] / prices["A"].iloc[jan_mid_pos - 1] - 1)
    actual_jan_ret = float(series.iloc[jan_mid_pos] / series.iloc[jan_mid_pos - 1] - 1)
    naive_jan_5050 = 0.5 * ret_a_jan + 0.0
    assert actual_jan_ret > naive_jan_5050 + 1e-6, (
        f"Drift im Januar fehlt: actual={actual_jan_ret}, naive_5050={naive_jan_5050}"
    )


def test_simulate_portfolio_no_available_tickers_returns_flat_series() -> None:
    """Edge-Case: keine Ticker im DataFrame → flache 1.0-Serie."""
    idx = pd.bdate_range("2025-01-01", "2025-01-10", tz="UTC")
    prices = pd.DataFrame({"X": [100.0] * len(idx)}, index=idx)

    series = BacktestService._simulate_portfolio(prices, ["NOT_IN_DATA"])

    assert (series == 1.0).all()
    assert len(series) == len(idx)


def test_simulate_portfolio_starts_at_one_for_normal_input() -> None:
    """Sanity: erste Beobachtung der kumulierten Reihe ist 1.0 (Index-Normalisierung)."""
    idx = pd.bdate_range("2025-01-01", periods=10, tz="UTC")
    prices = pd.DataFrame(
        {
            "A": np.linspace(100.0, 110.0, len(idx)),
            "B": np.linspace(100.0, 105.0, len(idx)),
        },
        index=idx,
    )

    series = BacktestService._simulate_portfolio(prices, ["A", "B"])

    assert abs(float(series.iloc[0]) - 1.0) < 1e-12
