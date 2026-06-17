from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_start_run_returns_uuid_string():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    from backend.infrastructure.persistence.repositories.cron_run_repository import (
        SQLACronRunRepository,
    )

    repo = SQLACronRunRepository(session)
    run_id = await repo.start_run("crypto_daily")
    assert isinstance(run_id, str)
    assert len(run_id) == 36  # UUID format
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_finish_run_updates_existing_row():
    from backend.infrastructure.persistence.models.cron_run_log import CronRunLogORM

    session = AsyncMock()
    row = CronRunLogORM(
        id="test-id",
        job_name="crypto_daily",
        started_at=datetime.now(UTC),
        status="running",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    from backend.infrastructure.persistence.repositories.cron_run_repository import (
        SQLACronRunRepository,
    )

    repo = SQLACronRunRepository(session)
    await repo.finish_run("test-id", "ok", records_saved=10)
    assert row.status == "ok"
    assert row.records_saved == 10
    assert row.finished_at is not None
