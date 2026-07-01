"""Tests für Diversification — Ledoit-Wolf-Kovarianz, Vola + Korrelation.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §5
      docs/specs/2026-04-21-prisma-capstone-design.md §6.5
"""

import numpy as np
import pandas as pd
import pytest

from backend.domain.models.diversification import DiversificationModel

pytestmark = pytest.mark.unit


def _run(prices: pd.DataFrame) -> dict[str, int | None]:
    """Hilfsfunktion: gibt {ticker: rank} zurück."""
    results = DiversificationModel().run(prices=prices)
    return {r.ticker: r.rank for r in results}


def _make_prices(returns: pd.DataFrame, start: float = 100.0) -> pd.DataFrame:
    """Wandelt eine Returns-DataFrame in eine Preis-DataFrame (kumuliert)."""
    return start * (1 + returns).cumprod()


class TestDiversificationFormula:
    def test_low_vol_low_corr_ranks_first(self) -> None:
        """3-Ticker Golden Dataset: A (low vola, low correlation), B (mid), C (high vola, high correlation).
        A muss Rang 1 erhalten, C Rang 3.
        """
        rng = np.random.default_rng(42)
        n_days = 252
        index = pd.date_range("2024-01-01", periods=n_days, freq="B")

        # A: niedrige Vola, unkorreliert
        a_returns = rng.normal(0.0005, 0.005, n_days)
        # B: mittlere Vola, leicht korreliert mit A
        b_returns = 0.3 * a_returns + rng.normal(0.0005, 0.012, n_days)
        # C: hohe Vola, stark korreliert mit B
        c_returns = 0.9 * b_returns + rng.normal(0.0005, 0.025, n_days)

        returns = pd.DataFrame(
            {"A": a_returns, "B": b_returns, "C": c_returns},
            index=index,
        )
        prices = _make_prices(returns)

        ranks = _run(prices)
        assert ranks["A"] == 1
        assert ranks["C"] == 3

    def test_negatively_correlated_ticker_ranks_first(self) -> None:
        """Regression W3-C-05: Ein stark NEGATIV korrelierter Titel ist der beste
        Diversifizierer und muss Rang 1 bekommen. Die alte Formel 2/(vol+avg_corr)
        erzeugte bei avg_corr<0 einen negativen Score und rankte ihn ZULETZT.
        """
        rng = np.random.default_rng(101)
        n = 252
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        base = rng.normal(0.0005, 0.010, n)
        # HEDGE: nahezu perfekt negativ korreliert zu BASE (bester Diversifizierer),
        # vergleichbare Vola. UP: stark positiv korreliert zu BASE (schlechtester).
        hedge = -base + rng.normal(0.0, 0.001, n)
        up = 0.95 * base + rng.normal(0.0, 0.001, n)
        returns = pd.DataFrame({"BASE": base, "HEDGE": hedge, "UP": up}, index=index)
        prices = _make_prices(returns)

        ranks = _run(prices)
        assert ranks["HEDGE"] == 1, f"negativ korrelierter Titel muss Rang 1 sein, ranks={ranks}"

    def test_deterministic(self) -> None:
        rng = np.random.default_rng(7)
        index = pd.date_range("2024-01-01", periods=120, freq="B")
        returns = pd.DataFrame(
            {
                "X": rng.normal(0, 0.01, 120),
                "Y": rng.normal(0, 0.02, 120),
                "Z": rng.normal(0, 0.015, 120),
            },
            index=index,
        )
        prices = _make_prices(returns)
        assert _run(prices) == _run(prices)

    def test_two_ticker_universe_ranks_both(self) -> None:
        """Spec §5 Edge-Case: ``n = 2 Ticker`` — Korrelation = ±1.0, Ledoit-Wolf
        bleibt stabil. Beide Ticker müssen valide gerankt werden, der mit der
        niedrigeren Vola gewinnt (Spec: Score = 2 / (volatility + avg_correlation)).
        """
        rng = np.random.default_rng(17)
        n = 60
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        returns = pd.DataFrame(
            {
                "LOW_VOL": rng.normal(0.0005, 0.005, n),
                "HIGH_VOL": rng.normal(0.0005, 0.025, n),
            },
            index=index,
        )
        prices = _make_prices(returns)

        ranks = _run(prices)
        assert ranks["LOW_VOL"] == 1
        assert ranks["HIGH_VOL"] == 2

    def test_tied_scores_yield_tied_ranks_method_min(self) -> None:
        """Spec §6 Ranking-Konvention: Gleichstand → gleicher Rang
        (``method='min'``), nächster Rang springt.

        Zwei identische Preisreihen → identischer Score → beide rank=1; ein
        dritter Ticker mit höherer Vola → rank=3 (nicht 2). Schützt
        ``_rank``-Loop-Logik gegen Off-by-one-Regression.
        """
        rng = np.random.default_rng(23)
        n = 60
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        twin = rng.normal(0.0005, 0.005, n)
        wide = rng.normal(0.0005, 0.025, n)
        returns = pd.DataFrame(
            {"TWIN_A": twin, "TWIN_B": twin, "WIDE": wide},
            index=index,
        )
        prices = _make_prices(returns)

        ranks = _run(prices)
        assert ranks["TWIN_A"] == ranks["TWIN_B"] == 1
        assert ranks["WIDE"] == 3


