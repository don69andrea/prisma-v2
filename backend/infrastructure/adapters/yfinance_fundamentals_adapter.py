"""YFinance-basierter Adapter für FundamentalsProvider-Port.

Mappt yfinance .info-Felder auf das Fundamentals-Dict das QualityClassicModel erwartet.
Fehlende yfinance-Felder → None (das Model behandelt None als fehlend, nicht als 0).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import yfinance as yf

from backend.domain.models.quality_classic import Fundamentals, UniverseData
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

_logger = logging.getLogger(__name__)

_RETRIES = 2
_BASE_DELAY = 1.0


class YFinanceFundamentalsAdapter(FundamentalsProvider):
    """Implementiert FundamentalsProvider via yfinance für SMI/SMIM-Tickers."""

    def __init__(self) -> None:
        self._swiss = YFinanceSwissAdapter()

    async def get_fundamentals(self, tickers: list[str]) -> UniverseData:
        tasks = [self._fetch_one(t) for t in tickers]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        results: UniverseData = {}
        for ticker, result in zip(tickers, fetched, strict=True):
            if isinstance(result, Exception):
                _logger.warning("FundamentalsProvider: %s Fehler — %s", ticker, result)
                results[ticker] = {}
            else:
                results[ticker] = result  # type: ignore[assignment]
        return results

    async def _fetch_one(self, ticker: str) -> Fundamentals:
        yf_ticker = self._swiss.build_yf_ticker(ticker)
        info: dict[str, Any] = {}
        for attempt in range(_RETRIES + 1):
            try:
                info = await asyncio.to_thread(lambda t=yf_ticker: yf.Ticker(t).info)
                break
            except Exception as exc:
                if attempt < _RETRIES:
                    await asyncio.sleep(_BASE_DELAY * (2 ** attempt))
                else:
                    _logger.warning(
                        "%s: yfinance nach %d Versuchen fehlgeschlagen: %s",
                        ticker, _RETRIES + 1, exc,
                    )
                    return {}

        fundamentals: Fundamentals = {}

        with contextlib.suppress(TypeError, ValueError):
            if (pe := info.get("trailingPE")) is not None:
                fundamentals["pe_ratio"] = float(pe)

        with contextlib.suppress(TypeError, ValueError):
            if (pb := info.get("priceToBook")) is not None:
                fundamentals["pb_ratio"] = float(pb)

        with contextlib.suppress(TypeError, ValueError, ZeroDivisionError):
            fcf = info.get("freeCashflow")
            mcap = info.get("marketCap")
            if fcf is not None and mcap and float(mcap) > 0:
                fundamentals["fcf_yield"] = float(fcf) / float(mcap)

        with contextlib.suppress(TypeError, ValueError):
            if (om := info.get("operatingMargins")) is not None:
                fundamentals["operating_margin"] = float(om)

        # yfinance liefert dividendYield als Dezimalbruch (0.038 = 3.8%)
        with contextlib.suppress(TypeError, ValueError):
            if (dy := info.get("dividendYield")) is not None:
                fundamentals["dividend_yield"] = float(dy) * 100.0

        # yfinance liefert debtToEquity in % (z.B. 45.3 = 0.453 als Ratio)
        with contextlib.suppress(TypeError, ValueError):
            if (de := info.get("debtToEquity")) is not None:
                fundamentals["debt_to_equity"] = float(de) / 100.0

        with contextlib.suppress(TypeError, ValueError):
            if (eg := info.get("earningsGrowth")) is not None:
                fundamentals["eps_growth_3y"] = float(eg)

        with contextlib.suppress(TypeError, ValueError):
            if (rg := info.get("revenueGrowth")) is not None:
                fundamentals["sales_growth_3y"] = float(rg)

        return fundamentals
