"""Unit-Tests für das RankingRun-Aggregate."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import WeightConfig

pytestmark = pytest.mark.unit


def _make_run(**overrides: object) -> RankingRun:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "created_at": datetime.now(tz=UTC),
        "universe_id": uuid.uuid4(),
        "weight_config": WeightConfig.equal(),
        "status": "pending",
    }
    defaults.update(overrides)
    return RankingRun(**defaults)  # type: ignore[arg-type]


class TestRankingRun:
    def test_default_status_is_pending(self) -> None:
        run = _make_run()
        assert run.status == "pending"

    def test_valid_statuses_accepted(self) -> None:
        for status in ("pending", "running", "completed", "failed"):
            run = _make_run(status=status)
            assert run.status == status

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_run(status="unknown")

    def test_ranking_run_is_immutable(self) -> None:
        run = _make_run()
        with pytest.raises((ValidationError, TypeError)):
            run.status = "completed"
