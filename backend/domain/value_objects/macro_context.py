"""Domain Value Object: MacroContext — Makro-Klima für Schweizer Investments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MacroContext:
    """Aktueller Makro-Kontext für den Schweizer Aktienmarkt.

    leitzins:     SNB-Leitzins in % (z.B. 0.25)
    chf_eur:      CHF pro EUR (z.B. 0.93)
    inflation_ch: Schweizer Inflationsrate YoY in % (None wenn nicht verfügbar)
    pmi_ch:       Schweizer PMI (None wenn nicht verfügbar)
    snapshot_date: Datum der Datenerhebung
    climate:      "EXPANSIV" | "NEUTRAL" | "RESTRIKTIV"
    narrative_de: Kurze deutsche Narrative (LLM-generiert, Pydantic-validiert)
    narrative_en: Kurze englische Narrative (LLM-generiert, Pydantic-validiert)
    """

    leitzins: float
    chf_eur: float
    inflation_ch: float | None
    pmi_ch: float | None
    snapshot_date: date
    climate: str
    narrative_de: str
    narrative_en: str

    @classmethod
    def climate_for(cls, leitzins: float, inflation_ch: float | None) -> str:
        """Bestimmt das Makro-Klima basierend auf SNB-Leitzins und Inflation."""
        if leitzins <= 0.0:
            return "EXPANSIV"
        if leitzins <= 0.75:
            if inflation_ch is None or inflation_ch <= 2.0:
                return "NEUTRAL"
            return "RESTRIKTIV"
        return "RESTRIKTIV"
