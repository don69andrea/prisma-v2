"""Unit-Tests für NewsRetrievalResult-Entity.

Phase 04-01/04-02 TDD: verify url field exists (B-02 / D-07 / REQ-4-04).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.domain.entities.news_retrieval_result import NewsRetrievalResult

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 22, 8, 0, 0, tzinfo=UTC)


def _result(**kwargs: object) -> NewsRetrievalResult:
    defaults = dict(
        chunk_id=uuid4(),
        news_document_id=uuid4(),
        chunk_idx=0,
        content="BTC hits ATH on institutional demand.",
        similarity=0.92,
        title="BTC hits ATH",
        url="https://cryptopanic.com/news/1/btc-hits-ath",
        source="CRYPTOPANIC",
        tickers=("BTC",),
        published_at=_NOW,
        metadata={},
    )
    defaults.update(kwargs)
    return NewsRetrievalResult(**defaults)  # type: ignore[arg-type]


class TestNewsRetrievalResult:
    def test_url_field_exists_and_roundtrips(self) -> None:
        """NewsRetrievalResult must have url: str field (B-02 — SentimentView.sources)."""
        r = _result()
        assert r.url == "https://cryptopanic.com/news/1/btc-hits-ath"

    def test_url_field_is_str(self) -> None:
        """url field type must be str."""
        r = _result(url="https://example.com/news/2")
        assert isinstance(r.url, str)

    def test_url_field_roundtrips_arbitrary_value(self) -> None:
        """url field preserves the exact value passed in."""
        url = "https://cryptopanic.com/news/42/eth-upgrade"
        r = _result(url=url)
        assert r.url == url

    def test_all_existing_fields_still_present(self) -> None:
        """Regression: existing fields must still be accessible after url addition."""
        r = _result()
        assert r.chunk_id is not None
        assert r.news_document_id is not None
        assert r.chunk_idx == 0
        assert r.content == "BTC hits ATH on institutional demand."
        assert r.similarity == 0.92
        assert r.title == "BTC hits ATH"
        assert r.source == "CRYPTOPANIC"
        assert r.tickers == ("BTC",)
        assert r.published_at == _NOW
        assert r.metadata == {}
