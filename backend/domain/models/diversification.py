"""Diversification — Ledoit-Wolf-Shrinkage-Kovarianz, Risk-Score je Aktie.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §5
      docs/specs/2026-04-21-prisma-capstone-design.md §6.5

Formel:
    1. returns = prices.pct_change().dropna()
    2. Ledoit-Wolf-Kovarianzmatrix
    3. Annualisierte Volatilität (std × √252) je Ticker
    4. Mittlere Korrelation (ohne Selbstkorrelation) je Ticker
    5. Score = 2 / (volatility + avg_correlation)        — hoch = besser
    6. Rang absteigend: höchster Score = Rang 1
    7. Edge-Cases: < 30 Datenpunkte → alle rank=None;
       n=1 Ticker → rank=1, confidence="low";
       Ticker mit std=0 → rank=None, confidence="low".
"""

from typing import Literal

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from backend.domain.models.base import ModelRankingResult

_MIN_DATAPOINTS: int = 30
_TRADING_DAYS_PER_YEAR: int = 252


class DiversificationModel:
    name: str = "diversification"
    category: Literal["Quality", "Trend", "Value", "Risk"] = "Risk"

    def run(self, prices: pd.DataFrame) -> list[ModelRankingResult]:
        """Berechnet Diversification-Ränge für ein Preis-Universum.

        Args:
            prices: DataFrame mit DatetimeIndex und Ticker-Spalten.

        Returns:
            Liste von ModelRankingResult, ein Eintrag pro Ticker.
        """
        if prices.empty or len(prices.columns) == 0:
            return []

        tickers: list[str] = list(prices.columns)

        # n=1 ist semantisch keine Diversification-Aussage (kein zweiter Ticker
        # zum Korrelieren). rank=1 / confidence="low" ist die kanonische
        # "no-rank-but-valid"-Antwort, unabhängig von der Datenpunkt-Anzahl —
        # bewusst VOR dem MIN_DATAPOINTS-Check.
        if len(tickers) == 1:
            return [ModelRankingResult(ticker=tickers[0], score=None, rank=1, confidence="low")]

        # fill_method=None: pandas' deprecated default 'pad' würde mid-series NaN
        # forward-fillen → künstliche 0%-Returns verfälschen Vola/Korrelation.
        # Spec §5: returns = prices.pct_change().dropna() — Zeilen droppen, nicht fillen.
        returns = prices.pct_change(fill_method=None).dropna()
        if len(returns) < _MIN_DATAPOINTS:
            return [
                ModelRankingResult(ticker=t, score=None, rank=None, confidence="low")
                for t in tickers
            ]

        scores = _compute_scores(returns, tickers)
        return _rank(scores)


def _compute_scores(returns: pd.DataFrame, tickers: list[str]) -> dict[str, float | None]:
    """Berechnet Diversification-Score je Ticker. None für Ticker mit Roh-Std=0."""
    # Erkennt Zero-Variance-Ticker an Roh-Returns, BEVOR Ledoit-Wolf shrinking
    # die Diagonale glättet und die Detektion verschleiert.
    raw_std = returns.std(axis=0)
    flat_tickers = {t for t in tickers if raw_std.get(t, 0.0) == 0.0}

    lw = LedoitWolf().fit(returns.to_numpy())
    cov_matrix = pd.DataFrame(lw.covariance_, index=tickers, columns=tickers)

    std_devs = np.sqrt(np.diag(cov_matrix.to_numpy()))

    scores: dict[str, float | None] = {}
    for i, ticker in enumerate(tickers):
        if ticker in flat_tickers:
            scores[ticker] = None
            continue

        std_i = float(std_devs[i])
        if std_i == 0.0:
            scores[ticker] = None
            continue

        # Korrelationen mit allen anderen Tickern (ohne Selbst, ohne Flat-Ticker)
        correlations: list[float] = []
        for j, other in enumerate(tickers):
            if i == j or other in flat_tickers or std_devs[j] == 0.0:
                continue
            corr = float(cov_matrix.iat[i, j]) / (std_i * float(std_devs[j]))
            correlations.append(corr)

        if not correlations:
            scores[ticker] = None
            continue

        avg_corr = sum(correlations) / len(correlations)
        volatility = std_i * np.sqrt(_TRADING_DAYS_PER_YEAR)
        denom = volatility + avg_corr
        if denom == 0.0:
            scores[ticker] = None
            continue
        scores[ticker] = float(2.0 / denom)

    # Bewahre Reihenfolge der Ticker
    return {t: scores.get(t) for t in tickers}


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
