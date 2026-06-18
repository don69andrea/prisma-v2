"""Analyze Router — SSE-Stream + HITL-Checkpoint für InvestmentDirector."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.domain.schemas.multiagent_schemas import CheckpointAnswer
from backend.interfaces.rest.dependencies import get_investment_director

router = APIRouter(tags=["analyze"])


@router.get("/analyze/stream")
async def analyze_stream(
    ticker: str,
    context: str = "unknown",
    director: Any = Depends(get_investment_director),
) -> StreamingResponse:
    """SSE-Endpoint: InvestmentDirector schreibt Events in Queue → Browser."""
    run_id = str(uuid.uuid4())
    queue: asyncio.Queue[Any] = asyncio.Queue()

    asyncio.create_task(
        director.run_with_events(
            ticker=ticker,
            context=context,
            run_id=run_id,
            event_queue=queue,
        )
    )

    async def event_stream() -> AsyncIterator[str]:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except TimeoutError:
                yield 'data: {"type": "error", "error": "Timeout"}\n\n'
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze/checkpoint/{checkpoint_id}")
async def submit_checkpoint(
    checkpoint_id: str,
    body: CheckpointAnswer,
    director: Any = Depends(get_investment_director),
) -> dict[str, str]:
    """User-Antwort auf einen Director-Checkpoint."""
    await director.resolve_checkpoint(checkpoint_id, body.answer)
    return {"status": "received"}
