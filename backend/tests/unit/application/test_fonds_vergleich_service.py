"""Unit-Tests für FondsVergleichService."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from backend.application.services.fonds_vergleich_service import (
    FondsNotFound,
    FondsVergleichService,
)
from backend.infrastructure.seeds.viac_fonds_catalog import VIAC_FONDS_CATALOG


def test_list_fonds_returns_all_entries() -> None:
    service = FondsVergleichService()
    result = service.list_fonds()
    assert len(result) == len(VIAC_FONDS_CATALOG)
    names = {item["name"] for item in result}
    assert "VIAC Global 100" in names
    assert "VIAC Schweiz 100" in names


@pytest.mark.asyncio
async def test_compare_unknown_fonds_raises() -> None:
    service = FondsVergleichService()
    with pytest.raises(FondsNotFound):
        await service.compare("NONEXISTENT", [{"ticker": "NESN", "weight": 1.0}])


@pytest.mark.asyncio
async def test_compare_no_yf_adapter_returns_zero_custom_metrics() -> None:
    """Ohne yfinance-Adapter → custom_metrics alle 0."""
    service = FondsVergleichService(yfinance_adapter=None)
    result = await service.compare(
        "VIAC Global 100",
        [{"ticker": "NESN", "weight": 1.0}],
    )
    assert result.fonds_name == "VIAC Global 100"
    assert result.custom_metrics.expected_return_pa == Decimal("0")
    assert result.custom_metrics.volatility_pa == Decimal("0")
    assert result.custom_metrics.sharpe_ratio is None
    assert result.disclaimer != ""
    assert "Anlageberatung" in result.disclaimer


@pytest.mark.asyncio
async def test_compare_with_mock_price_history() -> None:
    """Mit simulierten Preisdaten → plausible custom_metrics."""
    import numpy as np
    import pandas as pd

    # 756 Handelstage (~3 Jahre) mit realistischer Rendite
    rng = np.random.default_rng(42)
    prices = pd.Series(100.0 * (1 + rng.normal(0.0003, 0.01, 756)).cumprod())

    yf = AsyncMock()
    yf.get_price_history.return_value = prices

    service = FondsVergleichService(yfinance_adapter=yf)
    result = await service.compare(
        "VIAC Global 80",
        [{"ticker": "NESN", "weight": 0.6}, {"ticker": "NOVN", "weight": 0.4}],
    )
    assert result.fonds_name == "VIAC Global 80"
    # Volatilität muss positiv und in realistischem Bereich sein
    assert result.custom_metrics.volatility_pa > Decimal("0")
    assert result.custom_metrics.volatility_pa < Decimal("1")
    # Fonds-Metriken kommen aus Katalog und sind fest
    assert result.fonds_metrics.expected_return_pa == Decimal("0.081")


@pytest.mark.asyncio
async def test_compare_normalises_weights() -> None:
    """Weights müssen nicht exakt 1.0 ergeben — werden normalisiert."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(0)
    prices = pd.Series(100.0 * (1 + rng.normal(0.0003, 0.01, 500)).cumprod())
    yf = AsyncMock()
    yf.get_price_history.return_value = prices

    service = FondsVergleichService(yfinance_adapter=yf)
    # Weights 3+1 werden zu 0.75/0.25
    result = await service.compare(
        "VIAC Global 60",
        [{"ticker": "NESN", "weight": 3}, {"ticker": "NOVN", "weight": 1}],
    )
    assert result.custom_metrics.volatility_pa > Decimal("0")
