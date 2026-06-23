"""NewsIngestionService — Orchestriert RSS-Ingestion, Ticker-NER, Chunking, Embedding."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from backend.domain.entities.news_article import NewsArticle
from backend.domain.entities.news_chunk import NewsChunk
from backend.domain.repositories.embedding_repository import DuplicateUrl
from backend.domain.repositories.news_repository import NewsRepository
from backend.infrastructure.adapters.rss_news_adapter import RssNewsAdapter
from backend.infrastructure.adapters.ticker_ner import TickerNer
from backend.infrastructure.llm.client import LLMClient

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

_logger = logging.getLogger(__name__)

_CHUNK_SIZE = 512  # chars per chunk
_CHUNK_OVERLAP = 64  # overlap between chunks
_CRYPTOPANIC_TTL_DAYS = 7  # D-02: skip articles older than 7 days


# NZZ + SRF RSS feed URLs — environment-independent defaults.
# Production kann diese via Settings überschreiben (future: settings.rss_feeds).
DEFAULT_FEEDS: list[tuple[str, str]] = [
    ("NZZ", "https://www.nzz.ch/finanzen.rss"),
    ("SRF", "https://www.srf.ch/news/bnf/rss/1646"),
]


class NewsIngestionService:
    def __init__(
        self,
        news_repo: NewsRepository,
        rss_adapter: RssNewsAdapter,
        ticker_ner: TickerNer,
        llm_client: LLMClient,
        feeds: list[tuple[str, str]] | None = None,
        cryptopanic_adapter: CryptoPanicAdapter | None = None,
    ) -> None:
        self._repo = news_repo
        self._rss = rss_adapter
        self._ner = ticker_ner
        self._llm = llm_client
        self._feeds = feeds if feeds is not None else DEFAULT_FEEDS
        self._cryptopanic = cryptopanic_adapter

    async def ingest_all(self) -> dict[str, int]:
        """Ingested alle konfigurierten RSS-Feeds. Gibt Statistiken zurück."""
        stats: dict[str, int] = {"ingested": 0, "skipped_duplicate": 0, "errors": 0}
        for source, feed_url in self._feeds:
            try:
                result = await self._ingest_feed(source, feed_url)
                stats["ingested"] += result["ingested"]
                stats["skipped_duplicate"] += result["skipped_duplicate"]
                stats["errors"] += result["errors"]
            except Exception as exc:
                _logger.error("Feed ingestion failed for %s: %s", source, exc)
                stats["errors"] += 1
        return stats

    async def ingest_cryptopanic(self, coins: list[str]) -> dict[str, int]:
        """Ingestiert CryptoPanic-News für die angegebenen Coins.

        D-02: Artikel älter als 7 Tage werden übersprungen (TTL-Filter).
        D-02: url_hash-Dedup verhindert Re-Embedding.
        C-02 (Pitfall 6): chunk.metadata enthält votes_positive + votes_negative,
               damit D-03-Score-Formel Abstimmungsdaten lesen kann.
        D-07: Ticker aus raw.currencies — kein TickerNer-Aufruf.

        Returns:
            dict mit Schlüsseln "ingested", "skipped_duplicate", "errors".
        """
        if self._cryptopanic is None:
            return {"ingested": 0, "skipped_duplicate": 0, "errors": 0}
        stats: dict[str, int] = {"ingested": 0, "skipped_duplicate": 0, "errors": 0}
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=_CRYPTOPANIC_TTL_DAYS)

        for coin in coins:
            try:
                articles = await self._cryptopanic.fetch_articles(coin)
            except Exception as exc:
                _logger.error("CryptoPanic fetch failed for coin %s: %s", coin, exc)
                stats["errors"] += 1
                continue

            for raw in articles:
                try:
                    # D-02 TTL filter: skip articles older than 7 days
                    if raw.published_at is not None and raw.published_at < cutoff:
                        _logger.debug(
                            "Skipping old CryptoPanic article %s (published_at=%s)",
                            raw.url,
                            raw.published_at,
                        )
                        continue

                    # D-02 dedup: skip already-ingested URLs
                    url_hash = NewsArticle.hash_url(raw.url)
                    if await self._repo.exists_by_url_hash(url_hash):
                        stats["skipped_duplicate"] += 1
                        continue

                    # D-07: use currencies as tickers, no TickerNer
                    tickers: tuple[str, ...] = tuple(raw.currencies)
                    article = NewsArticle(
                        id=uuid.uuid4(),
                        url=raw.url,
                        url_hash=url_hash,
                        title=raw.title,
                        content=raw.title,  # CryptoPanic free API has no body
                        published_at=raw.published_at,
                        source="CRYPTOPANIC",
                        tickers=tickers,
                        ingested_at=now,
                    )

                    try:
                        await self._repo.save_article(article)
                    except DuplicateUrl:
                        stats["skipped_duplicate"] += 1
                        continue

                    # C-02 (Pitfall 6): chunk metadata MUST carry votes
                    chunk_metadata = {
                        "source": "CRYPTOPANIC",
                        "tickers": tickers,
                        "votes_positive": raw.votes_positive,
                        "votes_negative": raw.votes_negative,
                    }
                    chunks = _chunk_text_with_metadata(article, chunk_metadata)
                    if chunks:
                        texts = [c.content for c in chunks]
                        embeddings = await self._llm.embed(
                            texts=texts,
                            model="voyage-3-large",
                            feature="news_rag_ingestion",
                        )
                        if len(embeddings) != len(chunks):
                            _logger.error(
                                "Embedding count mismatch for %s: expected %d, got %d — skipping chunks",
                                raw.url,
                                len(chunks),
                                len(embeddings),
                            )
                            stats["errors"] += 1
                            continue
                        enriched = [
                            NewsChunk(
                                id=c.id,
                                news_document_id=c.news_document_id,
                                chunk_idx=c.chunk_idx,
                                content=c.content,
                                embedding=embeddings[i],
                                metadata=c.metadata,
                            )
                            for i, c in enumerate(chunks)
                        ]
                        await self._repo.save_chunks(enriched)

                    stats["ingested"] += 1
                    _logger.info(
                        "Ingested CryptoPanic article: %s (tickers=%s, votes+=%d, votes-=%d)",
                        raw.url,
                        tickers,
                        raw.votes_positive,
                        raw.votes_negative,
                    )
                except Exception as exc:
                    _logger.error("Failed to ingest CryptoPanic article %s: %s", raw.url, exc)
                    stats["errors"] += 1

        return stats

    async def _ingest_feed(self, source: str, feed_url: str) -> dict[str, int]:
        articles = await self._rss.fetch_articles(source=source, feed_url=feed_url)
        stats: dict[str, int] = {"ingested": 0, "skipped_duplicate": 0, "errors": 0}

        for raw in articles:
            try:
                url_hash = NewsArticle.hash_url(raw.url)
                if await self._repo.exists_by_url_hash(url_hash):
                    stats["skipped_duplicate"] += 1
                    continue

                tickers = self._ner.extract(f"{raw.title} {raw.content}")
                now = datetime.now(UTC)
                article = NewsArticle(
                    id=uuid.uuid4(),
                    url=raw.url,
                    url_hash=url_hash,
                    title=raw.title,
                    content=raw.content,
                    published_at=raw.published_at,
                    source=raw.source,
                    tickers=tickers,
                    ingested_at=now,
                )

                try:
                    await self._repo.save_article(article)
                except DuplicateUrl:
                    stats["skipped_duplicate"] += 1
                    continue

                chunks = _chunk_text(article)
                if chunks:
                    texts = [c.content for c in chunks]
                    embeddings = await self._llm.embed(
                        texts=texts,
                        model="voyage-3-large",
                        feature="news_rag_ingestion",
                    )
                    if len(embeddings) != len(chunks):
                        _logger.error(
                            "Embedding count mismatch for %s: expected %d, got %d — skipping chunks",
                            raw.url,
                            len(chunks),
                            len(embeddings),
                        )
                        stats["errors"] += 1
                        continue
                    enriched = [
                        NewsChunk(
                            id=c.id,
                            news_document_id=c.news_document_id,
                            chunk_idx=c.chunk_idx,
                            content=c.content,
                            embedding=embeddings[i],
                            metadata=c.metadata,
                        )
                        for i, c in enumerate(chunks)
                    ]
                    await self._repo.save_chunks(enriched)

                stats["ingested"] += 1
                _logger.info("Ingested news article: %s (tickers=%s)", raw.url, tickers)
            except Exception as exc:
                _logger.error("Failed to ingest article %s: %s", raw.url, exc)
                stats["errors"] += 1

        return stats


def _chunk_text_with_metadata(article: NewsArticle, metadata: dict[str, Any]) -> list[NewsChunk]:
    """Chunk article text using the provided metadata dict for each chunk.

    Used by ingest_cryptopanic() to inject votes_positive/votes_negative (C-02).
    """
    full_text = f"{article.title}\n\n{article.content}"
    chunks: list[NewsChunk] = []
    start = 0
    idx = 0
    while start < len(full_text):
        end = start + _CHUNK_SIZE
        content = full_text[start:end].strip()
        if content:
            chunks.append(
                NewsChunk(
                    id=uuid.uuid4(),
                    news_document_id=article.id,
                    chunk_idx=idx,
                    content=content,
                    embedding=[0.0] * 2048,  # placeholder — replaced after embed()
                    metadata=metadata,
                )
            )
            idx += 1
        start = end - _CHUNK_OVERLAP
    return chunks


def _chunk_text(article: NewsArticle) -> list[NewsChunk]:
    full_text = f"{article.title}\n\n{article.content}"
    chunks: list[NewsChunk] = []
    start = 0
    idx = 0
    while start < len(full_text):
        end = start + _CHUNK_SIZE
        content = full_text[start:end].strip()
        if content:
            chunks.append(
                NewsChunk(
                    id=uuid.uuid4(),
                    news_document_id=article.id,
                    chunk_idx=idx,
                    content=content,
                    embedding=[0.0] * 2048,  # placeholder — replaced after embed()
                    metadata={"source": article.source, "tickers": list(article.tickers)},
                )
            )
            idx += 1
        start = end - _CHUNK_OVERLAP
    return chunks
