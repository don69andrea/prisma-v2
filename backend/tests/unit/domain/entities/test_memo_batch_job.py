# backend/tests/unit/domain/entities/test_memo_batch_job.py
"""Tests fuer MemoBatchJob Entity."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.domain.entities.memo_batch_job import MemoBatchJob

pytestmark = pytest.mark.unit


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    """Default valid payload fuer MemoBatchJob. Override via kwargs."""
    payload: dict[str, Any] = {
        "id": uuid4(),
        "model_run_id": uuid4(),
        "top_n": 20,
        "language": "de",
        "status": "pending",
        "failed_stock_ids": [],
        "error_message": None,
        "created_at": datetime.now(UTC),
        "started_at": None,
        "completed_at": None,
    }
    payload.update(overrides)
    return payload


class TestMemoBatchJobValid:
    def test_minimal_valid(self) -> None:
        job = MemoBatchJob(**_valid_payload())
        assert job.status == "pending"
        assert job.top_n == 20
        assert job.failed_stock_ids == []

    def test_failed_stock_ids_default_empty(self) -> None:
        payload = _valid_payload()
        del payload["failed_stock_ids"]
        job = MemoBatchJob(**payload)
        assert job.failed_stock_ids == []


class TestMemoBatchJobFrozen:
    def test_is_frozen(self) -> None:
        job = MemoBatchJob(**_valid_payload())
        with pytest.raises(ValidationError):
            job.status = "running"


class TestMemoBatchJobConstraints:
    def test_top_n_too_low_raises(self) -> None:
        with pytest.raises(ValidationError):
            MemoBatchJob(**_valid_payload(top_n=0))

    def test_top_n_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            MemoBatchJob(**_valid_payload(top_n=101))

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            MemoBatchJob(**_valid_payload(status="unknown"))

    def test_invalid_language_raises(self) -> None:
        with pytest.raises(ValidationError):
            MemoBatchJob(**_valid_payload(language="fr"))

    def test_error_message_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            MemoBatchJob(**_valid_payload(error_message="x" * 1001))
