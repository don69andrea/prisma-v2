"""Synthetische Preisreihen — NUR für Tests.

Früher lebte diese Funktion als `_make_stub_prices` im Produktions-Router
`backend/interfaces/rest/routers/signals.py` und wurde dort fälschlich für ECHTE
Signal-/Backtest-Endpoints verwendet (Zufalls-Random-Walk statt Marktdaten,
Audit-Befund C-01). Sie ist jetzt hierher verschoben, damit sie ausschliesslich
in Tests genutzt werden kann und niemals in einen Produktionspfad gerät.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd


def make_synthetic_prices(coin: str, n: int = 200) -> pd.DataFrame:
    """Deterministischer Random-Walk als Preisreihe (Test-Fixture).

    Seed aus dem Coin-Namen → reproduzierbar pro Coin. Spalte = Coin,
    DatetimeIndex (UTC, täglich). Ausschliesslich für Tests.
    """
    rng = np.random.default_rng(seed=abs(hash(coin)) % 2**32)
    returns = rng.normal(0.001, 0.03, size=n)
    prices = 100.0 * np.cumprod(1 + returns)
    idx = pd.date_range(end=datetime.now(UTC), periods=n, freq="D", tz="UTC")
    return pd.DataFrame({coin: prices}, index=idx)
