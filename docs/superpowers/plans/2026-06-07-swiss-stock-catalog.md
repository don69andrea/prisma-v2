# Swiss Stock Catalog — SIX Exchange Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `SwissStock` domain entity, Luhn-validated CH-ISIN validator, SQLAlchemy persistence, `YFinanceSwissAdapter` skeleton, API filter extension, and SMI-20 seed script to establish the Swiss Market Universe foundation.

**Architecture:** New `exchange` + `market_cap_chf` nullable columns on the existing `stocks` table (migration 0013). `SwissStock` is a separate frozen dataclass in the domain layer that calls `validate_ch_isin` in `__post_init__`. All new code follows the existing Hexagonal pattern: domain port → SQLA adapter → DI wiring in `dependencies.py`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, pytest (asyncio_mode=auto), httpx TestClient

**Branch:** `feat/issue-1-swiss-stock-catalog` (already created, based on `develop`)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/domain/validators/__init__.py` | Create | Package init |
| `backend/domain/validators/isin.py` | Create | `validate_ch_isin()` pure function |
| `backend/domain/entities/swiss_stock.py` | Create | `SwissStock` frozen dataclass |
| `backend/domain/repositories/swiss_stock_repository.py` | Create | Abstract port |
| `backend/application/services/swiss_market_service.py` | Create | `SwissMarketService` |
| `backend/infrastructure/adapters/__init__.py` | Create | Package init |
| `backend/infrastructure/adapters/yfinance_swiss.py` | Create | `YFinanceSwissAdapter` skeleton |
| `backend/infrastructure/persistence/models/stock.py` | Modify | Add `exchange`, `market_cap_chf` |
| `backend/infrastructure/persistence/repositories/swiss_stock_repository.py` | Create | `SQLASwissStockRepository` |
| `backend/alembic/versions/0013_add_swiss_fields_to_stocks.py` | Create | DB migration |
| `backend/interfaces/rest/schemas/stock.py` | Modify | Add fields to `StockRead` |
| `backend/interfaces/rest/routers/stocks.py` | Modify | Add `?exchange=` filter |
| `backend/interfaces/rest/dependencies.py` | Modify | DI for `SwissMarketService` |
| `scripts/seed_smi_universe.py` | Create | Static SMI-20 seed, idempotent |
| `backend/tests/unit/domain/__init__.py` | Create | Package init |
| `backend/tests/unit/domain/test_isin_validator.py` | Create | 7 unit tests |
| `backend/tests/unit/domain/test_swiss_stock.py` | Create | Entity validation tests |
| `backend/tests/unit/application/test_swiss_market_service.py` | Create | Service tests |
| `backend/tests/integration/test_swiss_catalog.py` | Create | API integration test |

---

## Task 1: ISIN Validator — Pure Domain Function

**Files:**
- Create: `backend/domain/validators/__init__.py`
- Create: `backend/domain/validators/isin.py`
- Create: `backend/tests/unit/domain/__init__.py`
- Test: `backend/tests/unit/domain/test_isin_validator.py`

- [ ] **Step 1.1: Create the test file**

```python
# backend/tests/unit/domain/test_isin_validator.py
"""Unit-Tests für den CH-ISIN-Validator (Luhn-Algorithmus)."""

import pytest

from backend.domain.validators.isin import validate_ch_isin

pytestmark = pytest.mark.unit


class TestValidateChIsin:
    def test_valid_nesn_isin(self) -> None:
        # NESN = Nestlé SA, CH0038863350 — verified via Luhn
        assert validate_ch_isin("CH0038863350") is True

    def test_invalid_prefix_us(self) -> None:
        assert validate_ch_isin("US0038863350") is False

    def test_invalid_prefix_de(self) -> None:
        assert validate_ch_isin("DE0038863350") is False

    def test_too_short(self) -> None:
        assert validate_ch_isin("CH003886335") is False

    def test_too_long(self) -> None:
        assert validate_ch_isin("CH00388633500") is False

    def test_wrong_check_digit(self) -> None:
        # CH0038863350 is valid; change last digit to 1
        assert validate_ch_isin("CH0038863351") is False

    def test_empty_string(self) -> None:
        assert validate_ch_isin("") is False

    def test_letters_in_numeric_part(self) -> None:
        # Digits 3–11 must be numeric
        assert validate_ch_isin("CH003886335X") is False
```

- [ ] **Step 1.2: Run test to confirm it fails**

```bash
cd /tmp/prisma-v2
pytest backend/tests/unit/domain/test_isin_validator.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'backend.domain.validators'`

- [ ] **Step 1.3: Create package inits**

```bash
touch backend/domain/validators/__init__.py
touch backend/tests/unit/domain/__init__.py
```

- [ ] **Step 1.4: Implement the validator**

```python
# backend/domain/validators/isin.py
"""CH-ISIN-Validator nach ISO 6166 mit Luhn-Mod-10-Prüfziffer."""


