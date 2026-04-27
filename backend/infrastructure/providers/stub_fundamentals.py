"""Stub-Implementierung des FundamentalsProvider für Demo und Tests.

Liefert hardcodierte Fundamentaldaten für bekannte Demo-Ticker.
Unbekannte Ticker erhalten leere Daten (alle None).
"""

from backend.domain.models.quality_classic import Fundamentals, UniverseData
from backend.domain.ports.fundamentals_provider import FundamentalsProvider

_DEMO_DATA: dict[str, Fundamentals] = {
    "AAPL": {
        "pe_ratio": 28.0,
        "pb_ratio": 45.0,
        "fcf_yield": 0.038,
        "operating_margin": 0.302,
        "dividend_yield": 0.005,
        "debt_to_equity": 1.76,
        "eps_growth_3y": 0.09,
        "sales_growth_3y": 0.08,
    },
    "MSFT": {
        "pe_ratio": 35.0,
        "pb_ratio": 12.0,
        "fcf_yield": 0.025,
        "operating_margin": 0.425,
        "dividend_yield": 0.007,
        "debt_to_equity": 0.35,
        "eps_growth_3y": 0.15,
        "sales_growth_3y": 0.16,
    },
    "GOOGL": {
        "pe_ratio": 22.0,
        "pb_ratio": 5.5,
        "fcf_yield": 0.042,
        "operating_margin": 0.27,
        "dividend_yield": 0.0,
        "debt_to_equity": 0.06,
        "eps_growth_3y": 0.18,
        "sales_growth_3y": 0.12,
    },
    "NVDA": {
        "pe_ratio": 55.0,
        "pb_ratio": 30.0,
        "fcf_yield": 0.015,
        "operating_margin": 0.55,
        "dividend_yield": 0.001,
        "debt_to_equity": 0.42,
        "eps_growth_3y": 1.20,
        "sales_growth_3y": 0.85,
    },
    "JPM": {
        "pe_ratio": 12.0,
        "pb_ratio": 1.8,
        "fcf_yield": 0.06,
        "operating_margin": 0.35,
        "dividend_yield": 0.025,
        "debt_to_equity": 1.20,
        "eps_growth_3y": 0.08,
        "sales_growth_3y": 0.07,
    },
}

_EMPTY: Fundamentals = {
    "pe_ratio": None,
    "pb_ratio": None,
    "fcf_yield": None,
    "operating_margin": None,
    "dividend_yield": None,
    "debt_to_equity": None,
    "eps_growth_3y": None,
    "sales_growth_3y": None,
}


class StubFundamentalsProvider(FundamentalsProvider):
    async def get_fundamentals(self, tickers: list[str]) -> UniverseData:
        return {t: _DEMO_DATA.get(t, dict(_EMPTY)) for t in tickers}
