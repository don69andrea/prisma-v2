"""CI-Guard (Audit C-01): Der Signals-Router darf KEINE synthetischen
Zufallspreise in Produktions-Endpoints verwenden.

Historie: `_make_stub_prices` erzeugte einen deterministischen Random-Walk und
wurde fälschlich für echte Signal-/Backtest-Endpoints genutzt → die Plattform
lieferte erfundene BUY/HOLD/SELL-Signale. Dieser Guard verhindert die Rückkehr
solcher Muster in den Produktions-Router.
"""

from __future__ import annotations

import inspect

import pytest

from backend.interfaces.rest.routers import signals

pytestmark = pytest.mark.unit


def test_router_defines_no_synthetic_price_generator() -> None:
    src = inspect.getsource(signals)
    # Weder Definition noch Aufruf einer Stub-Preis-Funktion.
    assert "def _make_stub_prices" not in src
    assert "_make_stub_prices(" not in src
    # Kein Zufallszahlen-Generator (Random-Walk = erfundene Preise).
    for forbidden in ("default_rng", "np.random", "numpy.random"):
        assert forbidden not in src, f"Verbotenes Synthetik-Muster im Signals-Router: {forbidden}"


def test_load_prices_uses_real_market_adapter() -> None:
    src = inspect.getsource(signals._load_prices)
    assert "CryptoPriceAdapter" in src
    assert "fetch_ohlcv" in src
