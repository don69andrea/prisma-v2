# Pipeline Hardening — 6 Best-Practice-Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sechs identifizierte Schwachstellen in der Datenpipeline beheben: Market-Cap aus Startup entfernen, Pipeline-Monitoring einführen, Input-Validierung, Crypto-Cache-Expiry, Swiss-Stock-Snapshot, XGBoost-Versionierung.

**Architecture:** Jeder Task ist unabhängig deploybar. DB-Migrationen folgen dem bestehenden Alembic-Muster (0027, 0028). Neue Cron-Jobs werden in `render.yaml` registriert. Bestehende Tests werden nie gelöscht, neue folgen `pytestmark = pytest.mark.unit`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy (async), Alembic, Render (Free Tier), PostgreSQL 16.

## Global Constraints

- Alle Python-Files: `from __future__ import annotations` am Anfang
- Async-Pattern: `asyncio.to_thread()` — kein `run_in_executor`
- Kein `tenacity` — manueller Retry mit `_RETRIES = 2`, Exponential Backoff
- `pytestmark = pytest.mark.unit` in allen Unit-Test-Files
- Commits nach jedem Task: `ruff format backend/ && ruff check backend/` vor dem Commit
- Migrations-Nummerierung: nächste freie ist `0027`, dann `0028`
- `render.yaml` Cron-Schedules: UTC

---

### Task 1: Market-Cap-Refresh aus Startup-Pfad entfernen

**Warum:** `update_smi_market_caps.py` läuft bei jedem Deploy — mehrere Deploys/Tag = mehrere API-Stampedes. War direkte Ursache des Port-Timeout-Bugs.

**Files:**
- Modify: `scripts/backend-start.sh`
- Modify: `render.yaml`

**Interfaces:**
- Produces: Render-Cron `prisma-smi-market-caps` (täglich 05:00 UTC)

- [ ] **Step 1: Market-Cap-Block aus backend-start.sh entfernen**

Ersetze in `scripts/backend-start.sh`:
```sh
# Refresh market_cap_chf for all SMI stocks from yfinance.
# This runs after every deploy so Render's free-tier DB never starts with
# null market caps after a reset. The script is idempotent and tolerates
# partial failures (individual tickers are skipped on error, not the whole run).
echo "==> Refreshing SMI market caps from yfinance..."
python scripts/update_smi_market_caps.py || echo "WARNING: market cap refresh failed (non-fatal) — will retry on next deploy"
```

mit nichts (komplett entfernen). Das File soll danach nur noch zwei Befehle enthalten:
```sh
#!/bin/sh
set -e

echo "==> Running alembic migrations..."
if ! alembic upgrade head; then
    echo "ERROR: Alembic-Migration fehlgeschlagen — Container stoppt (kein Restart-Loop)"
    echo "Action: Migration-Fehler beheben, committen und neu deployen."
    exit 1
fi

echo "==> Starting uvicorn on 0.0.0.0:${PORT:-8000} ..."
exec uvicorn backend.interfaces.rest.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

- [ ] **Step 2: Neuen Cron in render.yaml eintragen**

Füge nach dem `prisma-crypto-daily`-Block in `render.yaml` ein:
```yaml
  - type: cron
    name: prisma-smi-market-caps
    runtime: docker
    dockerfilePath: ./Dockerfile.backend
    branch: main
    plan: free
    schedule: "0 5 * * *"
    dockerCommand: python scripts/update_smi_market_caps.py
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: prisma-v2-db
          property: connectionString
