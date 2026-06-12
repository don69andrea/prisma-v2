"""Unit-Tests für FactsheetService."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.application.services.factsheet_service import FactsheetService
from backend.application.services.stock_service import StockNotFound
from backend.domain.entities.stock import Stock
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.stock_repository import StockRepository

pytestmark = pytest.mark.unit


def _make_stock(ticker: str = "NESN") -> Stock:
    return Stock(
        id=uuid4(),
        ticker=ticker,
        name=f"{ticker} AG",
        currency="CHF",
        sector="Consumer Staples",
        country="CH",
    )


def _build_service(
    stock: Stock | None = _make_stock(),
    ranking_raw: dict[str, Any] | None = None,
) -> tuple[FactsheetService, AsyncMock, AsyncMock]:
    mock_stock_repo = AsyncMock(spec=StockRepository)
    mock_stock_repo.get_by_ticker.return_value = stock

    mock_run_repo = AsyncMock(spec=RankingRunRepository)
    mock_run_repo.get_latest_ticker_result.return_value = ranking_raw

    svc = FactsheetService(stock_repo=mock_stock_repo, run_repo=mock_run_repo)
    return svc, mock_stock_repo, mock_run_repo


class TestGetFactsheetFound:
    async def test_returns_stock_and_ranking_snapshot(self) -> None:
        stock = _make_stock("NESN")
        raw: dict[str, Any] = {
            "ticker": "NESN",
            "total_rank": 1,
            "weighted_avg": 0.85,
            "is_sweet_spot": True,
            "per_model_ranks": {"quality_classic": 1},
        }
        svc, _, _ = _build_service(stock=stock, ranking_raw=raw)

        result_stock, result_raw = await svc.get_factsheet("NESN")

        assert result_stock is stock
        assert result_raw is raw

    async def test_delegates_ticker_to_stock_repo(self) -> None:
        stock = _make_stock("ABBN")
        svc, mock_stock_repo, _ = _build_service(stock=stock)

        await svc.get_factsheet("ABBN")

        mock_stock_repo.get_by_ticker.assert_called_once_with("ABBN")

    async def test_delegates_ticker_to_run_repo(self) -> None:
        stock = _make_stock("ABBN")
        svc, _, mock_run_repo = _build_service(stock=stock)

        await svc.get_factsheet("ABBN")

        mock_run_repo.get_latest_ticker_result.assert_called_once_with("ABBN")

    async def test_ranking_raw_none_when_no_completed_run(self) -> None:
        # No completed run for this ticker → get_latest_ticker_result returns None
        stock = _make_stock("NESN")
        svc, _, _ = _build_service(stock=stock, ranking_raw=None)

        result_stock, result_raw = await svc.get_factsheet("NESN")

        assert result_stock is stock
        assert result_raw is None

    async def test_ranking_raw_contains_per_model_ranks(self) -> None:
        stock = _make_stock("NESN")
        per_model = {
            "quality_classic": 2,
            "alpha": 3,
            "trend_momentum": 1,
            "value_alpha_potential": 5,
            "diversification": 4,
        }
        raw: dict[str, Any] = {
            "ticker": "NESN",
            "total_rank": 2,
            "weighted_avg": 0.72,
            "is_sweet_spot": False,
            "per_model_ranks": per_model,
        }
        svc, _, _ = _build_service(stock=stock, ranking_raw=raw)

        _, result_raw = await svc.get_factsheet("NESN")

        assert result_raw is not None
        assert result_raw["per_model_ranks"] == per_model

    async def test_ranking_raw_sweet_spot_flag_preserved(self) -> None:
        stock = _make_stock("LOGN")
        raw: dict[str, Any] = {
            "ticker": "LOGN",
            "total_rank": 1,
            "weighted_avg": 0.91,
            "is_sweet_spot": True,
            "per_model_ranks": {},
        }
        svc, _, _ = _build_service(stock=stock, ranking_raw=raw)

        _, result_raw = await svc.get_factsheet("LOGN")

        assert result_raw is not None
        assert result_raw["is_sweet_spot"] is True

    async def test_ranking_raw_with_stock_id_field(self) -> None:
        stock = _make_stock("ZURN")
        stock_id = str(uuid4())
        raw: dict[str, Any] = {
            "stock_id": stock_id,
            "ticker": "ZURN",
            "total_rank": 3,
            "weighted_avg": 0.60,
            "is_sweet_spot": False,
            "per_model_ranks": {"quality_classic": 3},
        }
        svc, _, _ = _build_service(stock=stock, ranking_raw=raw)

        _, result_raw = await svc.get_factsheet("ZURN")

        assert result_raw is not None
        assert result_raw["stock_id"] == stock_id


class TestGetFactsheetNotFound:
    async def test_raises_stock_not_found_when_ticker_missing(self) -> None:
        svc, _, _ = _build_service(stock=None)

        with pytest.raises(StockNotFound):
            await svc.get_factsheet("UNKNOWN")

    async def test_run_repo_not_called_when_stock_missing(self) -> None:
        svc, _, mock_run_repo = _build_service(stock=None)

        with pytest.raises(StockNotFound):
            await svc.get_factsheet("UNKNOWN")

        mock_run_repo.get_latest_ticker_result.assert_not_called()

    async def test_stock_not_found_exception_carries_ticker(self) -> None:
        svc, _, _ = _build_service(stock=None)

        with pytest.raises(StockNotFound) as exc_info:
            await svc.get_factsheet("GHOST")

        assert "GHOST" in str(exc_info.value)
