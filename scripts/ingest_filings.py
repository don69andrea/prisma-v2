"""RAG-Ingestion: SEC-EDGAR 10-K/10-Q → Text-Chunks → Voyage-Embedding → pgvector.

ADR-0004 §3: 5 Ticker, je 2 Filings (1x 10-K + 1x 10-Q), ~800-Token-Chunks
mit 100-Token-Overlap → ~4000 Chunks total.

Voraussetzungen:
    VOYAGE_API_KEY=vk-...
    DATABASE_URL=postgresql+asyncpg://...  (oder default aus .env)

Ausfuehrung (einmalig, z.B. via Render Shell-Tab):
    source .venv/bin/activate
    python scripts/ingest_filings.py

Re-Ingestion ist idempotent: bestehende Chunks werden per UPSERT aktualisiert,
bekannte URLs werden uebersprungen (DuplicateUrl-Exception → logged + skipped).

Kosten: ~$0.24 Voyage-Embedding (ADR-0004 §7).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import sys
import time
import uuid
from datetime import UTC, date, datetime

import httpx
import voyageai

from backend.config import get_settings
from backend.domain.entities.document import Document
from backend.domain.entities.embedding_chunk import EMBEDDING_DIM, EmbeddingChunk
from backend.domain.repositories.embedding_repository import DuplicateUrl
from backend.infrastructure.persistence.repositories.embedding_repository import (
    SQLAEmbeddingRepository,
)
from backend.infrastructure.persistence.session import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ADR-0004 §3: 5 Ticker, je 1x 10-K + 1x 10-Q = 10 Filings total
_TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "JPM"]

# Hardcoded CIK-Nummern (SEC-EDGAR eindeutige Unternehmens-IDs)
_CIK_MAP = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "NVDA": "0001045810",
    "JPM": "0000019617",
}

_EDGAR_BASE = "https://data.sec.gov"
_CHUNK_CHARS = 3200  # ~800 Tokens bei ~4 chars/token
_OVERLAP_CHARS = 400  # ~100 Tokens Overlap
_VOYAGE_MODEL = "voyage-3-large"
_VOYAGE_BATCH = 8  # Voyage-SDK sendet bis 128 Texte pro Request; konservativer Wert


def _chunk_text(text: str) -> list[str]:
    """Teilt Text in ueberlappende Chunks (~800 Tokens, 100 Overlap)."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_CHARS
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += _CHUNK_CHARS - _OVERLAP_CHARS
    return [c for c in chunks if len(c.strip()) > 50]  # Kurzchunks filtern


def _extract_text_from_html(html: str) -> str:
    """Einfaches HTML-zu-Text via stdlib html.parser (kein beautifulsoup noetig)."""
    import html as html_lib
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._parts: list[str] = []
            self._skip = False

        def handle_starttag(self, tag: str, attrs: list) -> None:
            if tag in ("script", "style", "head"):
                self._skip = True

        def handle_endtag(self, tag: str) -> None:
            if tag in ("script", "style", "head"):
                self._skip = False

        def handle_data(self, data: str) -> None:
            if not self._skip:
                stripped = data.strip()
                if stripped:
                    self._parts.append(stripped)

        def get_text(self) -> str:
            return " ".join(self._parts)

    parser = _TextExtractor()
    parser.feed(html_lib.unescape(html))
    # Normalisiere Whitespace
    return re.sub(r"\s+", " ", parser.get_text()).strip()


async def _get_recent_filings(
    client: httpx.AsyncClient, cik: str, form_types: list[str], count: int
) -> list[dict]:
    """Laedt die `count` neuesten Filings der angegebenen Typen via EDGAR submissions API."""
    url = f"{_EDGAR_BASE}/submissions/CIK{cik}.json"
    resp = await client.get(url, headers={"User-Agent": "PRISMA-Capstone contact@example.com"})
    resp.raise_for_status()
    data = resp.json()

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])

    results = []
    for form, filing_date, accession in zip(forms, dates, accessions, strict=False):
        if form in form_types and len(results) < count:
            results.append(
                {
                    "form": form,
                    "filing_date": filing_date,
                    "accession": accession.replace("-", ""),
                    "cik": cik,
                }
            )
    return results


