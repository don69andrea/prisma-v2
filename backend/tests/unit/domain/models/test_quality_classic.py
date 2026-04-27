"""Tests für Quality Classic — Z-Score-Aggregation aus 8 Fundamentalkennzahlen.

Spec: docs/specs/2026-04-21-prisma-capstone-design.md §6.1
"""

import pytest

from backend.domain.models.quality_classic import QualityClassicModel

pytestmark = pytest.mark.unit


def _run(data: dict[str, dict[str, float | None]]) -> dict[str, int | None]:
    """Hilfsfunktion: gibt {ticker: rank} zurück (None = kein Rang)."""
    results = QualityClassicModel().run(fundamentals=data)
    return {r.ticker: r.rank for r in results}


# Minimale gültige Fundamentaldaten für einen Ticker
_GOOD: dict[str, float | None] = {
    "pe_ratio": 15.0,
    "pb_ratio": 2.0,
    "fcf_yield": 0.05,
    "operating_margin": 0.20,
    "dividend_yield": 0.03,
    "debt_to_equity": 0.5,
    "eps_growth_3y": 0.10,
    "sales_growth_3y": 0.08,
}
_BAD: dict[str, float | None] = {
    "pe_ratio": 40.0,
    "pb_ratio": 8.0,
    "fcf_yield": 0.01,
    "operating_margin": 0.03,
    "dividend_yield": 0.00,
    "debt_to_equity": 3.0,
    "eps_growth_3y": -0.05,
    "sales_growth_3y": -0.02,
}


class TestQualityClassicFormula:
    def test_better_fundamentals_get_lower_rank(self) -> None:
        ranks = _run({"GOOD": dict(_GOOD), "BAD": dict(_BAD)})
        assert ranks["GOOD"] == 1
        assert ranks["BAD"] == 2

    def test_golden_dataset_five_tickers(self) -> None:
        data: dict[str, dict[str, float | None]] = {
            "A": {**_GOOD},
            "B": {**_GOOD, "pe_ratio": 20.0},
            "C": {**_GOOD, "pe_ratio": 25.0, "pb_ratio": 3.0},
            "D": {**_BAD, "pe_ratio": 35.0},
            "E": {**_BAD},
        }
        ranks = _run(data)
        ra, rb, rc = ranks["A"], ranks["B"], ranks["C"]
        rd, re = ranks["D"], ranks["E"]
        assert ra is not None and rb is not None and rc is not None
        assert ra < rb < rc
        assert rd is not None and re is not None
        assert rd <= re
        assert set(ranks.values()) == {1, 2, 3, 4, 5}

    def test_identical_fundamentals_get_equal_rank(self) -> None:
        data: dict[str, dict[str, float | None]] = {
            "X": {**_GOOD},
            "Y": {**_GOOD},
            "Z": {**_GOOD},
        }
        ranks = _run(data)
        assert ranks["X"] == ranks["Y"] == ranks["Z"] == 1

    def test_deterministic(self) -> None:
        data: dict[str, dict[str, float | None]] = {"A": dict(_GOOD), "B": dict(_BAD)}
        assert _run(data) == _run(data)


class TestQualityClassicEdgeCases:
    def test_missing_metric_is_skipped(self) -> None:
        data: dict[str, dict[str, float | None]] = {
            "FULL": {**_GOOD},
            "PARTIAL": {**_GOOD, "pe_ratio": None},
        }
        results = {r.ticker: r for r in QualityClassicModel().run(fundamentals=data)}
        assert results["FULL"].rank is not None
        assert results["PARTIAL"].rank is not None

    def test_all_metrics_missing_gives_no_rank(self) -> None:
        data: dict[str, dict[str, float | None]] = {
            "OK": {**_GOOD},
            "EMPTY": {k: None for k in _GOOD},
        }
        ranks = _run(data)
        assert ranks["EMPTY"] is None
        assert ranks["OK"] == 1

    def test_single_ticker_gets_rank_one(self) -> None:
        ranks = _run({"SOLO": dict(_GOOD)})
        assert ranks["SOLO"] == 1

    def test_empty_universe_returns_empty(self) -> None:
        assert QualityClassicModel().run(fundamentals={}) == []
