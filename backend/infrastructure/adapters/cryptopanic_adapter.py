"""CryptoPanicAdapter — Fetcht Krypto-News aus der CryptoPanic Free API.

Verwendet httpx fuer HTTP mit Timeout+Retry (identisch zu RssNewsAdapter).
JSON-Parsing ist defensiv: malformed JSON oder fehlende Felder → [] (T-4-02).
Votes (positive/negative) defaulten zu 0 wenn subfield fehlt (A2 safety rule).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

_logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]  # Exponential Backoff in Sekunden

_BASE_URL = "https://cryptopanic.com/api/v1/posts/"
_MAX_ARTICLES = 50  # D-02: 50 articles per coin per run


@dataclass(frozen=True)
class RawCryptoPanicArticle:
    """Rohdaten eines CryptoPanic-Artikels fuer die News-RAG-Pipeline.

    votes_positive/votes_negative: immer int, defaulten zu 0 wenn fehlt (A2).
    currencies: Liste von Coin-Tickern aus dem currencies[].code-Feld.
    published_at: UTC-aware datetime oder None wenn nicht parsebar.
    """

    url: str
    title: str
    published_at: datetime | None
    votes_positive: int
    votes_negative: int
    currencies: list[str]


class CryptoPanicAdapter:
    """Fetcht Krypto-News aus der CryptoPanic Free API (auth_token=free).

    Nicht mockbar via Interface — Tests uebergeben httpx.AsyncClient-Mock
    als Constructor-Parameter (identisch zu RssNewsAdapter-Pattern).
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch_articles(self, coin: str) -> list[RawCryptoPanicArticle]:
        """Fetcht bis zu _MAX_ARTICLES News-Artikel fuer `coin` von der CryptoPanic API.

        Retry-Logik identisch zu RssNewsAdapter: 3 Versuche mit Backoff [1.0, 2.0, 4.0]s.
        Bei JSON-Parsefehler oder fehlendem 'results'-Key: return [] (T-4-02).
        """
        params = {
            "auth_token": "free",
            "currencies": coin,
            "kind": "news",
            "public": "true",
        }
        for attempt, backoff in enumerate(_RETRY_BACKOFF, start=1):
            try:
                raw_json = await self._fetch_raw(params)
                return _parse_response(raw_json)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= _MAX_RETRIES:
                    _logger.error(
                        "CryptoPanic fetch failed after %d attempts: %s",
                        _MAX_RETRIES,
                        exc,
                    )
                    raise
                _logger.warning(
                    "CryptoPanic attempt %d failed, retrying in %.1fs",
                    attempt,
                    backoff,
                )
                await asyncio.sleep(backoff)
        return []  # unreachable — loop always raises on last attempt

    async def _fetch_raw(self, params: dict[str, str]) -> dict:  # type: ignore[type-arg]
        """HTTP GET gegen CryptoPanic API. Gibt geparsten JSON-Dict zurueck.

        Bei JSON-Dekodierungsfehler (JSONDecodeError, DecodingError): logge und return {}
        → _parse_response({}) gibt [] zurueck (T-4-02 Threat Mitigation).
        """
        if self._client is not None:
            resp = await self._client.get(_BASE_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            try:
                return resp.json()  # type: ignore[no-any-return]
            except (json.JSONDecodeError, httpx.DecodingError, ValueError) as exc:
                _logger.error("CryptoPanic JSON parse error: %s", exc)
                return {}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            try:
                return resp.json()  # type: ignore[no-any-return]
            except (json.JSONDecodeError, httpx.DecodingError, ValueError) as exc:
                _logger.error("CryptoPanic JSON parse error: %s", exc)
                return {}


def _parse_response(raw_json: dict) -> list[RawCryptoPanicArticle]:  # type: ignore[type-arg]
    """Parst die CryptoPanic API-Antwort in RawCryptoPanicArticle-Objekte.

    Defensives Parsing:
    - Fehlendes 'results'-Key → return []
    - Fehlendes 'votes'-Dict oder fehlende Subfelder → default 0 (A2 safety rule)
    - Unparsebares 'published_at' → None (nicht abbrechen)
    - Ergebnis auf _MAX_ARTICLES beschraenkt (D-02)
    """
    try:
        results = raw_json.get("results")
    except (AttributeError, TypeError, KeyError) as exc:
        _logger.error("CryptoPanic response parsing error: %s", exc)
        return []

    if not results:
        return []

    articles: list[RawCryptoPanicArticle] = []
    for entry in results:
        try:
            url = entry.get("url", "")
            title = entry.get("title", "")
            if not url or not title:
                continue

            # Votes: defensives .get mit Default 0 (A2 safety rule)
            votes = entry.get("votes") or {}
            votes_positive = int(votes.get("positive", 0))
            votes_negative = int(votes.get("negative", 0))

            # Currencies: extrahiere .code aus jedem Eintrag
            currencies_raw = entry.get("currencies") or []
            currencies = [
                c["code"] for c in currencies_raw if isinstance(c, dict) and "code" in c
            ]

            # published_at: parse ISO-8601 zu UTC-aware datetime
            published_at = _parse_datetime(entry.get("published_at"))

            articles.append(
                RawCryptoPanicArticle(
                    url=url,
                    title=title,
                    published_at=published_at,
                    votes_positive=votes_positive,
                    votes_negative=votes_negative,
                    currencies=currencies,
                )
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Skipping CryptoPanic entry due to parse error: %s", exc)
            continue

    # D-02: Cap to _MAX_ARTICLES
    return articles[:_MAX_ARTICLES]


def _parse_datetime(raw: str | None) -> datetime | None:
    """Parst ISO-8601 Datetime-String zu UTC-aware datetime.

    CLAUDE.md: niemals naive datetime verwenden — immer UTC-aware.
    """
    if not raw:
        return None
    try:
        # Parse ISO-8601 format (e.g. "2026-06-22T08:30:00Z")
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(UTC)
    except (ValueError, AttributeError):
        _logger.warning("Could not parse CryptoPanic published_at: %r", raw)
        return None
