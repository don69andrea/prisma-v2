"""SQLAlchemy-Adapter fuer EmbeddingRepository (RAG Slice 1).

Pattern: session_factory pro Operation (PR #25-Stil, analog
SQLAResearchMemoRepository) — vermeidet Transaction-Leaks.
"""

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.document import Document
from backend.domain.entities.embedding_chunk import EmbeddingChunk
from backend.domain.repositories.embedding_repository import (
    DuplicateUrl,
    EmbeddingRepository,
    RetrievalResult,
)
from backend.infrastructure.persistence.models.embedding import (
    DocumentORM,
    EmbeddingChunkORM,
)


class SQLAEmbeddingRepository(EmbeddingRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_document(self, doc: Document) -> None:
        async with self._session_factory() as session:
            session.add(
                DocumentORM(
                    id=doc.id,
                    ticker=doc.ticker,
                    doc_type=doc.doc_type,
                    filing_date=doc.filing_date,
                    url=doc.url,
                    raw_text_hash=doc.raw_text_hash,
                    ingested_at=doc.ingested_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                # Detection per Constraint-Name (uq_documents_url ist in Migration
                # benannt) — robust gegen Postgres-Error-Message-Aenderungen.
                if "uq_documents_url" in str(exc.orig):
                    raise DuplicateUrl(doc.url) from exc
                raise

    async def save_chunks(self, chunks: list[EmbeddingChunk]) -> None:
        if not chunks:
            return
        async with self._session_factory() as session:
            # UPSERT: bei (document_id, chunk_idx)-Konflikt update statt fehlschlagen.
            # Macht Re-Ingestion idempotent.
            #
            # `pg_insert` gegen die `__table__` (statt der ORM-Klasse) — damit
            # konsistent DB-Column-Namen (`metadata`) verwendet werden koennen,
            # ohne mit `Base.metadata` zu kollidieren (was bei pg_insert(ORM)
            # einen Mapping-Konflikt zwischen ORM-Attribute `chunk_metadata` und
            # Column `metadata` ausloest — SQLA versucht, das ORM-Attribut
            # `chunk_metadata` aus dem dict zu lesen, findet aber Key `metadata`).
            #
            # `# type: ignore[arg-type]` ist noetig, weil mypy `pg_insert` als
            # `Insert[ORM]` typisiert und ein `Table` nicht in `type[ORM]` passt.
            # Zur Laufzeit ist `pg_insert(Table)` jedoch das offizielle SQLA-2.0-
            # Pattern fuer raw-Column-Inserts (siehe SQLA-Doc "Insert objects":
            # https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert
            # — Beispiele dort verwenden ebenfalls `__table__`).
            #
            # Folge-Slice: wenn `metadata` ohnehin nur intern verwendet wird,
            # koennte das ORM-Attribut umbenannt werden zu z.B. `meta`, um den
            # Workaround loszuwerden. Out-of-scope fuer Slice 1.
            stmt = pg_insert(EmbeddingChunkORM.__table__).values(  # type: ignore[arg-type]
                [
                    {
                        "id": c.id,
                        "document_id": c.document_id,
                        "chunk_idx": c.chunk_idx,
                        "content": c.content,
                        "embedding": c.embedding,
                        "metadata": c.metadata,
                    }
                    for c in chunks
                ]
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_doc_chunk_idx",
                set_={
                    "content": stmt.excluded.content,
                    "embedding": stmt.excluded.embedding,
                    "metadata": stmt.excluded.metadata,
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def get_document_by_url(self, url: str) -> Document | None:
        async with self._session_factory() as session:
            stmt = select(DocumentORM).where(DocumentORM.url == url)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return _orm_to_doc(row) if row else None

    async def count_chunks(self, document_id: UUID) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count(EmbeddingChunkORM.id)).where(
                EmbeddingChunkORM.document_id == document_id
            )
            count = (await session.execute(stmt)).scalar()
            return int(count or 0)

    async def list_documents(self, *, ticker: str | None = None) -> list[Document]:
        async with self._session_factory() as session:
            stmt = select(DocumentORM).order_by(DocumentORM.ingested_at.desc())
            if ticker is not None:
                stmt = stmt.where(DocumentORM.ticker == ticker)
            rows = (await session.execute(stmt)).scalars().all()
            return [_orm_to_doc(r) for r in rows]

    async def find_nearest(
        self,
        query_embedding: list[float],
        k: int,
        ticker: str | None = None,
    ) -> list[RetrievalResult]:
        # halfvec-Cast auf Query und Column, damit der HNSW-Index genutzt wird.
        # JOIN documents bringt ticker und doc_type mit.
        ticker_filter = "AND d.ticker = :ticker" if ticker else ""
        raw_sql = f"""
            SELECT
                ec.id          AS chunk_id,
                ec.document_id,
                ec.chunk_idx,
                ec.content,
                ec.metadata,
                d.ticker,
                d.doc_type,
                1 - ((ec.embedding::halfvec(2048)) <=> (:query::vector(2048)::halfvec(2048)))
                               AS similarity
            FROM embedding_chunks ec
            JOIN documents d ON d.id = ec.document_id
            WHERE 1=1 {ticker_filter}
            ORDER BY (ec.embedding::halfvec(2048)) <=> (:query::vector(2048)::halfvec(2048))
            LIMIT :k
        """
        params: dict[str, object] = {"query": str(query_embedding), "k": k}
        if ticker:
            params["ticker"] = ticker

        async with self._session_factory() as session:
            rows = (await session.execute(text(raw_sql), params)).mappings().all()

        return [
            RetrievalResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                chunk_idx=row["chunk_idx"],
                content=row["content"],
                similarity=float(row["similarity"]),
                ticker=row["ticker"],
                doc_type=row["doc_type"],
                metadata=row["metadata"] or {},
            )
            for row in rows
        ]


def _orm_to_doc(row: DocumentORM) -> Document:
    return Document(
        id=row.id,
        ticker=row.ticker,
        doc_type=row.doc_type,
        filing_date=row.filing_date,
        url=row.url,
        raw_text_hash=row.raw_text_hash,
        ingested_at=row.ingested_at,
    )