```

- [ ] **Step 3: buildFilter in render.yaml aktualisieren**

Im `prisma-v2-backend`-Service `buildFilter.paths` den Eintrag `scripts/update_smi_market_caps.py` entfernen (er wird nicht mehr beim Deploy benötigt).

- [ ] **Step 4: Commit**

```bash
git add scripts/backend-start.sh render.yaml
git commit -m "fix(deploy): market-cap-refresh aus Startup → täglichen Cron (05:00 UTC)"
```

---

### Task 2: Pipeline-Monitoring (cron_run_log + /health/pipeline)

**Warum:** Wenn ein Cron-Job um 06:30 fehlschlägt, bemerkt man es nur aus Render-Logs. Kein Alert, kein Staleness-Check im Frontend.

**Files:**
- Create: `backend/alembic/versions/0027_create_cron_run_log.py`
- Create: `backend/domain/models/cron_run_record.py`
- Create: `backend/domain/repositories/cron_run_repository.py`
- Create: `backend/infrastructure/persistence/models/cron_run_log.py`
- Create: `backend/infrastructure/persistence/repositories/cron_run_repository.py`
- Modify: `backend/scripts/crypto_daily_snapshot.py`
- Modify: `backend/application/services/news_ingestion_service.py` (nur `__main__`-Block)
- Modify: `backend/interfaces/rest/routers/health.py`
- Create: `backend/tests/unit/test_cron_run_log.py`

**Interfaces:**
- Produces: `CronRunRepository.log_start(job_name) -> str` (returns run_id), `CronRunRepository.log_finish(run_id, status, records, error)`, `GET /health/pipeline -> list[PipelineJobStatus]`
- Consumes: bestehende `get_session_factory()` aus `backend/infrastructure/persistence/session.py`

- [ ] **Step 1: Alembic-Migration schreiben**

Erstelle `backend/alembic/versions/0027_create_cron_run_log.py`:
```python
"""create cron_run_log table

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cron_run_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),  # "ok" | "error" | "running"
        sa.Column("records_saved", sa.Integer, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
    )
    op.create_index("ix_cron_run_log_job_started", "cron_run_log", ["job_name", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_cron_run_log_job_started", "cron_run_log")
    op.drop_table("cron_run_log")
```

- [ ] **Step 2: Domain-Model**

Erstelle `backend/domain/models/cron_run_record.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CronRunRecord:
    id: str
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str | None = None      # "ok" | "error" | "running"
    records_saved: int | None = None
    error_msg: str | None = None
```

- [ ] **Step 3: Port**

Erstelle `backend/domain/repositories/cron_run_repository.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from backend.domain.models.cron_run_record import CronRunRecord


class CronRunRepository(ABC):
    @abstractmethod
    async def start_run(self, job_name: str) -> str:
        """Legt neuen Run an, gibt run_id zurück."""

    @abstractmethod
    async def finish_run(
        self,
        run_id: str,
        status: str,
        records_saved: int | None = None,
        error_msg: str | None = None,
    ) -> None:
        """Schliesst einen Run ab."""

    @abstractmethod
    async def get_latest_per_job(self) -> list[CronRunRecord]:
        """Gibt den neuesten Run pro Job zurück."""
```

- [ ] **Step 4: ORM-Modell**

Erstelle `backend/infrastructure/persistence/models/cron_run_log.py`:
```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class CronRunLogORM(Base):
    __tablename__ = "cron_run_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    records_saved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 5: Repository-Implementierung**

Erstelle `backend/infrastructure/persistence/repositories/cron_run_repository.py`:
```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.cron_run_record import CronRunRecord
from backend.domain.repositories.cron_run_repository import CronRunRepository as Port
from backend.infrastructure.persistence.models.cron_run_log import CronRunLogORM


class SQLACronRunRepository(Port):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_run(self, job_name: str) -> str:
        run_id = str(uuid.uuid4())
        self._session.add(
            CronRunLogORM(
                id=run_id,
                job_name=job_name,
                started_at=datetime.now(UTC),
                status="running",
            )
        )
        await self._session.commit()
        return run_id

    async def finish_run(
        self,
        run_id: str,
        status: str,
        records_saved: int | None = None,
        error_msg: str | None = None,
    ) -> None:
        result = await self._session.execute(
            select(CronRunLogORM).where(CronRunLogORM.id == run_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.finished_at = datetime.now(UTC)
        row.status = status
        row.records_saved = records_saved
        row.error_msg = error_msg
        await self._session.commit()

    async def get_latest_per_job(self) -> list[CronRunRecord]:
        result = await self._session.execute(
            select(CronRunLogORM).order_by(
                CronRunLogORM.job_name, CronRunLogORM.started_at.desc()
            )
        )
        latest: dict[str, CronRunLogORM] = {}
        for row in result.scalars().all():
            latest.setdefault(row.job_name, row)
        return [
            CronRunRecord(
                id=r.id,
                job_name=r.job_name,
                started_at=r.started_at,
                finished_at=r.finished_at,
                status=r.status,
                records_saved=r.records_saved,
                error_msg=r.error_msg,
            )
            for r in latest.values()
        ]
```

- [ ] **Step 6: Unit-Test schreiben**

Erstelle `backend/tests/unit/test_cron_run_log.py`:
```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import UTC, datetime

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_start_run_returns_uuid_string():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    from backend.infrastructure.persistence.repositories.cron_run_repository import (
        SQLACronRunRepository,
    )
    repo = SQLACronRunRepository(session)
    run_id = await repo.start_run("crypto_daily")
    assert isinstance(run_id, str)
    assert len(run_id) == 36  # UUID format
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_finish_run_updates_existing_row():
    from backend.infrastructure.persistence.models.cron_run_log import CronRunLogORM
    session = AsyncMock()
    row = CronRunLogORM(
        id="test-id",
        job_name="crypto_daily",
        started_at=datetime.now(UTC),
        status="running",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    from backend.infrastructure.persistence.repositories.cron_run_repository import (
        SQLACronRunRepository,
    )
    repo = SQLACronRunRepository(session)
    await repo.finish_run("test-id", "ok", records_saved=10)
    assert row.status == "ok"
    assert row.records_saved == 10
    assert row.finished_at is not None
```

- [ ] **Step 7: Tests ausführen**

```bash
pytest backend/tests/unit/test_cron_run_log.py -v
```
Erwartung: 2 passed.

- [ ] **Step 8: crypto_daily_snapshot.py mit Logging erweitern**

In `backend/scripts/crypto_daily_snapshot.py`, die `main()`-Funktion um Run-Logging ergänzen. Import oben hinzufügen:
```python
from backend.infrastructure.persistence.repositories.cron_run_repository import SQLACronRunRepository
```

Den bestehenden Snapshot-Block in `main()` mit Run-Logging umhüllen:
```python
    run_id: str | None = None
    async with session_factory() as log_session:
        log_repo = SQLACronRunRepository(log_session)
        run_id = await log_repo.start_run("crypto_daily")

    # ... bestehender Snapshot-Code ...

    async with session_factory() as log_session:
        log_repo = SQLACronRunRepository(log_session)
        await log_repo.finish_run(run_id, "ok", records_saved=saved)
```

Fehlerfall: im `except`-Block von `main()`:
```python
    except Exception:
        log.exception("score_all() fehlgeschlagen")
        if run_id is not None:
            async with session_factory() as log_session:
                log_repo = SQLACronRunRepository(log_session)
                await log_repo.finish_run(run_id, "error", error_msg="score_all() fehlgeschlagen")
        return
```

- [ ] **Step 9: /health/pipeline Endpoint**

In `backend/interfaces/rest/routers/health.py` ergänzen (bestehenden Import-Block beibehalten):
```python
@router.get("/pipeline")
async def pipeline_health(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Letzter Run-Status pro Cron-Job."""
    from backend.infrastructure.persistence.repositories.cron_run_repository import (
        SQLACronRunRepository,
    )
    repo = SQLACronRunRepository(session)
    records = await repo.get_latest_per_job()
    return [
        {
            "job": r.job_name,
            "status": r.status,
            "last_run": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "records_saved": r.records_saved,
            "error": r.error_msg,
        }
        for r in records
    ]
