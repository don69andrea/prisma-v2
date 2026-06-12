"""Application Service: PDF Report Generator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

_logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "infrastructure" / "templates"
_CACHE_TTL = 6 * 3600


@dataclass(frozen=True)
class ReportData:
    ticker: str
    company_name: str
    exchange: str
    generated_at: date
    quant_scores: dict[str, float]
    quant_signals: dict[str, str]
    weighted_avg_score: float
    ml_signal: str
    ml_confidence: float
    shap_top5: list[Any]
    shap_expected_value: float
    price_chf: float | None
    market_cap_chf: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    dividend_yield: float | None
    eligible_3a: bool
    narrative_summary: str


class ReportService:
    """Generiert institutionelle PDF-Reports für einen Ticker."""

    async def generate_pdf(self, ticker: str) -> bytes:
        cached = await self._cache_get(ticker)
        if cached:
            return cached

        data = await self._aggregate_data(ticker)
        html = self._render_html(data)
        pdf_bytes = await asyncio.to_thread(self._render_pdf, html)

        await self._cache_set(ticker, pdf_bytes)
        return pdf_bytes

    async def _aggregate_data(self, ticker: str) -> ReportData:
        from backend.application.services.factsheet_service import FactsheetService
        from backend.application.services.ml_prediction_service import MLPredictionService
        from backend.infrastructure.persistence.repositories.ranking_run_repository import (
            SQLARankingRunRepository,
        )
        from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
            SQLASwissStockRepository,
        )
        from backend.infrastructure.persistence.session import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as _session:
            swiss_repo = SQLASwissStockRepository(session=_session)
            run_repo = SQLARankingRunRepository(session=_session)
            factsheet_svc = FactsheetService(stock_repo=swiss_repo, run_repo=run_repo)
        ml_svc = MLPredictionService()

        factsheet, ml_prediction = await asyncio.gather(
            factsheet_svc.get_factsheet(ticker),
            ml_svc.predict(ticker),
            return_exceptions=True,
        )

        if isinstance(factsheet, Exception) or factsheet is None:
            _logger.warning("Kein Factsheet für %s: %s", ticker, factsheet)
            factsheet = None

        if isinstance(ml_prediction, Exception) or ml_prediction is None:
            _logger.warning("Keine ML-Prediction für %s: %s", ticker, ml_prediction)
            ml_prediction = None

        quant_scores: dict[str, float] = {}
        quant_signals: dict[str, str] = {}
        if factsheet and hasattr(factsheet, "model_scores"):
            for ms in factsheet.model_scores or []:
                quant_scores[ms.model_name] = ms.score
                quant_signals[ms.model_name] = ms.signal

        return ReportData(
            ticker=ticker.upper(),
            company_name=getattr(factsheet, "company_name", ticker) or ticker,
            exchange=getattr(factsheet, "exchange", "—") or "—",
            generated_at=date.today(),
            quant_scores=quant_scores,
            quant_signals=quant_signals,
            weighted_avg_score=getattr(factsheet, "weighted_avg_score", 0.0) or 0.0,
            ml_signal=getattr(ml_prediction, "signal", "NEUTRAL") if ml_prediction else "NEUTRAL",
            ml_confidence=getattr(ml_prediction, "confidence", 0.0) if ml_prediction else 0.0,
            shap_top5=getattr(ml_prediction, "shap_values", [])[:5] if ml_prediction else [],
            shap_expected_value=getattr(ml_prediction, "shap_expected_value", 0.0)
            if ml_prediction
            else 0.0,
            price_chf=getattr(factsheet, "price_chf", None),
            market_cap_chf=getattr(factsheet, "market_cap_chf", None),
            pe_ratio=getattr(factsheet, "pe_ratio", None),
            pb_ratio=getattr(factsheet, "pb_ratio", None),
            dividend_yield=getattr(factsheet, "dividend_yield", None),
            eligible_3a=getattr(factsheet, "eligible_3a", False) or False,
            narrative_summary=_extract_narrative_summary(factsheet),
        )

    def _render_html(self, data: ReportData) -> str:
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
        template = env.get_template("report.html.j2")
        return template.render(
            ticker=data.ticker,
            company_name=data.company_name,
            exchange=data.exchange,
            generated_at=data.generated_at.strftime("%d.%m.%Y"),
            quant_scores=data.quant_scores,
            quant_signals=data.quant_signals,
            weighted_avg_score=data.weighted_avg_score,
            ml_signal=data.ml_signal,
            ml_confidence=data.ml_confidence,
            shap_top5=data.shap_top5,
            shap_expected_value=data.shap_expected_value,
            price_chf=data.price_chf,
            market_cap_chf=data.market_cap_chf,
            pe_ratio=data.pe_ratio,
            pb_ratio=data.pb_ratio,
            dividend_yield=data.dividend_yield,
            eligible_3a=data.eligible_3a,
            narrative_summary=data.narrative_summary,
        )

    def _render_pdf(self, html: str) -> bytes:
        import weasyprint

        return cast(bytes, weasyprint.HTML(string=html).write_pdf())

    async def _cache_get(self, ticker: str) -> bytes | None:
        try:
            import redis.asyncio as aioredis

            from backend.config import get_settings

            settings = get_settings()
            redis_url = getattr(settings, "redis_url", None)
            if not redis_url:
                return None
            client = aioredis.from_url(redis_url)
            raw = await client.get(f"report:{ticker.upper()}")
            await client.aclose()
            return bytes(raw) if raw else None
        except Exception:
            return None

    async def _cache_set(self, ticker: str, data: bytes) -> None:
        try:
            import redis.asyncio as aioredis

            from backend.config import get_settings

            settings = get_settings()
            redis_url = getattr(settings, "redis_url", None)
            if not redis_url:
                return
            client = aioredis.from_url(redis_url)
            await client.setex(f"report:{ticker.upper()}", _CACHE_TTL, data)
            await client.aclose()
        except Exception:
            pass


def _extract_narrative_summary(factsheet: object | None) -> str:
    if factsheet is None:
        return ""
    memo = getattr(factsheet, "research_memo", None)
    if not memo:
        return ""
    summary = getattr(memo, "summary", None) or getattr(memo, "content", None) or ""
    return str(summary)[:400]
