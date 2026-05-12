"""Alpha — Multi-Horizon Sharpe-gewichtete Outperformance vs. equal-weighted Universum.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §2
      docs/specs/2026-04-21-prisma-capstone-design.md §6.3
      docs/specs/2026-04-27-quant-models-redesign.md (Equal-Weighted Pattern)

Formel:
    benchmark = prices.mean(axis=1)                   # Equal-Weighted Universe

    Für h ∈ {5, 63, 126, 252, 504}:
        outperf(h) = prices.pct_change(h).iloc[-1]
                     − benchmark.pct_change(h).iloc[-1]

    daily_excess = prices.pct_change() − benchmark.pct_change()
    sharpe       = daily_excess.mean() / daily_excess.std() × √252
                   (Sharpe = 0 falls std = 0)

    raw_score = Σ(outperf(h) × normalized_weight(h)) + sharpe × SHARPE_WEIGHT
    score     = (raw_score − mean(raw_scores)) / std(raw_scores)   # Z-Score
    rank      = score.rank(ascending=False, method="min")

Spec-Deviations (dokumentiert in AI-USAGE.md):
- Equal-weighted Benchmark statt ^GSPC: konsistent mit Trend Momentum, Value Alpha
  Potential und Diversification (Pattern aus Redesign §3.1: "bewusst gegen
  cap-gewichtetes ^SSMI, das von Nestlé/Roche dominiert würde").
- SHARPE_WEIGHT = 0.05: Spec §2 sagt nur "additiv" ohne Zahl. Skalen-Argument:
  annualisierte Sharpe-SD ist über SMI-Tickers ~7× grösser als Outperformance-SD;
  Gewicht 0.05 hält Sharpe als Quality-Tilt, ohne die Horizont-Gewichtung zu
  überfahren. Empirische Validierung im ersten Backtest.

Edge-Cases:
- Leeres Universum → []
- 1 Ticker → benchmark = Ticker → outperf = 0, sharpe = 0 → score = 0, rank = 1
- < 32 Handelstage (MIN_PERIODS) → rank=None, confidence="low"
- Horizont h ≥ Historie → outperf(h) übersprungen, Gewicht auf verfügbare
  Horizonte umverteilt (Spec §2 Edge-Case)
- daily_excess.std() = 0 → Sharpe = 0 (Spec §2 Edge-Case)
"""

from typing import Literal

import numpy as np
import pandas as pd

from backend.domain.models.base import ModelRankingResult


class AlphaModel:
    name: str = "alpha"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Trend"

    HORIZONS: tuple[int, ...] = (5, 63, 126, 252, 504)
    WEIGHTS: tuple[float, ...] = (0.10, 0.15, 0.25, 0.30, 0.20)
    SHARPE_WEIGHT: float = 0.05
    MIN_PERIODS: int = 32
    TRADING_DAYS_PER_YEAR: int = 252

    def run(self, prices: pd.DataFrame) -> list[ModelRankingResult]:
        """Berechnet Alpha-Ränge für ein Preis-Universum.

        Args:
            prices: DataFrame mit DatetimeIndex und Ticker-Spalten.

        Returns:
            Liste von ModelRankingResult, ein Eintrag pro Ticker.
        """
        if prices.empty or len(prices.columns) == 0:
            return []

        tickers: list[str] = list(prices.columns)
        n_days = len(prices)

        if n_days < self.MIN_PERIODS:
            return [
                ModelRankingResult(ticker=t, score=None, rank=None, confidence="low")
                for t in tickers
            ]

        benchmark = prices.mean(axis=1)
        daily_excess = prices.pct_change().sub(benchmark.pct_change(), axis=0)

        # Sharpe je Ticker (annualisiert), Edge: std=0 → Sharpe=0
        excess_mean = daily_excess.mean()
        excess_std = daily_excess.std()
        sharpe = pd.Series(0.0, index=tickers)
        nonzero = excess_std > 0
        sharpe.loc[nonzero] = (
            excess_mean.loc[nonzero] / excess_std.loc[nonzero] * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        )

        # Multi-Horizon Outperformance mit dynamischer Gewichtsumverteilung
        available: list[tuple[int, float]] = [
            (h, w) for h, w in zip(self.HORIZONS, self.WEIGHTS, strict=True) if h < n_days
        ]
        total_w = sum(w for _, w in available)
        outperf_score = pd.Series(0.0, index=tickers)
        if total_w > 0:
            for h, w in available:
                stock_h = prices.pct_change(h).iloc[-1]
                bench_h = benchmark.pct_change(h).iloc[-1]
                outperf_score = outperf_score + (stock_h - bench_h) * (w / total_w)

        raw_score = outperf_score + self.SHARPE_WEIGHT * sharpe

        # Z-Score-Normalisierung über Ticker (Spec §2 finaler Schritt)
        rs_mean = raw_score.mean()
        rs_std = raw_score.std()
        if rs_std == 0 or pd.isna(rs_std):
            scores: dict[str, float | None] = {t: 0.0 for t in tickers}
        else:
            z = (raw_score - rs_mean) / rs_std
            scores = {t: (None if pd.isna(z[t]) else float(z[t])) for t in tickers}

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
