"""Swiss RAG Filings Ingestion — SIX Exchange Jahresberichte.

Scrapt PDF-Links für SMI-Titel, extrahiert Text via pypdf,
chunked (512 Zeichen / 64 Overlap), bettet mit Voyage AI ein,
speichert in swiss_rag_chunks (idempotent).

Erfordert: VOYAGE_API_KEY und DATABASE_URL in der Umgebung.

Ausführung:
    python -m scripts.ingest_swiss_filings [--tickers NESN NOVN ROG] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime

import httpx

from backend.domain.entities.swiss_filing_chunk import SwissFilingChunk
from backend.infrastructure.adapters.pdf_parser import PdfParser
from backend.infrastructure.adapters.six_filings_adapter import SixFilingsAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_logger = logging.getLogger(__name__)

# Standard SMI-Titelauswahl
_DEFAULT_TICKERS = [
    "NESN",
    "NOVN",
    "ROG",
    "ABBN",
    "ZURN",
    "ADEN",
    "GIVN",
    "SREN",
    "LONN",
    "PGHN",
]

_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def ingest_ticker(
    ticker: str,
    adapter: SixFilingsAdapter,
    parser: PdfParser,
    repo: object,
    voyage: object,
    dry_run: bool,
    limit_chunks: int | None = None,
    batch_delay: float = 0.0,
) -> dict[str, int]:
    from backend.infrastructure.persistence.repositories.swiss_filing_repository import (
        SQLASwissFilingRepository,
    )

    assert isinstance(repo, SQLASwissFilingRepository)

    stats = {"ingested": 0, "skipped_duplicate": 0, "errors": 0}
    links = await adapter.get_filing_links(ticker)
    if not links:
        _logger.info("%s: keine Filing-Links gefunden", ticker)
        return stats

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        for link in links:
            _logger.info("%s: Verarbeite %s ...", ticker, link.url[:70])
            try:
                resp = await client.get(link.url)
                resp.raise_for_status()
                pdf_bytes = resp.content
            except Exception as exc:
                _logger.warning("%s: HTTP-Fehler für %s — %s", ticker, link.url[:60], exc)
                stats["errors"] += 1
                continue

            text = parser.extract_text(pdf_bytes)
            if not text.strip():
                _logger.warning("%s: Kein Text extrahierbar aus %s", ticker, link.url[:60])
                stats["errors"] += 1
                continue

            chunks_text = parser.chunk_text(text)
            url_hash = SwissFilingChunk.hash_url(link.url)
            now = datetime.now(UTC)

            new_chunks: list[SwissFilingChunk] = []
            for idx, chunk_content in enumerate(chunks_text):
                if await repo.exists_by_url_hash_and_chunk(url_hash, idx):
                    stats["skipped_duplicate"] += 1
                    continue
                new_chunks.append(
                    SwissFilingChunk(
                        id=uuid.uuid4(),
                        url_hash=url_hash,
                        url=link.url,
                        ticker=link.ticker,
                        source=link.source,
                        language=link.language,
                        filing_date=link.filing_date,
                        doc_type=link.doc_type,
                        chunk_idx=idx,
                        content=chunk_content,
                        embedding=[],  # placeholder — wird gleich befüllt
                        metadata={"doc_type": link.doc_type, "source": link.source},
                        ingested_at=now,
                    )
                )

            if not new_chunks:
                _logger.info("%s: Alle Chunks bereits bekannt, überspringe", ticker)
                continue

            if limit_chunks is not None:
                new_chunks = new_chunks[:limit_chunks]

            if dry_run:
                _logger.info("%s [DRY-RUN]: würde %d Chunks einbetten", ticker, len(new_chunks))
                stats["ingested"] += len(new_chunks)
                continue

            # Voyage AI embedding — 8 Chunks/Batch, Delay für Rate-Limit (3 RPM Free Tier)
            import time
            _BATCH = 8
            embedded: list[SwissFilingChunk] = []
            for batch_start in range(0, len(new_chunks), _BATCH):
                batch = new_chunks[batch_start : batch_start + _BATCH]
                contents = [c.content for c in batch]
                result = voyage.embed(contents, model="voyage-3-large")  # type: ignore[union-attr]
                for chunk, emb in zip(batch, result.embeddings, strict=True):
                    embedded.append(
                        SwissFilingChunk(
                            id=chunk.id,
                            url_hash=chunk.url_hash,
                            url=chunk.url,
                            ticker=chunk.ticker,
                            source=chunk.source,
                            language=chunk.language,
                            filing_date=chunk.filing_date,
                            doc_type=chunk.doc_type,
                            chunk_idx=chunk.chunk_idx,
                            content=chunk.content,
                            embedding=emb,
                            metadata=chunk.metadata,
                            ingested_at=chunk.ingested_at,
                        )
                    )
                if batch_delay > 0 and batch_start + _BATCH < len(new_chunks):
                    _logger.info("Rate-Limit Pause: %.0fs ...", batch_delay)
                    time.sleep(batch_delay)

            await repo.save_chunks(embedded)
            stats["ingested"] += len(embedded)
            _logger.info("%s: %d Chunks eingebettet und gespeichert", ticker, len(embedded))

    return stats


async def main(tickers: list[str], dry_run: bool, limit_chunks: int | None = None, batch_delay: float = 0.0) -> None:
    import voyageai
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from backend.infrastructure.persistence.repositories.swiss_filing_repository import (
        SQLASwissFilingRepository,
    )

    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://prisma:prisma@localhost:5432/prisma"
    )
    voyage_key = os.environ.get("VOYAGE_API_KEY", "")
    if not voyage_key and not dry_run:
        _logger.error("VOYAGE_API_KEY nicht gesetzt")
        return

    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    repo = SQLASwissFilingRepository(session_factory=factory)
    voyage = voyageai.Client(api_key=voyage_key) if voyage_key else None  # type: ignore[attr-defined]
    parser = PdfParser()

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as http_client:
        adapter = SixFilingsAdapter(http_client=http_client)
        total_ingested = total_skipped = total_errors = 0
        for ticker in tickers:
            stats = await ingest_ticker(ticker, adapter, parser, repo, voyage, dry_run, limit_chunks=limit_chunks, batch_delay=batch_delay)
            total_ingested += stats["ingested"]
            total_skipped += stats["skipped_duplicate"]
            total_errors += stats["errors"]

    await engine.dispose()
    _logger.info(
        "Fertig: %d eingebettet, %d übersprungen, %d Fehler",
        total_ingested,
        total_skipped,
        total_errors,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Swiss RAG Filings Ingestion")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=_DEFAULT_TICKERS,
        help="Ticker-Symbole (default: SMI-Auswahl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Keine DB-Schreibzugriffe, nur Zählen",
    )
    parser.add_argument(
        "--limit-chunks",
        type=int,
        default=None,
        metavar="N",
        help="Max Chunks pro Filing (für Demo/Free-Tier: z.B. 50)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=21.0,
        metavar="SEC",
        help="Pause zwischen Embedding-Batches in Sekunden (default 21 für 3 RPM Free Tier)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(
        tickers=args.tickers,
        dry_run=args.dry_run,
        limit_chunks=args.limit_chunks,
        batch_delay=args.batch_delay,
    ))
