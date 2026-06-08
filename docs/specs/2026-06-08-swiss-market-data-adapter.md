# Spec: Swiss Market Data Adapter — Kurs + Fundamentaldaten

**Issue:** #5  
**Milestone:** v2.0 Swiss Foundation  
**Date:** 2026-06-08  
**Author:** Andrea Petretta (Coding-Agent: Claude Sonnet 4.6)  
**Status:** Draft — awaiting approval  
**Blocked by:** Issue #1 ✅

---

## Ziel

Den `YFinanceSwissAdapter`-Skeleton aus Issue #1 vollständig implementieren. Ziel: Live-Marktdaten (Kurse, Fundamentaldaten, Market Cap) für alle 20 SMI-Titel via yfinance (`.SW`-Suffix) abrufen. `market_cap_chf` wird erstmals befüllt.

---

## Nicht-Ziele

- Redis-Caching (deferred — separates Issue nach v2.0)
- SMIM/SPI-Tickers (Issue #4)
- SNB-Wechselkurskonvertierung (Issue #17)
- Echtzeit-Polling / WebSocket-Kurse
- SIX Exchange API (kostenpflichtig, deferred)
- Neuer REST-Endpunkt (bestehender `StockRead` zeigt `market_cap_chf` bereits)

---

## Architekturentscheidungen

### ADR-0012: SwissMarketDataProvider als eigener Port
`SwissMarketDataProvider` wird als separater ABC-Port in `domain/ports/` definiert — nicht als Erweiterung des bestehenden `MarketDataProvider`. Begründung: Swiss-spezifische Methoden (ISIN-Lookup, CHF-Fundamentaldaten) passen nicht in den generischen US-orientierten Port. Adapter bleibt austauschbar (SIX API als späteres Upgrade, ADR-0010).

### ADR-0013: yfinance synchron via ThreadPoolExecutor
`yfinance` ist eine synchrone Bibliothek. Alle `.info`- und `.history()`-Aufrufe laufen via `asyncio.get_event_loop().run_in_executor(None, fn)`, damit der FastAPI-Event-Loop nicht blockiert wird.

### ADR-0014: `SwissFundamentals` als frozen Dataclass
Fundamentaldaten aus yfinance werden als `SwissFundamentals`-Dataclass aus dem Domain-Layer zurückgegeben — kein roher `dict`. Sichert Typisierung ohne Pydantic-Overhead im Domain-Layer.

### ADR-0015: Retry mit manuellem Exponential Backoff (ohne tenacity)
`tenacity` ist nicht im Stack. Retry-Logik wird als einfacher Decorator `_with_retry(fn, retries=2, base_delay=1.0)` in `infrastructure/adapters/yfinance_swiss.py` implementiert. AGENTS.md: "Alle externen API-Calls haben Timeout + Retry mit Exponential Backoff."

---

## Domain

### Neues Value Object `SwissFundamentals`
**Datei:** `backend/domain/value_objects/swiss_fundamentals.py`

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SwissFundamentals:
    market_cap_chf: Decimal | None   # Marktkapitalisierung in CHF
    pe_ratio: float | None           # KGV (trailing)
    pb_ratio: float | None           # KBV
    dividend_yield: float | None     # Dividendenrendite (0.025 = 2.5%)
    eps_chf: float | None            # Earnings per Share in CHF
```

### Neuer Port `SwissMarketDataProvider`
**Datei:** `backend/domain/ports/swiss_market_data_provider.py`

```python
from abc import ABC, abstractmethod
from decimal import Decimal
import pandas as pd
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals


class SwissMarketDataProvider(ABC):

    @abstractmethod
    async def get_fundamentals(self, ticker: str) -> SwissFundamentals:
        """Gibt Fundamentaldaten für einen Swiss Stock zurück.

        Raises:
            SwissDataUnavailableError: wenn yfinance keinen .SW-Ticker kennt
        """
        ...

    @abstractmethod
    async def get_price_history(self, ticker: str, days: int = 252) -> pd.DataFrame:
        """Liefert Tagesschlusskurse (CHF) für die letzten `days` Handelstage.

        Returns:
            DataFrame mit DatetimeIndex (UTC) und Spalten: Close, Volume
        """
        ...

    @abstractmethod
    async def get_isin(self, ticker: str) -> str | None:
        """Ruft die ISIN direkt von yfinance ab — nützlich für Issue #26 ISIN-Verifikation."""
        ...
```

### Neue Domain Exception
**In `domain/exceptions.py` ergänzen:**

```python
class SwissDataUnavailableError(Exception):
    """yfinance hat keinen Datensatz für diesen .SW-Ticker."""
```

---

## Infrastructure

### `YFinanceSwissAdapter` (vollständig)
**Datei:** `backend/infrastructure/adapters/yfinance_swiss.py` (ersetzt Skeleton)

```python
import asyncio
import logging
import time
from decimal import Decimal
from functools import partial

import pandas as pd
import yfinance as yf

from backend.domain.exceptions import SwissDataUnavailableError
from backend.domain.ports.swiss_market_data_provider import SwissMarketDataProvider
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

_logger = logging.getLogger(__name__)
_TIMEOUT = 10.0   # Sekunden pro yfinance-Aufruf
_RETRIES = 2
_BASE_DELAY = 1.0  # Sekunden, verdoppelt sich pro Retry


class YFinanceSwissAdapter(SwissMarketDataProvider):

    def build_yf_ticker(self, ticker: str) -> str:
        return f"{ticker.upper()}.SW"

    async def get_fundamentals(self, ticker: str) -> SwissFundamentals:
        info = await self._fetch_info(ticker)
        return SwissFundamentals(
            market_cap_chf=Decimal(str(info["marketCap"])) if info.get("marketCap") else None,
            pe_ratio=info.get("trailingPE"),
            pb_ratio=info.get("priceToBook"),
            dividend_yield=info.get("dividendYield"),
            eps_chf=info.get("trailingEps"),
        )

    async def get_price_history(self, ticker: str, days: int = 252) -> pd.DataFrame:
        yf_ticker = self.build_yf_ticker(ticker)
        loop = asyncio.get_event_loop()
        fn = partial(self._sync_history, yf_ticker, days)
        return await loop.run_in_executor(None, fn)

    async def get_isin(self, ticker: str) -> str | None:
        info = await self._fetch_info(ticker)
        return info.get("isin")

    async def _fetch_info(self, ticker: str) -> dict:
        yf_ticker = self.build_yf_ticker(ticker)
        loop = asyncio.get_event_loop()
        fn = partial(self._sync_info, yf_ticker)
        return await self._with_retry(loop, fn, ticker)

    async def _with_retry(self, loop, fn, ticker: str) -> dict:
        last_exc: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                result = await loop.run_in_executor(None, fn)
                if not result:
                    raise SwissDataUnavailableError(ticker)
                return result
            except SwissDataUnavailableError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt)
                    _logger.warning("yfinance %s attempt %d failed: %s — retry in %.1fs",
                                    ticker, attempt + 1, exc, delay)
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _sync_info(yf_ticker: str) -> dict:
        return yf.Ticker(yf_ticker).info

    @staticmethod
    def _sync_history(yf_ticker: str, days: int) -> pd.DataFrame:
        df = yf.Ticker(yf_ticker).history(period=f"{days}d")
        return df[["Close", "Volume"]] if not df.empty else pd.DataFrame()
```

---

## Application Layer

### `SwissMarketService` erweitern
**Datei:** `backend/application/services/swiss_market_service.py` (erweitern)

Neue Methode:

```python
async def refresh_market_data(self, ticker: str) -> SwissStock:
    """Aktualisiert market_cap_chf für einen Ticker aus yfinance und persistiert."""
    fundamentals = await self._market_data.get_fundamentals(ticker.upper())
    existing = await self._repo.get_by_ticker(ticker)
    if existing is None:
        raise ValueError(f"Swiss Stock '{ticker}' nicht gefunden")
    updated = SwissStock(
        id=existing.id,
        ticker=existing.ticker,
        isin=existing.isin,
        name=existing.name,
        exchange=existing.exchange,
        sector=existing.sector,
        market_cap_chf=fundamentals.market_cap_chf,
    )
    await self._repo.upsert_batch([updated])
    return updated
```

`__init__` bekommt optionalen Parameter:

```python
def __init__(
    self,
    repo: SwissStockRepository,
    market_data: SwissMarketDataProvider | None = None,
) -> None:
    self._repo = repo
    self._market_data = market_data
```

---

## Dependency Injection

### `dependencies.py` erweitern

```python
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

async def get_swiss_market_data_provider() -> SwissMarketDataProvider:
    return YFinanceSwissAdapter()

async def get_swiss_market_service(
    repo: SwissStockRepository = Depends(get_swiss_stock_repository),
    market_data: SwissMarketDataProvider = Depends(get_swiss_market_data_provider),
) -> SwissMarketService:
    return SwissMarketService(repo=repo, market_data=market_data)
```

---

## Neues Script

### `scripts/update_smi_market_caps.py`

Standalone-Script (analog `seed_smi_universe.py`): iteriert über alle SMI-Stocks aus der DB, ruft für jeden `YFinanceSwissAdapter.get_fundamentals()` auf und aktualisiert `market_cap_chf` + `pe_ratio`-ähnliche Felder via `upsert_batch`.

**Scope für Issue #5:** Nur `market_cap_chf` — restliche Fundamentaldaten (pe_ratio, pb_ratio) folgen in Issue #6 wenn das Quant-Scoring-Modell kalibriert wird.

---

## `pyproject.toml` — neue Abhängigkeit

```toml
"yfinance>=0.2.40",
```

---

## Test-Cases

### Unit Tests (`tests/unit/infrastructure/test_yfinance_swiss_adapter.py`)

| Test | Setup | Erwartet |
|---|---|---|
| `test_build_yf_ticker` | `adapter.build_yf_ticker("novn")` | `"NOVN.SW"` |
| `test_get_fundamentals_ok` | Mock `yf.Ticker.info` → `{"marketCap": 250_000_000_000, ...}` | `SwissFundamentals(market_cap_chf=Decimal("250000000000"), ...)` |
| `test_get_fundamentals_empty_raises` | Mock `yf.Ticker.info` → `{}` | `SwissDataUnavailableError` |
| `test_get_price_history_ok` | Mock `.history()` → DataFrame mit Close/Volume | DataFrame mit 2 Spalten |
| `test_get_price_history_empty` | Mock `.history()` → leerer DataFrame | leerer DataFrame (kein Raise) |
| `test_get_isin` | Mock `.info` → `{"isin": "CH0038863350"}` | `"CH0038863350"` |
| `test_retry_on_exception` | Mock `.info` wirft 1x Exception, 2. Call OK | OK nach 1 Retry |

### Unit Tests (`tests/unit/application/test_swiss_market_service_data.py`)

| Test | Setup | Erwartet |
|---|---|---|
| `test_refresh_market_data_updates_market_cap` | Mock repo + mock market_data | `upsert_batch` mit neuem `market_cap_chf` aufgerufen |
| `test_refresh_market_data_raises_when_stock_not_found` | `repo.get_by_ticker` → None | `ValueError` |

---

## Dateistruktur (neu / erweitert)

```
backend/
├── domain/
│   ├── exceptions.py                           ERWEITERT (+SwissDataUnavailableError)
│   ├── ports/
│   │   └── swiss_market_data_provider.py       NEU
│   └── value_objects/
│       └── swiss_fundamentals.py               NEU
├── application/
│   └── services/
│       └── swiss_market_service.py             ERWEITERT (+refresh_market_data, +market_data param)
└── infrastructure/
    └── adapters/
        └── yfinance_swiss.py                   ERSETZT Skeleton — vollständige Implementierung

scripts/
└── update_smi_market_caps.py                   NEU

pyproject.toml                                  ERWEITERT (+yfinance)
```

---

## Akzeptanzkriterien

- [ ] `YFinanceSwissAdapter` implementiert `SwissMarketDataProvider`-Port vollständig
- [ ] `get_fundamentals("NESN")` gibt `SwissFundamentals` zurück (kein Crash)
- [ ] `get_price_history("NESN", 30)` gibt DataFrame mit `Close`/`Volume` zurück
- [ ] `get_isin("NESN")` gibt `"CH0038863350"` zurück (live-Verifikation Issue #26)
- [ ] Retry-Logik: bei transienten Fehlern 2 Retries mit Exponential Backoff
- [ ] Timeout 10s pro Aufruf (via ThreadPoolExecutor)
- [ ] `SwissMarketService.refresh_market_data(ticker)` aktualisiert `market_cap_chf` in DB
- [ ] `scripts/update_smi_market_caps.py` aktualisiert alle 20 SMI-Stocks idempotent
- [ ] `yfinance>=0.2.40` in `pyproject.toml`
- [ ] 7 Unit Tests Adapter + 2 Unit Tests Service (alle grün)
- [ ] CI grün (ruff, mypy, pytest)
- [ ] Kein API-Key im Code

---

*PRISMA V2 · Issue #5 · v2.0 Swiss Foundation · 2026-06-08*
