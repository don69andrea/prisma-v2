"""Alpha — gewichteter Outperformance-Score über 5 Horizonte + Sharpe-Bonus.

Spec: docs/specs/2026-04-21-prisma-capstone-design.md §6.3
Daten: Yahoo Tagespreise + ^SSMI als Benchmark
"""

from typing import Any, Literal

from backend.domain.models.base import ModelRankingResult


class AlphaModel:
    name: str = "alpha"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Trend"

    def run(self, prices: Any) -> list[ModelRankingResult]:
        raise NotImplementedError(
            "Alpha implementation pending. "
            "See docs/specs/2026-04-21-prisma-capstone-design.md §6.3 — "
            "5-Horizon-Outperformance (1W/3M/6M/1J/2J), Sharpe-Bonus, Rang aufsteigend."
        )
