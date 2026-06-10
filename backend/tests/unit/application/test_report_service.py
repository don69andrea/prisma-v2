"""Unit-Tests für ReportService."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from backend.application.services.report_service import ReportData, ReportService
from backend.domain.value_objects.ml_prediction import SHAPEntry

pytestmark = pytest.mark.unit


def _make_report_data() -> ReportData:
    return ReportData(
        ticker="NESN.SW",
        company_name="Nestlé S.A.",
        exchange="SIX",
        generated_at=date(2026, 6, 10),
        quant_scores={"Quality": 72.0, "Trend": 55.0, "Value": 60.0},
        quant_signals={"Quality": "BUY", "Trend": "HOLD", "Value": "HOLD"},
        weighted_avg_score=62.4,
        ml_signal="OUTPERFORM",
        ml_confidence=0.72,
        shap_top5=[
            SHAPEntry("roe_zscore", 0.31, 1.2, "Return on Equity"),
            SHAPEntry("vol_30d", -0.18, 0.14, "30-Tage Volatilität"),
        ],
        shap_expected_value=0.12,
        price_chf=89.5,
        market_cap_chf=230_000_000_000.0,
        pe_ratio=22.3,
        pb_ratio=4.1,
        dividend_yield=0.025,
        eligible_3a=True,
        narrative_summary="Nestlé zeigt starke Qualitätskennzahlen.",
    )


def test_report_data_instantiation() -> None:
    data = _make_report_data()
    assert data.ticker == "NESN.SW"
    assert data.eligible_3a is True
    assert len(data.shap_top5) == 2


@pytest.mark.asyncio
async def test_generate_pdf_returns_bytes() -> None:
    """generate_pdf() returns bytes when _render_pdf is mocked."""
    svc = ReportService()
    data = _make_report_data()

    with (
        patch.object(svc, "_aggregate_data", new_callable=AsyncMock, return_value=data),
        patch.object(svc, "_render_pdf", return_value=b"%PDF-mock"),
    ):
        pdf_bytes = await svc.generate_pdf("NESN.SW")

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes == b"%PDF-mock"


@pytest.mark.asyncio
async def test_generate_pdf_uses_cache() -> None:
    """Second call uses cache — _aggregate_data called only once."""
    svc = ReportService()
    data = _make_report_data()
    aggregate_mock = AsyncMock(return_value=data)

    with (
        patch.object(svc, "_aggregate_data", aggregate_mock),
        patch.object(svc, "_render_pdf", return_value=b"%PDF-mock"),
        patch.object(svc, "_cache_get", new_callable=AsyncMock, side_effect=[None, b"%PDF-cached"]),
        patch.object(svc, "_cache_set", new_callable=AsyncMock),
    ):
        await svc.generate_pdf("NESN.SW")  # cache miss
        result2 = await svc.generate_pdf("NESN.SW")  # cache hit

    aggregate_mock.assert_called_once()
    assert result2 == b"%PDF-cached"


def test_render_html_produces_html() -> None:
    """_render_html() produces a non-empty HTML string with key content."""
    svc = ReportService()
    data = _make_report_data()
    html = svc._render_html(data)
    assert "NESN.SW" in html
    assert "OUTPERFORM" in html
    assert "Nestlé S.A." in html
