"""CoinMetricsAdapter — On-Chain Daten via Coin Metrics Community API (no auth).

Alle HTTP-Aufrufe via httpx.AsyncClient.
Retry: _RETRIES=2, _BASE_DELAY=1.0, Exponential Backoff (base * 2**attempt).
Endpoint: https://community-api.coinmetrics.io/v4/timeseries/asset-metrics

Feldmapping:
  SplyMVRVCur  → mvrv_z
  RealizedCap  → realized_cap
  AdrActCnt    → active_addresses
  FlowOutExNtv - FlowInExNtv → exchange_netflow

NULL-Fallback: Wenn Coin keine Daten hat (404 oder leere Response),
wird ein leerer DataFrame zurückgegeben (kein Raise).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

import httpx
import pandas as pd

_logger = logging.getLogger(__name__)

_BASE_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
_METRICS = "RealizedCap,SplyMVRVCur,AdrActCnt,FlowOutExNtv,FlowInExNtv"
_RETRIES = 2
_BASE_DELAY = 1.0

_EMPTY_COLUMNS = [
    "date",
    "asset",
    "mvrv_z",
    "realized_cap",
    "active_addresses",
    "tx_volume",
    "exchange_netflow",
]


class CoinMetricsAdapter:
    """Adapter für On-Chain-Daten via Coin Metrics Community API.

    Liefert Daten als DataFrame mit Spalten:
    [date, asset, mvrv_z, realized_cap, active_addresses, tx_volume, exchange_netflow]
    """

    async def fetch_onchain(
        self,
        assets: list[str],
        start: str = "2017-01-01",
    ) -> pd.DataFrame:
        """Lädt On-Chain-Metriken für mehrere Assets ab einem Startdatum.

        Args:
            assets: Liste von Asset-Symbolen, z.B. ["btc", "eth"]
            start: Startdatum im Format "YYYY-MM-DD" (default: 2017-01-01)

        Returns:
            DataFrame mit Spalten: date, asset, mvrv_z, realized_cap,
            active_addresses, tx_volume, exchange_netflow.
            Leerer DataFrame wenn Coin nicht verfügbar.

        Raises:
            httpx.ConnectError / httpx.TimeoutException: Nach _RETRIES+1 fehlgeschlagenen
            Versuchen bei Netzwerkfehlern (nicht bei 404 = Coin nicht verfügbar).
        """
        params = {
            "assets": ",".join(assets),
            "metrics": _METRICS,
            "frequency": "1d",
            "start_time": start,
        }

        last_exc: Exception | None = None

        for attempt in range(_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(_BASE_URL, params=params)
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as status_err:
                        if status_err.response.status_code == 404:
                            _logger.info(
                                "Coin Metrics: Coin(s) %s nicht verfügbar (404) — NULL-Fallback",
                                assets,
                            )
                            return pd.DataFrame(columns=_EMPTY_COLUMNS)
                        raise

                    data = response.json().get("data", [])
                    if not data:
                        _logger.info(
                            "Coin Metrics: keine Daten für %s — leerer DataFrame",
                            assets,
                        )
                        return pd.DataFrame(columns=_EMPTY_COLUMNS)

                    return self._transform(data)

            except httpx.HTTPStatusError:
                raise  # Bereits behandelt (404 → früher Return), andere Status durchreichen
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    _logger.warning(
                        "Coin Metrics request attempt %d/%d failed: %s — retry in %.1fs",
                        attempt + 1,
                        _RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _parse_date(time_str: str) -> date:
        """Parsed ISO-8601-Timestamp (z.B. '2024-01-01T00:00:00.000000000Z') zu date."""
        # Nanozeitsekunden abschneiden falls vorhanden
        time_str = time_str.split(".")[0]
        if not time_str.endswith("Z"):
            time_str += "Z"
        # Format mit Sekunden: "2024-01-01T00:00:00Z"
        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.replace(tzinfo=UTC).date()

    @staticmethod
    def _to_float_or_none(value: str | None) -> float | None:
        """Konvertiert String zu float, gibt None bei leerem/fehlendem Wert zurück."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _transform(cls, data: list[dict[str, str]]) -> pd.DataFrame:
        """Transformiert Coin Metrics JSON-Data in internes DataFrame-Format.

        Args:
            data: Liste von Dicts aus response["data"]

        Returns:
            DataFrame mit Spalten: date, asset, mvrv_z, realized_cap,
            active_addresses, tx_volume, exchange_netflow
        """
        rows = []
        for entry in data:
            flow_out = cls._to_float_or_none(entry.get("FlowOutExNtv"))
            flow_in = cls._to_float_or_none(entry.get("FlowInExNtv"))
            if flow_out is not None and flow_in is not None:
                exchange_netflow: float | None = flow_out - flow_in
            else:
                exchange_netflow = None

            rows.append(
                {
                    "date": cls._parse_date(entry["time"]),
                    "asset": entry.get("asset", ""),
                    "mvrv_z": cls._to_float_or_none(entry.get("SplyMVRVCur")),
                    "realized_cap": cls._to_float_or_none(entry.get("RealizedCap")),
                    "active_addresses": cls._to_float_or_none(entry.get("AdrActCnt")),
                    "tx_volume": None,  # Nicht im Community-API-Plan enthalten
                    "exchange_netflow": exchange_netflow,
                }
            )

        return pd.DataFrame(rows, columns=_EMPTY_COLUMNS)
