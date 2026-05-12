"""Trend Momentum — EWMA der relativen Returns vs. equal-weighted Universum.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §3
      docs/specs/2026-04-27-quant-models-redesign.md §3.1

Formel:
    Benchmark    = prices.mean(axis=1)            # Equal-Weighted Universe
    rel_returns  = prices.pct_change()
                   .sub(benchmark.pct_change(), axis=0)
    exp_momentum = rel_returns.ewm(halflife=63, min_periods=32).mean()
    score        = exp_momentum.iloc[-1]
    rank         = score.rank(ascending=False, method="min")

halflife=63: heute = volles Gewicht, vor 63 Handelstagen = 50%, vor 126 Tagen = 25%.
Filtert kurzfristiges Rauschen, erfasst 3-12-Monats-Trend (Jegadeesh-Titman 1993,
Carhart 1997).

Edge-Cases:
- < 32 Datenpunkte → EWMA NaN → rank=None, confidence="low"
- 1 Ticker → Benchmark = Ticker → rel_returns = 0 → score=0 → rank=1
- Alle Ticker identisch → rel_returns = 0 → alle rank=1 (Gleichstand)
- Leeres Universum → []
"""

from typing import Literal

import pandas as pd

from backend.domain.models.base import ModelRankingResult


class TrendMomentumModel:
    name: str = "trend_momentum"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Trend"

    HALFLIFE_DAYS: int = 63
    MIN_PERIODS: int = 32

    def run(self, prices: pd.DataFrame) -> list[ModelRankingResult]:
        """Berechnet Trend-Momentum-Ränge für ein Preis-Universum.

        Args:
            prices: DataFrame mit DatetimeIndex und Ticker-Spalten.

        Returns:
            Liste von ModelRankingResult, ein Eintrag pro Ticker.
        """
        if prices.empty or len(prices.columns) == 0:
            return []

        tickers: list[str] = list(prices.columns)
        benchmark = prices.mean(axis=1)
        rel_returns = prices.pct_change().sub(benchmark.pct_change(), axis=0)

        exp_momentum = rel_returns.ewm(
            halflife=self.HALFLIFE_DAYS, min_periods=self.MIN_PERIODS
        ).mean()
        snapshot = exp_momentum.iloc[-1]

        scores: dict[str, float | None] = {
            ticker: (None if pd.isna(snapshot[ticker]) else float(snapshot[ticker]))
            for ticker in tickers
        }
        return _rank(scores)


def _rank(scores: dict[str, float | None]) -> list[ModelRankingResult]:
    """Vergibt Ränge absteigend nach Score (höchster Score = Rang 1).

    Gleicher Score → gleicher Rang (method="min", konsistent mit Spec §6).
    """
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
