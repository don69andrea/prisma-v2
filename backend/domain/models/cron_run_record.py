from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CronRunRecord:
    id: str
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str | None = None  # "ok" | "error" | "running"
    records_saved: int | None = None
    error_msg: str | None = None
