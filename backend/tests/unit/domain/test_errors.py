"""Unit-Tests für Domain-Exceptions.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §8.
"""

from decimal import Decimal

import pytest

from backend.domain.errors import (
    BudgetCapExceeded,
    SwissDataUnavailableError,
    YahooFinanceBlockedError,
)

pytestmark = pytest.mark.unit


class TestBudgetCapExceeded:
    def test_is_an_exception(self) -> None:
        exc = BudgetCapExceeded(
            current_usd=Decimal("5.00"),
            attempted_usd=Decimal("0.50"),
            cap_usd=Decimal("8.00"),
        )
        assert isinstance(exc, Exception)

    def test_attributes_are_preserved(self) -> None:
        exc = BudgetCapExceeded(
            current_usd=Decimal("7.50"),
            attempted_usd=Decimal("1.00"),
            cap_usd=Decimal("8.00"),
        )
        assert exc.current_usd == Decimal("7.50")
        assert exc.attempted_usd == Decimal("1.00")
        assert exc.cap_usd == Decimal("8.00")

    def test_constructor_is_keyword_only(self) -> None:
        # Positional-Args müssen abgelehnt werden — schützt vor
        # Argument-Reihenfolge-Bugs (`current` vs `cap` vertauscht).
        with pytest.raises(TypeError):
            BudgetCapExceeded(  # type: ignore[misc]
                Decimal("5.00"),
                Decimal("0.50"),
                Decimal("8.00"),
            )

    def test_message_formats_amounts_with_two_decimals(self) -> None:
        exc = BudgetCapExceeded(
            current_usd=Decimal("7.501"),
            attempted_usd=Decimal("0.499"),
            cap_usd=Decimal("8.000"),
        )
        message = str(exc)
        assert "7.50" in message
        assert "0.50" in message
        assert "8.00" in message
        assert "USD" in message


class TestYahooFinanceBlockedError:
    def test_is_a_swiss_data_unavailable_error(self) -> None:
        """Subklassen-Beziehung erlaubt `except SwissDataUnavailableError`,
        um beide Fälle (unbekannter Ticker / Yahoo-Blockade) einheitlich
        abzufangen, während Router bei Bedarf differenzieren können."""
        exc = YahooFinanceBlockedError("NESN")
        assert isinstance(exc, SwissDataUnavailableError)
        assert isinstance(exc, Exception)

    def test_attributes_are_preserved(self) -> None:
        exc = YahooFinanceBlockedError("NESN")
        assert exc.ticker == "NESN"

    def test_message_mentions_ticker_and_blockage(self) -> None:
        exc = YahooFinanceBlockedError("NESN")
        message = str(exc)
        assert "NESN" in message
        assert "Yahoo Finance" in message

    def test_cause_is_included_in_message_when_given(self) -> None:
        exc = YahooFinanceBlockedError("NESN", cause="401 Unauthorized")
        assert "401 Unauthorized" in str(exc)
