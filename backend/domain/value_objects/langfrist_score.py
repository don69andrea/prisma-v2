"""LangfristScore — Score (0–10) für 30-Jahres-Altersvorsorge-Eignung (VIAC/Säule 3a)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LangfristScore:
    """Gesamtscore + Komponenten für die Langfrist-Eignung eines Swiss Stocks.

    `value` ist der gewichtete Gesamtscore (0.0 = schlechteste, 10.0 = beste Eignung).
    `components` enthält die Einzel-Scores (je 0–10) für die vier Dimensionen:
      - dividende:   Dividendenstabilität (Gewicht 35%)
      - bilanz:      Bilanzqualität / EPS (Gewicht 30%)
      - stabilitaet: Kursvolatilität (Gewicht 25%)
      - marktkapita: Marktkapitalisierung / Unternehmensgrösse (Gewicht 10%)
    """

    ticker: str
    value: float  # 0.0–10.0
    components: dict[str, float] = field(default_factory=dict)
    explanation: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 10.0):
            raise ValueError(f"value muss zwischen 0 und 10 liegen, erhalten: {self.value}")
