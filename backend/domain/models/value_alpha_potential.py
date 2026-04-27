"""Value Alpha Potential — Mean-Reversion gegen das eigene 1J-Outperformance-Hoch.

Spec: docs/specs/2026-04-27-quant-models-redesign.md §3.2
Daten: Yahoo Tagespreise (~1.5 Jahre für 252d-Rolling-Window)

Formel-Skizze (siehe Spec für Detail):
    horizon = 63
    alpha = stock_returns.pct_change(horizon) - benchmark_returns.pct_change(horizon)
    rolling_max_alpha = alpha.rolling(window=252, min_periods=68).max()
    potential = rolling_max_alpha - alpha
    score = potential.iloc[-1]
    rank = score.rank(ascending=False, method="min").astype(int)
"""

from typing import Any, Literal

from backend.domain.models.base import ModelRankingResult


class ValueAlphaPotentialModel:
    name: str = "value_alpha_potential"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Value"

    ALPHA_HORIZON_DAYS: int = 63
    ROLLING_MAX_WINDOW_DAYS: int = 252
    MIN_PERIODS: int = 68

    def run(self, prices: Any) -> list[ModelRankingResult]:
        raise NotImplementedError(
            "Value Alpha Potential implementation pending. "
            "See docs/specs/2026-04-27-quant-models-redesign.md §3.2."
        )
