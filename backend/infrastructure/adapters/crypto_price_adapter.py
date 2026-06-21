"""CryptoPriceAdapter — OHLCV-Backfill für Top-10 Krypto-Universe via yfinance.

Alle yfinance-Aufrufe laufen via asyncio.to_thread (kein run_in_executor).
Retry: _RETRIES=2, _BASE_DELAY=1.0, Exponential Backoff (base * 2**attempt).
Ticker-Format: "BTC-USD" (direkt, kein .SW-Suffix).
"""

from __future__ import annotations

import asyncio
import logging

import pandas as pd
import yfinance

_logger = logging.getLogger(__name__)

_RETRIES = 2
_BASE_DELAY = 1.0
_MIN_COVERAGE_ROWS = 200
_MAX_GAP_TRADING_DAYS = 3


class CryptoPriceAdapter:
    """Adapter für Krypto-Preisdaten (OHLCV) via yfinance.

    Liefert Daten als DataFrame mit Spalten:
    [date, open, high, low, close, volume, symbol]
    """

    async def fetch_ohlcv(
        self,
        symbol: str,
        start: str = "2017-01-01",
    ) -> pd.DataFrame:
        """Lädt OHLCV-Daten für ein Krypto-Symbol ab einem Startdatum.

        Args:
            symbol: Ticker-Symbol, z.B. "BTC-USD"
            start: Startdatum im Format "YYYY-MM-DD" (default: 2017-01-01)

        Returns:
            DataFrame mit Spalten: date (Index), open, high, low, close, volume, symbol

        Raises:
            Exception: Wenn nach _RETRIES Wiederholungen kein Ergebnis erzielt wurde
        """
        last_exc: Exception | None = None

        for attempt in range(_RETRIES + 1):
            try:
                raw_df: pd.DataFrame = await asyncio.to_thread(
                    yfinance.download,
                    symbol,
                    start=start,
                    interval="1d",
                    progress=False,
                    auto_adjust=True,
                )
                return self._transform(raw_df, symbol)
            except Exception as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    _logger.warning(
                        "yfinance download %s attempt %d/%d failed: %s — retry in %.1fs",
                        symbol,
                        attempt + 1,
                        _RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    def validate_coverage(self, df: pd.DataFrame) -> None:
        """Prüft ob der DataFrame ausreichend Datenpunkte ohne grosse Lücken hat.

        Args:
            df: DataFrame mit DatetimeIndex (Börsentage)

        Raises:
            ValueError: Wenn weniger als _MIN_COVERAGE_ROWS Zeilen vorhanden
            ValueError: Wenn eine Lücke > _MAX_GAP_TRADING_DAYS aufeinanderfolgenden
                        Tagen im Index besteht
        """
        if len(df) < _MIN_COVERAGE_ROWS:
            raise ValueError(
                f"Unzureichende Datenmenge: {len(df)} Zeilen vorhanden, "
                f"mindestens {_MIN_COVERAGE_ROWS} erforderlich."
            )

        # Lückenprüfung: Differenz zwischen aufeinanderfolgenden Datumseinträgen
        if len(df) > 1:
            day_diffs = df.index.to_series().diff().dt.days.dropna()
            max_gap = day_diffs.max()
            if max_gap > _MAX_GAP_TRADING_DAYS:
                raise ValueError(
                    f"Datenlücke von {max_gap:.0f} Tagen gefunden (max. erlaubt: "
                    f"{_MAX_GAP_TRADING_DAYS} Tage). "
                    f"Mögliche gap im Datensatz um {day_diffs.idxmax()}."
                )

    @staticmethod
    def _transform(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Transformiert yfinance-DataFrame in das interne Format.

        Umbenennung: Open→open, High→high, Low→low, Close→close, Volume→volume
        Fügt symbol-Spalte hinzu.
        Setzt Index-Name auf 'date'.

        Args:
            raw_df: Roher yfinance DataFrame
            symbol: Krypto-Symbol für die symbol-Spalte

        Returns:
            Bereinigter DataFrame mit Kleinbuchstaben-Spalten und symbol
        """
        if raw_df.empty:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "symbol"]
            )

        # Flache MultiIndex-Spalten wenn yfinance MultiIndex zurückgibt
        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df = raw_df.droplevel(1, axis=1)

        # Spaltenauswahl und Umbenennung
        column_map = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }

        # Nur vorhandene Spalten selektieren
        existing_cols = {k: v for k, v in column_map.items() if k in raw_df.columns}
        df = raw_df[list(existing_cols.keys())].rename(columns=existing_cols)

        # Symbol-Spalte hinzufügen
        df = df.copy()
        df["symbol"] = symbol

        # Index-Name setzen
        df.index.name = "date"

        return df
