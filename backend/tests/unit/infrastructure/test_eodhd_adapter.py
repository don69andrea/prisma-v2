"""Unit tests for EODHD Fundamentals Adapter."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_disabled_when_no_key():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    ad = EodhdFundamentalsAdapter(api_key="")
    assert not ad.enabled


def test_disabled_for_placeholder_key():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    ad = EodhdFundamentalsAdapter(api_key="your-eodhd-key")
    assert not ad.enabled


def test_enabled_with_real_key():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    ad = EodhdFundamentalsAdapter(api_key="abc123-real-key")
    assert ad.enabled


def test_to_symbol_adds_sw():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    assert EodhdFundamentalsAdapter.to_symbol("NESN") == "NESN.SW"


def test_to_symbol_keeps_existing_suffix():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    assert EodhdFundamentalsAdapter.to_symbol("NESN.SW") == "NESN.SW"


@pytest.mark.asyncio
async def test_fetch_quarterly_returns_empty_when_disabled():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    ad = EodhdFundamentalsAdapter(api_key="")
    result = await ad.fetch_quarterly("NESN")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_quarterly_returns_empty_on_http_error():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    ad = EodhdFundamentalsAdapter(api_key="real-key-abc")
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await ad.fetch_quarterly("BADTICKER")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_quarterly_parses_minimal_eodhd_response():
    """Verify adapter parses a minimal EODHD JSON structure and returns PIT-correct rows."""
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    minimal_response = {
        "General": {"Sector": "Healthcare"},
        "Highlights": {
            "MarketCapitalization": "250000000000",
            "PERatio": "25.5",
            "EnterpriseValueEbitda": "18.2",
            "DividendYield": "0.028",
            "EarningsShare": "4.5",
        },
        "Financials": {
            "Income_Statement": {
                "quarterly": {
                    "2024-03-31": {
                        "totalRevenue": "22000000000",
                        "netIncome": "3000000000",
                        "epsActual": "4.5",
                        "filing_date": "2024-05-15",
                    },
                }
            },
            "Balance_Sheet": {
                "quarterly": {
                    "2024-03-31": {
                        "totalStockholderEquity": "40000000000",
                        "shortLongTermDebtTotal": "10000000000",
                    },
                }
            },
            "Cash_Flow": {
                "quarterly": {
                    "2024-03-31": {
                        "freeCashFlow": "5000000000",
                    },
                }
            },
        },
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = minimal_response

    ad = EodhdFundamentalsAdapter(api_key="real-key-abc")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        rows = await ad.fetch_quarterly("NESN")

    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "NESN"
    assert r["period_end"] == datetime.date(2024, 3, 31)
    assert r["publish_date"] == datetime.date(2024, 5, 15)  # PIT filing_date
    assert r["period_type"] == "quarterly"
    assert r["source"] == "eodhd"
    assert r["sector"] == "Healthcare"
    assert r["roe"] is not None
    assert r["eps_chf"] == 4.5
