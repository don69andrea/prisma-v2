"""SIX Exchange Filings Adapter — PDF-Link-Discovery pro Ticker.

Strategie:
1. Versuche, die SIX-Seite eines Tickers zu scrapen (HTTP GET + Link-Extraktion)
2. Fallback auf statische Liste bekannter Jahresbericht-PDFs der SMI-Titel

Fehler-Toleranz: Netzwerk-Fehler bei Scraping → still → nur Static Fallback.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date

import httpx

_logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_RETRY_DELAYS = [1.0, 2.0, 4.0]  # Exponential backoff (Sekunden)

# Statischer Fallback: ausgewählte SMI/SMIM Jahresberichte (öffentlich zugänglich)
# Format: (ticker, url, filing_date, doc_type, language)
_STATIC_FILINGS: list[tuple[str, str, date, str, str]] = [
    # Nestlé — Annual Review 2025 (verifiziert 2026-06-11)
    (
        "NESN",
        "https://www.nestle.com/sites/default/files/2026-02/annual-review-2025-en.pdf",
        date(2026, 2, 13),
        "Annual Review",
        "en",
    ),
    # Nestlé — Finanzberichte + Corporate Governance 2025 (verifiziert 2026-06-11)
    (
        "NESN",
        "https://www.nestle.com/sites/default/files/2026-02/corp-governance-compensation-financial-statements-2025-en.pdf",
        date(2026, 2, 13),
        "Financial Statements",
        "en",
    ),
    # Zurich Insurance — Annual Report 2024 (verifiziert 2026-06-11)
    (
        "ZURN",
        "https://www.zurich.com/-/media/project/zwp/zurich/docs/en/investor-relations/annual-reports/2024/zurich-annual-report-2024.pdf",
        date(2025, 3, 1),
        "Annual Report",
        "en",
    ),
]


@dataclass(frozen=True)
class FilingLink:
    ticker: str
    url: str
    filing_date: date
    doc_type: str
    language: str
    source: str  # "SIX" | "IR"


class SixFilingsAdapter:
    """Ermittelt PDF-Links für Swiss Filings (SIX-Scraping + Static Fallback)."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    async def get_filing_links(self, ticker: str) -> list[FilingLink]:
        """Gibt bekannte PDF-Links für den Ticker zurück.

        Versucht zuerst SIX-Scraping, fällt bei Fehler auf Static-Liste zurück.
        """
        static = [
            FilingLink(
                ticker=f[0],
                url=f[1],
                filing_date=f[2],
                doc_type=f[3],
                language=f[4],
                source="IR",
            )
            for f in _STATIC_FILINGS
            if f[0].upper() == ticker.upper()
        ]
        scraped = await self._scrape_six(ticker)
        # Scraped links haben Priorität, Static als Ergänzung
        seen_urls = {lnk.url for lnk in scraped}
        combined = scraped + [lnk for lnk in static if lnk.url not in seen_urls]
        return combined

    async def _scrape_six(self, ticker: str) -> list[FilingLink]:
        """Versucht, PDF-Links von der SIX-Unternehmensseite zu scrapen."""
        if self._client is None:
            return []
        url = f"https://www.six-group.com/en/market-data/shares/{ticker.lower()}.html"
        try:
            resp = await self._client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            return _extract_pdf_links(resp.text, ticker)
        except Exception as exc:
            _logger.debug("SIX scraping fehlgeschlagen für %s: %s", ticker, exc)
            return []


def _extract_pdf_links(html: str, ticker: str) -> list[FilingLink]:
    """Extrahiert PDF-hrefs aus HTML (einfache Regex-Methode)."""
    pdf_pattern = re.compile(r'href=["\']([^"\']*\.pdf)["\']', re.IGNORECASE)
    annual_keywords = re.compile(r"(annual.report|jahresbericht|rapport.annuel)", re.IGNORECASE)
    semi_keywords = re.compile(
        r"(half.year|halbjahr|semi.annual|rapport.semestriel)", re.IGNORECASE
    )

    results: list[FilingLink] = []
    for match in pdf_pattern.finditer(html):
        pdf_url = match.group(1)
        if not pdf_url.startswith("http"):
            pdf_url = "https://www.six-group.com" + pdf_url

        ctx = html[max(0, match.start() - 100) : match.end() + 100]
        if annual_keywords.search(ctx):
            doc_type = "Jahresbericht"
        elif semi_keywords.search(ctx):
            doc_type = "Halbjahresbericht"
        else:
            continue  # Kein erkannter Berichtstyp

        lang = "de" if re.search(r"\bde\b", pdf_url) else "en"
        results.append(
            FilingLink(
                ticker=ticker.upper(),
                url=pdf_url,
                filing_date=date.today(),  # unbekannt → heute als Platzhalter
                doc_type=doc_type,
                language=lang,
                source="SIX",
            )
        )
    return results
