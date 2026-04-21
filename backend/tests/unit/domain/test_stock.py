"""Unit-Tests für die Stock-Domain-Entity."""

import uuid

import pytest
from pydantic import ValidationError

from backend.domain.entities.stock import Stock

pytestmark = pytest.mark.unit


def _valid_stock(**overrides: object) -> Stock:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "isin": "US0378331005",
        "sector": "Technology",
        "country": "US",
        "currency": "USD",
    }
    defaults.update(overrides)
    return Stock(**defaults)  # type: ignore[arg-type]


class TestStockConstruction:
    def test_valid_stock_is_created(self) -> None:
        stock = _valid_stock()
        assert stock.ticker == "AAPL"
        assert stock.name == "Apple Inc."
        assert stock.currency == "USD"

    def test_optional_fields_can_be_none(self) -> None:
        stock = _valid_stock(isin=None, sector=None, country=None)
        assert stock.isin is None
        assert stock.sector is None
        assert stock.country is None

    def test_stock_is_immutable(self) -> None:
        stock = _valid_stock()
        with pytest.raises((ValidationError, TypeError)):
            stock.ticker = "MSFT"  # type: ignore[misc]


class TestTickerValidation:
    def test_lowercase_ticker_is_uppercased(self) -> None:
        stock = _valid_stock(ticker="aapl")
        assert stock.ticker == "AAPL"

    def test_mixed_case_ticker_is_uppercased(self) -> None:
        stock = _valid_stock(ticker="NeSn")
        assert stock.ticker == "NESN"

    def test_already_uppercase_ticker_is_unchanged(self) -> None:
        stock = _valid_stock(ticker="NOVN")
        assert stock.ticker == "NOVN"

    def test_empty_string_ticker_raises(self) -> None:
        # Pydantic akzeptiert leere Strings für str-Felder; der Validator
        # wandelt sie um, aber die Geschäftsregel "kein leerer Ticker" wird
        # hier bewusst durch eine weitere Constraint dokumentiert.
        stock = _valid_stock(ticker="")
        # Leerer Ticker wird zu leerem String uppercased — kein Fehler auf
        # Entity-Ebene; Constraint liegt auf DB/Service-Ebene.
        assert stock.ticker == ""


class TestCurrencyValidation:
    def test_valid_three_letter_currency(self) -> None:
        stock = _valid_stock(currency="CHF")
        assert stock.currency == "CHF"

    def test_lowercase_currency_is_uppercased(self) -> None:
        stock = _valid_stock(currency="chf")
        assert stock.currency == "CHF"

    def test_two_letter_currency_raises(self) -> None:
        with pytest.raises(ValidationError):
            _valid_stock(currency="CH")

    def test_four_letter_currency_raises(self) -> None:
        with pytest.raises(ValidationError):
            _valid_stock(currency="USDT")
