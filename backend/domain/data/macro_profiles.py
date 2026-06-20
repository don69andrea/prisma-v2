"""Makro-Profile für SMI/SMIM-Titel — geteilte Konstanten für alle Makro-Agenten.

FIX-03: _EXPORT_HEAVY und _DOMESTIC_FOCUS waren in macro_agent.py und
macro_agent_v2.py dupliziert. Beide Agenten importieren jetzt von hier.
"""

from __future__ import annotations

# Exportlastige Titel (Auslandumsatz >80%) — starker CHF belastet diese
EXPORT_HEAVY: frozenset[str] = frozenset(
    {
        "NESN.SW",  # Nestlé — >98% Auslandumsatz
        "ROG.SW",  # Roche — Pharma, global
        "NOVN.SW",  # Novartis — Pharma, global
        "LONN.SW",  # Lonza — Pharma/Biotech, global
        "LOGN.SW",  # Logitech — Tech, global
        "BARN.SW",  # Barry Callebaut — Schokolade, global
        "GIVN.SW",  # Givaudan — Aromen/Duftstoffe, global
        "ABBN.SW",  # ABB — Industrieausrüstung, global
        "KNIN.SW",  # Kuehne+Nagel — Logistik, global
        "SCHP.SW",  # Schindler — Aufzüge, global
        "LISN.SW",  # Lindt & Sprüngli — Schokolade, global
        "GEBN.SW",  # Geberit — Sanitärtechnik, europäisch
        "CFR.SW",  # Richemont — Uhren/Luxus, global
        "SREN.SW",  # Swiss Re — Rückversicherung, global
        "STMN.SW",  # Straumann — Dental, global
        "VACN.SW",  # VAT Group — Halbleiter-Vakuumventile, global
    }
)

# Inlandsfokussierte Titel (CHF-Stärke weniger relevant)
DOMESTIC_FOCUS: frozenset[str] = frozenset(
    {
        "UBSG.SW",  # UBS — Bankwesen, Schweizer Heimbasis
        "SLHN.SW",  # Swiss Life — CH Versicherung
        "BAER.SW",  # Julius Bär — Wealth Management, CHF-Erlöse
        "PGHN.SW",  # Partners Group — CH domiziliert
    }
)

# Sektoren die per se exportlastig sind (Sektor-Hint aus InvestorProfile)
EXPORT_SECTORS: frozenset[str] = frozenset(
    {"pharma", "tech", "luxury", "industrial", "chemical"}
)

# chf_eur = 1 CHF in EUR. Höher = stärkerer CHF.
CHF_STRONG_THRESHOLD = 0.95  # CHF stark → schadet Exporteuren
CHF_WEAK_THRESHOLD = 0.91  # CHF schwach → begünstigt Exporteure
