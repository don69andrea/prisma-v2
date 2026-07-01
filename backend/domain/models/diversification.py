"""Diversification — Ledoit-Wolf-Shrinkage-Kovarianz, Risk-Score je Aktie.

Spec: docs/specs/2026-04-28-quant-mvp-models.md §5
      docs/specs/2026-04-21-prisma-prisma-v2-design.md §6.5

Formel:
    1. returns = prices.pct_change().dropna()
    2. Ledoit-Wolf-Kovarianzmatrix
    3. Annualisierte Volatilität (std × √252) je Ticker
    4. Mittlere Korrelation (ohne Selbstkorrelation) je Ticker
    5. Score = 2 / (volatility + 1 + avg_correlation)    — hoch = besser
       (avg_correlation nach [0,2] verschoben → Nenner immer positiv; negative
        Korrelation = bester Diversifizierer = höchster Score, kein Vorzeichen-Kippen)
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
    """Berechnet Diversification-Score je Ticker. None für Ticker mit Roh-Std=0.

    Vektorisierte NumPy-Implementation: Korrelationen via Matrix-Operationen
    statt Python-Loop. Spec §5 Performance-Ziel: <500ms für 500 Ticker.
    """
    # Erkennt Zero-Variance-Ticker an Roh-Returns, BEVOR Ledoit-Wolf shrinking
    # die Diagonale glättet und die Detektion verschleiert.
    raw_std = returns.std(axis=0).to_numpy()
    flat_mask = raw_std == 0.0

    lw = LedoitWolf().fit(returns.to_numpy())
    cov = lw.covariance_
    std_devs = np.sqrt(np.diag(cov))

    # safe_std: 1.0 statt 0.0 in der Division, um Division-by-Zero-Warnings zu
    # vermeiden — betroffene Einträge werden später durch `invalid` maskiert.
    safe_std = np.where(std_devs == 0.0, 1.0, std_devs)
    corr_matrix = cov / np.outer(safe_std, safe_std)

    # weights[i, j] = 1 wenn j ein valider Korrelationspartner für i ist:
    # j != i, j nicht flat, std_devs[j] > 0.
    valid_partner = (~flat_mask) & (std_devs > 0)
    n = len(tickers)
    weights = np.broadcast_to(valid_partner.astype(float), (n, n)).copy()
    np.fill_diagonal(weights, 0.0)

    sum_corr = (corr_matrix * weights).sum(axis=1)
    count_corr = weights.sum(axis=1)
    safe_count = np.where(count_corr == 0.0, 1.0, count_corr)
    avg_corr = sum_corr / safe_count

    volatility = std_devs * np.sqrt(_TRADING_DAYS_PER_YEAR)
    # avg_corr ∈ [-1, 1] wird nach [0, 2] verschoben (1 + avg_corr), damit der
    # Nenner IMMER positiv ist. Vorher: 2 / (volatility + avg_corr) — bei negativer
    # Korrelation wurde der Nenner negativ (bester Diversifizierer bekam negativen
    # Score → Rang zuletzt) bzw. es gab einen Pol nahe avg_corr ≈ -volatility.
    # Die additive +1-Konstante verschiebt alle Nenner uniform → die Rang-Ordnung
    # aller bisher gültigen (positiver-Nenner-)Ticker bleibt exakt erhalten; nur
    # zuvor negative Nenner (negative Korrelation) werden nun korrekt eingeordnet.
    denom = volatility + 1.0 + avg_corr
    raw_scores = 2.0 / denom

    invalid = flat_mask | (std_devs == 0.0) | (count_corr == 0.0)
    return {
        ticker: (None if invalid[i] else float(raw_scores[i])) for i, ticker in enumerate(tickers)
    }


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
