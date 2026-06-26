from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_coingecko_filters_zero_price():
    from backend.infrastructure.adapters.coingecko_adapter import _validate_market_entry

    valid = {"id": "bitcoin", "current_price": 85000.0, "market_cap": 1_600_000_000_000}
    invalid = {"id": "bitcoin", "current_price": 0.0, "market_cap": 1_600_000_000_000}
    assert _validate_market_entry(valid) is True
    assert _validate_market_entry(invalid) is False


def test_coingecko_filters_missing_price():
    from backend.infrastructure.adapters.coingecko_adapter import _validate_market_entry

    entry = {"id": "bitcoin", "market_cap": 1_600_000_000_000}
    assert _validate_market_entry(entry) is False


def test_fear_greed_valid_range():
    from backend.infrastructure.adapters.fear_greed_adapter import _validate_fear_greed

    assert _validate_fear_greed(50) == 50
    assert _validate_fear_greed(0) == 0
    assert _validate_fear_greed(100) == 100


def test_fear_greed_clamps_out_of_range():
    from backend.infrastructure.adapters.fear_greed_adapter import _validate_fear_greed

    assert _validate_fear_greed(-1) is None
    assert _validate_fear_greed(101) is None
