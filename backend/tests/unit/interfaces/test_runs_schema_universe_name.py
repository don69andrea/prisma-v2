"""Schema-Tests für RunResponse.universe_name."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import WeightConfig
from backend.interfaces.rest.schemas.runs import RunResponse

pytestmark = pytest.mark.unit


class TestRunResponseUniverseName:
    def test_from_domain_includes_universe_name(self) -> None:
        run = RankingRun(
            id=uuid4(),
            created_at=datetime.now(tz=UTC),
            universe_id=uuid4(),
            weight_config=WeightConfig.equal(),
            status="completed",
        )

        response = RunResponse.from_domain(run, universe_name="Demo-US-5")

        assert response.universe_name == "Demo-US-5"
        assert response.id == run.id
        assert response.status == "completed"

    def test_from_domain_accepts_deleted_fallback(self) -> None:
        run = RankingRun(
            id=uuid4(),
            created_at=datetime.now(tz=UTC),
            universe_id=uuid4(),
            weight_config=WeightConfig.equal(),
            status="completed",
        )

        response = RunResponse.from_domain(run, universe_name="(deleted)")

        assert response.universe_name == "(deleted)"