```

- [ ] **Step 10: Commit**

```bash
git add backend/alembic/versions/0027_create_cron_run_log.py \
        backend/domain/models/cron_run_record.py \
        backend/domain/repositories/cron_run_repository.py \
        backend/infrastructure/persistence/models/cron_run_log.py \
        backend/infrastructure/persistence/repositories/cron_run_repository.py \
        backend/scripts/crypto_daily_snapshot.py \
        backend/interfaces/rest/routers/health.py \
        backend/tests/unit/test_cron_run_log.py
git commit -m "feat(monitoring): cron_run_log Tabelle + /health/pipeline Endpoint"
```

---

### Task 3: Input-Validierung in Crypto-Adaptern

**Warum:** CoinGecko und FearGreed können korrupte Daten liefern (price=0, rsi=NaN, fear_greed=150). Diese landen ohne Check direkt in der DB.

**Files:**
- Modify: `backend/infrastructure/adapters/coingecko_adapter.py`
- Modify: `backend/infrastructure/adapters/fear_greed_adapter.py`
- Modify: `backend/infrastructure/adapters/yfinance_crypto.py`
- Create: `backend/tests/unit/infrastructure/test_crypto_adapter_validation.py`

**Interfaces:**
- Consumes: bestehende Adapter-Interfaces (keine Änderung an Signaturen)
- Produces: ungültige Datenpunkte werden geloggt und gefiltert statt gespeichert

- [ ] **Step 1: Failing Test schreiben**

Erstelle `backend/tests/unit/infrastructure/test_crypto_adapter_validation.py`:
```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_coingecko_filters_zero_price():
    from backend.infrastructure.adapters.coingecko_adapter import _validate_market_entry

    valid = {"id": "bitcoin", "current_price": 85000.0, "market_cap": 1_600_000_000_000}
    invalid = {"id": "bitcoin", "current_price": 0.0, "market_cap": 1_600_000_000_000}
    assert _validate_market_entry(valid) is True
    assert _validate_market_entry(invalid) is False


def test_coingecko_filters_missing_price():
    from backend.infrastructure.adapters.coingecko_adapter import _validate_market_entry

    entry = {"id": "bitcoin", "market_cap": 1_600_000_000_000}
    assert _validate_market_entry(entry) is False


def test_fear_greed_clamps_out_of_range():
    from backend.infrastructure.adapters.fear_greed_adapter import _validate_fear_greed

    assert _validate_fear_greed(50) == 50
    assert _validate_fear_greed(-1) is None
    assert _validate_fear_greed(101) is None
    assert _validate_fear_greed(0) == 0
    assert _validate_fear_greed(100) == 100
```

- [ ] **Step 2: Test ausführen — muss fehlschlagen**

```bash
pytest backend/tests/unit/infrastructure/test_crypto_adapter_validation.py -v
```
Erwartung: ImportError / AttributeError (Funktionen existieren noch nicht).

- [ ] **Step 3: Validierungsfunktion in coingecko_adapter.py hinzufügen**

In `backend/infrastructure/adapters/coingecko_adapter.py` nach den Imports einfügen:
```python
def _validate_market_entry(entry: dict) -> bool:
    """Gibt False zurück wenn ein Marktdaten-Eintrag offensichtlich korrupt ist."""
    price = entry.get("current_price")
    return price is not None and price > 0
```

Und in `get_market_data()` nach dem API-Call das Filtering hinzufügen:
```python
        raw: list[dict[str, Any]] = await asyncio.to_thread(...)
        result = [e for e in raw if _validate_market_entry(e)]
        invalid = len(raw) - len(result)
        if invalid:
            _logger.warning("CoinGecko: %d ungültige Einträge gefiltert", invalid)
```

- [ ] **Step 4: Validierungsfunktion in fear_greed_adapter.py hinzufügen**

In `backend/infrastructure/adapters/fear_greed_adapter.py` nach den Imports einfügen:
```python
def _validate_fear_greed(value: int) -> int | None:
    """Gibt None zurück wenn der Fear&Greed-Wert ausserhalb 0–100 liegt."""
    if not (0 <= value <= 100):
        return None
    return value
