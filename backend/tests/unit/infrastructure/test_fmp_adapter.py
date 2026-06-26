"""Unit tests for FMP Fundamentals Adapter."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_disabled_when_no_key():
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    assert not FmpFundamentalsAdapter(api_key="").enabled


def test_disabled_for_placeholder_key():
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    assert not FmpFundamentalsAdapter(api_key="your-fmp-key").enabled


def test_enabled_with_real_key():
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    assert FmpFundamentalsAdapter(api_key="abc123").enabled


def test_to_symbol_adds_sw():
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    assert FmpFundamentalsAdapter.to_symbol("NESN") == "NESN.SW"


def test_to_symbol_keeps_suffix():
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    assert FmpFundamentalsAdapter.to_symbol("NESN.SW") == "NESN.SW"


@pytest.mark.asyncio
async def test_returns_empty_when_disabled():
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    result = await FmpFundamentalsAdapter(api_key="").fetch_quarterly("NESN")
    assert result == []


@pytest.mark.asyncio
async def test_returns_empty_on_http_error():
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    ad = FmpFundamentalsAdapter(api_key="real-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("httpx.AsyncClient") as cls:
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = AsyncMock(return_value=mock_resp)
        cls.return_value = ctx
        result = await ad.fetch_quarterly("NESN")

    assert result == []


@pytest.mark.asyncio
async def test_parses_fmp_key_metrics_response():
    """Verify PIT-correct row is produced from FMP key-metrics structure."""
    from backend.infrastructure.adapters.fmp_fundamentals_adapter import FmpFundamentalsAdapter

    fmp_response = [
        {
            "date": "2024-03-31",
            "fillingDate": "2024-05-10",
            "pe": 22.5,
            "pb": 3.1,
            "evToEbitda": 15.0,
            "roe": 0.12,
            "debtToEquity": 0.45,
            "freeCashFlowMargin": 0.08,
            "eps": 4.2,
            "dividendYield": 0.025,
            "marketCap": 250000000000.0,
        },
        {
            "date": "2023-12-31",
            "fillingDate": "2024-02-15",
            "pe": 20.0,
            "pb": 2.9,
            "evToEbitda": 14.5,
            "roe": 0.11,
            "debtToEquity": 0.42,
            "freeCashFlowMargin": 0.07,
            "eps": 3.9,
            "dividendYield": 0.024,
            "marketCap": 240000000000.0,
        },
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fmp_response

    ad = FmpFundamentalsAdapter(api_key="real-key")
    with patch("httpx.AsyncClient") as cls:
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = AsyncMock(return_value=mock_resp)
        cls.return_value = ctx
        rows = await ad.fetch_quarterly("NESN")

    assert len(rows) == 2
    r = rows[0]
    assert r["ticker"] == "NESN"
    assert r["period_end"] == datetime.date(2024, 3, 31)
    assert r["publish_date"] == datetime.date(2024, 5, 10)
    assert r["period_type"] == "quarterly"
    assert r["source"] == "fmp"
    assert r["pe_ratio"] == 22.5
    assert r["roe"] == pytest.approx(12.0, abs=0.01)  # 0.12 * 100
    assert r["fcf_margin"] == pytest.approx(8.0, abs=0.01)  # 0.08 * 100
    assert r["eps_chf"] == 4.2
