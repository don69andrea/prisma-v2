"""Integration-Tests fuer SQLAEmbeddingRepository gegen Live-Postgres mit pgvector.

Voraussetzung: docker-compose up -d db, alembic upgrade head.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.document import Document
from backend.domain.entities.embedding_chunk import EMBEDDING_DIM, EmbeddingChunk
from backend.domain.repositories.embedding_repository import DuplicateUrl
from backend.infrastructure.persistence.models.embedding import DocumentORM
from backend.infrastructure.persistence.repositories.embedding_repository import (
    SQLAEmbeddingRepository,
)

pytestmark = [pytest.mark.integration]


# --- Test-Builders -----------------------------------------------------------


def _new_doc(
    *,
    ticker: str = "AAPL",
    doc_type: str = "10-K",
    url: str | None = None,
) -> Document:
    return Document(
        id=uuid.uuid4(),
        ticker=ticker,
        doc_type=doc_type,
        filing_date=date(2024, 1, 1),
        url=url or f"https://sec.gov/{uuid.uuid4()}.pdf",
        raw_text_hash=None,
        ingested_at=datetime.now(UTC),
    )


def _new_chunk(
    *,
    document_id: uuid.UUID,
    chunk_idx: int = 0,
    content: str | None = None,
) -> EmbeddingChunk:
    return EmbeddingChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        chunk_idx=chunk_idx,
        content=content or f"chunk content {chunk_idx}",
        embedding=[0.1] * EMBEDDING_DIM,
        metadata={"section": "Risk Factors"},
    )


def _unique_ticker() -> str:
    """Eindeutiger 6-stelliger Ticker pro Test-Lauf — verhindert Akkumulation
    aus vorherigen Runs (Test-DB ist persistent zwischen Tests)."""
    return f"T{uuid.uuid4().hex[:5].upper()}"


# --- Fixtures ----------------------------------------------------------------


@pytest_asyncio.fixture
async def repo(
    session_factory: async_sessionmaker[AsyncSession],
) -> SQLAEmbeddingRepository:
    """SUT: Repository mit echter session_factory (von conftest)."""
    return SQLAEmbeddingRepository(session_factory)


# --- Tests -------------------------------------------------------------------


class TestSaveAndGetDocument:
    async def test_roundtrip(self, repo: SQLAEmbeddingRepository) -> None:
        doc = _new_doc()
        await repo.save_document(doc)
        loaded = await repo.get_document_by_url(doc.url)
        assert loaded is not None
        assert loaded.id == doc.id
        assert loaded.ticker == doc.ticker
        assert loaded.doc_type == doc.doc_type

    async def test_get_missing_returns_none(self, repo: SQLAEmbeddingRepository) -> None:
        loaded = await repo.get_document_by_url("https://nowhere.example/x.pdf")
        assert loaded is None

    async def test_duplicate_url_raises(self, repo: SQLAEmbeddingRepository) -> None:
        url = f"https://sec.gov/dup-{uuid.uuid4()}.pdf"
        await repo.save_document(_new_doc(url=url))
        with pytest.raises(DuplicateUrl):
            await repo.save_document(_new_doc(url=url))


class TestSaveChunks:
    async def test_batch_insert(self, repo: SQLAEmbeddingRepository) -> None:
        doc = _new_doc()
        await repo.save_document(doc)
        chunks = [_new_chunk(document_id=doc.id, chunk_idx=i) for i in range(50)]
        await repo.save_chunks(chunks)
        assert await repo.count_chunks(doc.id) == 50

    async def test_empty_batch_is_noop(self, repo: SQLAEmbeddingRepository) -> None:
        doc = _new_doc()
        await repo.save_document(doc)
        await repo.save_chunks([])
        assert await repo.count_chunks(doc.id) == 0

    async def test_upsert_on_duplicate_chunk_idx(self, repo: SQLAEmbeddingRepository) -> None:
        """Re-Ingestion mit gleichem (document_id, chunk_idx) updated content."""
        doc = _new_doc()
        await repo.save_document(doc)
        first = _new_chunk(document_id=doc.id, chunk_idx=0, content="original")
        await repo.save_chunks([first])
        second = _new_chunk(document_id=doc.id, chunk_idx=0, content="updated")
        await repo.save_chunks([second])
        assert await repo.count_chunks(doc.id) == 1


class TestCascadeDelete:
    async def test_delete_document_deletes_chunks(
        self,
        repo: SQLAEmbeddingRepository,
        db_session: AsyncSession,
    ) -> None:
        doc = _new_doc()
        await repo.save_document(doc)
        await repo.save_chunks([_new_chunk(document_id=doc.id, chunk_idx=i) for i in range(5)])

        # Direkt via Session loeschen (kein delete_document im Slice-1-Port)
        await db_session.execute(delete(DocumentORM).where(DocumentORM.id == doc.id))
        await db_session.commit()

        assert await repo.count_chunks(doc.id) == 0


class TestListDocuments:
    async def test_list_all(self, repo: SQLAEmbeddingRepository) -> None:
        # Test-DB ist persistent zwischen Tests, daher unique URLs nutzen,
        # nicht 'genau N docs' asserten — sondern dass unsere docs drin sind.
        d1 = _new_doc(ticker=_unique_ticker())
        d2 = _new_doc(ticker=_unique_ticker())
        await repo.save_document(d1)
        await repo.save_document(d2)
        all_docs = await repo.list_documents()
        urls = {d.url for d in all_docs}
        assert d1.url in urls
        assert d2.url in urls

    async def test_filtered_by_ticker(self, repo: SQLAEmbeddingRepository) -> None:
        ticker_a = _unique_ticker()
        ticker_b = _unique_ticker()
        d_a = _new_doc(ticker=ticker_a)
        d_b = _new_doc(ticker=ticker_b)
        await repo.save_document(d_a)
        await repo.save_document(d_b)
        a_docs = await repo.list_documents(ticker=ticker_a)
        urls = {d.url for d in a_docs}
        assert d_a.url in urls
        assert d_b.url not in urls

    async def test_sorted_desc_by_ingested_at(self, repo: SQLAEmbeddingRepository) -> None:
        ticker = _unique_ticker()
        # Explizite ingested_at-Werte verhindern datetime.now()-µs-Race-Flakes.
        d_old_base = _new_doc(ticker=ticker)
        d_old = Document(
            id=d_old_base.id,
            ticker=d_old_base.ticker,
            doc_type=d_old_base.doc_type,
            filing_date=d_old_base.filing_date,
            url=d_old_base.url,
            raw_text_hash=d_old_base.raw_text_hash,
            ingested_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        d_new_base = _new_doc(ticker=ticker)
        d_new = Document(
            id=d_new_base.id,
            ticker=d_new_base.ticker,
            doc_type=d_new_base.doc_type,
            filing_date=d_new_base.filing_date,
            url=d_new_base.url,
            raw_text_hash=d_new_base.raw_text_hash,
            ingested_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        await repo.save_document(d_old)
        await repo.save_document(d_new)
        docs = await repo.list_documents(ticker=ticker)
        assert docs[0].url == d_new.url
        assert docs[-1].url == d_old.url
