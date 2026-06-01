"""FastAPI Router für RAG-Retrieval-Endpoint."""

from fastapi import APIRouter, Depends

from backend.application.services.retrieval_service import RetrievalService
from backend.interfaces.rest.dependencies import get_retrieval_service
from backend.interfaces.rest.schemas.rag import (
    ChunkResponse,
    RetrieveRequest,
    RetrieveResponse,
)

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


@router.post(
    "/retrieve",
    response_model=RetrieveResponse,
    summary="Semantische Suche im RAG-Corpus (pgvector HNSW)",
)
async def retrieve(
    request: RetrieveRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> RetrieveResponse:
    """POST /api/v1/rag/retrieve — Semantische Suche über SEC-Filing-Chunks."""
    results = await service.retrieve(query=request.query, k=request.k, ticker=request.ticker)
    return RetrieveResponse(
        results=[
            ChunkResponse(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                chunk_idx=r.chunk_idx,
                content=r.content,
                similarity=r.similarity,
                ticker=r.ticker,
                doc_type=r.doc_type,
            )
            for r in results
        ],
        total=len(results),
    )
