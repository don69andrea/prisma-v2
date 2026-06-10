"""LangfristScoreCalculator — Berechnet den VIAC 30-Jahres-Score für Swiss Stocks.

Regelbasiert, kein I/O, kein LLM — deterministisch und testbar.
Kalibrierung auf SMI/SMIM-Charakteristika (Stand 2026).
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.value_objects.langfrist_score import LangfristScore
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

# Gewichtung der vier Komponenten (Summe = 1.0)
_W_DIVIDENDE = 0.35
_W_BILANZ = 0.30
_W_STABILITAET = 0.25
_W_MARKTKAPITA = 0.10


class LangfristScoreCalculator:
    """Berechnet LangfristScore aus Fundamentaldaten und optionaler Volatilität."""

    def calculate(
        self,
        ticker: str,
        fundamentals: SwissFundamentals,
        annualized_volatility: float | None = None,
    ) -> LangfristScore:
        dividende = self._score_dividende(fundamentals.dividend_yield)
        bilanz = self._score_bilanz(fundamentals)
        stabilitaet = self._score_stabilitaet(annualized_volatility)
        marktkapita = self._score_marktkapita(fundamentals.market_cap_chf)

        value = round(
            dividende * _W_DIVIDENDE
            + bilanz * _W_BILANZ
            + stabilitaet * _W_STABILITAET
            + marktkapita * _W_MARKTKAPITA,
            2,
        )
        value = max(0.0, min(10.0, value))

        return LangfristScore(
            ticker=ticker,
            value=value,
            components={
                "dividende": round(dividende, 2),
                "bilanz": round(bilanz, 2),
                "stabilitaet": round(stabilitaet, 2),
                "marktkapita": round(marktkapita, 2),
            },
            explanation=self._explain(dividende, bilanz, stabilitaet, marktkapita),
        )

    @staticmethod
    def _score_dividende(dividend_yield: float | None) -> float:
        if dividend_yield is None:
            return 5.0
        if dividend_yield >= 0.04:
            return 10.0
        if dividend_yield >= 0.03:
            return 8.5
        if dividend_yield >= 0.02:
            return 7.0
        if dividend_yield >= 0.01:
            return 5.0
        return 3.0

    @staticmethod
    def _score_bilanz(f: SwissFundamentals) -> float:
        score = 5.0
        if f.eps_chf is not None:
            score = 8.0 if f.eps_chf > 0 else 2.0
        if f.pb_ratio is not None:
            if f.pb_ratio < 2:
                score = min(10.0, score + 1.5)
            elif f.pb_ratio > 6:
                score = max(0.0, score - 1.5)
        return score

    @staticmethod
    def _score_stabilitaet(vol: float | None) -> float:
        if vol is None:
            return 5.0
        if vol < 0.12:
            return 9.5
        if vol < 0.18:
            return 8.0
        if vol < 0.25:
            return 6.5
        if vol < 0.35:
            return 4.5
        return 2.5

    @staticmethod
    def _score_marktkapita(market_cap_chf: Decimal | None) -> float:
        if market_cap_chf is None:
            return 5.0
        cap = float(market_cap_chf)
        if cap >= 50_000_000_000:
            return 10.0
        if cap >= 10_000_000_000:
            return 8.5
        if cap >= 1_000_000_000:
            return 7.0
        if cap >= 100_000_000:
            return 5.0
        return 3.0

    @staticmethod
    def _explain(div: float, bil: float, stab: float, cap: float) -> str:
        parts: list[str] = []
        if div >= 8.0:
            parts.append("starke Dividendenrendite (>3%)")
        elif div <= 3.5:
            parts.append("keine/geringe Dividende")

        if bil >= 8.0:
            parts.append("solide Bilanz & positiver EPS")
        elif bil <= 3.0:
            parts.append("schwache Bilanzqualität")

        if stab >= 8.0:
            parts.append("niedrige Volatilität (<18%)")
        elif stab <= 3.5:
            parts.append("hohe Volatilität (>35%)")

        if cap >= 8.0:
            parts.append("Large-Cap (>10 Mrd. CHF)")
        elif cap <= 4.0:
            parts.append("Small-Cap (<100 Mio. CHF)")

        if not parts:
            return "Ausgeglichenes Profil für langfristige Vorsorge."
        return "Treiber: " + ", ".join(parts) + "."
