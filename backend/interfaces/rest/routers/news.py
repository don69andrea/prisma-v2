"""REST-Router für News-RAG unter /api/v1/news."""

from fastapi import APIRouter, Depends

from backend.application.services.news_ingestion_service import NewsIngestionService
from backend.application.services.news_retrieval_service import NewsRetrievalService
from backend.interfaces.rest.dependencies import (
    get_news_ingestion_service,
    get_news_retrieval_service,
)
from backend.interfaces.rest.schemas.news import (
    NewsChunkResult,
    NewsIngestResponse,
    NewsRetrieveRequest,
    NewsRetrieveResponse,
)

router = APIRouter(prefix="/api/v1/news", tags=["news-rag"])


@router.post(
    "/ingest",
    response_model=NewsIngestResponse,
    summary="RSS-News-Feeds ingesten (NZZ + SRF)",
    description=(
        "Triggert manuelle Ingestion aller konfigurierten CH-Finanz-RSS-Feeds. "
        "Duplikate werden via URL-Hash dedupliziert. "
        "Wird täglich automatisch via APScheduler ausgeführt."
    ),
)
async def ingest_news(
    service: NewsIngestionService = Depends(get_news_ingestion_service),
) -> NewsIngestResponse:
    stats = await service.ingest_all()
    return NewsIngestResponse(
        ingested=stats["ingested"],
        skipped_duplicate=stats["skipped_duplicate"],
        errors=stats["errors"],
    )


@router.post(
    "/retrieve",
    response_model=NewsRetrieveResponse,
    summary="Semantische Suche im News-RAG-Corpus",
    description="Sucht ähnliche News-Chunks via pgvector HNSW. Optional nach Ticker gefiltert.",
)
async def retrieve_news(
    request: NewsRetrieveRequest,
    service: NewsRetrievalService = Depends(get_news_retrieval_service),
) -> NewsRetrieveResponse:
    results = await service.retrieve(
        query=request.query,
        k=request.k,
        ticker=request.ticker,
    )
    return NewsRetrieveResponse(
        results=[
            NewsChunkResult(
                chunk_id=str(r.chunk_id),
                news_document_id=str(r.news_document_id),
                chunk_idx=r.chunk_idx,
                content=r.content,
                similarity=r.similarity,
                title=r.title,
                source=r.source,
                tickers=list(r.tickers),
                published_at=r.published_at,
            )
            for r in results
        ],
        total=len(results),
    )
