"""Value Alpha Potential — Mean-Reversion gegen das eigene 1J-Outperformance-Hoch.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §4
      docs/specs/2026-04-27-quant-models-redesign.md §3.2

Formel:
    benchmark_prices = prices.mean(axis=1)            # Equal-Weighted Universe
    alpha            = prices.pct_change(63)
                       .sub(benchmark_prices.pct_change(63), axis=0)
    rolling_max      = alpha.rolling(window=252, min_periods=68).max()
    potential        = rolling_max - alpha            # Distance to Peak
    score            = potential.iloc[-1]
    rank             = score.rank(ascending=False, method="min")

Annahme: Mean-Reversion. Was stark outperformt hat, kehrt häufig dazu zurück. Höchster
Score (= grösste Distanz zum eigenen 1J-Hoch) = grösstes Aufholpotential = Rang 1.

Edge-Cases:
- < 68 Datenpunkte für rolling-max → score=None, rank=None, confidence="low"
- 1 Ticker → benchmark = Ticker → alpha = 0 → potential = 0 → rank=1
- Negativer potential (heutiger Peak) → gültig, wird normal gerankt
- Leeres Universum → []
"""

from typing import Literal

import pandas as pd

from backend.domain.models.base import ModelRankingResult


class ValueAlphaPotentialModel:
    name: str = "value_alpha_potential"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Value"

    ALPHA_HORIZON_DAYS: int = 63
    ROLLING_MAX_WINDOW_DAYS: int = 252
    MIN_PERIODS: int = 68

    def run(self, prices: pd.DataFrame) -> list[ModelRankingResult]:
        """Berechnet Value-Alpha-Potential-Ränge.

        Args:
            prices: DataFrame mit DatetimeIndex und Ticker-Spalten.

        Returns:
            Liste von ModelRankingResult, ein Eintrag pro Ticker.
        """
        if prices.empty or len(prices.columns) == 0:
            return []

        tickers: list[str] = list(prices.columns)
        benchmark = prices.mean(axis=1)

        alpha = prices.pct_change(self.ALPHA_HORIZON_DAYS).sub(
            benchmark.pct_change(self.ALPHA_HORIZON_DAYS), axis=0
        )
        rolling_max = alpha.rolling(
            window=self.ROLLING_MAX_WINDOW_DAYS, min_periods=self.MIN_PERIODS
        ).max()
        potential = rolling_max - alpha
        snapshot = potential.iloc[-1]

        scores: dict[str, float | None] = {
            ticker: (None if pd.isna(snapshot[ticker]) else float(snapshot[ticker]))
            for ticker in tickers
        }
        return _rank(scores)


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
