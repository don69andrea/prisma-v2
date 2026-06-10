"""Tests für SwissFundamentals Value Object."""

from decimal import Decimal

import pytest

from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

pytestmark = pytest.mark.unit


def test_swiss_fundamentals_all_fields() -> None:
    f = SwissFundamentals(
        market_cap_chf=Decimal("250000000000"),
        pe_ratio=22.5,
        pb_ratio=3.2,
        dividend_yield=0.027,
        eps_chf=5.4,
    )
    assert f.market_cap_chf == Decimal("250000000000")
    assert f.pe_ratio == 22.5
    assert f.dividend_yield == 0.027


def test_swiss_fundamentals_all_none() -> None:
    f = SwissFundamentals(
        market_cap_chf=None,
        pe_ratio=None,
        pb_ratio=None,
        dividend_yield=None,
        eps_chf=None,
    )
    assert f.market_cap_chf is None


def test_swiss_fundamentals_is_frozen() -> None:
    f = SwissFundamentals(
        market_cap_chf=Decimal("1"),
        pe_ratio=None,
        pb_ratio=None,
        dividend_yield=None,
        eps_chf=None,
    )
    with pytest.raises(AttributeError):
        f.market_cap_chf = Decimal("2")  # type: ignore[misc]
