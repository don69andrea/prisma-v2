"""SimFin Adapter — historische Fundamentaldaten für ML-Training (nur offline).

Wird NICHT in der Inferenz-Pipeline verwendet (kein API-Key in Prod nötig).
Nur in scripts/train_return_predictor.py mit --simfin-key aktiviert.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

_logger = logging.getLogger(__name__)

# SimFin market suffix mapping
_SUFFIX_TO_MARKET: dict[str, str] = {
    "sw": "ch",
    "de": "de",
    "pa": "fr",
    "as": "nl",
    "mc": "es",
    "mi": "it",
}


def ticker_to_simfin_market(ticker: str) -> str:
    """Leitet SimFin-Markt aus Ticker-Suffix ab (z.B. SAP.DE → 'de', NESN → 'ch')."""
    if "." in ticker:
        suffix = ticker.rsplit(".", 1)[-1].lower()
        return _SUFFIX_TO_MARKET.get(suffix, "de")
    return "ch"


def ticker_clean(ticker: str) -> str:
    """Entfernt Börsen-Suffix für SimFin-Lookup (NESN.SW → NESN, SAP.DE → SAP)."""
    return ticker.split(".")[0].upper()


class SimFinAdapter:
    """Lädt historische Point-in-Time Fundamentaldaten von SimFin für ML-Training.

    Cached alle Downloads lokal (SimFin-SDK schreibt CSV-Dateien ins data_dir).
    Bei fehlenden Daten gibt get_fundamentals_on_date() None zurück → Fallback
    auf _stub_fundamentals() im Aufrufer.
    """

    def __init__(self, api_key: str, data_dir: Path | None = None) -> None:
        try:
            import simfin as sf
        except ImportError as exc:
            raise ImportError(
                "simfin nicht installiert — `pip install simfin` ausführen."
            ) from exc

        self._sf = sf
        self._data_dir = data_dir or Path.home() / ".simfin_cache"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, pd.DataFrame | None] = {}

        sf.set_api_key(api_key)
        sf.set_data_dir(str(self._data_dir))
        _logger.info("SimFinAdapter initialisiert (data_dir=%s)", self._data_dir)

    def _load_derived(self, market: str) -> pd.DataFrame | None:
        """Lädt 'derived' Quartalsdaten (P/E, P/B, DivYield) für einen Markt."""
        if market in self._cache:
            return self._cache[market]
        try:
            df = self._sf.load(dataset="derived", variant="quarterly", market=market)
            if df is not None and not df.empty:
                _logger.info("SimFin derived geladen: market=%s, %d Einträge", market, len(df))
            self._cache[market] = df
            return df
        except Exception as exc:
            _logger.warning("SimFin Ladefehler market=%s: %s", market, exc)
            self._cache[market] = None
            return None

    def get_fundamentals_on_date(
        self,
        ticker: str,
        snap_date: date,
        market: str = "ch",
    ) -> SwissFundamentals | None:
        """Gibt Point-in-Time Fundamentaldaten für (ticker, snap_date) zurück.

        Nutzt den letzten verfügbaren Quartalsbericht vor snap_date.
        Returns None wenn keine Daten verfügbar.
        """
        derived = self._load_derived(market)
        if derived is None:
            return None

        clean = ticker_clean(ticker)

        try:
            # MultiIndex: (Ticker, Date) or just index by Ticker
            idx = derived.index
            if hasattr(idx, "levels"):
                # MultiIndex — first level should be Ticker
                tickers_available = idx.get_level_values(0).unique()
                if clean not in tickers_available:
                    return None
                ticker_df = derived.loc[clean]
            else:
                if clean not in derived.index:
                    return None
                ticker_df = derived.loc[[clean]]

            # Ensure DatetimeIndex
            if not isinstance(ticker_df.index, pd.DatetimeIndex):
                ticker_df = ticker_df.copy()
                ticker_df.index = pd.to_datetime(ticker_df.index)

            snap_ts = pd.Timestamp(snap_date)
            historical = ticker_df[ticker_df.index <= snap_ts]
            if historical.empty:
                return None

            row = historical.iloc[-1]

            # Try multiple column name variants (SimFin changes names across versions)
            def _get(candidates: list[str]) -> float | None:
                for c in candidates:
                    val = row.get(c)
                    if val is not None and not pd.isna(val):
                        return float(val)
                return None

            pe = _get(["P/E", "Price to Earnings Ratio (TTM)", "PE Ratio"])
            pb = _get(["P/B", "Price to Book Value", "PB Ratio"])
            div = _get(["Dividend Yield", "Dividend Yield (%)", "Div. Yield"])
            eps = _get(["EPS (Diluted)", "Earnings per Share (Diluted)", "EPS"])

            if div is not None and div > 1.0:
                div = div / 100.0  # SimFin sometimes gives % as 2.5 instead of 0.025

            return SwissFundamentals(
                market_cap_chf=None,
                pe_ratio=pe,
                pb_ratio=pb,
                dividend_yield=div,
                eps_chf=eps,
            )

        except Exception as exc:
            _logger.debug("SimFin Lookup %s@%s fehlgeschlagen: %s", ticker, snap_date, exc)
            return None