```

Im `get_current()`-Response-Parsing, den `value` durch `_validate_fear_greed(value)` ersetzen und bei `None` auf Fallback `50` (neutral) setzen mit Warning-Log.

- [ ] **Step 5: Tests ausführen**

```bash
pytest backend/tests/unit/infrastructure/test_crypto_adapter_validation.py -v
```
Erwartung: 4 passed.

- [ ] **Step 6: Alle Crypto-Tests ausführen**

```bash
pytest backend/tests/unit/ -k "crypto" -q
```
Erwartung: alle bestehenden Tests weiterhin grün.

- [ ] **Step 7: Commit**

```bash
git add backend/infrastructure/adapters/coingecko_adapter.py \
        backend/infrastructure/adapters/fear_greed_adapter.py \
        backend/tests/unit/infrastructure/test_crypto_adapter_validation.py
git commit -m "feat(validation): input-validierung in crypto-adaptern — zero-price + fear&greed range"
```

---

### Task 4: Crypto-Cache mit Expiry (statt forever)

**Warum:** `CryptoScoringService._cache_result` wird nie invalidiert — nach 6h liefert der Service noch immer Daten von 06:30. Der tägliche Snapshot ist vorhanden, wird aber nicht genutzt.

**Files:**
- Modify: `backend/application/services/crypto_scoring_service.py`
- Modify: `backend/tests/unit/application/test_crypto_scoring_fixes.py`

**Interfaces:**
- Consumes: bestehender `CryptoScoringService` (keine Änderung an der öffentlichen Signatur)
- Produces: Cache expired nach `_CACHE_TTL_SECONDS = 600` (10 Minuten)

- [ ] **Step 1: Failing Test schreiben**

In `backend/tests/unit/application/test_crypto_scoring_fixes.py` am Ende anfügen:
```python
@pytest.mark.asyncio
async def test_score_all_cache_expires_after_ttl(mock_scoring_service):
    """Cache soll nach TTL ablaufen — nicht für immer gecacht bleiben."""
    from datetime import UTC, datetime, timedelta
    import backend.application.services.crypto_scoring_service as svc_module

    service = mock_scoring_service
    # Erster Call — befüllt Cache
    await service.score_all()
    assert service._cache_result is not None
    assert service._cache_time is not None

    # Cache-Zeit künstlich in die Vergangenheit setzen (TTL + 1s)
    service._cache_time = datetime.now(UTC) - timedelta(seconds=svc_module._CACHE_TTL_SECONDS + 1)

    # Zweiter Call — muss neu rechnen (nicht aus Cache)
    service._score_all_uncached = AsyncMock(return_value=[])
    await service.score_all()
    service._score_all_uncached.assert_awaited_once()
```

- [ ] **Step 2: Test ausführen — muss fehlschlagen**

```bash
pytest backend/tests/unit/application/test_crypto_scoring_fixes.py::test_score_all_cache_expires_after_ttl -v
```
Erwartung: `AttributeError: _cache_time`.

- [ ] **Step 3: CryptoScoringService anpassen**

In `backend/application/services/crypto_scoring_service.py`:

Import ergänzen: `from datetime import UTC, datetime, timedelta`

Konstante nach den Imports einfügen:
```python
_CACHE_TTL_SECONDS = 600  # 10 Minuten — danach wird live neu berechnet
```

`__init__` anpassen:
```python
        self._cache_result: list[CryptoSignal] | None = None
        self._cache_time: datetime | None = None  # NEU
```

`score_all()` anpassen:
```python
    async def score_all(self) -> list[CryptoSignal]:
        async with self._cache_lock:
            now = datetime.now(UTC)
            cache_valid = (
                self._cache_result is not None
                and self._cache_time is not None
                and (now - self._cache_time).total_seconds() < _CACHE_TTL_SECONDS
            )
            if cache_valid:
                return self._cache_result  # type: ignore[return-value]
            result = await self._score_all_uncached()
            self._cache_result = result
            self._cache_time = now
            return result
```

- [ ] **Step 4: Bestehenden TTL-Test anpassen**

Der bestehende Test `test_score_all_cache_expires` in der Datei testet vermutlich ein anderes Verhalten. Prüfen und ggf. anpassen, dass er mit `_cache_time` arbeitet.

- [ ] **Step 5: Tests ausführen**

```bash
pytest backend/tests/unit/application/test_crypto_scoring_fixes.py -v
```
Erwartung: alle Tests grün inkl. dem neuen.

- [ ] **Step 6: Commit**

```bash
git add backend/application/services/crypto_scoring_service.py \
        backend/tests/unit/application/test_crypto_scoring_fixes.py
