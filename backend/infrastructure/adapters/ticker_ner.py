"""TickerNer — Dictionary-basierte Ticker-Erkennung in Freitext.

Erkennt Swiss-Stock-Ticker (z.B. NESN, NOVN) via Wort-Grenzen-Regex.
Zusätzlich werden bekannte Firmennamen (z.B. "Nestlé") auf ihren Ticker
gemappt, da News-Artikel (NZZ/SRF) i.d.R. den Firmennamen statt des
Ticker-Symbols verwenden.

Keine ML-Inferenz — deterministisch und CI-freundlich.
"""

from __future__ import annotations

import re

# Firmenname (lowercase, ohne Rechtsform) -> Ticker. Nur Namen, deren
# Ziel-Ticker in SWISS_TICKERS enthalten ist, wirken sich in extract() aus.
COMPANY_NAME_TO_TICKER: dict[str, str] = {
    # SMI-20
    "abb": "ABBN",
    "adecco": "ADEN",
    "alcon": "ALLN",
    "givaudan": "GIVN",
    "holcim": "HOLN",
    "kuehne+nagel": "KNIN",
    "kühne+nagel": "KNIN",
    "kuehne nagel": "KNIN",
    "kühne nagel": "KNIN",
    "lonza": "LONN",
    "nestle": "NESN",
    "nestlé": "NESN",
    "partners group": "PGHN",
    "roche": "ROG",
    "swisscom": "SCMN",
    "sgs": "SGSN",
    "sika": "SIKA",
    "swiss life": "SLHN",
    "swiss re": "SRENH",
    "ubs": "UBSG",
    "swatch": "UHRN",
    "zurich insurance": "ZURN",
    "novartis": "NOVN",
    # SMIM-30
    "amrize": "AMSN",
    "julius baer": "BAER",
    "baloise": "BARN",
    "bachem": "BCHN",
    "bkw": "BKWN",
    "basler kantonalbank": "BSLN",
    "clariant": "CLTN",
    "cosmo pharmaceuticals": "COTN",
    "ems-chemie": "EMSN",
    "emmi": "EMMN",
    "flughafen zuerich": "FHZN",
    "flughafen zürich": "FHZN",
    "fenaco": "FORN",
    "geberit": "GEBN",
    "helvetia": "HELN",
    "hochdorf": "HOCN",
    "implenia": "INRN",
    "interroll": "IREN",
    "jungfraubahn": "JFIN",
    "lindt": "LISP",
    "lindt & spruengli": "LISP",
    "lindt & sprüngli": "LISP",
    "mobimo": "MBTN",
    "mobiliar": "MOBN",
    "phoenix mecano": "PATN",
    "psp swiss property": "PSPN",
    "st. galler kantonalbank": "SGKN",
    "stadler rail": "SRAIL",
    "temenos": "TEMN",
    "vat group": "VACN",
    "valora": "VATN",
    "waadtlaender kantonalbank": "WKBN",
    "vaudoise": "WKBN",
    "zehnder": "ZEHN",
}


class TickerNer:
    """Extrahiert bekannte Ticker-Symbole aus einem Text.

    Wort-Grenzen verhindern, dass «ABB» in «ABBN» oder «ABBC» matched.
    Erkennt sowohl Ticker-Symbole direkt (NESN) als auch bekannte
    Firmennamen (Nestlé) und löst sie auf den jeweiligen Ticker auf.
    """

    def __init__(
        self,
        known_tickers: frozenset[str],
        company_aliases: dict[str, str] | None = None,
    ) -> None:
        self._tickers = known_tickers
        aliases = company_aliases if company_aliases is not None else COMPANY_NAME_TO_TICKER
        # Nur Aliase behalten, deren Ziel-Ticker auch bekannt ist.
        self._aliases = {
            name: ticker for name, ticker in aliases.items() if ticker in known_tickers
        }

        alternatives = [re.escape(t) for t in known_tickers] + [
            re.escape(name) for name in self._aliases
        ]
        if alternatives:
            # Längere Alternativen zuerst, damit z.B. "kuehne+nagel" vor
            # kürzeren Teil-Treffern matched.
            alternatives.sort(key=len, reverse=True)
            joined = "|".join(alternatives)
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
            lower = m.lower()
            ticker = self._aliases.get(lower, m.upper())
            if ticker not in seen:
                seen.add(ticker)
                result.append(ticker)
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
