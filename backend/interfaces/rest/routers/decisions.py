"""REST Router: Decision Intelligence API — GET /api/v1/decisions."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.application.agents.macro_agent import MacroIntelligenceAgent
from backend.application.services.macro_service import MacroService
from backend.application.services.signal_aggregation_service import SignalAggregationService
from backend.application.services.universe_service import UniverseNotFound, UniverseService
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.interfaces.rest.dependencies import (
    get_llm_client,
    get_swiss_stock_repository,
    get_universe_service,
)
from backend.interfaces.rest.schemas.decision import (
    DecisionListResponse,
    DecisionSignalResponse,
    ExplainRequest,
    ExplainResponse,
)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])
_logger = logging.getLogger(__name__)


def _signal_reason(signal: str, weighted_score: float, quant_score: float) -> str:
    """Erzeugt eine kurze Alltagssprache-Erklärung des aggregierten Signals."""
    score_label = "stark" if quant_score >= 70 else ("moderat" if quant_score >= 45 else "schwach")
    if signal == "BUY":
        return (
            f"Starkes Kaufsignal: Quant-Analyse {score_label}, "
            f"PRISMA-Score {weighted_score:.0f}/100."
        )
    if signal == "HOLD":
        return (
            f"Neutral halten: Quant-Analyse {score_label}, "
            f"PRISMA-Score {weighted_score:.0f}/100. Beobachten."
        )
    return (
        f"Verkaufssignal: Quant-Analyse {score_label}, "
        f"PRISMA-Score {weighted_score:.0f}/100. Schwache Fundamentaldaten."
    )


_MAX_LIVE_TICKERS = 12


def get_signal_aggregation_service(
    swiss_stock_repo: SwissStockRepository = Depends(get_swiss_stock_repository),
    llm_client: object = Depends(get_llm_client),
) -> SignalAggregationService:
    macro_agent = MacroIntelligenceAgent(macro_service=MacroService(llm_client=llm_client))
    return SignalAggregationService(swiss_stock_repo=swiss_stock_repo, macro_agent=macro_agent)


def _build_response(
    signals: list[Any],
    signal_filter: str | None,
    eligible_only: bool,
) -> DecisionListResponse:
    if signal_filter is not None:
        signals = [s for s in signals if s.signal == signal_filter.upper()]
    if eligible_only:
        signals = [s for s in signals if s.is_3a_eligible]
    items = [
        DecisionSignalResponse(
            ticker=s.ticker,
            snapshot_date=s.snapshot_date,
            signal=s.signal,
            confidence=s.confidence,
            weighted_score=s.weighted_score,
            quant_score=s.quant_score,
            ml_score=s.ml_score,
            macro_score=s.macro_score,
            is_3a_eligible=s.is_3a_eligible,
            signal_reason=_signal_reason(s.signal, s.weighted_score, s.quant_score),
        )
        for s in signals
    ]
    return DecisionListResponse(items=items, total=len(items))


@router.get(
    "/live",
    response_model=DecisionListResponse,
    summary="BUY/HOLD/SELL Signale für beliebige Ticker (kein Universe nötig)",
    description=(
        "Berechnet Signale direkt für eine komma-separierte Ticker-Liste. "
        "Ideal für Discovery-Flow: keine universe_id erforderlich. Max. 25 Ticker."
    ),
)
async def live_decisions(
    tickers: str = Query(..., description="Komma-separierte Ticker, z.B. NESN,ROG,NOVN"),
    signal: str | None = Query(default=None),
    eligible_only: bool = Query(default=False),
    aggregation_service: SignalAggregationService = Depends(get_signal_aggregation_service),
) -> DecisionListResponse:
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Keine Ticker angegeben."
        )
    if len(ticker_list) > _MAX_LIVE_TICKERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximal {_MAX_LIVE_TICKERS} Ticker erlaubt, {len(ticker_list)} übergeben.",
        )
    signals = await aggregation_service.get_signals(ticker_list)
    return _build_response(signals, signal, eligible_only)


_EXPLAIN_SYSTEM = """\
Du bist ein quantitativer Analyst einer Schweizer Vermögensverwaltung.
Erkläre eine algorithmische Investitionsentscheidung auf Deutsch, präzise und verständlich.
Antworte NUR mit einem JSON-Objekt (kein Markdown, kein Text davor/danach):
{
  "overall": "...",
  "quant_why": "...",
  "ml_why": "...",
  "macro_why": "...",
  "risk_note": "..."
}
"""

_EXPLAIN_HAIKU = "claude-haiku-4-5-20251001"


@router.post(
    "/explain",
    response_model=ExplainResponse,
    summary="LLM-Erklärung warum ein Signal so entschieden wurde",
)
async def explain_decision(
    body: ExplainRequest,
    llm_client: object = Depends(get_llm_client),
) -> ExplainResponse:
    """Generiert eine Haiku-basierte Erklärung warum TICKER dieses Signal erhalten hat.

    Erklärt nicht nur den Score-Wert, sondern den inhaltlichen Grund:
    warum ist der Quant-Score so hoch/niedrig, was sagt das ML-Modell wirklich aus,
    warum begünstigt/belastet das Makroumfeld diesen Titel.
    """
    import json

    from backend.infrastructure.llm.client import LLMClient

    client: LLMClient = llm_client  # type: ignore[assignment]

    ticker = body.ticker.upper()
    quant_band = (
        "stark" if body.quant_score >= 70 else ("moderat" if body.quant_score >= 45 else "schwach")
    )
    ml_label = (
        "OUTPERFORM"
        if body.ml_score >= 75
        else ("NEUTRAL" if body.ml_score >= 35 else "UNDERPERFORM")
    )
    macro_band = (
        "günstig"
        if body.macro_score >= 70
        else ("neutral" if body.macro_score >= 45 else "ungünstig")
    )

    user_msg = f"""