class TestDiversificationPerformance:
    def test_500_tickers_252_days_under_2s(self) -> None:
        """Spec §5 Performance-Ziel: Diversification für 500 Ticker × 252 Tage
        unter 500ms ohne Coverage-Instrumentierung. CI läuft mit ``--cov=backend``,
        was numpy-Pfade 3-5× verlangsamt — daher Test-Threshold 2.0s.

        Der ursprüngliche Python-Loop in ``_compute_scores`` brauchte bei n=500
        ~12s ohne und ~40s mit Coverage. 2.0s diskriminiert daher klar zwischen
        Vektorisierung (typ. 0.05-1.5s mit Coverage) und Loop-Regression.
        """
        import time

        rng = np.random.default_rng(2026)
        n_tickers = 500
        n_days = 252
        index = pd.date_range("2024-01-01", periods=n_days, freq="B")
        returns = pd.DataFrame(
            rng.normal(0.0005, 0.015, size=(n_days, n_tickers)),
            index=index,
            columns=[f"T{i:03d}" for i in range(n_tickers)],
        )
        prices = _make_prices(returns)

        start = time.perf_counter()
        results = DiversificationModel().run(prices=prices)
        elapsed = time.perf_counter() - start

        assert len(results) == n_tickers
        assert all(r.rank is not None for r in results)
        assert elapsed < 2.0, (
            f"500 Ticker × 252 Tage dauerte {elapsed:.3f}s — Threshold 2.0s "
            f"(siehe Docstring zu Coverage-Overhead). Python-Loop reaktiviert?"
        )


class TestDiversificationEdgeCases:
    def test_empty_universe_returns_empty(self) -> None:
        prices = pd.DataFrame()
        assert DiversificationModel().run(prices=prices) == []

    def test_single_ticker_gets_rank_one_with_low_confidence(self) -> None:
        rng = np.random.default_rng(0)
        index = pd.date_range("2024-01-01", periods=60, freq="B")
        prices = _make_prices(pd.DataFrame({"SOLO": rng.normal(0, 0.01, 60)}, index=index))

        results = DiversificationModel().run(prices=prices)
        assert len(results) == 1
        assert results[0].ticker == "SOLO"
        assert results[0].rank == 1
        assert results[0].confidence == "low"

    def test_insufficient_datapoints_yields_no_ranks(self) -> None:
        """< 30 Datenpunkte → Ledoit-Wolf instabil → rank=None für alle."""
        rng = np.random.default_rng(1)
        index = pd.date_range("2024-01-01", periods=20, freq="B")
        returns = pd.DataFrame(
            {"A": rng.normal(0, 0.01, 20), "B": rng.normal(0, 0.02, 20)},
            index=index,
        )
        prices = _make_prices(returns)

        results = DiversificationModel().run(prices=prices)
        assert all(r.rank is None for r in results)
        assert all(r.confidence == "low" for r in results)

    def test_mid_series_nan_drops_rows_not_forward_filled(self) -> None:
        """Spec §5: ``returns = prices.pct_change().dropna()`` — Mid-Series-NaN
        müssen *Zeilen entfernen*, nicht still forward-filled werden.

        Yahoo-Realität (gesperrter Handel, late listings, Holiday-Mismatches)
        produziert mid-series NaN. Pandas-Default ``fill_method='pad'`` (deprecated)
        forward-fillt diese stillschweigend → NaN-Tage werden 0%-Returns →
        Vola/Korrelation verfälscht, ohne dass der Algorithmus es bemerkt.

        Setup: 70 Tage, 50 NaN-Mid in A. Spec-konform (``fill_method=None``)
        droppt die NaN-Zeilen → 18 valide Rows < MIN_DATAPOINTS → all rank=None.
        Bei forward-fill (Bug) bleiben ~69 Zeilen → A bekäme einen
        artificially-low-volatility-Score und würde Rang 1 belegen.
        """
        rng = np.random.default_rng(11)
        n = 70
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        a_prices = (1 + rng.normal(0.0005, 0.010, n)).cumprod() * 100
        b_prices = (1 + rng.normal(0.0005, 0.012, n)).cumprod() * 100
        c_prices = (1 + rng.normal(0.0005, 0.015, n)).cumprod() * 100
        prices = pd.DataFrame({"A": a_prices, "B": b_prices, "C": c_prices}, index=index)
        # 50 mid-series NaN in A: Spec-konformes dropna() reduziert Returns < MIN_DATAPOINTS
        prices.iloc[5:55, 0] = np.nan

        ranks = _run(prices)
        assert all(rank is None for rank in ranks.values()), (
            f"Mid-NaN müssen Zeilen droppen (nicht forward-filled werden), ranks={ranks}"
        )

    def test_zero_variance_ticker_gets_no_rank(self) -> None:
        """Ticker mit konstanten Preisen → std=0 → rank=None, confidence='low'."""
        rng = np.random.default_rng(3)
        n = 80
        index = pd.date_range("2024-01-01", periods=n, freq="B")
        returns = pd.DataFrame(
            {
                "NORMAL_A": rng.normal(0, 0.01, n),
                "NORMAL_B": rng.normal(0, 0.012, n),
                "FLAT": np.zeros(n),
            },
            index=index,
        )
        prices = _make_prices(returns)

        results = {r.ticker: r for r in DiversificationModel().run(prices=prices)}
        assert results["FLAT"].rank is None
        assert results["FLAT"].confidence == "low"
        assert results["NORMAL_A"].rank is not None
        assert results["NORMAL_B"].rank is not None
