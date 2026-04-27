"""Trend Momentum — EWMA der relativen Returns vs. equal-weighted Universum.

Spec: docs/specs/2026-04-27-quant-models-redesign.md §3.1
Daten: Yahoo Tagespreise (~2 Jahre Historie für stabile EWMA)

Formel-Skizze (siehe Spec für Detail):
    rel_returns = stock_returns - benchmark_returns   # benchmark = prices.mean(axis=1)
    ewma = rel_returns.ewm(halflife=63, min_periods=32).mean()
    score = ewma.iloc[-1]
    rank = score.rank(ascending=False, method="min").astype(int)
"""

from typing import Any, Literal

from backend.domain.models.base import ModelRankingResult


class TrendMomentumModel:
    name: str = "trend_momentum"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Trend"

    HALFLIFE_DAYS: int = 63
    MIN_PERIODS: int = 32

    def run(self, prices: Any) -> list[ModelRankingResult]:
        raise NotImplementedError(
            "Trend Momentum implementation pending. "
            "See docs/specs/2026-04-27-quant-models-redesign.md §3.1."
        )
