"""Tests für StubFundamentalsProvider — Demo-Fundamentaldaten.

Audit-Finding F-RANK-1 (docs/usability-performance-audit-2026-06-16.md, K-1):
`_DEMO_DATA` enthielt ausschliesslich US-Tech-Ticker. Für das gesamte
SMI-20-Hauptuniversum lieferte `get_fundamentals()` daher `_EMPTY`
(alle Felder None), wodurch `quality_classic` für jeden Schweizer
Ticker `rank=None` vergab — ein Kernfeature-Ausfall auf einer
Schweizer Aktien-Plattform.
"""

import pytest

from backend.infrastructure.providers.stub_fundamentals import StubFundamentalsProvider

pytestmark = pytest.mark.unit

# SMI-20-Konstituenten, siehe scripts/seed_smi_universe.py
SMI_20_TICKERS = [
    "NESN",
    "NOVN",
    "ROG",
    "ABBN",
    "ZURN",
    "UBSG",
    "UHR",
    "GEBN",
    "GIVN",
    "LONN",
    "SREN",
    "SGKN",
    "SLHN",
    "SCMN",
    "SIKA",
    "HOLN",
    "PGHN",
    "KNIN",
    "CFR",
    "STMN",
]


class TestStubFundamentalsSmiCoverage:
    @pytest.mark.asyncio
    async def test_smi_20_tickers_have_non_empty_fundamentals(self) -> None:
        """Jeder SMI-20-Ticker muss plausible Demo-Fundamentaldaten liefern.

        Vorher: fehlten in _DEMO_DATA → _EMPTY (alle Felder None) →
        quality_classic vergab rank=None für das gesamte CH-Universum.
        """
        provider = StubFundamentalsProvider()
        result = await provider.get_fundamentals(SMI_20_TICKERS)

        for ticker in SMI_20_TICKERS:
            fundamentals = result[ticker]
            assert fundamentals["pe_ratio"] is not None, f"{ticker}: pe_ratio fehlt"
            assert fundamentals["pb_ratio"] is not None, f"{ticker}: pb_ratio fehlt"
            assert fundamentals["fcf_yield"] is not None, f"{ticker}: fcf_yield fehlt"
            assert fundamentals["operating_margin"] is not None, f"{ticker}: operating_margin fehlt"
            assert fundamentals["dividend_yield"] is not None, f"{ticker}: dividend_yield fehlt"
            assert fundamentals["debt_to_equity"] is not None, f"{ticker}: debt_to_equity fehlt"
            assert fundamentals["eps_growth_3y"] is not None, f"{ticker}: eps_growth_3y fehlt"
            assert fundamentals["sales_growth_3y"] is not None, f"{ticker}: sales_growth_3y fehlt"

    @pytest.mark.asyncio
    async def test_smi_20_pe_ratios_are_plausible(self) -> None:
        """Grobe Plausibilitätsprüfung: KGVs liegen in realistischem Bereich."""
        provider = StubFundamentalsProvider()
        result = await provider.get_fundamentals(SMI_20_TICKERS)

        for ticker in SMI_20_TICKERS:
            pe_ratio = result[ticker]["pe_ratio"]
            assert pe_ratio is not None
            assert 0 < pe_ratio < 100, f"{ticker}: unplausibles pe_ratio={pe_ratio}"

    @pytest.mark.asyncio
    async def test_unknown_ticker_still_returns_empty(self) -> None:
        """Bestehende Fallback-Semantik für unbekannte Ticker bleibt erhalten."""
        provider = StubFundamentalsProvider()
        result = await provider.get_fundamentals(["NEVERHEARDOFIT"])
        assert result["NEVERHEARDOFIT"]["pe_ratio"] is None

    @pytest.mark.asyncio
    async def test_us_tech_tickers_still_covered(self) -> None:
        """Regression: ursprüngliche US-Tech-Demodaten bleiben unverändert nutzbar."""
        provider = StubFundamentalsProvider()
        result = await provider.get_fundamentals(["AAPL", "MSFT"])
        assert result["AAPL"]["pe_ratio"] == 28.0
        assert result["MSFT"]["pe_ratio"] == 35.0
