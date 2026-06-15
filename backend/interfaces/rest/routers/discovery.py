"""REST Router: Discovery Engine."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.discovery_service import DiscoveryService
from backend.application.services.profile_classifier import ProfileClassifier
from backend.domain.entities.investor_profile import InvestorProfile
from backend.domain.entities.swiss_stock import SwissStock
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.persistence.repositories.investor_profile_repository import (
    SQLAInvestorProfileRepository,
)
from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
    SQLASwissStockRepository,
)
from backend.interfaces.rest.dependencies import get_llm_client, get_session
from backend.interfaces.rest.schemas.investor_profile import (
    AnswerRequest,
    AnswerResponse,
    CompleteRequest,
    CompleteResponse,
    DiscoveredStockResponse,
    DiscoveryResponse,
    InvestorProfileCreateRequest,
    InvestorProfileResponse,
    SessionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["discovery"])
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DI helpers
# ---------------------------------------------------------------------------


def _get_discovery_service(session: AsyncSession = Depends(get_session)) -> DiscoveryService:
    return DiscoveryService(
        swiss_stock_repo=SQLASwissStockRepository(session=session),
        market_data=YFinanceSwissAdapter(),
        db_session=session,
    )


def _get_profile_classifier(llm: LLMClient = Depends(get_llm_client)) -> ProfileClassifier:
    return ProfileClassifier(llm_client=llm)


def _to_stock_response(s: SwissStock) -> DiscoveredStockResponse:
    return DiscoveredStockResponse(
        ticker=s.ticker,
        name=s.name,
        sector=s.sector,
        market_cap_chf=s.market_cap_chf,
        exchange=s.exchange,
    )


def _to_profile_response(p: InvestorProfile) -> InvestorProfileResponse:
    return InvestorProfileResponse(
        session_id=p.session_id,
        risk_profile=p.risk_profile,
        sector_affinity=list(p.sector_affinity),
        time_horizon=p.time_horizon,
        investment_goal=p.investment_goal,
        confidence_score=p.confidence_score,
        onboarding_complete=p.onboarding_complete,
    )


# ---------------------------------------------------------------------------
# Conversational Discovery (neue Endpunkte R2.3-6 / R2.4-3)
# ---------------------------------------------------------------------------


@router.post(
    "/discovery/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Neue Discovery-Session starten",
)
async def create_session(
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    """Legt ein leeres InvestorProfile an und gibt die session_id zurück."""
    session_id = str(uuid.uuid4())
    repo = SQLAInvestorProfileRepository(session=session)
    profile = InvestorProfile(session_id=session_id)
    await repo.save(profile)
    return SessionResponse(session_id=session_id)


@router.post(
    "/discovery/answer",
    response_model=AnswerResponse,
    summary="Antwort auf Discovery-Frage einreichen",
)
async def submit_answer(
    body: AnswerRequest,
    session: AsyncSession = Depends(get_session),
    classifier: ProfileClassifier = Depends(_get_profile_classifier),
) -> AnswerResponse:
    """Aktualisiert das Profil basierend auf der Nutzerantwort für den jeweiligen Turn."""
    repo = SQLAInvestorProfileRepository(session=session)
    profile = await repo.get_by_session_id(body.session_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Session für session_id={body.session_id!r} gefunden.",
        )

    answer = body.answer
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}

    if body.turn == 1:
        profession_text = answer if isinstance(answer, str) else str(answer)
        classification = await classifier.classify_turn1(profession_text)
        updates["profession"] = profession_text
        updates["financial_knowledge"] = classification.financial_knowledge
        updates["sector_hint"] = classification.sector_hint
        if classification.sector_hint:
            existing = list(profile.sector_affinity)
            if classification.sector_hint not in existing:
                existing.append(classification.sector_hint)
            updates["sector_affinity"] = existing

    elif body.turn == 2:
        goal_text = answer if isinstance(answer, str) else str(answer)
        investment_goal, time_horizon = classifier.classify_turn2(goal_text)
        updates["investment_goal"] = investment_goal
        updates["time_horizon"] = time_horizon

    elif body.turn == 3:
        risk_choice = answer if isinstance(answer, str) else str(answer)
        updates["risk_profile"] = classifier.classify_turn3(risk_choice)

    elif body.turn == 4:
        tickers = answer if isinstance(answer, list) else [answer]
        sector_affinity, known_tickers = classifier.classify_turn4(
            tickers,
            body.brand_data or {},
        )
        updates["sector_affinity"] = sector_affinity
        updates["known_tickers"] = known_tickers

    elif body.turn == 5:
        amount_text = answer if isinstance(answer, str) else str(answer)
        updates["investment_amount"] = classifier.classify_turn_amount(amount_text)

    elif body.turn == 6:
        esg_text = answer if isinstance(answer, str) else str(answer)
        updates["esg_preference"] = classifier.classify_turn_esg(esg_text)

    elif body.turn == 7:
        income_text = answer if isinstance(answer, str) else str(answer)
        updates["income_preference"] = classifier.classify_turn_income(income_text)

    updated_profile = profile.model_copy(update=updates)
    new_confidence = classifier.calculate_confidence(updated_profile)
    updated_profile = updated_profile.model_copy(update={"confidence_score": new_confidence})
    await repo.save(updated_profile)

    next_turn = body.turn + 1 if body.turn < 7 else None
    return AnswerResponse(
        session_id=body.session_id,
        next_turn=next_turn,
        confidence=new_confidence,
        partial_profile=_to_profile_response(updated_profile),
    )


@router.post(
    "/discovery/complete",
    response_model=CompleteResponse,
    summary="Profil abschliessen und personalisierte Titel abrufen",
)
async def complete_discovery(
    body: CompleteRequest,
    session: AsyncSession = Depends(get_session),
    service: DiscoveryService = Depends(_get_discovery_service),
) -> CompleteResponse:
    """Markiert das Profil als abgeschlossen und gibt die personalisierte Titelliste zurück."""
    repo = SQLAInvestorProfileRepository(session=session)
    profile = await repo.get_by_session_id(body.session_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Session für session_id={body.session_id!r} gefunden.",
        )

    completed = profile.model_copy(
        update={"onboarding_complete": True, "updated_at": datetime.now(UTC)}
    )
    await repo.save(completed)

    stocks = await service.get_personalized_universe(completed)
    return CompleteResponse(
        profile=_to_profile_response(completed),
        recommended_stocks=[_to_stock_response(s) for s in stocks],
    )


# ---------------------------------------------------------------------------
# Legacy: POST /profile + GET /discover (R2.3-5 — direktes Profil-Speichern)
# ---------------------------------------------------------------------------


@router.post(
    "/profile",
    response_model=InvestorProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Investorenprofil direkt speichern (ohne Gesprächsflow)",
)
async def save_profile(
    body: InvestorProfileCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> InvestorProfileResponse:
    """Erstellt oder ersetzt das Investorenprofil für eine Session."""
    repo = SQLAInvestorProfileRepository(session=session)
    profile = InvestorProfile(
        session_id=body.session_id,
        risk_profile=body.risk_profile,
        sector_affinity=body.sector_affinity,
        time_horizon=body.time_horizon,
        investment_goal=body.investment_goal,
        profession=body.profession,
        known_tickers=body.known_tickers,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repo.save(profile)
    return _to_profile_response(profile)


@router.get(
    "/discover",
    response_model=DiscoveryResponse,
    summary="Personalisiertes Aktienuniversum abrufen",
)
async def discover(
    session_id: str = Query(..., description="Session-ID des Investorenprofils"),
    session: AsyncSession = Depends(get_session),
    service: DiscoveryService = Depends(_get_discovery_service),
) -> DiscoveryResponse:
    """Gibt die gefilterte Titelliste für das gespeicherte Investorenprofil zurück."""
    repo = SQLAInvestorProfileRepository(session=session)
    profile = await repo.get_by_session_id(session_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kein Investorenprofil für session_id={session_id!r} gefunden.",
        )

    stocks = await service.get_personalized_universe(profile)
    return DiscoveryResponse(
        session_id=session_id,
        total=len(stocks),
        stocks=[_to_stock_response(s) for s in stocks],
    )
