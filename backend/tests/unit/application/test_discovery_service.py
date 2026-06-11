"""Unit-Tests für DiscoveryService."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.application.services.discovery_service import DiscoveryService
from backend.domain.entities.investor_profile import InvestorProfile
from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.value_objects.swiss_quant_score import SwissQuantScore

pytestmark = pytest.mark.unit


def _make_stock(ticker: str, sector: str = "tech") -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker=ticker,
        isin="CH0012221716",  # valid CH ISIN
        name=f"{ticker} AG",
        exchange="XSWX",
        sector=sector,
        market_cap_chf=Decimal("10000000000"),
    )


def _make_score(composite: float) -> SwissQuantScore:
    score = MagicMock(spec=SwissQuantScore)
    score.composite = composite
    return score


def _make_service(stocks: list[SwissStock], composite: float = 75.0) -> DiscoveryService:
    repo = MagicMock()
    repo.list_by_exchange = AsyncMock(return_value=stocks)

    market_data = MagicMock()
    market_data.get_fundamentals = AsyncMock(return_value=MagicMock())

    service = DiscoveryService(swiss_stock_repo=repo, market_data=market_data)
    service._scorer = MagicMock()
    service._scorer.score = MagicMock(return_value=_make_score(composite))
    service._eligibility = MagicMock()
    return service


def _make_profile(**kwargs: Any) -> InvestorProfile:
    defaults = {"session_id": "test-sess"}
    defaults.update(kwargs)
    return InvestorProfile(**defaults)


class TestDiscoveryServiceSectorFilter:
    @pytest.mark.asyncio
    async def test_empty_affinity_returns_all(self) -> None:
        stocks = [_make_stock("NESN.SW", "consumer"), _make_stock("LOGN.SW", "tech")]
        service = _make_service(stocks)
        profile = _make_profile(sector_affinity=[])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_sector_filter_applied(self) -> None:
        stocks = [_make_stock("NESN.SW", "consumer"), _make_stock("LOGN.SW", "tech")]
        service = _make_service(stocks)
        profile = _make_profile(sector_affinity=["tech"])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1
        assert result[0].ticker == "LOGN.SW"

    @pytest.mark.asyncio
    async def test_sector_filter_case_insensitive(self) -> None:
        stocks = [_make_stock("LOGN.SW", "Tech")]
        service = _make_service(stocks)
        profile = _make_profile(sector_affinity=["tech"])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1


class TestDiscoveryServiceRiskFilter:
    @pytest.mark.asyncio
    async def test_conservative_excludes_low_composite(self) -> None:
        stocks = [_make_stock("NESN.SW")]
        service = _make_service(stocks, composite=60.0)  # below 70.0 conservative floor
        profile = _make_profile(risk_profile="conservative")
        result = await service.get_personalized_universe(profile)
        assert result == []

    @pytest.mark.asyncio
    async def test_moderate_includes_above_40(self) -> None:
        stocks = [_make_stock("NESN.SW")]
        service = _make_service(stocks, composite=45.0)
        profile = _make_profile(risk_profile="moderate")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_aggressive_includes_all(self) -> None:
        stocks = [_make_stock("NESN.SW")]
        service = _make_service(stocks, composite=10.0)
        profile = _make_profile(risk_profile="aggressive")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1


class TestDiscoveryServiceKnownTickerPriority:
    @pytest.mark.asyncio
    async def test_known_tickers_sorted_first(self) -> None:
        stocks = [
            _make_stock("UNKNOWN.SW"),
            _make_stock("NESN.SW"),
        ]
        service = _make_service(stocks, composite=80.0)
        profile = _make_profile(known_tickers=["NESN.SW"])
        result = await service.get_personalized_universe(profile)
        assert result[0].ticker == "NESN.SW"

    @pytest.mark.asyncio
    async def test_unknown_ticker_not_excluded(self) -> None:
        stocks = [_make_stock("UNKNOWN.SW"), _make_stock("NESN.SW")]
        service = _make_service(stocks, composite=80.0)
        profile = _make_profile(known_tickers=["NESN.SW"])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 2


class TestDiscoveryServiceErrorHandling:
    @pytest.mark.asyncio
    async def test_scoring_error_skips_stock(self) -> None:
        stocks = [_make_stock("NESN.SW"), _make_stock("LOGN.SW")]
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=stocks)
        market_data = MagicMock()
        market_data.get_fundamentals = AsyncMock(return_value=MagicMock())

        service = DiscoveryService(swiss_stock_repo=repo, market_data=market_data)
        service._scorer = MagicMock()
        service._scorer.score = MagicMock(side_effect=Exception("yfinance error"))
        service._eligibility = MagicMock()

        profile = _make_profile(risk_profile="aggressive")
        result = await service.get_personalized_universe(profile)
        assert result == []
