"""Tests fuer Document-Entity (RAG Slice 1)."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from backend.domain.entities.document import Document

pytestmark = pytest.mark.unit


def _new_doc(**overrides: object) -> Document:
    base: dict[str, object] = {
        "id": uuid4(),
        "ticker": "AAPL",
        "doc_type": "10-K",
        "filing_date": date(2024, 1, 1),
        "url": "https://sec.gov/aapl-10k-2024.pdf",
        "raw_text_hash": None,
        "ingested_at": datetime.now(UTC),
    }
    base.update(overrides)
    return Document(**base)  # type: ignore[arg-type]


class TestDocument:
    def test_constructs_with_minimal_fields(self) -> None:
        doc = _new_doc()
        assert doc.ticker == "AAPL"
        assert doc.doc_type == "10-K"
        assert doc.raw_text_hash is None

    def test_frozen_prevents_reassignment(self) -> None:
        doc = _new_doc()
        with pytest.raises(FrozenInstanceError):
            doc.ticker = "MSFT"  # type: ignore[misc]

    def test_ingested_at_must_be_tz_aware(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _new_doc(ingested_at=datetime(2024, 1, 1))  # naive

    def test_doc_type_must_be_10k_or_10q(self) -> None:
        with pytest.raises(ValueError, match="doc_type"):
            _new_doc(doc_type="8-K")

    def test_accepts_10q(self) -> None:
        doc = _new_doc(doc_type="10-Q")
        assert doc.doc_type == "10-Q"

    def test_url_required_nonempty(self) -> None:
        with pytest.raises(ValueError, match="url"):
            _new_doc(url="")
