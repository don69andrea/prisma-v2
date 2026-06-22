"""RED test stub — NewsRetrievalResult must have url:str field (REQ-4-04).

Status: RED until backend/domain/entities/news_retrieval_result.py adds `url: str`
field (plan 04-01).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 22, 10, 0, 0, tzinfo=UTC)


def _make_result(**kwargs) -> object:
    from backend.domain.entities.news_retrieval_result import NewsRetrievalResult

    defaults = dict(
        chunk_id=uuid4(),
        news_document_id=uuid4(),
        chunk_idx=0,
        content="BTC sentiment is positive after halving.",
        similarity=0.87,
        title="BTC Halving Impact on Sentiment",
        url="https://cryptopanic.com/news/456/btc-halving",
        source="CRYPTOPANIC",
        tickers=("BTC",),
        published_at=_NOW,
        metadata={"source": "CRYPTOPANIC", "tickers": ["BTC"]},
    )
    defaults.update(kwargs)
    return NewsRetrievalResult(**defaults)


class TestNewsRetrievalResultUrlField:
    """REQ-4-04: NewsRetrievalResult must expose url:str for SentimentView.sources."""

    def test_result_has_url_field(self) -> None:
        """NewsRetrievalResult must accept and expose a url field."""
        result = _make_result(url="https://cryptopanic.com/news/456/btc-halving")
        assert hasattr(result, "url")
        assert result.url == "https://cryptopanic.com/news/456/btc-halving"

    def test_url_is_string(self) -> None:
        """url field must be a str."""
        result = _make_result()
        assert isinstance(result.url, str)

    def test_url_round_trips(self) -> None:
        """url passed in must equal url read back (frozen dataclass)."""
        url = "https://cryptopanic.com/news/789/eth-merge-update"
        result = _make_result(url=url)
        assert result.url == url

    def test_existing_fields_still_present(self) -> None:
        """Adding url must not break existing fields (non-regression)."""
        result = _make_result()
        assert hasattr(result, "chunk_id")
        assert hasattr(result, "content")
        assert hasattr(result, "similarity")
        assert hasattr(result, "title")
        assert hasattr(result, "source")
        assert hasattr(result, "tickers")
        assert hasattr(result, "published_at")
        assert hasattr(result, "metadata")