Ticker: {ticker}
Signal: {body.signal} ({round(body.confidence * 100)}% Konfidenz)
Gewichteter Gesamtscore: {body.weighted_score:.1f}/100 → {body.signal} (BUY ≥65 / HOLD 40–64 / SELL <40)

METRIKEN:
1. Quant-Score: {body.quant_score:.0f}/100 × 0.45 = {body.quant_score * 0.45:.1f} Punkte
   Einordnung: {quant_band} (Skala: <45=schwach, 45–69=moderat, ≥70=stark)
   Misst: Fundamentalqualität (Bewertung, Dividende, Cashflow, Kapitalrendite) relativ zu SMI-Bändern.

2. ML-Score: {body.ml_score:.0f}/100 × 0.35 = {body.ml_score * 0.35:.1f} Punkte
   Modell-Output: {ml_label} (OUTPERFORM=85 / NEUTRAL=50 / UNDERPERFORM=15)
   Misst: LightGBM-Vorhersage auf historischen Preis- und Fundamental-Features.

3. Makro-Score: {body.macro_score:.0f}/100 × 0.20 = {body.macro_score * 0.20:.1f} Punkte
   Einordnung: {macro_band} (Skala: SNB ≤0%=80 / ≤0.5%=65 / ≤1%=50 / ≤1.5%=35 / >1.5%=20)
   Misst: Geldpolitisches Umfeld (SNB-Leitzins, CHF/EUR, Inflation).

AUFGABE — erkläre in je 2 präzisen Sätzen pro Feld:
- overall: Warum hat {ticker} genau dieses Signal ({body.signal}) erhalten?
- quant_why: Warum ist der Quant-Score {body.quant_score:.0f}? Was sagt das über die Fundamentaldaten von {ticker} aus?
- ml_why: Warum zeigt das ML-Modell {ml_label}? Was bedeutet das für die erwartete Kursentwicklung?
- macro_why: Warum ist der Makro-Score {body.macro_score:.0f}? Wie wirkt das aktuelle Umfeld auf {ticker}?
- risk_note: Ein kurzer Risikohinweis (1 Satz, keine Anlageberatung).
"""

    try:
        response = await client.messages_create(
            model=_EXPLAIN_HAIKU,
            max_tokens=600,
            feature="decision_explain",
            system=_EXPLAIN_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        data = json.loads(raw)
        return ExplainResponse(
            ticker=ticker,
            overall=data.get("overall", ""),
            quant_why=data.get("quant_why", ""),
            ml_why=data.get("ml_why", ""),
            macro_why=data.get("macro_why", ""),
            risk_note=data.get("risk_note", "Keine Anlageberatung."),
        )
    except Exception as exc:
        _logger.warning("explain_decision LLM fehlgeschlagen für %s: %s", ticker, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Erklärung temporär nicht verfügbar.",
        ) from exc


@router.get(
    "",
    response_model=DecisionListResponse,
    summary="BUY/HOLD/SELL Signale für ein Universum",
    description=(
        "Berechnet aggregierte Handelssignale (Quant 45% + ML 35% + Macro 20%) "
        "für alle Ticker eines Universums. Optionale Filter: signal-Typ, 3a-Eligible. "
        "Signale ohne Marktdaten werden übersprungen."
    ),
)
async def list_decisions(
    universe_id: UUID = Query(..., description="Universum-ID"),
    signal: str | None = Query(default=None, description="Filter: BUY | HOLD | SELL"),
    eligible_only: bool = Query(default=False, description="Nur 3a-eligible Titel zurückgeben"),
    universe_service: UniverseService = Depends(get_universe_service),
    aggregation_service: SignalAggregationService = Depends(get_signal_aggregation_service),
) -> DecisionListResponse:
    try:
        universe = await universe_service.get_universe(universe_id)
    except UniverseNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    tickers = list(universe.tickers)
    signals = await aggregation_service.get_signals(tickers)

    if signal is not None:
        signal_upper = signal.upper()
        if signal_upper not in {"BUY", "HOLD", "SELL"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="signal muss BUY, HOLD oder SELL sein.",
            )
        signals = [s for s in signals if s.signal == signal_upper]

    if eligible_only:
        signals = [s for s in signals if s.is_3a_eligible]

    items = [
        DecisionSignalResponse(
            ticker=s.ticker,
            snapshot_date=s.snapshot_date,
            signal=s.signal,
            confidence=s.confidence,
            weighted_score=s.weighted_score,
            quant_score=s.quant_score,
            ml_score=s.ml_score,
            macro_score=s.macro_score,
            is_3a_eligible=s.is_3a_eligible,
            signal_reason=_signal_reason(s.signal, s.weighted_score, s.quant_score),
        )
        for s in signals
    ]

    return DecisionListResponse(items=items, total=len(items))
