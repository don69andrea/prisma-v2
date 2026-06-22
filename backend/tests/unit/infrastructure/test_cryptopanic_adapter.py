"""RED test stub — CryptoPanicAdapter JSON parsing (REQ-4-01, T-4-02).

Status: RED until backend/infrastructure/adapters/cryptopanic_adapter.py
is implemented (plan 04-03).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Static CryptoPanic JSON fixture (from PATTERNS.md — no live API in tests)
# ---------------------------------------------------------------------------

_BTC_FIXTURE = {
    "results": [
        {
            "url": "https://cryptopanic.com/news/1/btc-hits-ath",
            "title": "BTC hits ATH",
            "published_at": "2026-06-22T08:30:00Z",
            "votes": {"positive": 11, "negative": 2},
            "currencies": [{"code": "BTC"}],
        }
    ]
}

_MULTI_COIN_FIXTURE = {
    "results": [
        {
            "url": "https://cryptopanic.com/news/2/btc-eth-news",
            "title": "BTC and ETH both rally",
            "published_at": "2026-06-22T09:00:00Z",
            "votes": {"positive": 8, "negative": 1},
            "currencies": [{"code": "BTC"}, {"code": "ETH"}],
        }
    ]
}

_MALFORMED_FIXTURE = b"this is not valid json {"

# ---------------------------------------------------------------------------
# Helper: build mock httpx response
# ---------------------------------------------------------------------------


def _make_mock_client(json_payload: Any) -> AsyncMock:
    """Return a mock httpx AsyncClient whose .get() returns json_payload."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_payload
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCryptoPanicAdapterParsing:
    """REQ-4-01: CryptoPanicAdapter.fetch_articles() parses votes and currencies."""

    async def test_fetch_articles_parses_votes_positive(self) -> None:
        """Adapter parses votes.positive == 11 from static fixture."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client(_BTC_FIXTURE)
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert len(articles) == 1
        assert articles[0].votes_positive == 11

    async def test_fetch_articles_parses_votes_negative(self) -> None:
        """Adapter parses votes.negative == 2 from static fixture."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client(_BTC_FIXTURE)
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert len(articles) == 1
        assert articles[0].votes_negative == 2

    async def test_fetch_articles_parses_currencies(self) -> None:
        """Adapter parses currencies[].code into currencies list."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client(_BTC_FIXTURE)
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert articles[0].currencies == ["BTC"]

    async def test_fetch_articles_url_parsed(self) -> None:
        """Adapter extracts url field from result."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client(_BTC_FIXTURE)
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert articles[0].url == "https://cryptopanic.com/news/1/btc-hits-ath"

    async def test_fetch_articles_title_parsed(self) -> None:
        """Adapter extracts title field."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client(_BTC_FIXTURE)
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert articles[0].title == "BTC hits ATH"

    async def test_fetch_articles_multi_currency(self) -> None:
        """Adapter handles articles tagged with multiple currencies."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client(_MULTI_COIN_FIXTURE)
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert len(articles) == 1
        assert "BTC" in articles[0].currencies
        assert "ETH" in articles[0].currencies


class TestCryptoPanicAdapterErrorHandling:
    """T-4-02: Malformed JSON → adapter returns [] (does not raise)."""

    async def test_malformed_json_returns_empty_list(self) -> None:
        """Adapter returns [] on JSON decode error — does not propagate exception."""
        import json

        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_resp = MagicMock()
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert articles == []

    async def test_missing_results_key_returns_empty_list(self) -> None:
        """Adapter returns [] if API response has no 'results' key."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client({"error": "rate limited"})
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert articles == []

    async def test_empty_results_returns_empty_list(self) -> None:
        """Adapter returns [] if API returns empty results list."""
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_client = _make_mock_client({"results": []})
        adapter = CryptoPanicAdapter(client=mock_client)
        articles = await adapter.fetch_articles("BTC")

        assert articles == []
