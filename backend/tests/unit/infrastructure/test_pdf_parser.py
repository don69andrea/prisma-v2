"""Unit-Tests für PdfParser."""

from __future__ import annotations

import pytest

from backend.infrastructure.adapters.pdf_parser import CHUNK_OVERLAP, CHUNK_SIZE, PdfParser

pytestmark = pytest.mark.unit


class TestChunkText:
    def test_empty_text_returns_empty_list(self) -> None:
        parser = PdfParser()
        assert parser.chunk_text("") == []

    def test_whitespace_only_returns_empty(self) -> None:
        parser = PdfParser()
        assert parser.chunk_text("   \n\t  ") == []

    def test_short_text_single_chunk(self) -> None:
        parser = PdfParser()
        text = "Kurzer Text"
        result = parser.chunk_text(text, chunk_size=100, overlap=10)
        assert result == ["Kurzer Text"]

    def test_long_text_splits_into_multiple_chunks(self) -> None:
        parser = PdfParser()
        text = "A" * 1200
        chunks = parser.chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        assert len(chunks) > 1

    def test_chunks_have_correct_max_size(self) -> None:
        parser = PdfParser()
        text = "B" * 2000
        chunks = parser.chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        for chunk in chunks:
            assert len(chunk) <= CHUNK_SIZE

    def test_overlap_produces_continuity(self) -> None:
        parser = PdfParser()
        text = "X" * 600
        chunks = parser.chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        assert len(chunks) >= 2

    def test_exact_chunk_size_single_chunk(self) -> None:
        parser = PdfParser()
        text = "C" * CHUNK_SIZE
        chunks = parser.chunk_text(text)
        assert len(chunks) == 1

    def test_strips_whitespace_from_chunks(self) -> None:
        parser = PdfParser()
        text = "  hello  " + " " * 600
        chunks = parser.chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        assert all(chunk == chunk.strip() for chunk in chunks)


class TestExtractText:
    def test_invalid_bytes_returns_empty_string(self) -> None:
        parser = PdfParser()
        result = parser.extract_text(b"not a pdf at all")
        assert result == ""

    def test_empty_bytes_returns_empty_string(self) -> None:
        parser = PdfParser()
        result = parser.extract_text(b"")
        assert result == ""
