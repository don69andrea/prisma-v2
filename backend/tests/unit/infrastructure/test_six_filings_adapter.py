"""Unit-Tests für SixFilingsAdapter."""

from __future__ import annotations

from datetime import date

import pytest

from backend.infrastructure.adapters.six_filings_adapter import (
    FilingLink,
    SixFilingsAdapter,
    _extract_pdf_links,
)

pytestmark = pytest.mark.unit


class TestStaticFallback:
    async def test_known_ticker_has_static_links(self) -> None:
        adapter = SixFilingsAdapter(http_client=None)
        links = await adapter.get_filing_links("NESN")
        assert len(links) >= 1
        assert all(isinstance(lnk, FilingLink) for lnk in links)

    async def test_links_have_required_fields(self) -> None:
        adapter = SixFilingsAdapter(http_client=None)
        links = await adapter.get_filing_links("NESN")
        for lnk in links:
            assert lnk.ticker == "NESN"
            assert lnk.url.startswith("https://")
            assert isinstance(lnk.filing_date, date)
            assert lnk.language in ("de", "en", "fr")
            assert lnk.source in ("SIX", "IR")

    async def test_unknown_ticker_returns_empty(self) -> None:
        adapter = SixFilingsAdapter(http_client=None)
        links = await adapter.get_filing_links("XXXX_UNKNOWN")
        assert links == []

    async def test_ticker_case_insensitive(self) -> None:
        adapter = SixFilingsAdapter(http_client=None)
        links_upper = await adapter.get_filing_links("NOVN")
        links_lower = await adapter.get_filing_links("novn")
        assert len(links_upper) == len(links_lower)

    async def test_nesn_has_static_link(self) -> None:
        adapter = SixFilingsAdapter(http_client=None)
        links = await adapter.get_filing_links("NESN")
        assert any("nestle" in lnk.url.lower() for lnk in links)


class TestExtractPdfLinks:
    def test_extracts_annual_report_link(self) -> None:
        html = '<a href="/docs/annual-report-2023.pdf">Annual Report 2023</a>'
        links = _extract_pdf_links(html, "TEST")
        assert len(links) == 1
        assert links[0].doc_type == "Jahresbericht"

    def test_extracts_halbjahr_link(self) -> None:
        html = '<a href="/docs/half-year-2023.pdf">Half-year Report</a>'
        links = _extract_pdf_links(html, "TEST")
        assert len(links) == 1
        assert links[0].doc_type == "Halbjahresbericht"

    def test_ignores_non_report_pdfs(self) -> None:
        html = '<a href="/brochure.pdf">Product brochure</a>'
        links = _extract_pdf_links(html, "TEST")
        assert links == []

    def test_extracts_multiple_links(self) -> None:
        html = (
            '<a href="/annual-report-2023.pdf">Annual 2023</a>'
            '<a href="/annual-report-2022.pdf">Annual 2022</a>'
        )
        links = _extract_pdf_links(html, "TEST")
        assert len(links) == 2
