"""Swiss-kalibrierter Quant-Scorer für SIX-kotierte Titel.

Scoring-Bänder sind auf SMI-Durchschnittswerte kalibriert.
Alle Methoden sind zustandslos und seiteneffektfrei.
"""

from __future__ import annotations

from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals
from backend.domain.value_objects.swiss_quant_score import SwissQuantScore

_BUY_THRESHOLD = 70.0
_HOLD_THRESHOLD = 40.0


class SwissQuantScorer:
    """Berechnet einen quantitativen Score für Swiss Stocks.

    Kalibrierung auf SMI-Titel (Stand 2026):
    - P/E: tiefe Werte < 15 bevorzugt (SMI-Median ~18)
    - P/B: < 2 attraktiv (SMI-Median ~3)
    - Dividende: > 2% gut für CH-Vorsorge-Kontext
    - EPS: positiv = Mindestvoraussetzung
    """

    def score(self, ticker: str, fundamentals: SwissFundamentals) -> SwissQuantScore:
        value_score = self._score_value(fundamentals)
        income_score = self._score_income(fundamentals)
        quality_score = self._score_quality(fundamentals)
        composite = round(value_score * 0.4 + income_score * 0.4 + quality_score * 0.2, 2)
        signal = (
            "BUY"
            if composite >= _BUY_THRESHOLD
            else "HOLD"
            if composite >= _HOLD_THRESHOLD
            else "SELL"
        )
        signal_reason = self._generate_signal_reason(
            composite=composite,
            signal=signal,
            value_score=value_score,
            quality_score=quality_score,
            income_score=income_score,
        )
        return SwissQuantScore(
            ticker=ticker,
            value_score=value_score,
            income_score=income_score,
            quality_score=quality_score,
            composite=composite,
            signal=signal,
            signal_reason=signal_reason,
        )

    @staticmethod
    def _generate_signal_reason(
        composite: float,
        signal: str,
        value_score: float,
        quality_score: float,
        income_score: float,
    ) -> str:
        """Generiert eine Alltagssprache-Erklärung für das Signal."""
        parts: list[str] = []

        if value_score >= 70:
            parts.append("günstig bewertet")
        elif value_score <= 30:
            parts.append("hoch bewertet")

        if quality_score >= 70:
            parts.append("hohe Qualität")
        elif quality_score <= 30:
            parts.append("schwache Qualität")

        if income_score >= 70:
            parts.append("attraktive Dividende")

        factors = ", ".join(parts) if parts else "gemischte Fundamentaldaten"

        if signal == "BUY":
            return (
                f"Starkes Kaufsignal: {factors}. PRISMA-Score: {composite:.0f}/100."
            )
        if signal == "HOLD":
            return (
                f"Neutral: {factors}. PRISMA-Score: {composite:.0f}/100. Beobachten."
            )
        return (
            f"Verkaufssignal: {factors}. PRISMA-Score: {composite:.0f}/100."
        )

    @staticmethod
    def interpret_score(score: float) -> str:
        """Wandelt numerischen Score in lesbares Label um."""
        if score >= 80:
            return "Ausgezeichnet"
        if score >= 65:
            return "Gut"
        if score >= 50:
            return "Durchschnittlich"
        if score >= 35:
            return "Schwach"
        return "Sehr schwach"

    def _score_value(self, f: SwissFundamentals) -> float:
        pe_score = self._score_pe(f.pe_ratio)
        pb_score = self._score_pb(f.pb_ratio)
        return round(pe_score * 0.6 + pb_score * 0.4, 2)

    def _score_income(self, f: SwissFundamentals) -> float:
        if f.dividend_yield is None:
            return 50.0
        dy = f.dividend_yield
        if dy > 0.03:
            return 100.0
        if dy > 0.02:
            return 75.0
        if dy > 0.01:
            return 50.0
        return 25.0

    def _score_quality(self, f: SwissFundamentals) -> float:
        if f.eps_chf is None:
            return 50.0
        return 100.0 if f.eps_chf > 0 else 0.0

    @staticmethod
    def _score_pe(pe: float | None) -> float:
        if pe is None:
            return 50.0
        if pe <= 0:
            return 0.0
        if pe < 15:
            return 100.0
        if pe < 20:
            return 75.0
        if pe < 25:
            return 50.0
        return 25.0

    @staticmethod
    def _score_pb(pb: float | None) -> float:
        if pb is None:
            return 50.0
        if pb < 2:
            return 100.0
        if pb < 4:
            return 75.0
        if pb < 6:
            return 50.0
        return 25.0
