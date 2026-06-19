"""Quality Classic — gleichgewichtete Z-Score-Aggregation aus 8 Fundamentalkennzahlen.

Spec: docs/specs/2026-04-21-prisma-prisma-v2-design.md §6.1
Daten: Yahoo Finance + FinancialModelingPrep Free Tier (Snapshot)

Formel:
    1. Z-Score je Kennzahl über alle Tickers (std=0 → z=0)
    2. "Niedrig = besser"-Kennzahlen werden invertiert (×−1)
    3. Gleichgewichteter Durchschnitt der verfügbaren Z-Scores → Quality-Score
    4. Rang aufsteigend: Ticker mit höchstem Score bekommt Rang 1
    5. Ticker ohne verfügbare Kennzahlen → rank=None, confidence="low"
"""

import statistics
from typing import Literal

from backend.domain.models.base import ModelRankingResult

# (metric_name, direction): direction=1 → hoch ist besser, -1 → niedrig ist besser
_METRICS: list[tuple[str, int]] = [
    ("pe_ratio", -1),
    ("pb_ratio", -1),
    ("fcf_yield", 1),
    ("operating_margin", 1),
    ("dividend_yield", 1),
    ("debt_to_equity", -1),
    ("eps_growth_3y", 1),
    ("sales_growth_3y", 1),
]

Fundamentals = dict[str, float | None]
UniverseData = dict[str, Fundamentals]


class QualityClassicModel:
    name: str = "quality_classic"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Quality"

    def run(self, fundamentals: UniverseData) -> list[ModelRankingResult]:
        """Berechnet Quality-Classic-Ränge für alle Tickers im Universum.

        Args:
            fundamentals: {ticker: {metric: value | None}}

        Returns:
            Liste von ModelRankingResult, sortiert nach Rang (None-Ränge am Ende).
        """
        if not fundamentals:
            return []

        z_scores = _compute_z_scores(fundamentals)
        scores = _aggregate_scores(fundamentals, z_scores)
        return _rank(scores)


def _compute_z_scores(data: UniverseData) -> dict[str, dict[str, float]]:
    """Berechnet Z-Scores je Kennzahl über alle Tickers."""
    z: dict[str, dict[str, float]] = {ticker: {} for ticker in data}

    for metric, direction in _METRICS:
        values = {ticker: v for ticker, row in data.items() if (v := row.get(metric)) is not None}
        if len(values) < 2:
            # Zu wenige Datenpunkte → Z-Score 0 für alle verfügbaren
            for ticker in values:
                z[ticker][metric] = 0.0
            continue

        mean = statistics.mean(values.values())
        std = statistics.stdev(values.values())

        for ticker, v in values.items():
            raw_z = (v - mean) / std if std > 0 else 0.0
            z[ticker][metric] = raw_z * direction

    return z


def _aggregate_scores(
    data: UniverseData, z_scores: dict[str, dict[str, float]]
) -> dict[str, float | None]:
    """Mittelt Z-Scores pro Ticker. Ticker ohne Werte → None."""
    scores: dict[str, float | None] = {}
    for ticker in data:
        ticker_z = list(z_scores[ticker].values())
        scores[ticker] = statistics.mean(ticker_z) if ticker_z else None
    return scores


def _rank(scores: dict[str, float | None]) -> list[ModelRankingResult]:
    """Vergibt Ränge absteigend nach Score (höchster Score = Rang 1)."""
    ranked = sorted(
        ((t, s) for t, s in scores.items() if s is not None),
        key=lambda x: x[1],
        reverse=True,
    )

    results: list[ModelRankingResult] = []
    current_rank = 1
    for i, (ticker, score) in enumerate(ranked):
        if i > 0 and score < ranked[i - 1][1]:
            current_rank = i + 1
        results.append(ModelRankingResult(ticker=ticker, score=score, rank=current_rank))

    for ticker, s in scores.items():
        if s is None:
            results.append(
                ModelRankingResult(ticker=ticker, score=None, rank=None, confidence="low")
            )

    return results
