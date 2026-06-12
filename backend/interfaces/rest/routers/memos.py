"""POST /memos/generate + GET /memos/{stock_id}/{run_id} +
POST /memos/batch + GET /memos/jobs/{job_id}.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §6
      docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md §6

Route-Reihenfolge: statische Pfade (/generate, /batch, /jobs/{job_id})
MUESSEN vor dem parametrischen Catch-All (/{stock_id}/{run_id}) registriert
werden, da FastAPI Routen in Deklarationsreihenfolge matched.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.research_memo import (
    ContradictionItem,
    ResearchMemo,
)
from backend.interfaces.rest.dependencies import get_narrative_service
from backend.interfaces.rest.schemas.memo_batch import (
    BatchJobAcceptedResponse,
    BatchJobResponse,
    BatchMemoSummary,
    BatchProgress,
    BatchRequest,
)

router = APIRouter(prefix="/memos", tags=["memos"])


class GenerateMemoRequest(BaseModel):
    stock_id: UUID
    model_run_id: UUID | None = None
    language: Literal["de", "en"] = "de"


class MemoResponse(BaseModel):
    id: UUID
    stock_id: UUID
    model_run_id: UUID | None
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
            is_error=memo.is_error,
        )


# ---------------------------------------------------------------------------
# Static-prefix routes — MUST be declared before /{stock_id}/{run_id}
# ---------------------------------------------------------------------------


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


@router.post(
    "/batch",
    response_model=BatchJobAcceptedResponse,
    status_code=202,
)
async def post_batch(
    body: BatchRequest,
    service: NarrativeService = Depends(get_narrative_service),
) -> BatchJobAcceptedResponse:
    """Startet einen asynchronen Batch-Memo-Run fuer die Top-N Stocks eines Runs.

    Gibt 202 Accepted zurueck — der eigentliche Batch laeuft im Hintergrund.
    Status-Polling via GET /memos/jobs/{job_id}.
    """
    try:
        job = await service.start_batch(
            body.model_run_id,
            top_n=body.top_n,
            language=body.language,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        # F4: start_batch wirft ValueError bei ungültigem top_n (z.B. top_n=0).
        # Pydantic-Schema filtert das normalerweise, aber bei direktem Service-
        # Aufruf oder Schema-Bypass → 422 statt 500.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    # BudgetCapExceeded: NICHT lokal fangen — globaler Handler in
    # exception_handlers.py liefert 402 mit strukturiertem Body + Retry-After.
    # Konsistent ueber alle AI-Endpoints (PR #70 W2).

    return BatchJobAcceptedResponse(
        job_id=job.id,
        model_run_id=job.model_run_id,
        top_n=job.top_n,
        language=job.language,
        status="pending",
        created_at=job.created_at,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=BatchJobResponse,
)
async def get_job(
    job_id: UUID,
    service: NarrativeService = Depends(get_narrative_service),
) -> BatchJobResponse:
    """Liefert aktuellen Job-Status inkl. Progress und Memo-Zusammenfassung."""
    job = await service.get_batch_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    memos = await service.list_memos_for_run(
        job.model_run_id,
        language=job.language,
        stock_ids=job.expected_stock_ids or None,
    )

    # Get-Stock-Ticker-Map fuer das Frontend
    stock_ids = [m.stock_id for m in memos]
    ticker_map = await service.get_stock_ticker_map(stock_ids)

    memo_summaries = [
        BatchMemoSummary(
            stock_id=m.stock_id,
            ticker=ticker_map.get(m.stock_id),  # None falls Stock geloescht (CASCADE-edge)
            one_liner=m.one_liner,
            is_error=m.is_error,
        )
        for m in memos
    ]

    # F1: Für terminale Jobs (complete/partial/failed) ist completed = top_n - failed,
    # da die DB-Records die definitive Wahrheit sind (job.failed_stock_ids ist final).
    # Während running/pending wird len(memos) als Live-Progress-Indikator verwendet —
    # zeigt wieviele Memos schon persistiert wurden, unabhängig ob von diesem Batch.
    _terminal = job.status in ("complete", "partial", "failed")
    _completed = job.top_n - len(job.failed_stock_ids) if _terminal else len(memos)

    return BatchJobResponse(
        job_id=job.id,
        model_run_id=job.model_run_id,
        top_n=job.top_n,
        language=job.language,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        progress=BatchProgress(
            expected=job.top_n,
            completed=_completed,
            failed=len(job.failed_stock_ids),
        ),
        failed_stock_ids=job.failed_stock_ids,
        error_message=job.error_message,
        memos=memo_summaries,
    )


# ---------------------------------------------------------------------------
# Parametric catch-all — MUST be declared last
# ---------------------------------------------------------------------------


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
