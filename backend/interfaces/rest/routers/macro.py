"""REST Router: Macro Intelligence API — GET /api/v1/macro/context + /score/{ticker}."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.application.agents.macro_agent import MacroIntelligenceAgent
from backend.application.services.macro_service import MacroService
from backend.application.services.retrieval_service import RetrievalService
from backend.interfaces.rest.dependencies import get_llm_client, get_retrieval_service
from backend.interfaces.rest.schemas.macro import MacroContextResponse, MacroScoreResponse

router = APIRouter(prefix="/api/v1/macro", tags=["macro"])
_logger = logging.getLogger(__name__)


def get_macro_service(
    llm_client: object = Depends(get_llm_client),
) -> MacroService:
    return MacroService(llm_client=llm_client)


@router.get(
    "/context",
    response_model=MacroContextResponse,
    summary="Aktueller Makro-Kontext Schweiz",
    description=(
        "Liefert SNB-Leitzins, CHF/EUR-Kurs und das Makro-Klima "
        "(EXPANSIV / NEUTRAL / RESTRIKTIV) inkl. kurzer LLM-Narrative (DE + EN). "
        "SNB-Daten via data.snb.ch mit Fallback auf hardcodierte Historie."
    ),
)
async def get_macro_context(
    service: MacroService = Depends(get_macro_service),
) -> MacroContextResponse:
    try:
        ctx = await service.get_context()
    except Exception as exc:
        _logger.exception("Fehler beim Abrufen des Makro-Kontexts")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Makro-Daten vorübergehend nicht verfügbar.",
        ) from exc

    return MacroContextResponse(
        leitzins=ctx.leitzins,
        chf_eur=ctx.chf_eur,
        inflation_ch=ctx.inflation_ch,
        pmi_ch=ctx.pmi_ch,
        snapshot_date=ctx.snapshot_date,
        climate=ctx.climate,
        narrative_de=ctx.narrative_de,
        narrative_en=ctx.narrative_en,
    )


@router.get(
    "/score/{ticker}",
    response_model=MacroScoreResponse,
    summary="Ticker-spezifischer Makro-Score",
    description=(
        "Berechnet einen Makro-Score (0–100) für den angegebenen SIX-Ticker "
        "basierend auf SNB-Leitzins, CHF/EUR-Kurs und Exportprofil. "
        "Optional wird RAG-Kontext (Makro-News zum Ticker) angehängt. "
        "Bei RAG-Fehler: graceful Fallback, rag_context_used=False."
    ),
)
async def get_macro_score(
    ticker: str,
    service: MacroService = Depends(get_macro_service),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> MacroScoreResponse:
    """Berechnet den Makro-Score für einen Ticker (rule-based, immer 200)."""
    agent = MacroIntelligenceAgent(macro_service=service)
    try:
        macro_score = await agent.get_macro_score(ticker=ticker)
    except Exception as exc:
        _logger.exception("Fehler beim Berechnen des Makro-Scores für %s", ticker)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Makro-Score vorübergehend nicht verfügbar.",
        ) from exc

    # RAG-Integration: Makro-News zum Ticker abrufen
    rag_context_used = False
    if retrieval is not None:
        try:
            rag_results = await retrieval.retrieve(
                query=f"Makro-Umfeld {ticker} Schweizer Aktien SNB CHF",
                k=3,
                ticker=ticker,
            )
            if rag_results:
                rag_context_used = True
                _logger.debug(
                    "RAG-Kontext für %s: %d Dokumente abgerufen", ticker, len(rag_results)
                )
        except Exception as exc:
            _logger.warning("RAG-Kontext für %s nicht verfügbar — Fallback", ticker, exc_info=True)
            rag_context_used = False

    return MacroScoreResponse(
        ticker=macro_score.ticker,
        score=macro_score.score,
        leitzins=macro_score.leitzins,
        chf_eur=macro_score.chf_eur,
        climate=macro_score.climate,
        rag_context_used=rag_context_used,
    )