git commit -m "fix(cache): crypto score_all cache nach 10 min invalidieren statt für immer"
```

---

### Task 5: Swiss Stock Daily Snapshot

**Warum:** Jeder `/decision`-Request ruft yFinance live auf. yFinance ist nicht für Production-Traffic ausgelegt. Swiss Stocks brauchen denselben täglichen Snapshot wie Crypto.

**Files:**
- Create: `backend/alembic/versions/0028_create_stock_daily_signals.py`
- Create: `backend/domain/models/stock_signal_record.py`
- Create: `backend/domain/repositories/stock_signal_repository.py`
- Create: `backend/infrastructure/persistence/models/stock_daily_signal.py`
- Create: `backend/infrastructure/persistence/repositories/stock_signal_repository.py`
- Create: `backend/scripts/stock_daily_snapshot.py`
- Modify: `render.yaml`
- Modify: `backend/interfaces/rest/routers/decisions.py`
- Create: `backend/tests/unit/test_stock_daily_snapshot.py`

**Interfaces:**
- Produces: `StockSignalRepository.save(record)`, `StockSignalRepository.get_today(ticker)`, `StockSignalRepository.get_today_all() -> list[StockSignalRecord]`
- Consumes: `SignalAggregationService.get_signals(tickers)` (existiert bereits), `DecisionSignal` Value Object

SMI20-Ticker (für Snapshot-Script, identisch mit `update_smi_market_caps.py`):
```python
_SMI20 = [
    "NESN", "NOVN", "ROG", "ABBN", "ZURN", "UBSG", "UHR", "GEBN",
    "GIVN", "LONN", "SREN", "SGKN", "SLHN", "SCMN", "SIKA", "HOLN",
    "PGHN", "KNIN", "CFR", "STMN",
]
```

- [ ] **Step 1: Alembic-Migration**

Erstelle `backend/alembic/versions/0028_create_stock_daily_signals.py`:
```python
"""create stock_daily_signals table

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_daily_signals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("signal", sa.String(10), nullable=False),
        sa.Column("weighted_score", sa.Float, nullable=False),
        sa.Column("quant_score", sa.Float, nullable=False),
        sa.Column("ml_score", sa.Float, nullable=False),
        sa.Column("macro_score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("is_3a_eligible", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_stock_daily_signals_ticker_date",
        "stock_daily_signals",
        ["ticker", "snapshot_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_daily_signals_ticker_date", "stock_daily_signals")
    op.drop_table("stock_daily_signals")
```

- [ ] **Step 2: Domain-Model**

Erstelle `backend/domain/models/stock_signal_record.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class StockSignalRecord:
    id: str
    ticker: str
    snapshot_date: date
    signal: str
    weighted_score: float
    quant_score: float
    ml_score: float
    macro_score: float
    confidence: float
    is_3a_eligible: bool
    created_at: datetime | None = None
```

- [ ] **Step 3: Repository-Port**

Erstelle `backend/domain/repositories/stock_signal_repository.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from backend.domain.models.stock_signal_record import StockSignalRecord


class StockSignalRepository(ABC):
    @abstractmethod
    async def save(self, record: StockSignalRecord) -> None:
        """Upsert: ein Snapshot pro Ticker pro Kalendertag."""

    @abstractmethod
    async def get_today(self, ticker: str) -> StockSignalRecord | None:
        """Heutiger Snapshot für einen Ticker oder None."""

    @abstractmethod
    async def get_today_all(self) -> list[StockSignalRecord]:
        """Alle heutigen Snapshots (für Bulk-Antwort auf /decisions)."""
```

- [ ] **Step 4: ORM-Modell**

Erstelle `backend/infrastructure/persistence/models/stock_daily_signal.py`:
```python
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class StockDailySignalORM(Base):
    __tablename__ = "stock_daily_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    signal: Mapped[str] = mapped_column(String(10), nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    quant_score: Mapped[float] = mapped_column(Float, nullable=False)
    ml_score: Mapped[float] = mapped_column(Float, nullable=False)
    macro_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_3a_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Repository-Implementierung**

Erstelle `backend/infrastructure/persistence/repositories/stock_signal_repository.py`:
```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.stock_signal_record import StockSignalRecord
from backend.domain.repositories.stock_signal_repository import StockSignalRepository as Port
from backend.infrastructure.persistence.models.stock_daily_signal import StockDailySignalORM


class SQLAStockSignalRepository(Port):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: StockSignalRecord) -> None:
        existing = await self._session.execute(
            select(StockDailySignalORM).where(
                StockDailySignalORM.ticker == record.ticker,
                StockDailySignalORM.snapshot_date == record.snapshot_date,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            row.signal = record.signal
            row.weighted_score = record.weighted_score
            row.quant_score = record.quant_score
            row.ml_score = record.ml_score
            row.macro_score = record.macro_score
            row.confidence = record.confidence
            row.is_3a_eligible = record.is_3a_eligible
        else:
            self._session.add(
                StockDailySignalORM(
                    id=str(uuid.uuid4()),
                    ticker=record.ticker,
                    snapshot_date=record.snapshot_date,
                    signal=record.signal,
                    weighted_score=record.weighted_score,
                    quant_score=record.quant_score,
                    ml_score=record.ml_score,
                    macro_score=record.macro_score,
                    confidence=record.confidence,
                    is_3a_eligible=record.is_3a_eligible,
                )
            )

    async def get_today(self, ticker: str) -> StockSignalRecord | None:
        today = datetime.now(UTC).date()
        result = await self._session.execute(
            select(StockDailySignalORM).where(
                StockDailySignalORM.ticker == ticker.upper(),
                StockDailySignalORM.snapshot_date == today,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_today_all(self) -> list[StockSignalRecord]:
        today = datetime.now(UTC).date()
        result = await self._session.execute(
            select(StockDailySignalORM).where(
                StockDailySignalORM.snapshot_date == today
            )
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    @staticmethod
    def _to_domain(row: StockDailySignalORM) -> StockSignalRecord:
        return StockSignalRecord(
            id=row.id,
            ticker=row.ticker,
            snapshot_date=row.snapshot_date,
            signal=row.signal,
            weighted_score=row.weighted_score,
            quant_score=row.quant_score,
            ml_score=row.ml_score,
            macro_score=row.macro_score,
            confidence=row.confidence,
            is_3a_eligible=row.is_3a_eligible,
            created_at=row.created_at,
        )
```

- [ ] **Step 6: Failing Test für Snapshot-Script schreiben**

Erstelle `backend/tests/unit/test_stock_daily_snapshot.py`:
```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_snapshot_saves_one_record_per_signal():
    """main() soll für jedes erfolgreich berechnete Signal ein Record speichern."""
    from backend.domain.value_objects.decision_signal import DecisionSignal

    mock_signal = DecisionSignal(
        ticker="NESN",
        snapshot_date=date(2026, 6, 17),
        signal="BUY",
        confidence=0.72,
        weighted_score=72.0,
        quant_score=68.0,
        ml_score=80.0,
        macro_score=65.0,
        is_3a_eligible=True,
    )

    with (
        patch(
            "backend.scripts.stock_daily_snapshot.SignalAggregationService"
        ) as MockSvc,
        patch(
            "backend.scripts.stock_daily_snapshot.get_session_factory"
        ) as MockFactory,
    ):
        mock_svc = AsyncMock()
        mock_svc.get_signals = AsyncMock(return_value=[mock_signal])
        MockSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        MockFactory.return_value = MagicMock(return_value=mock_session)

        with patch(
            "backend.scripts.stock_daily_snapshot.SQLAStockSignalRepository"
        ) as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.save = AsyncMock()
            MockRepo.return_value = mock_repo

            from backend.scripts.stock_daily_snapshot import main
            await main()

        mock_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_snapshot_continues_after_one_ticker_fails():
    """Ein fehlgeschlagener Ticker darf den ganzen Snapshot nicht abbrechen."""
    from backend.domain.value_objects.decision_signal import DecisionSignal

    mock_signals = [
        DecisionSignal("NESN", date(2026, 6, 17), "BUY", 0.72, 72.0, 68.0, 80.0, 65.0, True),
        DecisionSignal("NOVN", date(2026, 6, 17), "HOLD", 0.50, 50.0, 52.0, 48.0, 50.0, False),
    ]

    with (
        patch("backend.scripts.stock_daily_snapshot.SignalAggregationService") as MockSvc,
        patch("backend.scripts.stock_daily_snapshot.get_session_factory") as MockFactory,
        patch("backend.scripts.stock_daily_snapshot.SQLAStockSignalRepository") as MockRepo,
    ):
        mock_svc = AsyncMock()
        mock_svc.get_signals = AsyncMock(return_value=mock_signals)
        MockSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        MockFactory.return_value = MagicMock(return_value=mock_session)

        mock_repo = AsyncMock()
        mock_repo.save = AsyncMock(side_effect=[Exception("DB-Fehler"), None])
        MockRepo.return_value = mock_repo

        from backend.scripts.stock_daily_snapshot import main
        await main()

        assert mock_repo.save.await_count == 2
```

- [ ] **Step 7: Test ausführen — muss fehlschlagen**

```bash
pytest backend/tests/unit/test_stock_daily_snapshot.py -v
```
Erwartung: `ModuleNotFoundError: backend.scripts.stock_daily_snapshot`.

- [ ] **Step 8: Snapshot-Script implementieren**

Erstelle `backend/scripts/stock_daily_snapshot.py`:
```python
#!/usr/bin/env python3
"""Swiss Stock Daily Snapshot — läuft täglich via Render Cron.

