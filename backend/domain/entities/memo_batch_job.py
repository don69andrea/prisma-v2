# backend/domain/entities/memo_batch_job.py
"""MemoBatchJob — Job-Entity fuer asynchrone Multi-Memo-Generierung.

Spec: docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md §4
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MemoBatchJob(BaseModel):
    """Job-State fuer einen Multi-Memo-Batch-Run.

    Status-Lifecycle:
        pending → running → complete | partial | failed
    """

    model_config = {"frozen": True}

    id: UUID
    model_run_id: UUID
    top_n: int = Field(..., ge=1, le=100)
    language: Literal["de", "en"]
    status: Literal["pending", "running", "complete", "partial", "failed"]
    failed_stock_ids: list[UUID] = Field(default_factory=list)
    expected_stock_ids: list[UUID] = Field(default_factory=list)
    error_message: str | None = Field(None, max_length=1000)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
