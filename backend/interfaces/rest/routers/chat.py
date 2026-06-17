"""REST Router: PRISMA Chat — SSE Streaming via Claude Tool Use."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.application.services.chat_service import ChatMessage, ChatService
from backend.interfaces.rest.dependencies import get_chat_service
from backend.interfaces.rest.schemas.chat import ChatRequest

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
_logger = logging.getLogger(__name__)


@router.post(
    "",
    summary="PRISMA Chat — Natursprache-Query mit Claude Tool Use",
    description=(
        "Streamt SSE-Events: token | tool_call | tool_result | done | error. "
        "Nutzt Claude mit PRISMA-Tools (search_stocks, filter_stocks, get_factsheet, "
        "get_macro_context, compare_stocks, get_ranking)."
    ),
    # FIX-3: require_admin_api_key NICHT hier — ist bereits via
    # app.include_router(router, dependencies=[Depends(require_admin_api_key)]) aktiv.
    # Doppelaufruf führt zu 2 API-Key-Checks und verursacht Konflikte.
)
async def chat(
    req: ChatRequest,
    svc: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    messages = [ChatMessage(role=m.role, content=m.content) for m in req.history]
    messages.append(ChatMessage(role="user", content=req.message))

    return StreamingResponse(
        svc.stream(messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
