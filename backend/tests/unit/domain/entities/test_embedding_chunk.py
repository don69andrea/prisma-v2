"""Tests fuer EmbeddingChunk-Entity (RAG Slice 1)."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from backend.domain.entities.embedding_chunk import EMBEDDING_DIM, EmbeddingChunk

pytestmark = pytest.mark.unit


def _new_chunk(**overrides: object) -> EmbeddingChunk:
    base: dict[str, object] = {
        "id": uuid4(),
        "document_id": uuid4(),
        "chunk_idx": 0,
        "content": "sample chunk text",
        "embedding": [0.1] * EMBEDDING_DIM,
        "metadata": {},
    }
    base.update(overrides)
    return EmbeddingChunk(**base)  # type: ignore[arg-type]


class TestEmbeddingChunk:
    def test_constructs_happy(self) -> None:
        chunk = _new_chunk()
        assert chunk.chunk_idx == 0
        assert len(chunk.embedding) == EMBEDDING_DIM
        assert chunk.metadata == {}

    def test_frozen_prevents_reassignment(self) -> None:
        chunk = _new_chunk()
        with pytest.raises(FrozenInstanceError):
            chunk.chunk_idx = 1  # type: ignore[misc]

    def test_embedding_must_be_correct_dim(self) -> None:
        with pytest.raises(ValueError, match=f"embedding must be {EMBEDDING_DIM}-dim"):
            _new_chunk(embedding=[0.1] * 100)

    def test_chunk_idx_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="chunk_idx"):
            _new_chunk(chunk_idx=-1)

    def test_content_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="content"):
            _new_chunk(content="")

    def test_embedding_dim_constant(self) -> None:
        assert EMBEDDING_DIM == 1024
