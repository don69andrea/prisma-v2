"""SQLAlchemy-Adapter für NewsRepository (News-RAG)."""

import math
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.news_article import NewsArticle
from backend.domain.entities.news_chunk import NewsChunk
from backend.domain.entities.news_retrieval_result import NewsRetrievalResult
from backend.domain.repositories.embedding_repository import DuplicateUrl
from backend.domain.repositories.news_repository import NewsRepository
from backend.infrastructure.persistence.models.news import NewsChunkORM, NewsDocumentORM


class SQLANewsRepository(NewsRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_article(self, article: NewsArticle) -> None:
        async with self._session_factory() as session:
            session.add(
                NewsDocumentORM(
                    id=article.id,
                    url_hash=article.url_hash,
                    url=article.url,
                    title=article.title,
                    content_preview=article.content[:500] if article.content else None,
                    published_at=article.published_at,
                    source=article.source,
                    tickers=list(article.tickers) if article.tickers else None,
                    ingested_at=article.ingested_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if "uq_news_documents_url_hash" in str(exc.orig):
                    raise DuplicateUrl(article.url) from exc
                raise

    async def exists_by_url_hash(self, url_hash: str) -> bool:
        async with self._session_factory() as session:
            stmt = select(NewsDocumentORM.id).where(NewsDocumentORM.url_hash == url_hash)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return row is not None

    async def save_chunks(self, chunks: list[NewsChunk]) -> None:
        if not chunks:
            return
        async with self._session_factory() as session:
            stmt = pg_insert(NewsChunkORM.__table__).values(  # type: ignore[arg-type]
                [
                    {
                        "id": c.id,
                        "news_document_id": c.news_document_id,
                        "chunk_idx": c.chunk_idx,
                        "content": c.content,
                        "embedding": c.embedding,
                        "metadata": c.metadata,
                    }
                    for c in chunks
                ]
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_news_doc_chunk_idx",
                set_={
                    "content": stmt.excluded.content,
                    "embedding": stmt.excluded.embedding,
                    "metadata": stmt.excluded.metadata,
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def find_nearest(
        self,
        query_embedding: list[float],
        k: int,
        ticker: str | None = None,
        max_age_days: int | None = None,
    ) -> list[NewsRetrievalResult]:
        ticker_filter = "AND :ticker = ANY(nd.tickers)" if ticker else ""
        # Optional 7-day soft-TTL filter: only return articles published within max_age_days
        # Uses a bound parameter — NEVER string-concat the interval value (AGENTS.md §7/§8).
        age_filter = (
            "AND nd.published_at > NOW() - INTERVAL '1 day' * :max_age_days"
            if max_age_days is not None
            else ""
        )
        # K-6: Validate embedding values — NaN/Inf would cause a PostgreSQL parsing error.
        validated = [float(v) for v in query_embedding]
        if any(not math.isfinite(v) for v in validated):
            raise ValueError("Embedding contains non-finite values (NaN/Inf)")
        query_vector_str = "[" + ",".join(f"{v:.8f}" for v in validated) + "]"
        raw_sql = f"""
            SELECT
                nc.id              AS chunk_id,
                nc.news_document_id,
                nc.chunk_idx,
                nc.content,
                nc.metadata,
                nd.title,
                nd.url,
                nd.source,
                nd.tickers,
                nd.published_at,
                1 - ((nc.embedding::halfvec(1024)) <=> ('{query_vector_str}'::vector(1024)::halfvec(1024)))
                                   AS similarity
            FROM news_chunks nc
            JOIN news_documents nd ON nd.id = nc.news_document_id
            WHERE 1=1 {ticker_filter} {age_filter}
            ORDER BY (nc.embedding::halfvec(1024)) <=> ('{query_vector_str}'::vector(1024)::halfvec(1024))
            LIMIT :k
        """
        from sqlalchemy import text

        params: dict[str, object] = {"k": k}
        if ticker:
            params["ticker"] = ticker
        if max_age_days is not None:
            params["max_age_days"] = max_age_days

        async with self._session_factory() as session:
            rows = (await session.execute(text(raw_sql), params)).mappings().all()

        results = []
        for row in rows:
            sim = float(row["similarity"])
            if math.isnan(sim):
                continue
            raw_tickers: list[str] | None = row["tickers"]
            published: datetime | None = row["published_at"]
            results.append(
                NewsRetrievalResult(
                    chunk_id=UUID(str(row["chunk_id"])),
                    news_document_id=UUID(str(row["news_document_id"])),
                    chunk_idx=int(row["chunk_idx"]),
                    content=str(row["content"]),
                    similarity=sim,
                    title=str(row["title"]),
                    url=str(row["url"]),
                    source=str(row["source"]),
                    tickers=tuple(raw_tickers) if raw_tickers else (),
                    published_at=published,
                    metadata=dict(row["metadata"]) if row["metadata"] else {},
                )
            )
        return results
