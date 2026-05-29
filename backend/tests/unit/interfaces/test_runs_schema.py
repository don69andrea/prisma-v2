"""Schema-Tests für runs-Response-Modelle."""

import uuid

import pytest

from backend.interfaces.rest.schemas.runs import RankingItem

pytestmark = pytest.mark.unit


class TestRankingItemSchema:
    def test_accepts_stock_id_uuid(self) -> None:
        """Neue Runs liefern stock_id als UUID — Schema akzeptiert es."""
        stock_id = uuid.uuid4()
        item = RankingItem.model_validate(
            {
                "stock_id": str(stock_id),
                "ticker": "AAPL",
                "total_rank": 1,
                "weighted_avg": 0.95,
                "is_sweet_spot": True,
                "per_model_ranks": {"quality_classic": 1},
            }
        )
        assert item.stock_id == stock_id

    def test_stock_id_optional_for_legacy_runs(self) -> None:
        """Alte Runs ohne stock_id im JSONB müssen valid sein (stock_id default None)."""
        item = RankingItem.model_validate(
            {
                "ticker": "MSFT",
                "total_rank": 2,
                "weighted_avg": 0.88,
                "is_sweet_spot": False,
                "per_model_ranks": {"quality_classic": 2},
            }
        )
        assert item.stock_id is None