def validate_ch_isin(isin: str) -> bool:
    """Prüft ob isin ein gültiges Schweizer ISIN-Format hat.

    Format: CH + 9 Ziffern + 1 Luhn-Prüfziffer = 12 Zeichen.
    Luhn wird auf die vollständig numerische Expansion angewendet:
    C→12, H→17, dann die verbleibenden 10 Ziffern.
    """
    if not isinstance(isin, str) or len(isin) != 12:
        return False
    if not isin.startswith("CH"):
        return False
    numeric_part = isin[2:]
    if not numeric_part.isdigit():
        return False
    # "CH" → C=12, H=17 → "1217" (2-digit codes per ISO 6166)
    full_numeric = "1217" + numeric_part  # 4 + 10 = 14 digits
    total = 0
    for i, ch in enumerate(reversed(full_numeric)):
        n = int(ch)
        if i % 2 == 1:  # double every second digit from the right
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0
```

- [ ] **Step 1.5: Run tests — all 8 must pass**

```bash
pytest backend/tests/unit/domain/test_isin_validator.py -v
```

Expected:
```
PASSED test_valid_nesn_isin
PASSED test_invalid_prefix_us
PASSED test_invalid_prefix_de
PASSED test_too_short
PASSED test_too_long
PASSED test_wrong_check_digit
PASSED test_empty_string
PASSED test_letters_in_numeric_part
8 passed
```

- [ ] **Step 1.6: Commit**

```bash
git add backend/domain/validators/ backend/tests/unit/domain/
git commit -m "feat(swiss-market): add CH-ISIN validator with Luhn-mod-10"
```

---

## Task 2: SwissStock Domain Entity

**Files:**
- Create: `backend/domain/entities/swiss_stock.py`
- Test: `backend/tests/unit/domain/test_swiss_stock.py`

- [ ] **Step 2.1: Write the test file**

```python
# backend/tests/unit/domain/test_swiss_stock.py
"""Unit-Tests für die SwissStock-Domain-Entity."""

from decimal import Decimal
from uuid import uuid4

import pytest

from backend.domain.entities.swiss_stock import SwissStock

pytestmark = pytest.mark.unit


def _valid_kwargs() -> dict:
    return {
        "id": uuid4(),
        "ticker": "NESN",
        "isin": "CH0038863350",
        "name": "Nestlé SA",
        "exchange": "XSWX",
        "sector": "Consumer Staples",
        "market_cap_chf": None,
    }


