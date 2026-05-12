"""POST /memos/generate + GET /memos/{stock_id}/{run_id}.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §6.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo
from backend.interfaces.rest.dependencies import get_narrative_service

router = APIRouter(prefix="/memos", tags=["memos"])


class GenerateMemoRequest(BaseModel):
    stock_id: UUID
    model_run_id: UUID
    language: Literal["de", "en"] = "de"


class MemoResponse(BaseModel):
    id: UUID
    stock_id: UUID
    model_run_id: UUID
    language: Literal["de", "en"]
    one_liner: str
    ranking_interpretation: str
    sweet_spot: bool
    sweet_spot_explanation: str | None
    contradictions: list[ContradictionItem]
    key_strengths: list[str]
    key_risks: list[str]
    confidence: Literal["low", "medium", "high"]
    model_version: str
    created_at: datetime
    is_error: bool

    @classmethod
    def from_entity(cls, memo: ResearchMemo) -> "MemoResponse":
        is_error = memo.model_version == "error-fallback" or memo.one_liner.startswith(
            "Memo-Generierung fehlgeschlagen"
        )
        return cls(
            id=memo.id,
            stock_id=memo.stock_id,
            model_run_id=memo.model_run_id,
            language=memo.language,
            one_liner=memo.one_liner,
            ranking_interpretation=memo.ranking_interpretation,
            sweet_spot=memo.sweet_spot,
            sweet_spot_explanation=memo.sweet_spot_explanation,
            contradictions=list(memo.contradictions),
            key_strengths=list(memo.key_strengths),
            key_risks=list(memo.key_risks),
            confidence=memo.confidence,
            model_version=memo.model_version,
            created_at=memo.created_at,
            is_error=is_error,
        )


@router.post("/generate", response_model=MemoResponse)
async def generate_memo(
    request: GenerateMemoRequest,
    service: NarrativeService = Depends(get_narrative_service),
) -> MemoResponse:
    try:
        memo = await service.generate_memo(
            request.stock_id, request.model_run_id, language=request.language
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except anthropic.APITimeoutError as exc:
        # Spec §7: SDK-Retries (max_retries=3) erschoepft, Upstream antwortet
        # nicht innerhalb 30s. 504 signalisiert "transient — retry", Client
        # kann den Call wiederholen ohne Annahme dass Memo schon generiert ist.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Anthropic API timeout — bitte erneut versuchen",
        ) from exc
    return MemoResponse.from_entity(memo)


@router.get("/{stock_id}/{run_id}", response_model=MemoResponse)
async def get_memo(
    stock_id: UUID,
    run_id: UUID,
    language: Literal["de", "en"] = "de",
    service: NarrativeService = Depends(get_narrative_service),
) -> MemoResponse:
    memo = await service.get_memo(stock_id, run_id, language=language)
    if memo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")
    return MemoResponse.from_entity(memo)
