"""RssNewsAdapter — Fetcht + parst CH-Finanz-RSS-Feeds (NZZ / SRF).

Verwendet httpx für HTTP mit Timeout+Retry, stdlib xml.etree für Parsing.
Kein feedparser-Dependency — nur stdlib + httpx (bereits in pyproject.toml).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

_logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]  # Exponential Backoff in Sekunden


@dataclass(frozen=True)
class RawArticle:
    url: str
    title: str
    content: str  # description / summary aus RSS
    published_at: datetime | None
    source: str


class RssNewsAdapter:
    """Fetcht einen RSS-Feed und gibt rohe Artikel zurück.

    Nicht mockbar via Interface — Tests patchen `httpx.AsyncClient.get`.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch_articles(self, source: str, feed_url: str) -> list[RawArticle]:
        """Fetcht `feed_url` und parst alle <item>-Elemente."""
        import asyncio

        for attempt, backoff in enumerate(_RETRY_BACKOFF, start=1):
            try:
                xml_text = await self._fetch_raw(feed_url)
                return _parse_rss(xml_text, source)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= _MAX_RETRIES:
                    _logger.error("RSS fetch failed after %d attempts: %s", _MAX_RETRIES, exc)
                    raise
                _logger.warning("RSS fetch attempt %d failed, retrying in %.1fs", attempt, backoff)
                await asyncio.sleep(backoff)
        return []  # unreachable — loop always raises on last attempt

    async def _fetch_raw(self, url: str) -> str:
        if self._client is not None:
            resp = await self._client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text


def _parse_rss(xml_text: str, source: str) -> list[RawArticle]:
    articles: list[RawArticle] = []
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 — RSS is trusted internal config
    except ET.ParseError as exc:
        _logger.error("RSS XML parse error: %s", exc)
        return []

    channel = root.find("channel")
    items = root.findall(".//item") if channel is None else channel.findall("item")

    for item in items:
        link = _text(item, "link") or _text(item, "guid")
        title = _text(item, "title")
        if not link or not title:
            continue
        description = _text(item, "description") or ""
        pub_date_raw = _text(item, "pubDate")
        published_at = _parse_date(pub_date_raw)
        articles.append(
            RawArticle(
                url=link.strip(),
                title=title.strip(),
                content=description.strip(),
                published_at=published_at,
                source=source,
            )
        )
    return articles


def _text(element: ET.Element, tag: str) -> str | None:
    child = element.find(tag)
    return child.text if child is not None else None


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return dt.astimezone(UTC)
    except Exception:
        return None
