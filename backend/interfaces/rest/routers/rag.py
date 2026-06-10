"""FastAPI Router für RAG-Retrieval-Endpoints (SEC Filings + Swiss Filings)."""

from fastapi import APIRouter, Depends

from backend.application.services.retrieval_service import RetrievalService
from backend.application.services.swiss_filing_retrieval_service import (
    SwissFilingRetrievalService,
)
from backend.interfaces.rest.dependencies import (
    get_retrieval_service,
    get_swiss_filing_retrieval_service,
)
from backend.interfaces.rest.schemas.rag import (
    ChunkResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from backend.interfaces.rest.schemas.swiss_rag import (
    SwissRagChunkResult,
    SwissRagRetrieveRequest,
    SwissRagRetrieveResponse,
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


@router.post(
    "/swiss/retrieve",
    response_model=SwissRagRetrieveResponse,
    summary="Semantische Suche im Swiss-RAG-Corpus (SIX Jahresberichte)",
)
async def swiss_retrieve(
    request: SwissRagRetrieveRequest,
    service: SwissFilingRetrievalService = Depends(get_swiss_filing_retrieval_service),
) -> SwissRagRetrieveResponse:
    """POST /api/v1/rag/swiss/retrieve — kNN-Suche über swiss_rag_chunks."""
    results = await service.retrieve(
        query=request.query,
        k=request.k,
        ticker=request.ticker,
        language=request.language,
    )
    return SwissRagRetrieveResponse(
        results=[
            SwissRagChunkResult(
                chunk_id=r.chunk_id,
                chunk_idx=r.chunk_idx,
                url=r.url,
                ticker=r.ticker,
                source=r.source,
                language=r.language,
                filing_date=r.filing_date,
                doc_type=r.doc_type,
                content=r.content,
                similarity=r.similarity,
            )
            for r in results
        ],
        total=len(results),
    )