async def _get_filing_text_url(client: httpx.AsyncClient, cik: str, accession: str) -> str | None:
    """Findet die URL des Haupt-Text-Dokuments aus dem Filing-Index."""
    index_url = f"{_EDGAR_BASE}/Archives/edgar/data/{int(cik)}/{accession}/{accession}-index.json"
    try:
        resp = await client.get(
            index_url, headers={"User-Agent": "PRISMA-Capstone contact@example.com"}
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        return None

    data = resp.json()
    for doc in data.get("documents", []):
        doc_type = doc.get("type", "").strip()
        name = doc.get("filename", "")
        # Bevorzuge HTM/HTML-Hauptdokument; TXT als Fallback
        if doc_type in ("10-K", "10-Q", "10-K/A", "10-Q/A") and name.lower().endswith(
            (".htm", ".html", ".txt")
        ):
            return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{name}"
    return None


async def _download_and_extract(client: httpx.AsyncClient, url: str) -> str:
    """Laedt ein Filing-Dokument und extrahiert reinen Text."""
    resp = await client.get(url, headers={"User-Agent": "PRISMA-Capstone contact@example.com"})
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "html" in content_type or url.endswith((".htm", ".html")):
        return _extract_text_from_html(resp.text)
    # Plaintext: strip SGML-Tags falls vorhanden
    return re.sub(r"<[^>]+>", " ", resp.text)


async def ingest() -> None:
    settings = get_settings()
    if not settings.voyage_api_key:
        log.error("VOYAGE_API_KEY nicht gesetzt — Abbruch.")
        sys.exit(1)

    voyage = voyageai.Client(api_key=settings.voyage_api_key)
    repo = SQLAEmbeddingRepository(session_factory=get_session_factory())

    total_chunks = 0
    total_docs = 0

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
        for ticker in _TICKERS:
            cik = _CIK_MAP[ticker]
            log.info("[%s] Suche Filings (CIK %s)...", ticker, cik)

            filings_10k = await _get_recent_filings(http, cik, ["10-K"], count=2)
            filings_10q = await _get_recent_filings(http, cik, ["10-Q"], count=2)
            filings = filings_10k + filings_10q
            if not filings:
                log.warning("[%s] Keine Filings gefunden — ueberspringe.", ticker)
                continue

            for filing in filings:
                filing_url = await _get_filing_text_url(http, cik, filing["accession"])
                if not filing_url:
                    log.warning(
                        "[%s] Kein Text-Dokument in %s — ueberspringe.", ticker, filing["accession"]
                    )
                    continue

                # Filing ueberspringen falls URL schon in DB
                existing = await repo.get_document_by_url(filing_url)
                if existing:
                    log.info("[%s] %s bereits ingested — ueberspringe.", ticker, filing["form"])
                    continue

                log.info("[%s] Lade %s %s...", ticker, filing["form"], filing_url)
                try:
                    raw_text = await _download_and_extract(http, filing_url)
                except Exception as exc:
                    log.error("[%s] Download fehlgeschlagen: %s", ticker, exc)
                    continue

                text_hash = hashlib.sha256(raw_text.encode()).hexdigest()
                doc = Document(
                    id=uuid.uuid4(),
                    ticker=ticker,
                    doc_type=filing["form"],
                    filing_date=date.fromisoformat(filing["filing_date"]),
                    url=filing_url,
                    raw_text_hash=text_hash,
                    ingested_at=datetime.now(tz=UTC),
                )

                try:
                    await repo.save_document(doc)
                except DuplicateUrl:
                    log.info("[%s] URL-Duplikat (race) — ueberspringe.", ticker)
                    continue

                chunks_text = _chunk_text(raw_text)
                log.info("[%s] %d Chunks → Voyage-Embedding...", ticker, len(chunks_text))

                all_embeddings: list[list[float]] = []
                for i in range(0, len(chunks_text), _VOYAGE_BATCH):
                    batch = chunks_text[i : i + _VOYAGE_BATCH]
                    t0 = time.perf_counter()
                    resp = voyage.embed(batch, model=_VOYAGE_MODEL)
                    elapsed = time.perf_counter() - t0
                    log.debug("  Batch %d-%d: %.2fs", i, i + len(batch), elapsed)
                    all_embeddings.extend(resp.embeddings)

                embedding_chunks = [
                    EmbeddingChunk(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        chunk_idx=idx,
                        content=text,
                        embedding=emb,
                        metadata={"ticker": ticker, "doc_type": filing["form"]},
                    )
                    for idx, (text, emb) in enumerate(zip(chunks_text, all_embeddings, strict=True))
                    if len(emb) == EMBEDDING_DIM
                ]

                await repo.save_chunks(embedding_chunks)
                log.info("[%s] %d Chunks gespeichert.", ticker, len(embedding_chunks))
                total_chunks += len(embedding_chunks)
                total_docs += 1

                await asyncio.sleep(0.5)  # EDGAR Rate-Limit: max 10 req/s

    log.info("Ingestion abgeschlossen: %d Docs, %d Chunks.", total_docs, total_chunks)


if __name__ == "__main__":
    asyncio.run(ingest())
