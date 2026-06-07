"""Unit-Tests für die SwissStock-Domain-Entity."""

from decimal import Decimal
from uuid import uuid4

import pytest

from backend.domain.entities.swiss_stock import SwissStock

pytestmark = pytest.mark.unit


def _valid_kwargs() -> dict:
    return {
        "id": uuid4(),
        "ticker": "NESN",
        "isin": "CH0038863350",
        "name": "Nestlé SA",
        "exchange": "XSWX",
        "sector": "Consumer Staples",
        "market_cap_chf": None,
    }


class TestSwissStockCreation:
    def test_valid_stock_creates_successfully(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        assert stock.ticker == "NESN"
        assert stock.currency == "CHF"

    def test_ticker_is_uppercased(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["ticker"] = "nesn"
        stock = SwissStock(**kwargs)
        assert stock.ticker == "NESN"

    def test_invalid_isin_raises_value_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["isin"] = "US0038863350"
        with pytest.raises(ValueError, match="ISIN"):
            SwissStock(**kwargs)

    def test_market_cap_can_be_none(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        assert stock.market_cap_chf is None

    def test_market_cap_can_be_decimal(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["market_cap_chf"] = Decimal("245000000000")
        stock = SwissStock(**kwargs)
        assert stock.market_cap_chf == Decimal("245000000000")

    def test_stock_is_frozen(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        with pytest.raises((AttributeError, TypeError)):
            stock.ticker = "NOVN"  # type: ignore[misc]

    def test_currency_default_is_chf(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        assert stock.currency == "CHF"
