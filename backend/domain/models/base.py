"""Gemeinsame Typen für alle 5 Quant-Modelle.

Jedes Modell ist eine Klasse mit `name`, `category` und einer `run`-Methode,
die eine Liste von ModelRankingResult zurückgibt — ein Eintrag pro Ticker.
"""

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel


class ModelRankingResult(BaseModel):
    """Ranking-Ergebnis einer Aktie aus einem Quant-Modell.

    rank=None und score=None bedeuten: für diesen Ticker konnte kein
    valides Ergebnis berechnet werden (z.B. zu wenig Datenpunkte). Das ist
    kein Fehler, sondern eine bewusste "no-rank"-Aussage.
    """

    model_config = {"frozen": True}

    ticker: str
    score: float | None
    rank: int | None
    confidence: Literal["low", "medium", "high"] = "high"


@runtime_checkable
class QuantModel(Protocol):
    """Schnittstelle, die alle 5 Modelle implementieren."""

    name: str
    category: Literal["Quality", "Trend", "Value", "Risk"]

    def run(self, prices: Any) -> list[ModelRankingResult]:
        """Berechnet Ränge für ein Universum.

        prices: Pandas-DataFrame mit Tickers als Spalten und Datum als Index.
                Typisierung als Any, weil pandas (noch) nicht in den
                Project-Deps ist — wird mit der ersten konkreten
                Implementierung gehärtet.
        """
        ...