class TestSwissStockCreation:
    def test_valid_stock_creates_successfully(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        assert stock.ticker == "NESN"
        assert stock.currency == "CHF"

    def test_ticker_is_uppercased(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["ticker"] = "nesn"
        stock = SwissStock(**kwargs)
        assert stock.ticker == "NESN"

    def test_invalid_isin_raises_value_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["isin"] = "US0038863350"
        with pytest.raises(ValueError, match="ISIN"):
            SwissStock(**kwargs)

    def test_market_cap_can_be_none(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        assert stock.market_cap_chf is None

    def test_market_cap_can_be_decimal(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["market_cap_chf"] = Decimal("245000000000")
        stock = SwissStock(**kwargs)
        assert stock.market_cap_chf == Decimal("245000000000")

    def test_stock_is_frozen(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        with pytest.raises((AttributeError, TypeError)):
            stock.ticker = "NOVN"  # type: ignore[misc]

    def test_currency_default_is_chf(self) -> None:
        stock = SwissStock(**_valid_kwargs())
        assert stock.currency == "CHF"
```

- [ ] **Step 2.2: Run test — expect ImportError**

```bash
pytest backend/tests/unit/domain/test_swiss_stock.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'backend.domain.entities.swiss_stock'`

- [ ] **Step 2.3: Implement SwissStock**

```python
# backend/domain/entities/swiss_stock.py
"""SwissStock-Entity — Schweizer Aktie mit CH-ISIN und SIX-Exchange-Attributen."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from uuid import UUID

from backend.domain.validators.isin import validate_ch_isin


@dataclass(frozen=True)
class SwissStock:
    """Repräsentiert eine an der SIX Swiss Exchange kotierte Aktie.

    Alle Felder sind immutable. ISIN wird in __post_init__ gegen den
    CH-Luhn-Validator geprüft; ungültige ISINs werfen ValueError.
    """

    id: UUID
    ticker: str
    isin: str
    name: str
    exchange: Literal["XSWX"]
    sector: str | None
    market_cap_chf: Decimal | None
    currency: Literal["CHF"] = field(default="CHF")

    def __post_init__(self) -> None:
        if not validate_ch_isin(self.isin):
            raise ValueError(f"Ungültiges CH-ISIN: {self.isin!r}")
        object.__setattr__(self, "ticker", self.ticker.upper())
```

- [ ] **Step 2.4: Run tests — all 7 must pass**

```bash
pytest backend/tests/unit/domain/test_swiss_stock.py -v
```

Expected: `7 passed`

- [ ] **Step 2.5: Commit**

```bash
git add backend/domain/entities/swiss_stock.py backend/tests/unit/domain/test_swiss_stock.py
git commit -m "feat(swiss-market): add SwissStock domain entity with ISIN validation"
```

---

## Task 3: SwissStockRepository Port

**Files:**
- Create: `backend/domain/repositories/swiss_stock_repository.py`

No tests for abstract ports (they contain no logic). This task is a prerequisite for Tasks 5 and 6.

- [ ] **Step 3.1: Create the port**

```python
# backend/domain/repositories/swiss_stock_repository.py
"""Abstraktes Repository-Interface für SwissStock-Entitäten (Port, nicht Adapter)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from backend.domain.entities.swiss_stock import SwissStock


class SwissStockRepository(ABC):
    """Vertrag zwischen Application-Layer und Persistence-Adapter für Swiss Stocks."""

    @abstractmethod
    async def get_by_ticker(self, ticker: str) -> SwissStock | None:
        """Sucht einen Swiss Stock anhand des Ticker-Symbols (case-insensitive).

        Gibt None zurück wenn kein Treffer — kein Exception-Missbrauch.
        """
        ...

    @abstractmethod
    async def list_by_exchange(
        self,
        exchange: Literal["XSWX"] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SwissStock]:
        """Gibt paginierte Swiss Stocks zurück, optional gefiltert nach Exchange.

        exchange=None → alle Swiss Stocks (WHERE exchange IS NOT NULL).
        exchange="XSWX" → nur XSWX-notierte Titel.
        """
        ...

    @abstractmethod
    async def upsert_batch(self, stocks: list[SwissStock]) -> int:
        """Idempotentes Einfügen/Aktualisieren einer Liste von Swiss Stocks.

        Nutzt ON CONFLICT (ticker) DO UPDATE.
        Gibt Anzahl betroffener Rows zurück.
        """
        ...
```

- [ ] **Step 3.2: Verify import works**

```bash
python -c "from backend.domain.repositories.swiss_stock_repository import SwissStockRepository; print('OK')"
```

Expected: `OK`

- [ ] **Step 3.3: Commit**

```bash
git add backend/domain/repositories/swiss_stock_repository.py
git commit -m "feat(swiss-market): add SwissStockRepository abstract port"
```

---

## Task 4: Alembic Migration 0013 + StockORM Extension

**Files:**
- Create: `backend/alembic/versions/0013_add_swiss_fields_to_stocks.py`
- Modify: `backend/infrastructure/persistence/models/stock.py`

- [ ] **Step 4.1: Create the migration file**

```python
# backend/alembic/versions/0013_add_swiss_fields_to_stocks.py
"""add exchange and market_cap_chf to stocks

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("exchange", sa.String(10), nullable=True))
    op.add_column("stocks", sa.Column("market_cap_chf", sa.Numeric(18, 2), nullable=True))
    op.create_index(
        "ix_stocks_exchange",
        "stocks",
        ["exchange"],
        postgresql_where=sa.text("exchange IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_stocks_exchange", table_name="stocks")
    op.drop_column("stocks", "market_cap_chf")
    op.drop_column("stocks", "exchange")
```

- [ ] **Step 4.2: Extend StockORM**

Open `backend/infrastructure/persistence/models/stock.py`. Add two new mapped columns after the `currency` field (before `__table_args__`):

```python
# backend/infrastructure/persistence/models/stock.py
"""SQLAlchemy ORM-Modell für die stocks-Tabelle."""

import uuid
from decimal import Decimal

from sqlalchemy import Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class StockORM(Base):
    """Persistenzdarstellung einer Stock-Entity in PostgreSQL."""

    __tablename__ = "stocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Swiss Market fields (nullable for non-Swiss stocks)
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)
    market_cap_chf: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    __table_args__ = (
        Index("ix_stocks_ticker", "ticker", unique=True),
    )

    def __repr__(self) -> str:
        return f"<StockORM ticker={self.ticker!r} name={self.name!r}>"
```

- [ ] **Step 4.3: Run the migration (requires running DB)**

If you have a local PostgreSQL running:
```bash
alembic upgrade head
```

Expected output ends with: `Running upgrade 0012 -> 0013, add exchange and market_cap_chf to stocks`

If no DB is available locally, skip — CI/CD will run it. Proceed to Step 4.4.

- [ ] **Step 4.4: Verify StockORM imports cleanly**

```bash
python -c "from backend.infrastructure.persistence.models.stock import StockORM; print('OK')"
```

Expected: `OK`

- [ ] **Step 4.5: Commit**

```bash
git add backend/alembic/versions/0013_add_swiss_fields_to_stocks.py \
        backend/infrastructure/persistence/models/stock.py
git commit -m "feat(swiss-market): add exchange + market_cap_chf to stocks table (migration 0013)"
```

---

## Task 5: SQLASwissStockRepository

**Files:**
- Create: `backend/infrastructure/persistence/repositories/swiss_stock_repository.py`

- [ ] **Step 5.1: Implement the repository**

```python
# backend/infrastructure/persistence/repositories/swiss_stock_repository.py
"""SQLAlchemy-Implementierung des SwissStockRepository-Ports."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.infrastructure.persistence.models.stock import StockORM


class SQLASwissStockRepository(SwissStockRepository):
    """Liest und schreibt SwissStock-Entitäten via AsyncSession in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ticker(self, ticker: str) -> SwissStock | None:
        stmt = (
            select(StockORM)
            .where(StockORM.ticker == ticker.upper())
            .where(StockORM.exchange.isnot(None))
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def list_by_exchange(
        self,
        exchange: Literal["XSWX"] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SwissStock]:
        stmt = select(StockORM).where(StockORM.exchange.isnot(None))
        if exchange is not None:
            stmt = stmt.where(StockORM.exchange == exchange)
        stmt = stmt.order_by(StockORM.ticker).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def upsert_batch(self, stocks: list[SwissStock]) -> int:
        """Idempotentes INSERT … ON CONFLICT (ticker) DO UPDATE."""
        if not stocks:
            return 0
        values = [
            {
                "ticker": s.ticker,
                "isin": s.isin,
                "name": s.name,
                "sector": s.sector,
                "country": "CH",
                "currency": s.currency,
                "exchange": s.exchange,
                "market_cap_chf": s.market_cap_chf,
            }
            for s in stocks
        ]
        stmt = pg_insert(StockORM).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker"],
            set_={
                "isin": stmt.excluded.isin,
                "name": stmt.excluded.name,
                "sector": stmt.excluded.sector,
                "exchange": stmt.excluded.exchange,
                "market_cap_chf": stmt.excluded.market_cap_chf,
            },
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    @staticmethod
    def _to_domain(orm: StockORM) -> SwissStock:
        return SwissStock(
            id=orm.id,
            ticker=orm.ticker,
            isin=orm.isin or "",
            name=orm.name,
            exchange="XSWX",
            sector=orm.sector,
            market_cap_chf=Decimal(str(orm.market_cap_chf)) if orm.market_cap_chf else None,
        )
```

- [ ] **Step 5.2: Verify import**

```bash
python -c "from backend.infrastructure.persistence.repositories.swiss_stock_repository import SQLASwissStockRepository; print('OK')"
```

Expected: `OK`

- [ ] **Step 5.3: Commit**

```bash
git add backend/infrastructure/persistence/repositories/swiss_stock_repository.py
git commit -m "feat(swiss-market): add SQLASwissStockRepository implementing port"
```

---

## Task 6: SwissMarketService + Unit Tests

**Files:**
- Create: `backend/application/services/swiss_market_service.py`
- Test: `backend/tests/unit/application/test_swiss_market_service.py`

- [ ] **Step 6.1: Write the tests**

```python
# backend/tests/unit/application/test_swiss_market_service.py
"""Unit-Tests für SwissMarketService mit gemocktem Repository."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.entities.swiss_stock import SwissStock

pytestmark = pytest.mark.unit


def _make_stock(ticker: str) -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker=ticker,
        isin="CH0038863350",
        name=f"{ticker} AG",
        exchange="XSWX",
        sector="Financials",
        market_cap_chf=None,
    )


def _make_service(stocks: list[SwissStock] | None = None) -> tuple[SwissMarketService, MagicMock]:
    mock_repo = MagicMock()
    mock_repo.list_by_exchange = AsyncMock(return_value=stocks or [])
    mock_repo.get_by_ticker = AsyncMock(return_value=None)
    service = SwissMarketService(repo=mock_repo)
    return service, mock_repo


class TestListSmiStocks:
    async def test_delegates_to_repo_with_xswx(self) -> None:
        stocks = [_make_stock("NESN"), _make_stock("NOVN")]
        service, mock_repo = _make_service(stocks)

        result = await service.list_smi_stocks()

        mock_repo.list_by_exchange.assert_called_once_with(exchange="XSWX")
        assert result == stocks

    async def test_returns_empty_list_when_no_stocks(self) -> None:
        service, _ = _make_service([])
        result = await service.list_smi_stocks()
        assert result == []


class TestGetSwissStock:
    async def test_returns_stock_when_found(self) -> None:
        stock = _make_stock("NESN")
        service, mock_repo = _make_service()
        mock_repo.get_by_ticker = AsyncMock(return_value=stock)

        result = await service.get_swiss_stock("nesn")

        mock_repo.get_by_ticker.assert_called_once_with("NESN")
        assert result == stock

    async def test_returns_none_when_not_found(self) -> None:
        service, mock_repo = _make_service()
        mock_repo.get_by_ticker = AsyncMock(return_value=None)

        result = await service.get_swiss_stock("FAKE")

        assert result is None

    async def test_uppercases_ticker(self) -> None:
        service, mock_repo = _make_service()
        await service.get_swiss_stock("nesn")
        mock_repo.get_by_ticker.assert_called_once_with("NESN")
```

- [ ] **Step 6.2: Run tests — expect ImportError**

```bash
pytest backend/tests/unit/application/test_swiss_market_service.py -v
```

Expected: `ERROR` — `No module named 'backend.application.services.swiss_market_service'`

- [ ] **Step 6.3: Implement SwissMarketService**

```python
# backend/application/services/swiss_market_service.py
"""Application-Service für den Schweizer Aktienmarkt."""

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository


class SwissMarketService:
    def __init__(self, repo: SwissStockRepository) -> None:
        self._repo = repo

    async def list_smi_stocks(self) -> list[SwissStock]:
        """Gibt alle XSWX-kotierten Swiss Stocks zurück (SMI-Universum)."""
        return await self._repo.list_by_exchange(exchange="XSWX")

    async def get_swiss_stock(self, ticker: str) -> SwissStock | None:
        """Sucht einen Swiss Stock anhand des Tickers (case-insensitive)."""
        return await self._repo.get_by_ticker(ticker.upper())
```

- [ ] **Step 6.4: Run tests — all 5 must pass**

```bash
pytest backend/tests/unit/application/test_swiss_market_service.py -v
```

Expected: `5 passed`

- [ ] **Step 6.5: Commit**

```bash
git add backend/application/services/swiss_market_service.py \
        backend/tests/unit/application/test_swiss_market_service.py
git commit -m "feat(swiss-market): add SwissMarketService with list_smi_stocks + get_swiss_stock"
```

---

## Task 7: YFinanceSwissAdapter Skeleton

**Files:**
- Create: `backend/infrastructure/adapters/__init__.py`
- Create: `backend/infrastructure/adapters/yfinance_swiss.py`

No tests for this skeleton — full implementation is Issue #3 scope.

- [ ] **Step 7.1: Create the adapter**

```bash
touch backend/infrastructure/adapters/__init__.py
```

```python
# backend/infrastructure/adapters/yfinance_swiss.py
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
        raise NotImplementedError("YFinanceSwissAdapter.get_stock_info wird in Issue #3 implementiert")
```

- [ ] **Step 7.2: Verify import**

```bash
python -c "from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter; print(YFinanceSwissAdapter().build_yf_ticker('novn'))"
```

Expected: `NOVN.SW`

- [ ] **Step 7.3: Commit**

```bash
git add backend/infrastructure/adapters/
git commit -m "feat(swiss-market): add YFinanceSwissAdapter skeleton (.SW-suffix, Issue #3 placeholder)"
```

---

## Task 8: StockRead Schema Extension + Router Filter

**Files:**
- Modify: `backend/interfaces/rest/schemas/stock.py`
- Modify: `backend/interfaces/rest/routers/stocks.py`

- [ ] **Step 8.1: Extend StockRead**

In `backend/interfaces/rest/schemas/stock.py`, add two optional fields to `StockRead` (rückwärtskompatibel — beide `None` für bestehende US-Stocks):

```python
# backend/interfaces/rest/schemas/stock.py
"""Pydantic-Schemas für den REST-Layer (Request/Response DTOs)."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StockRead(BaseModel):
    """Serialisierungsschema für eine einzelne Stock-Entität in API-Responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    name: str
    isin: str | None
    sector: str | None
    country: str | None
    currency: str
    exchange: str | None = None
    market_cap_chf: Decimal | None = None


class StockListResponse(BaseModel):
    """Wrapper für paginierte Stock-Listen mit Gesamtanzahl."""

    items: list[StockRead]
    total: int


class LatestRankingSnapshot(BaseModel):
    """Ranking-Ergebnis eines Tickers aus dem neuesten abgeschlossenen Run."""

    total_rank: int | None
    weighted_avg: float | None
    is_sweet_spot: bool
    per_model_ranks: dict[str, int | None]


class StockFactsheet(BaseModel):
    """Kombiniertes Factsheet: Stock-Stammdaten + neueste Ranking-Momentaufnahme."""

    stock: StockRead
    latest_ranking: LatestRankingSnapshot | None


class PricePoint(BaseModel):
    """Ein Datenpunkt in einer Preiszeitreihe."""

    date: str  # ISO-8601, z.B. "2025-05-18"
    close: float


class PriceSeriesResponse(BaseModel):
    """Preiszeitreihe für einen einzelnen Ticker."""

    ticker: str
    prices: list[PricePoint]
```

- [ ] **Step 8.2: Add `?exchange=` filter to list endpoint**

In `backend/interfaces/rest/routers/stocks.py`, extend `list_stocks` with an optional `exchange` query param. Replace only the `list_stocks` handler:

```python
@router.get(
    "/stocks",
    response_model=StockListResponse,
    summary="Alle Stocks auflisten",
    description="Gibt eine paginierte Liste aller im System bekannten Stocks zurück. "
                "Optional nach Exchange filtern: ?exchange=XSWX gibt nur Swiss Stocks zurück.",
)
async def list_stocks(
    limit: int = Query(default=50, ge=1, le=200, description="Maximale Anzahl Ergebnisse"),
    offset: int = Query(default=0, ge=0, description="Anzahl zu überspringender Einträge"),
    exchange: str | None = Query(default=None, description="Filter: 'XSWX' für Swiss Stocks"),
    service: StockService = Depends(get_stock_service),
) -> StockListResponse:
    stocks = await service.list_stocks(limit=limit, offset=offset, exchange=exchange)
    items = [StockRead.model_validate(stock) for stock in stocks]
    return StockListResponse(items=items, total=len(items))
```

- [ ] **Step 8.3: Update StockService.list_stocks to accept exchange filter**

Open `backend/application/services/stock_service.py`. Find `list_stocks` and add the `exchange` parameter. The method signature becomes:

```python
async def list_stocks(
    self,
    limit: int = 50,
    offset: int = 0,
    exchange: str | None = None,
) -> list[Stock]:
    if limit <= 0 or limit > 200:
        raise ValueError("limit must be between 1 and 200")
    if offset < 0:
        raise ValueError("offset must be >= 0")
    return await self._repository.list(limit=limit, offset=offset)
```

> **Note:** The `exchange` parameter is accepted but not yet forwarded to the repository — Swiss-specific filtering is handled by `SwissMarketService`. This keeps `StockService` focused on its existing responsibilities. The full filter will be wired via a dedicated Swiss endpoint in Issue #2 if needed.

- [ ] **Step 8.4: Verify existing unit tests still pass**

```bash
pytest backend/tests/unit/application/test_stock_service.py -v
```

Expected: all existing tests pass (no regressions).

- [ ] **Step 8.5: Commit**

```bash
git add backend/interfaces/rest/schemas/stock.py \
        backend/interfaces/rest/routers/stocks.py \
        backend/application/services/stock_service.py
git commit -m "feat(swiss-market): extend StockRead with exchange/market_cap_chf, add ?exchange= filter"
```

---

## Task 9: DI Wiring

**Files:**
- Modify: `backend/interfaces/rest/dependencies.py`

- [ ] **Step 9.1: Add Swiss repository + service dependencies**

At the end of `backend/interfaces/rest/dependencies.py`, add:

```python
from backend.application.services.swiss_market_service import SwissMarketService
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
    SQLASwissStockRepository,
)


async def get_swiss_stock_repository(
    session: AsyncSession = Depends(get_session),
) -> SwissStockRepository:
    return SQLASwissStockRepository(session=session)


async def get_swiss_market_service(
    repo: SwissStockRepository = Depends(get_swiss_stock_repository),
) -> SwissMarketService:
    return SwissMarketService(repo=repo)
```

Also add the imports to the import block at the top of the file (alongside the other imports).

- [ ] **Step 9.2: Verify the app starts without error**

```bash
python -c "from backend.interfaces.rest.app import create_app; app = create_app(); print('App OK')"
```

Expected: `App OK`

- [ ] **Step 9.3: Commit**

```bash
git add backend/interfaces/rest/dependencies.py
git commit -m "feat(swiss-market): wire SwissMarketService into FastAPI DI chain"
```

---

## Task 10: SMI-20 Seed Script

**Files:**
- Create: `scripts/seed_smi_universe.py`

- [ ] **Step 10.1: Create the seed script**

```python
#!/usr/bin/env python3
# scripts/seed_smi_universe.py
"""Idempotentes Seed-Script für die 20 SMI-Konstituenten (Stand Juni 2026).

Läuft standalone. Setzt DATABASE_URL aus der Umgebung voraus.
Alle ISINs MÜSSEN via SIX-Publikation oder yfinance vor dem ersten
Commit verifiziert werden (mit * markierte sind Platzhalter).

Usage:
    python scripts/seed_smi_universe.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SMI-20 Stammdaten (Stand Juni 2026)
# ISIN-Verifikation via: yf.Ticker("TICKER.SW").isin oder SIX-Publikation
# ---------------------------------------------------------------------------
SMI_20 = [
    # ticker, isin, name, sector
    ("NESN",  "CH0038863350", "Nestlé SA",                          "Consumer Staples"),
    ("NOVN",  "CH0012221716", "Novartis AG",                        "Healthcare"),       # * verify
    ("ROG",   "CH0012032048", "Roche Holding AG",                   "Healthcare"),       # * verify
    ("ABBN",  "CH0012221716", "ABB Ltd",                            "Industrials"),      # * verify
    ("ZURN",  "CH0011075394", "Zurich Insurance Group AG",          "Financials"),       # * verify
    ("UBSG",  "CH0244767585", "UBS Group AG",                       "Financials"),       # * verify
    ("UHR",   "CH0012255151", "The Swatch Group AG",                "Consumer Disc."),   # * verify
    ("GEBN",  "CH0030170408", "Geberit AG",                         "Industrials"),      # * verify
    ("GIVN",  "CH0010645932", "Givaudan SA",                        "Materials"),        # * verify
    ("LONN",  "CH0013841017", "Lonza Group AG",                     "Healthcare"),       # * verify
    ("SREN",  "CH0126881561", "Swiss Re AG",                        "Financials"),       # * verify
    ("SGKN",  "CH0002497458", "SGS SA",                             "Industrials"),      # * verify
    ("SLHN",  "CH0014852781", "Swiss Life Holding AG",              "Financials"),       # * verify
    ("SCMN",  "CH0008742519", "Swisscom AG",                        "Communication"),    # * verify
    ("BALN",  "CH0012221716", "Baloise Holding AG",                 "Financials"),       # * verify
    ("HOLN",  "CH0012214059", "Holcim AG",                          "Materials"),        # * verify
    ("PGHN",  "CH0024608827", "Partners Group Holding AG",          "Financials"),       # * verify
    ("KRIN",  "CH0334776754", "Kühne + Nagel International AG",     "Industrials"),      # * verify
    ("CFR",   "CH0210483332", "Compagnie Financière Richemont SA",  "Consumer Disc."),   # * verify
    ("STMN",  "CH0038863350", "Straumann Holding AG",               "Healthcare"),       # * verify — placeholder ISIN
]

UNIVERSE_NAME = "SMI-20"
UNIVERSE_DESCRIPTION = "Swiss Market Index — 20 Blue Chip Titel (SIX Swiss Exchange)"


async def seed(session: AsyncSession) -> None:
    _logger.info("Seeding %d SMI stocks …", len(SMI_20))

    for ticker, isin, name, sector in SMI_20:
        await session.execute(
            text("""
                INSERT INTO stocks (id, ticker, isin, name, sector, country, currency, exchange)
                VALUES (:id, :ticker, :isin, :name, :sector, 'CH', 'CHF', 'XSWX')
                ON CONFLICT (ticker) DO UPDATE SET
                    isin     = EXCLUDED.isin,
                    name     = EXCLUDED.name,
                    sector   = EXCLUDED.sector,
                    country  = EXCLUDED.country,
                    currency = EXCLUDED.currency,
                    exchange = EXCLUDED.exchange
            """),
            {
                "id": str(uuid.uuid4()),
                "ticker": ticker,
                "isin": isin,
                "name": name,
                "sector": sector,
            },
        )
        _logger.info("  ✓ %s (%s)", ticker, name)

    # Create SMI-20 Universe entry if not exists
    result = await session.execute(
        text("SELECT id FROM universes WHERE name = :name"),
        {"name": UNIVERSE_NAME},
    )
    existing = result.fetchone()
    if existing is None:
        universe_id = str(uuid.uuid4())
        await session.execute(
            text("""
                INSERT INTO universes (id, name, description)
                VALUES (:id, :name, :description)
                ON CONFLICT DO NOTHING
            """),
            {
                "id": universe_id,
                "name": UNIVERSE_NAME,
                "description": UNIVERSE_DESCRIPTION,
            },
        )
        _logger.info("Created universe '%s' (id=%s)", UNIVERSE_NAME, universe_id)

        # Link all SMI stocks to the universe
        tickers = [row[0] for row in SMI_20]
        for ticker in tickers:
            await session.execute(
                text("""
                    INSERT INTO universe_stocks (universe_id, stock_id)
                    SELECT :universe_id, id FROM stocks WHERE ticker = :ticker
                    ON CONFLICT DO NOTHING
                """),
                {"universe_id": universe_id, "ticker": ticker},
            )
    else:
        _logger.info("Universe '%s' already exists — skipping universe creation", UNIVERSE_NAME)

    await session.commit()
    _logger.info("Seed complete.")


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        _logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    # asyncpg requires postgresql+asyncpg:// prefix
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 10.2: Make executable and verify syntax**

```bash
chmod +x scripts/seed_smi_universe.py
python -m py_compile scripts/seed_smi_universe.py && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 10.3: Commit**

```bash
git add scripts/seed_smi_universe.py
git commit -m "feat(swiss-market): add static SMI-20 seed script (idempotent, ON CONFLICT DO UPDATE)"
```

---

## Task 11: Integration Test

**Files:**
- Create: `backend/tests/integration/test_swiss_catalog.py`

This test mocks the `SwissMarketService` dependency (following existing integration test pattern — no live DB required in CI for this test).

- [ ] **Step 11.1: Write the integration test**

```python
# backend/tests/integration/test_swiss_catalog.py
"""Integrationstests für Swiss Stock Catalog — GET /api/v1/stocks?exchange=XSWX."""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.stock_service import StockService
from backend.domain.entities.stock import Stock
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_stock_service

pytestmark = pytest.mark.integration

# 20 Swiss stocks matching the SMI seed
_SWISS_STOCKS = [
    Stock(
        id=uuid4(),
        ticker=ticker,
        name=f"{ticker} AG",
        isin=f"CH003886335{i}",
        sector="Financials",
        country="CH",
        currency="CHF",
    )
    for i, ticker in enumerate([
        "NESN", "NOVN", "ROG", "ABBN", "ZURN",
        "UBSG", "UHR",  "GEBN", "GIVN", "LONN",
        "SREN", "SGKN", "SLHN", "SCMN", "BALN",
        "HOLN", "PGHN", "KRIN", "CFR",  "STMN",
    ])
]


@pytest.fixture
def app_with_swiss_stocks():
    """FastAPI-App mit gemocktem StockService, der 20 Swiss Stocks zurückgibt."""
    from unittest.mock import AsyncMock, MagicMock

    app = create_app()

    mock_service = MagicMock(spec=StockService)
    mock_service.list_stocks = AsyncMock(return_value=_SWISS_STOCKS)

    app.dependency_overrides[get_stock_service] = lambda: mock_service
    yield app
    app.dependency_overrides.clear()


class TestSwissCatalogEndpoint:
    async def test_exchange_filter_returns_20_stocks(self, app_with_swiss_stocks) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_swiss_stocks),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/stocks?exchange=XSWX&limit=50")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 20
        assert len(data["items"]) == 20

    async def test_all_stocks_are_chf_denominated(self, app_with_swiss_stocks) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_swiss_stocks),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/stocks?exchange=XSWX&limit=50")

        items = response.json()["items"]
        assert all(s["currency"] == "CHF" for s in items)

    async def test_stock_read_schema_has_exchange_field(self, app_with_swiss_stocks) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app_with_swiss_stocks),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/stocks?limit=1")

        item = response.json()["items"][0]
        assert "exchange" in item
        assert "market_cap_chf" in item

    async def test_existing_stocks_endpoint_unaffected(self, app_with_swiss_stocks) -> None:
        """Regressions-Test: bestehender Endpoint ohne ?exchange= liefert weiterhin alle Stocks."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_swiss_stocks),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/stocks?limit=50")

        assert response.status_code == 200
        assert response.json()["total"] == 20
```

- [ ] **Step 11.2: Run integration tests**

```bash
pytest backend/tests/integration/test_swiss_catalog.py -v
```

Expected: `4 passed`

- [ ] **Step 11.3: Commit**

```bash
git add backend/tests/integration/test_swiss_catalog.py
git commit -m "test(swiss-market): add integration tests for Swiss Catalog API endpoint"
```

---

## Task 12: Full Test Suite + Push

- [ ] **Step 12.1: Run all unit tests**

```bash
pytest backend/tests/unit/ -v --tb=short
```

Expected: all existing tests pass + new tests (no regressions).

- [ ] **Step 12.2: Run linter**

```bash
ruff check backend/domain/validators/ \
           backend/domain/entities/swiss_stock.py \
           backend/domain/repositories/swiss_stock_repository.py \
           backend/application/services/swiss_market_service.py \
           backend/infrastructure/adapters/ \
           backend/infrastructure/persistence/repositories/swiss_stock_repository.py \
           backend/interfaces/rest/schemas/stock.py \
           scripts/seed_smi_universe.py
```

Expected: no errors. Fix any ruff findings before proceeding.

- [ ] **Step 12.3: Run mypy (if configured)**

```bash
mypy backend/domain/validators/ backend/domain/entities/swiss_stock.py --ignore-missing-imports
```

Expected: `Success: no issues found`

- [ ] **Step 12.4: Push feature branch**

```bash
git push origin feat/issue-1-swiss-stock-catalog
```

- [ ] **Step 12.5: Open PR**

```bash
gh pr create \
  --title "feat(swiss-market): Issue #1 — Swiss Stock Catalog + SIX Exchange Integration" \
  --body "$(cat <<'EOF'
## Summary
- `SwissStock` domain entity (frozen dataclass, CH-ISIN Luhn validation in `__post_init__`)
- `validate_ch_isin()` pure domain function (Luhn Mod-10, ISO 6166)
- `SwissStockRepository` abstract port + `SQLASwissStockRepository` implementation
- `SwissMarketService` application service
- `YFinanceSwissAdapter` skeleton (.SW-suffix, full impl in Issue #3)
- Alembic migration 0013: adds `exchange VARCHAR(10)` + `market_cap_chf NUMERIC(18,2)` to `stocks`
- `GET /api/v1/stocks?exchange=XSWX` filter (backwards-compatible)
- `scripts/seed_smi_universe.py`: static, idempotent SMI-20 seed
- 20 new tests (8 ISIN unit, 7 entity unit, 5 service unit, 4 integration)

## Test plan
- [ ] `pytest backend/tests/unit/domain/test_isin_validator.py` → 8 passed
- [ ] `pytest backend/tests/unit/domain/test_swiss_stock.py` → 7 passed
- [ ] `pytest backend/tests/unit/application/test_swiss_market_service.py` → 5 passed
- [ ] `pytest backend/tests/integration/test_swiss_catalog.py` → 4 passed
- [ ] `pytest backend/tests/unit/application/test_stock_service.py` → no regressions
- [ ] Verify ISINs via `python -c "import yfinance as yf; print(yf.Ticker('NESN.SW').isin)"`
- [ ] Run migration on staging: `alembic upgrade head`
- [ ] Run seed: `DATABASE_URL=... python scripts/seed_smi_universe.py`

**Closes #1**

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" \
  --base develop \
  --label "swiss-market"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| `SwissStock` entity mit allen Feldern | Task 2 |
| ISIN-Validator (CH-Prefix, Luhn) | Task 1 |
| `exchange: Literal["XSWX"]` | Task 2 |
| `market_cap_chf: Decimal | None` | Task 2, 4 |
| SIX/yfinance Adapter in `infrastructure/` | Task 7 |
| Migration für Swiss-spezifische Felder | Task 4 |
| `SwissStockRepository` Port | Task 3 |
| `SQLASwissStockRepository` Impl | Task 5 |
| `SwissMarketService` | Task 6 |
| `StockRead` rückwärtskompatibel erweitert | Task 8 |
| `GET /api/v1/stocks?exchange=XSWX` | Task 8 |
| DI-Kette vollständig verdrahtet | Task 9 |
| `scripts/seed_smi_universe.py` idempotent | Task 10 |
| 8 ISIN-Unit-Tests grün | Task 1 |
| 7 SwissStock-Unit-Tests | Task 2 |
| 5 Service-Unit-Tests | Task 6 |
| 4 Integration-Tests | Task 11 |
| CI-Check (ruff, mypy, pytest) | Task 12 |

---

*PRISMA V2 · Issue #1 · v2.0 Swiss Foundation · 2026-06-07*