Berechnet SignalAggregationService-Signale für alle SMI20-Titel
und persistiert sie in stock_daily_signals.
"""
from __future__ import annotations

import asyncio
import logging

from backend.application.services.signal_aggregation_service import SignalAggregationService
from backend.infrastructure.persistence.repositories.stock_signal_repository import (
    SQLAStockSignalRepository,
)
from backend.infrastructure.persistence.session import get_session_factory
from backend.domain.models.stock_signal_record import StockSignalRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stock_daily_snapshot")

_SMI20 = [
    "NESN", "NOVN", "ROG", "ABBN", "ZURN", "UBSG", "UHR", "GEBN",
    "GIVN", "LONN", "SREN", "SGKN", "SLHN", "SCMN", "SIKA", "HOLN",
    "PGHN", "KNIN", "CFR", "STMN",
]


async def main() -> None:
    log.info("=== Stock Daily Snapshot gestartet ===")
    scoring_svc = SignalAggregationService()

    try:
        signals = await scoring_svc.get_signals(_SMI20)
    except Exception:
        log.exception("get_signals() fehlgeschlagen")
        return

    session_factory = get_session_factory()
    saved = 0
    async with session_factory() as session:
        repo = SQLAStockSignalRepository(session)
        for signal in signals:
            try:
                record = StockSignalRecord(
                    id="",  # Repository generiert UUID
                    ticker=signal.ticker,
                    snapshot_date=signal.snapshot_date,
                    signal=signal.signal,
                    weighted_score=signal.weighted_score,
                    quant_score=signal.quant_score,
                    ml_score=signal.ml_score,
                    macro_score=signal.macro_score,
                    confidence=signal.confidence,
                    is_3a_eligible=signal.is_3a_eligible,
                )
                await repo.save(record)
                saved += 1
                log.info("  OK %s: %s (%.1f)", signal.ticker, signal.signal, signal.weighted_score)
            except Exception:
                log.exception("  FEHLER bei %s", signal.ticker)
        await session.commit()

    log.info("=== Snapshot fertig: %d/%d gespeichert ===", saved, len(signals))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 9: Tests ausführen**

```bash
pytest backend/tests/unit/test_stock_daily_snapshot.py -v
```
Erwartung: 2 passed.

- [ ] **Step 10: Cron in render.yaml registrieren**

```yaml
  - type: cron
    name: prisma-stock-daily
    runtime: docker
    dockerfilePath: ./Dockerfile.backend
    branch: main
    plan: free
    schedule: "0 7 * * *"
    dockerCommand: python -m backend.scripts.stock_daily_snapshot
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: prisma-v2-db
          property: connectionString
      - key: ANTHROPIC_API_KEY
        sync: false
```

- [ ] **Step 11: /decisions Snapshot-Fallback einbauen**

In `backend/interfaces/rest/routers/decisions.py` den `list_decisions`-Endpoint ergänzen, sodass er bei vorhandenem Tagesschnitt diesen bevorzugt. Nach den bestehenden Imports hinzufügen:
```python
from backend.infrastructure.persistence.repositories.stock_signal_repository import (
    SQLAStockSignalRepository,
)
```

Im `list_decisions`-Handler vor dem `aggregation_service.get_signals()`-Call einfügen:
```python
    # Tagesschnitt vorhanden → direkt aus DB (kein yFinance-Call)
    stock_signal_repo = SQLAStockSignalRepository(session)
    snapshots = await stock_signal_repo.get_today_all()
    if len(snapshots) >= 10:
        return [
            DecisionResponse(
                ticker=s.ticker,
                signal=s.signal,
                weighted_score=s.weighted_score,
                quant_score=s.quant_score,
                ml_score=s.ml_score,
                macro_score=s.macro_score,
                confidence=s.confidence,
                is_3a_eligible=s.is_3a_eligible,
                signal_reason=_signal_reason(s.signal, s.weighted_score, s.quant_score),
                snapshot_date=s.snapshot_date,
            )
            for s in snapshots
        ]
    # Kein Snapshot → live berechnen (Fallback)
```

- [ ] **Step 12: Commit**

```bash
git add backend/alembic/versions/0028_create_stock_daily_signals.py \
        backend/domain/models/stock_signal_record.py \
        backend/domain/repositories/stock_signal_repository.py \
        backend/infrastructure/persistence/models/stock_daily_signal.py \
        backend/infrastructure/persistence/repositories/stock_signal_repository.py \
        backend/scripts/stock_daily_snapshot.py \
        backend/tests/unit/test_stock_daily_snapshot.py \
        backend/interfaces/rest/routers/decisions.py \
        render.yaml
git commit -m "feat(pipeline): swiss stock daily snapshot — stock_daily_signals tabelle + cron + decisions-fallback"
```

---

### Task 6: XGBoost Model-Versionierung

**Warum:** `return_predictor_latest.joblib` ist ein einziger File ohne Versionierung. Ein schlechtes Modell kann nicht rückgängig gemacht werden.

**Files:**
- Create: `backend/application/services/model_registry.py`
- Modify: `backend/application/services/ml_prediction_service.py`
- Modify: `backend/interfaces/rest/routers/health.py`
- Create: `backend/tests/unit/application/test_model_registry.py`

**Interfaces:**
- Produces: `ModelRegistry.get_active_model_path() -> Path`, `ModelRegistry.register(path, meta) -> None`, `ModelRegistry.list_versions() -> list[dict]`
- Consumes: bestehender `_MODELS_DIR = Path(...) / "models"`

- [ ] **Step 1: Failing Test schreiben**

Erstelle `backend/tests/unit/application/test_model_registry.py`:
```python
from __future__ import annotations

import json
import pytest
from pathlib import Path

pytestmark = pytest.mark.unit


def test_registry_returns_latest_path(tmp_path):
    from backend.application.services.model_registry import ModelRegistry

    (tmp_path / "model_v1.joblib").touch()
    registry_data = {
        "active": "model_v1.joblib",
        "versions": [
            {"file": "model_v1.joblib", "trained_at": "2026-06-17", "accuracy": 0.61}
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry_data))
    registry = ModelRegistry(models_dir=tmp_path)
    assert registry.get_active_model_path() == tmp_path / "model_v1.joblib"


def test_registry_returns_none_when_no_registry(tmp_path):
    from backend.application.services.model_registry import ModelRegistry

    registry = ModelRegistry(models_dir=tmp_path)
    assert registry.get_active_model_path() is None


def test_registry_list_versions(tmp_path):
    from backend.application.services.model_registry import ModelRegistry

    registry_data = {
        "active": "model_v2.joblib",
        "versions": [
            {"file": "model_v1.joblib", "trained_at": "2026-06-10", "accuracy": 0.59},
            {"file": "model_v2.joblib", "trained_at": "2026-06-17", "accuracy": 0.61},
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry_data))
    registry = ModelRegistry(models_dir=tmp_path)
    versions = registry.list_versions()
    assert len(versions) == 2
    assert versions[1]["file"] == "model_v2.joblib"
```

- [ ] **Step 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest backend/tests/unit/application/test_model_registry.py -v
```
Erwartung: `ModuleNotFoundError`.

- [ ] **Step 3: ModelRegistry implementieren**

Erstelle `backend/application/services/model_registry.py`:
```python
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)
_REGISTRY_FILE = "registry.json"


class ModelRegistry:
    """Datei-basierte Modell-Registry in models/registry.json.

    Ermöglicht Versionstracking und schnellen Rollback ohne DB-Dependency.
    """

    def __init__(self, models_dir: Path | None = None) -> None:
        if models_dir is None:
            models_dir = Path(__file__).resolve().parents[3] / "models"
        self._dir = models_dir
        self._registry_path = self._dir / _REGISTRY_FILE

    def _load(self) -> dict[str, Any]:
        if not self._registry_path.exists():
            return {"active": None, "versions": []}
        with self._registry_path.open() as f:
            return json.load(f)

    def get_active_model_path(self) -> Path | None:
        """Gibt den Pfad zum aktiven Modell zurück, oder None wenn kein Registry-File."""
        data = self._load()
        active = data.get("active")
        if not active:
            return None
        path = self._dir / active
        if not path.exists():
            _logger.warning("Registry zeigt auf nicht-existentes Modell: %s", path)
            return None
        return path

    def list_versions(self) -> list[dict[str, Any]]:
        """Gibt alle registrierten Modell-Versionen zurück."""
        return self._load().get("versions", [])

    def register(self, filename: str, meta: dict[str, Any], set_active: bool = True) -> None:
        """Registriert eine neue Modell-Version und setzt sie optional als aktiv."""
        data = self._load()
        entry = {"file": filename, **meta}
        data["versions"].append(entry)
        if set_active:
            data["active"] = filename
        self._registry_path.write_text(json.dumps(data, indent=2))
        _logger.info("Modell registriert: %s (active=%s)", filename, set_active)
```

- [ ] **Step 4: ml_prediction_service.py Registry-aware machen**

In `backend/application/services/ml_prediction_service.py` die `_load_model()`-Funktion erweitern: zuerst Registry prüfen, Fallback auf `return_predictor_latest.joblib`:
```python
def _load_model() -> tuple[Any, str]:
    global _model_cache, _model_type_cache
    if _model_cache is not None:
        return _model_cache, _model_type_cache

    import joblib
    from backend.application.services.model_registry import ModelRegistry

    registry = ModelRegistry()
    model_path = registry.get_active_model_path() or _LATEST_MODEL

    if not model_path.exists():
        raise FileNotFoundError(
            f"Kein trainiertes Modell gefunden unter {model_path}. "
            "Bitte zuerst `python scripts/train_return_predictor.py` ausführen."
        )

    _model_cache = joblib.load(model_path)
    _model_type_cache = "unknown"
    # ... bestehender Meta-Lade-Code bleibt unverändert
```

- [ ] **Step 5: /health/model-info Endpoint**

In `backend/interfaces/rest/routers/health.py` ergänzen:
```python
@router.get("/model-info")
async def model_info() -> dict:
    """Aktive ML-Modell-Version und verfügbare Versionen."""
    from backend.application.services.model_registry import ModelRegistry
    registry = ModelRegistry()
    active_path = registry.get_active_model_path()
    return {
        "active": active_path.name if active_path else "return_predictor_latest.joblib (legacy)",
        "versions": registry.list_versions(),
    }
```

- [ ] **Step 6: Tests ausführen**

```bash
pytest backend/tests/unit/application/test_model_registry.py -v
```
Erwartung: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/application/services/model_registry.py \
        backend/application/services/ml_prediction_service.py \
        backend/interfaces/rest/routers/health.py \
        backend/tests/unit/application/test_model_registry.py
git commit -m "feat(ml): model-registry für versionierung + rollback + /health/model-info"
```

---

## Reihenfolge der Tasks

Task 1 und Tasks 3–6 sind unabhängig parallelisierbar. Task 2 (Monitoring) sollte vor dem Swiss-Stock-Snapshot deployt sein, damit neue Crons sofort geloggt werden.

**Empfohlene Execution-Reihenfolge:**
1. Task 1 (Market-Cap-Cron) — sofort, minimales Risiko
2. Task 2 (Monitoring) — Migrations-Abhängigkeit: 0027
3. Task 3 (Validierung) — unabhängig
4. Task 4 (Cache-Expiry) — unabhängig
5. Task 5 (Stock-Snapshot) — Migrations-Abhängigkeit: 0028, baut auf Task 2 auf
6. Task 6 (ML-Registry) — unabhängig
