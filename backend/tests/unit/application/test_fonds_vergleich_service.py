"""Unit-Tests für FondsVergleichService."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from backend.application.services.fonds_vergleich_service import (
    FondsNotFound,
    FondsVergleichService,
)
from backend.infrastructure.seeds.viac_fonds_catalog import VIAC_FONDS_CATALOG


class _FakeYFAdapter:
    """Adapter-Double mit der ECHTEN get_price_history-Signatur (days=...).

    Bewusst KEIN AsyncMock: der reale Adapter akzeptiert ausschliesslich das
    Keyword `days`. Ein AsyncMock würde jede Signatur schlucken und damit die
    W3-C-02-Regression (Service ruft mit `years=` → TypeError → Null-Metriken)
    verstecken. Die feste Signatur erzwingt den korrekten Aufruf und gibt —
    wie der echte Adapter — einen DataFrame mit ["Close", "Volume"] zurück.
    """

    def __init__(self, price_frames: dict[str, Any]) -> None:
        self._frames = price_frames
        self.calls: list[tuple[str, int]] = []

    async def get_price_history(self, ticker: str, days: int = 252) -> Any:
        self.calls.append((ticker, days))
        return self._frames[ticker]


def _make_close_frame(prices: Any) -> Any:
    """Baut einen DataFrame wie der reale YFinanceSwissAdapter (Close + Volume)."""
    import numpy as np
    import pandas as pd

    return pd.DataFrame({"Close": np.asarray(prices), "Volume": np.ones(len(prices))})


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
    """Mit simulierten Preisdaten → custom_metrics sind NICHT konstant 0 (W3-C-02)."""
    import numpy as np

    # 756 Handelstage (~3 Jahre) mit realistischer positiver Drift
    rng = np.random.default_rng(42)
    nesn = 100.0 * (1 + rng.normal(0.0003, 0.01, 756)).cumprod()
    novn = 100.0 * (1 + rng.normal(0.0003, 0.01, 756)).cumprod()

    yf = _FakeYFAdapter({"NESN": _make_close_frame(nesn), "NOVN": _make_close_frame(novn)})

    service = FondsVergleichService(yfinance_adapter=yf, risk_free_rate=0.01)
    result = await service.compare(
        "VIAC Global 80",
        [{"ticker": "NESN", "weight": 0.6}, {"ticker": "NOVN", "weight": 0.4}],
        lookback_years=3,
    )
    assert result.fonds_name == "VIAC Global 80"
    # KERN-ASSERTION W3-C-02: Custom-Metriken dürfen NICHT konstant 0 sein.
    assert result.custom_metrics.expected_return_pa != Decimal("0")
    assert result.custom_metrics.volatility_pa > Decimal("0")
    assert result.custom_metrics.volatility_pa < Decimal("1")
    assert result.custom_metrics.sharpe_ratio is not None
    # Adapter wurde mit der ECHTEN Signatur (days=lookback_years*252) aufgerufen.
    assert ("NESN", 756) in yf.calls
    assert ("NOVN", 756) in yf.calls
    # Fonds-Metriken kommen aus Katalog und sind fest
    assert result.fonds_metrics.expected_return_pa == Decimal("0.081")


@pytest.mark.asyncio
async def test_compare_normalises_weights() -> None:
    """Weights müssen nicht exakt 1.0 ergeben — werden normalisiert."""
    import numpy as np

    rng = np.random.default_rng(0)
    nesn = 100.0 * (1 + rng.normal(0.0003, 0.01, 500)).cumprod()
    novn = 100.0 * (1 + rng.normal(0.0003, 0.01, 500)).cumprod()
    yf = _FakeYFAdapter({"NESN": _make_close_frame(nesn), "NOVN": _make_close_frame(novn)})

    service = FondsVergleichService(yfinance_adapter=yf, risk_free_rate=0.01)
    # Weights 3+1 werden zu 0.75/0.25
    result = await service.compare(
        "VIAC Global 60",
        [{"ticker": "NESN", "weight": 3}, {"ticker": "NOVN", "weight": 1}],
    )
    assert result.custom_metrics.volatility_pa > Decimal("0")
    assert result.custom_metrics.expected_return_pa != Decimal("0")


def test_router_get_service_injects_yfinance_adapter() -> None:
    """W3-C-02: Der Router muss den YFinanceSwissAdapter in den Service injizieren."""
    from backend.interfaces.rest.routers.fonds_vergleich import _get_service

    sentinel_adapter = object()
    service = _get_service(yf_adapter=sentinel_adapter)  # type: ignore[arg-type]
    assert service._yf is sentinel_adapter
