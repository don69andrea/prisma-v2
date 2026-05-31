"""Unit-Tests für _compute_metrics — Golden-Dataset, Vorzeichen-Korrektheit.

Spec: docs/specs/2026-05-12-backtest-service-light.md §6
Bug #143: max_drawdown wurde positiv berechnet (falsche Formel), muss negativ sein.
"""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backend.application.services.backtest_service import BacktestService

pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_series(values: list[float]) -> pd.Series:
    """Erstellt eine pd.Series mit DatetimeIndex (Trading-Day-Frequenz)."""
    idx = pd.date_range("2024-01-02", periods=len(values), freq="B", tz="UTC")
    return pd.Series(values, index=idx)


# ── Test §9.1: max_drawdown-Vorzeichen (Bug #143) ─────────────────────────


class TestMaxDrawdownSign:
    """Spec §6: max_drawdown muss negativ sein (Verlust = negativ).

    Formel laut Spec:
        drawdown = (series - cummax) / cummax
        max_drawdown = float(drawdown.min())   # min → negativstes Element

    Bug #143: Die falsche Formel (rolling_max - portfolio) / rolling_max
    lieferte einen positiven Wert.
    """

    def test_max_drawdown_is_negative_for_drawdown_series(self) -> None:
        """Eine Serie mit Rückgang muss max_drawdown < 0 liefern."""
        # Preis steigt auf 1.5, fällt dann auf 0.75 → 50 % Drawdown vom Peak
        values = [1.0, 1.1, 1.3, 1.5, 1.2, 0.9, 0.75, 0.8, 0.85, 0.9]
        series = _make_series(values)
        metrics = BacktestService._compute_metrics(series)

        assert metrics.max_drawdown < Decimal("0"), (
            f"max_drawdown muss negativ sein (Spec §6), aber war {metrics.max_drawdown}"
        )

    def test_max_drawdown_approx_minus_50_percent(self) -> None:
        """Expliziter 50 %-Drawdown: Peak=1.0, Tief=0.50 → max_drawdown ≈ -0.50.

        Spec §9.1: Eine 50%-Drawdown-Reihe → MaxDD ≈ -0.50
        """
        # Aufstieg bis 1.0, dann halbieren
        values = [1.0, 0.5]
        series = _make_series(values)
        metrics = BacktestService._compute_metrics(series)

        assert metrics.max_drawdown < Decimal("0"), (
            f"max_drawdown muss negativ sein, war {metrics.max_drawdown}"
        )
        assert abs(metrics.max_drawdown - Decimal("-0.5")) < Decimal("0.001"), (
            f"Erwarte max_drawdown ≈ -0.50, war {metrics.max_drawdown}"
        )

    def test_max_drawdown_zero_for_monotone_increasing_series(self) -> None:
        """Rein steigende Serie → kein Drawdown → max_drawdown == 0.

        Spec §9.1: konstante 10 % Jahres-Performance → MaxDD = 0.
        """
        # Gleichmäßig von 1.0 auf 1.1 steigen — kein einziger Rückgang
        n = 252
        values = list(np.linspace(1.0, 1.1, n))
        series = _make_series(values)
        metrics = BacktestService._compute_metrics(series)

        assert metrics.max_drawdown == Decimal("0"), (
            f"Monoton steigende Serie → max_drawdown == 0, war {metrics.max_drawdown}"
        )

    def test_max_drawdown_is_most_severe_not_last(self) -> None:
        """Mehrere Rückgänge: max_drawdown entspricht dem schlimmsten.

        Kleiner Drawdown zuerst (-10 %), danach größerer (-40 %) → Ergebnis ≈ -0.40.
        """
        # Kleiner Dip: 1.0 → 0.9 (+Recovery auf 1.1), dann großer Dip: 1.1 → 0.66
        values = [1.0, 0.9, 1.1, 0.66]
        series = _make_series(values)
        metrics = BacktestService._compute_metrics(series)

        # Größter Drawdown ist vom Peak 1.1 auf 0.66 ≈ -0.40
        assert metrics.max_drawdown < Decimal("-0.35"), (
            f"Erwarte max_drawdown < -0.35 (tiefstes Tief), war {metrics.max_drawdown}"
        )
        assert metrics.max_drawdown > Decimal("-0.45"), (
            f"Erwarte max_drawdown > -0.45, war {metrics.max_drawdown}"
        )
