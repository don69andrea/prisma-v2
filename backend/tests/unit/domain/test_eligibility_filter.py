"""Unit-Tests für EligibilityFilter — Swiss 3a-Eignungsprüfung."""

from decimal import Decimal
from uuid import uuid4

import pytest

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.services.eligibility_filter import EligibilityFilter
from backend.domain.value_objects.eligibility_result import EligibilityReason

pytestmark = pytest.mark.unit

_filter = EligibilityFilter()


def _stock(
    ticker: str = "NESN",
    exchange: str = "XSWX",
    market_cap_chf: Decimal | None = Decimal("245_000_000_000"),
    isin: str = "CH0038863350",
    sector: str | None = "Consumer Staples",
) -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker=ticker,
        isin=isin,
        name=f"{ticker} AG",
        exchange=exchange,  # type: ignore[arg-type]
        sector=sector,
        market_cap_chf=market_cap_chf,
    )


class TestEligibleStock:
    def test_xswx_large_cap_is_eligible(self) -> None:
        result = _filter.check(_stock())
        assert result.eligible is True
        assert result.reasons == ()

    def test_xswx_without_market_cap_is_eligible(self) -> None:
        result = _filter.check(_stock(market_cap_chf=None))
        assert result.eligible is True

    def test_xswx_exactly_at_minimum_cap_is_eligible(self) -> None:
        result = _filter.check(_stock(market_cap_chf=Decimal("100_000_000")))
        assert result.eligible is True

    def test_ticker_preserved_in_result(self) -> None:
        result = _filter.check(_stock(ticker="NOVN"))
        assert result.ticker == "NOVN"


class TestIneligibleStock:
    def test_exchange_not_recognized_fails(self) -> None:
        stock = _stock(exchange="XNAS", isin="CH0038863350")  # type: ignore[arg-type]
        result = _filter.check(stock)
        assert result.eligible is False
        assert EligibilityReason.EXCHANGE_NOT_RECOGNIZED in result.reasons

    def test_market_cap_below_minimum_fails(self) -> None:
        result = _filter.check(_stock(market_cap_chf=Decimal("50_000_000")))
        assert result.eligible is False
        assert EligibilityReason.MARKET_CAP_TOO_LOW in result.reasons

    def test_market_cap_just_below_minimum_fails(self) -> None:
        result = _filter.check(_stock(market_cap_chf=Decimal("99_999_999")))
        assert result.eligible is False
        assert EligibilityReason.MARKET_CAP_TOO_LOW in result.reasons

    def test_both_reasons_when_both_rules_violated(self) -> None:
        stock = _stock(exchange="NYSE", market_cap_chf=Decimal("10_000_000"), isin="CH0038863350")  # type: ignore[arg-type]
        result = _filter.check(stock)
        assert result.eligible is False
        assert EligibilityReason.EXCHANGE_NOT_RECOGNIZED in result.reasons
        assert EligibilityReason.MARKET_CAP_TOO_LOW in result.reasons
        assert len(result.reasons) == 2
