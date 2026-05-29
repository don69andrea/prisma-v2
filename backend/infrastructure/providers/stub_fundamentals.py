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
    "AMZN": {
        "pe_ratio": 42.0,
        "pb_ratio": 8.5,
        "fcf_yield": 0.035,
        "operating_margin": 0.085,
        "dividend_yield": 0.0,
        "debt_to_equity": 0.65,
        "eps_growth_3y": 0.55,
        "sales_growth_3y": 0.18,
    },
    "TSLA": {
        "pe_ratio": 65.0,
        "pb_ratio": 10.0,
        "fcf_yield": 0.012,
        "operating_margin": 0.085,
        "dividend_yield": 0.0,
        "debt_to_equity": 0.10,
        "eps_growth_3y": 0.45,
        "sales_growth_3y": 0.32,
    },
    "META": {
        "pe_ratio": 24.0,
        "pb_ratio": 7.5,
        "fcf_yield": 0.060,
        "operating_margin": 0.34,
        "dividend_yield": 0.005,
        "debt_to_equity": 0.27,
        "eps_growth_3y": 0.45,
        "sales_growth_3y": 0.12,
    },
    "NFLX": {
        "pe_ratio": 42.0,
        "pb_ratio": 9.8,
        "fcf_yield": 0.040,
        "operating_margin": 0.22,
        "dividend_yield": 0.0,
        "debt_to_equity": 0.78,
        "eps_growth_3y": 0.32,
        "sales_growth_3y": 0.10,
    },
    "AMD": {
        "pe_ratio": 48.0,
        "pb_ratio": 4.2,
        "fcf_yield": 0.025,
        "operating_margin": 0.18,
        "dividend_yield": 0.0,
        "debt_to_equity": 0.10,
        "eps_growth_3y": 0.85,
        "sales_growth_3y": 0.55,
    },
    "INTC": {
        "pe_ratio": 18.0,
        "pb_ratio": 1.3,
        "fcf_yield": -0.02,
        "operating_margin": 0.06,
        "dividend_yield": 0.012,
        "debt_to_equity": 0.45,
        "eps_growth_3y": -0.25,
        "sales_growth_3y": -0.08,
    },
    "ORCL": {
        "pe_ratio": 28.0,
        "pb_ratio": 38.0,
        "fcf_yield": 0.050,
        "operating_margin": 0.30,
        "dividend_yield": 0.013,
        "debt_to_equity": 4.5,
        "eps_growth_3y": 0.07,
        "sales_growth_3y": 0.06,
    },
    "CRM": {
        "pe_ratio": 48.0,
        "pb_ratio": 4.5,
        "fcf_yield": 0.045,
        "operating_margin": 0.21,
        "dividend_yield": 0.001,
        "debt_to_equity": 0.16,
        "eps_growth_3y": 0.95,
        "sales_growth_3y": 0.18,
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
