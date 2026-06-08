"""TickerNer — Dictionary-basierte Ticker-Erkennung in Freitext.

Erkennt Swiss-Stock-Ticker (z.B. NESN, NOVN) via Wort-Grenzen-Regex.
Keine ML-Inferenz — deterministisch und CI-freundlich.
"""

from __future__ import annotations

import re


class TickerNer:
    """Extrahiert bekannte Ticker-Symbole aus einem Text.

    Wort-Grenzen verhindern, dass «ABB» in «ABBN» oder «ABBC» matched.
    """

    def __init__(self, known_tickers: frozenset[str]) -> None:
        self._tickers = known_tickers
        # Ein gemeinsames Pattern für alle Ticker — effizienter als N Patterns.
        if known_tickers:
            joined = "|".join(re.escape(t) for t in sorted(known_tickers, key=len, reverse=True))
            self._pattern: re.Pattern[str] | None = re.compile(
                rf"\b({joined})\b",
                re.IGNORECASE,
            )
        else:
            self._pattern = None

    def extract(self, text: str) -> tuple[str, ...]:
        if self._pattern is None:
            return ()
        matches = self._pattern.findall(text)
        # Deduplizieren + Uppercase, Reihenfolge der ersten Erwähnung beibehalten
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            upper = m.upper()
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
        return tuple(result)


# Standard-Set der SMI-20 + SMIM-30-Ticker — kann zur Laufzeit durch
# DB-geladene Ticker ergänzt werden.
SWISS_TICKERS: frozenset[str] = frozenset(
    {
        # SMI-20
        "ABBN",
        "ADEN",
        "ALLN",
        "CSGN",
        "GIVN",
        "HOLN",
        "KNIN",
        "LONN",
        "NESN",
        "NOVN",
        "PGHN",
        "ROG",
        "SCMN",
        "SGSN",
        "SIKA",
        "SLHN",
        "SRENH",
        "UBSG",
        "UHRN",
        "ZURN",
        # SMIM-30
        "AMSN",
        "BAER",
        "BARN",
        "BCHN",
        "BKWN",
        "BSLN",
        "CLTN",
        "COTN",
        "EMSN",
        "EMMN",
        "FHZN",
        "FORN",
        "GEBN",
        "HELN",
        "HOCN",
        "INRN",
        "IREN",
        "JFIN",
        "LISP",
        "MBTN",
        "MOBN",
        "PATN",
        "PSPN",
        "SGKN",
        "SRAIL",
        "TEMN",
        "VACN",
        "VATN",
        "WKBN",
        "ZEHN",
    }
)
