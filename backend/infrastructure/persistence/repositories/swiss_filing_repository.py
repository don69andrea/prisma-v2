"""SQLAlchemy-Adapter für SwissFilingRepository (Swiss RAG)."""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.swiss_filing_chunk import SwissFilingChunk
from backend.domain.entities.swiss_filing_retrieval_result import SwissFilingRetrievalResult
from backend.domain.repositories.swiss_filing_repository import SwissFilingRepository
from backend.infrastructure.persistence.models.swiss_filing import SwissFilingChunkORM


class SQLASwissFilingRepository(SwissFilingRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def exists_by_url_hash_and_chunk(self, url_hash: str, chunk_idx: int) -> bool:
        async with self._session_factory() as session:
            stmt = select(SwissFilingChunkORM.id).where(
                SwissFilingChunkORM.url_hash == url_hash,
                SwissFilingChunkORM.chunk_idx == chunk_idx,
            )
            row = (await session.execute(stmt)).first()
            return row is not None

    async def save_chunks(self, chunks: list[SwissFilingChunk]) -> None:
        if not chunks:
            return
        async with self._session_factory() as session:
            stmt = pg_insert(SwissFilingChunkORM.__table__).values(  # type: ignore[arg-type]
                [
                    {
                        "id": c.id,
                        "url_hash": c.url_hash,
                        "url": c.url,
                        "ticker": c.ticker,
                        "source": c.source,
                        "language": c.language,
                        "filing_date": c.filing_date,
                        "doc_type": c.doc_type,
                        "chunk_idx": c.chunk_idx,
                        "content": c.content,
                        "embedding": c.embedding,
                        "metadata": c.metadata,
                        "ingested_at": c.ingested_at,
                    }
                    for c in chunks
                ]
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_swiss_rag_url_chunk",
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
        language: str | None = None,
    ) -> list[SwissFilingRetrievalResult]:
        ticker_filter = "AND ticker = :ticker" if ticker else ""
        language_filter = "AND language = :language" if language else ""
        # K-6: Validate embedding values — NaN/Inf would cause a PostgreSQL parsing error.
        validated = [float(v) for v in query_embedding]
        if any(not math.isfinite(v) for v in validated):
            raise ValueError("Embedding contains non-finite values (NaN/Inf)")
        query_vector_str = "[" + ",".join(f"{v:.8f}" for v in validated) + "]"

        raw_sql = f"""
            SELECT
                id          AS chunk_id,
                chunk_idx,
                url,
                ticker,
                source,
                language,
                filing_date,
                doc_type,
                content,
                metadata,
                1 - ((embedding::halfvec(1024)) <=> ('{query_vector_str}'::vector(1024)::halfvec(1024)))
                            AS similarity
            FROM swiss_rag_chunks
            WHERE 1=1 {ticker_filter} {language_filter}
            ORDER BY (embedding::halfvec(1024)) <=> ('{query_vector_str}'::vector(1024)::halfvec(1024))
            LIMIT :k
        """
        params: dict[str, object] = {"k": k}
        if ticker:
            params["ticker"] = ticker
        if language:
            params["language"] = language

        async with self._session_factory() as session:
            rows = (await session.execute(text(raw_sql), params)).mappings().all()

        results: list[SwissFilingRetrievalResult] = []
        for row in rows:
            sim = float(row["similarity"])
            if math.isnan(sim):
                continue
            results.append(
                SwissFilingRetrievalResult(
                    chunk_id=UUID(str(row["chunk_id"])),
                    chunk_idx=int(row["chunk_idx"]),
                    url=str(row["url"]),
                    ticker=str(row["ticker"]),
                    source=str(row["source"]),
                    language=str(row["language"]),
                    filing_date=row["filing_date"],
                    doc_type=str(row["doc_type"]),
                    content=str(row["content"]),
                    similarity=sim,
                    metadata=dict(row["metadata"] or {}),
                )
            )
        return results
