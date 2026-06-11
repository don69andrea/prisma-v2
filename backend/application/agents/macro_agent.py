"""MacroIntelligenceAgent — Ticker-spezifischer Makro-Score für CH-Aktien."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend.application.services.macro_service import MacroService

_logger = logging.getLogger(__name__)

# SMI/SMIM-Exporteure (Auslandumsatz >80%) — starker CHF = Gegenwind
_EXPORT_HEAVY: frozenset[str] = frozenset({
    "NESN.SW",    # Nestlé — >98% Auslandumsatz
    "ROG.SW",     # Roche — Pharma, global
    "NOVN.SW",    # Novartis — Pharma, global
    "LONN.SW",    # Lonza — Pharma/Biotech, global
    "LOGN.SW",    # Logitech — Tech, global
    "BARN.SW",    # Barry Callebaut — Schokolade, global
    "GIVN.SW",    # Givaudan — Aromen/Duftstoffe, global
    "ABBN.SW",    # ABB — Industrieausrüstung, global
    "KNIN.SW",    # Kuehne+Nagel — Logistik, global
    "SCHP.SW",    # Schindler — Aufzüge, global
    "LISN.SW",    # Lindt & Sprüngli — Schokolade, global
    "GEBN.SW",    # Geberit — Sanitärtechnik, europäisch
    "CFR.SW",     # Richemont — Uhren/Luxus, global
    "SREN.SW",    # Swiss Re — Rückversicherung, global
    "STMN.SW",    # Straumann — Dental, global
    "VACN.SW",    # VAT Group — Tech, global
})

# Inlandsfokussierte Titel (CHF-Stärke weniger relevant)
_DOMESTIC_FOCUS: frozenset[str] = frozenset({
    "UBSG.SW",    # UBS — Bankwesen, Schweizer Heimbasis
    "SLHN.SW",    # Swiss Life — CH Versicherung
    "BAER.SW",    # Julius Bär — Wealth Management, CHF-Erlöse
    "PGHN.SW",    # Partners Group — CH domiziliert
})

# Sektoren die per se exportlastig sind (Sektor-Hint aus InvestorProfile)
_EXPORT_SECTORS: frozenset[str] = frozenset({"pharma", "tech", "luxury", "industrial", "chemical"})

# chf_eur = 1 CHF in EUR (Fallback: 0.93). Höher = stärkerer CHF.
_CHF_STRONG_THRESHOLD = 0.95   # CHF stark → schadet Exporteuren
_CHF_WEAK_THRESHOLD = 0.91     # CHF schwach → begünstigt Exporteure


class MacroScore(BaseModel):
    """Ticker-spezifischer Makro-Score mit Einzelkomponenten."""

    ticker: str
    score: float = Field(ge=0.0, le=100.0)
    leitzins: float
    chf_eur: float
    climate: str
    chf_impact: str  # "POSITIV" | "NEUTRAL" | "NEGATIV"
    reasoning: str


class MacroIntelligenceAgent:
    """Berechnet einen ticker-spezifischen Makro-Score (0–100).

    Berücksichtigt drei Faktoren:
    - SNB-Leitzins: Niedrig = akkommodativ (+15 bis +20 Punkte)
    - CHF-Stärke: Exporteure leiden bei starkem CHF; Inlandstitel profitieren
    - Inflation CH: Stabil (<2%) = positiv (+10 Punkte)

    Args:
        macro_service: Injizierter MacroService für SNB/CHF-Daten.
    """

    def __init__(self, macro_service: MacroService) -> None:
        self._macro_service = macro_service

    async def get_macro_score(self, ticker: str, sector: str | None = None) -> MacroScore:
        """Berechnet den Makro-Score für einen Schweizer Aktien-Ticker.

        Args:
            ticker: SIX-Ticker-Symbol (z.B. 'NESN.SW')
            sector: Optionaler Sektor-Hint ('pharma', 'tech', usw.)

        Returns:
            MacroScore mit Score 0–100 und Begründung.
        """
        ctx = await self._macro_service.get_context()

        score = 50.0  # Baseline
        reasons: list[str] = []

        # --- SNB-Leitzins-Anpassung ---
        if ctx.leitzins <= 0.0:
            score += 20
            reasons.append(f"Negativzins ({ctx.leitzins:.2f}%) — sehr akkommodativ")
        elif ctx.leitzins <= 0.5:
            score += 15
            reasons.append(f"Tiefer Leitzins ({ctx.leitzins:.2f}%) — akkommodativ")
        elif ctx.leitzins <= 1.0:
            score += 5
            reasons.append(f"Moderater Leitzins ({ctx.leitzins:.2f}%) — leicht positiv")
        elif ctx.leitzins <= 1.5:
            score -= 10
            reasons.append(f"Erhöhter Leitzins ({ctx.leitzins:.2f}%) — restriktiv")
        else:
            score -= 20
            reasons.append(f"Hoher Leitzins ({ctx.leitzins:.2f}%) — stark restriktiv")

        # --- CHF-Stärke-Anpassung (per Ticker) ---
        # chf_eur = 1 CHF in EUR; höherer Wert = stärkerer CHF
        is_exporter = (
            ticker.upper() in _EXPORT_HEAVY
            or (sector is not None and sector.lower() in _EXPORT_SECTORS)
        )
        is_domestic = ticker.upper() in _DOMESTIC_FOCUS

        chf_impact = "NEUTRAL"

        if ctx.chf_eur > _CHF_STRONG_THRESHOLD:
            # Starker CHF: schadet Exporteuren, neutral bis leicht positiv für Inlandstitel
            if is_exporter:
                score -= 15
                chf_impact = "NEGATIV"
                reasons.append(
                    f"Starker CHF ({ctx.chf_eur:.4f}/EUR) belastet Exportumsätze"
                )
            elif is_domestic:
                score += 5
                chf_impact = "POSITIV"
                reasons.append(
                    f"Starker CHF ({ctx.chf_eur:.4f}/EUR) begünstigt Inlandstitel"
                )
            else:
                reasons.append(f"CHF stark ({ctx.chf_eur:.4f}/EUR) — Sektor-neutral")
        elif ctx.chf_eur < _CHF_WEAK_THRESHOLD:
            # Schwacher CHF: begünstigt Exporteure
            if is_exporter:
                score += 10
                chf_impact = "POSITIV"
                reasons.append(
                    f"Schwacher CHF ({ctx.chf_eur:.4f}/EUR) begünstigt Exportumsätze"
                )
            else:
                reasons.append(f"CHF schwach ({ctx.chf_eur:.4f}/EUR) — Sektor-neutral")
        else:
            reasons.append(f"CHF im Gleichgewicht ({ctx.chf_eur:.4f}/EUR)")

        # --- Inflation CH ---
        if ctx.inflation_ch is not None:
            if ctx.inflation_ch <= 0.0:
                score -= 5
                reasons.append(f"Deflationsrisiko (Inflation {ctx.inflation_ch:.1f}%)")
            elif ctx.inflation_ch <= 2.0:
                score += 10
                reasons.append(f"Stabile Inflation ({ctx.inflation_ch:.1f}%) — positiv")
            elif ctx.inflation_ch <= 3.0:
                reasons.append(f"Erhöhte Inflation ({ctx.inflation_ch:.1f}%) — beobachten")
            else:
                score -= 10
                reasons.append(f"Hohe Inflation ({ctx.inflation_ch:.1f}%) — belastend")
        else:
            # Keine Inflationsdaten verfügbar → historisch stabil angenommen
            score += 10
            reasons.append("CH-Inflation historisch stabil angenommen (+10)")

        return MacroScore(
            ticker=ticker.upper(),
            score=round(max(0.0, min(100.0, score)), 2),
            leitzins=ctx.leitzins,
            chf_eur=ctx.chf_eur,
            climate=ctx.climate,
            chf_impact=chf_impact,
            reasoning=" | ".join(reasons),
        )
