"""yfinance-Adapter für Schweizer Aktien (SIX Swiss Exchange, .SW-Suffix).

Dieses Modul ist ein Skeleton für Issue #1.
Vollständige Implementierung (Kurse, Fundamentaldaten, Caching) folgt in Issue #3.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


class YFinanceSwissAdapter:
    """Adapter für Swiss Market Data via yfinance.

    SIX-kotierte Titel haben das Suffix .SW in yfinance (z.B. NOVN.SW).
    """

    def build_yf_ticker(self, ticker: str) -> str:
        """Konvertiert einen PRISMA-Ticker in das yfinance-Format.

        Beispiel: "NOVN" → "NOVN.SW"
        """
        return f"{ticker.upper()}.SW"

    async def get_stock_info(self, ticker: str) -> dict:
        """Ruft yfinance .info-Dict für einen Swiss Stock ab.

        Implementierung folgt in Issue #3.
        Timeout: 10s. Retry: 2x Exponential Backoff.
        """
        raise NotImplementedError(
            "YFinanceSwissAdapter.get_stock_info wird in Issue #3 implementiert"
        )
