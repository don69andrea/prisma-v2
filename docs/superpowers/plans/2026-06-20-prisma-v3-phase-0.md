# PRISMA V3 — Phase 0: Dataset Coverage Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the Phase 0 blocking gate — copy seed skeleton files into the repo, run `verify_dataset_coverage.py`, produce `docs/dataset_coverage.md`, and lock the fundamentals source in `backend/config.py` — before any ML code is written.

**Architecture:** Seed files (alembic migrations 0031–0035, ETL pipeline, EODHD adapter, seed scripts) are copied from `prisma_v3_seed/` into the correct repo paths per `prisma_v3_seed/README_SEED.md §1`. A new `backend/application/pipeline/` module provides idempotent ETL helpers. The EODHD adapter probes CH-fundamentals coverage. The coverage report gates all subsequent phases.

**Tech Stack:** Python 3.12, SQLAlchemy (async/text()), Alembic, yfinance, httpx, pytest, pydantic-settings, uv.

## Global Constraints

- Never push directly to `main` — always Feature-Branch → PR → CI green → merge (CLAUDE.md / AGENTS.md).
- All DB writes via Repository-pattern (raw SQL via `text()`, session via `get_session_factory()`) — no ORM in seeds.
- No `_stub_fundamentals()` in training paths — log loudly and abort instead (CHALLENGE 01 / FIX-14).
- Fundamentals always via `publish_date`, never `period_end` (PIT rule — spec §16.6).
- `asyncio.to_thread()` for sync calls, never `run_in_executor` (CLAUDE.md Async-Pattern).
- Tests: `pytestmark = pytest.mark.unit` in all unit test files.
- Lint: `ruff check backend/` + `ruff format --check backend/` must pass before commit.
- Config fields use pydantic `Settings` class — never naked `os.getenv`.

---

## File Map

| Source (prisma_v3_seed/) | Destination (prisma-v2/) | Action |
|---|---|---|
| `alembic/0031_create_stock_price_history.py` | `backend/alembic/versions/` | Copy |
| `alembic/0032_create_stock_fundamentals.py` | `backend/alembic/versions/` | Copy |
| `alembic/0033_create_crypto_price_history.py` | `backend/alembic/versions/` | Copy |
| `alembic/0034_create_signal_outcomes.py` | `backend/alembic/versions/` | Copy |
| `alembic/0035_create_macro_rates.py` | `backend/alembic/versions/` | Copy |
| `pipeline/etl.py` | `backend/application/pipeline/etl.py` | Copy |
| `pipeline/load.py` | `backend/application/pipeline/load.py` | Copy |
| `adapters/eodhd_fundamentals_adapter.py` | `backend/infrastructure/adapters/eodhd_fundamentals_adapter.py` | Copy |
| `scripts/verify_dataset_coverage.py` | `scripts/verify_dataset_coverage.py` | Copy |
| `scripts/seed_historical_prices.py` | `scripts/seed_historical_prices.py` | Copy |
| `scripts/seed_crypto_history.py` | `scripts/seed_crypto_history.py` | Copy |
| `scripts/seed_fundamentals.py` | `scripts/seed_fundamentals.py` | Copy |
| `config_additions.py` | merge into `backend/config.py` | Adapt + Merge |
| `workflows/historical-seed.yml` | `.github/workflows/historical-seed.yml` | Copy |
| `PRISMA_V3_ANNOTATED_v33.md` | repo root | Copy |
| `prisma_v3_seed/` folder | repo root | Copy folder |

New files to create:
- `backend/application/pipeline/__init__.py`

---

## Task 1: Git Branch + Repo-Root Files

**Files:**
- No code changes — git + file copy operations only.

- [ ] **Step 1: Verify you are on main and it's clean**

```bash
cd /Users/andreapetretta/prisma-v2
git checkout main && git pull origin main
git status
```
Expected: clean working tree, up to date with origin/main.

- [ ] **Step 2: Create feature branch**

```bash
git checkout -b feature/prisma-v3-phase-0
```
Expected: `Switched to a new branch 'feature/prisma-v3-phase-0'`

- [ ] **Step 3: Copy spec + seed folder to repo root**

```bash
cp "/Users/andreapetretta/Desktop/Business Intelligence/PRISMA_V3_ANNOTATED_v33.md" \
   /Users/andreapetretta/prisma-v2/PRISMA_V3_ANNOTATED_v33.md

cp -R "/Users/andreapetretta/Desktop/Business Intelligence/prisma_v3_seed" \
   /Users/andreapetretta/prisma-v2/prisma_v3_seed
```
Expected: both exist in repo root.

- [ ] **Step 4: Verify copies**

```bash
ls /Users/andreapetretta/prisma-v2/PRISMA_V3_ANNOTATED_v33.md
ls /Users/andreapetretta/prisma-v2/prisma_v3_seed/README_SEED.md
```
Expected: both files found.

- [ ] **Step 5: Stage, commit**

```bash
cd /Users/andreapetretta/prisma-v2
git add PRISMA_V3_ANNOTATED_v33.md prisma_v3_seed/
git commit -m "$(cat <<'EOF'
chore(v3): add PRISMA V3 spec + seed skeleton to repo root

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Alembic Migrations 0031–0035

**Files:**
- Create: `backend/alembic/versions/0031_create_stock_price_history.py`
- Create: `backend/alembic/versions/0032_create_stock_fundamentals.py`
- Create: `backend/alembic/versions/0033_create_crypto_price_history.py`
- Create: `backend/alembic/versions/0034_create_signal_outcomes.py`
- Create: `backend/alembic/versions/0035_create_macro_rates.py`

**Interfaces:**
- Consumes: existing migration chain ending at `0030` (down_revision="0030" in 0031)
- Produces: 5 new tables in DB; alembic head = `0035`

- [ ] **Step 1: Copy migration files**

```bash
cd /Users/andreapetretta/prisma-v2
cp prisma_v3_seed/alembic/0031_create_stock_price_history.py backend/alembic/versions/
cp prisma_v3_seed/alembic/0032_create_stock_fundamentals.py backend/alembic/versions/
cp prisma_v3_seed/alembic/0033_create_crypto_price_history.py backend/alembic/versions/
cp prisma_v3_seed/alembic/0034_create_signal_outcomes.py backend/alembic/versions/
cp prisma_v3_seed/alembic/0035_create_macro_rates.py backend/alembic/versions/
```

- [ ] **Step 2: Verify chain is intact**

```bash
cd /Users/andreapetretta/prisma-v2
grep -h "^revision\|^down_revision" backend/alembic/versions/003[1-5]*.py
```
Expected output (in order):
```
revision = "0031"
down_revision = "0030"
revision = "0032"
down_revision = "0031"
revision = "0033"
down_revision = "0032"
revision = "0034"
down_revision = "0033"
revision = "0035"
down_revision = "0034"
```

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/003[1-5]*.py
git commit -m "$(cat <<'EOF'
feat(db): add V3 migrations 0031-0035 (price history, fundamentals, signal outcomes, macro rates)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: ETL Pipeline Module

**Files:**
- Create: `backend/application/pipeline/__init__.py`
- Create: `backend/application/pipeline/etl.py`
- Create: `backend/application/pipeline/load.py`
- Test: `backend/tests/unit/application/test_pipeline_etl.py`

**Interfaces:**
- Produces:
  - `normalize_ohlcv(df: pd.DataFrame, *, ticker: str, source: str, currency: str) -> list[dict]`
  - `normalize_crypto_ohlcv(df: pd.DataFrame, *, ticker: str, interval: str, source: str, currency: str) -> list[dict]`
  - `validate_ohlcv(rows: list[dict], *, table: str, spike_pct: float) -> tuple[list[dict], ValidationReport]`
  - `bulk_upsert(table: str, rows: Sequence[dict], batch: int) -> int` (async)

- [ ] **Step 1: Write failing tests first (TDD)**

Create `backend/tests/unit/application/test_pipeline_etl.py`:

```python
"""Unit tests for ETL pipeline — normalize + validate helpers."""

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ── normalize_ohlcv ──────────────────────────────────────────────────────────

def test_normalize_ohlcv_basic():
    from backend.application.pipeline.etl import normalize_ohlcv

    df = pd.DataFrame(
        {"Open": [100.0], "High": [105.0], "Low": [98.0], "Close": [103.0], "Volume": [10000]},
        index=pd.to_datetime(["2024-01-02"]),
    )
    rows = normalize_ohlcv(df, ticker="NESN", source="yfinance", currency="CHF")
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "NESN"
    assert r["currency"] == "CHF"
    assert r["source"] == "yfinance"
    assert r["close"] == 103.0
    import datetime
    assert r["date"] == datetime.date(2024, 1, 2)


def test_normalize_ohlcv_lowercase_columns():
    """Seed DataFrames may already have lowercase columns."""
    from backend.application.pipeline.etl import normalize_ohlcv

    df = pd.DataFrame(
        {"open": [50.0], "high": [52.0], "low": [49.0], "close": [51.0], "volume": [500]},
        index=pd.to_datetime(["2024-03-01"]),
    )
    rows = normalize_ohlcv(df, ticker="NOVN", source="yfinance", currency="CHF")
    assert rows[0]["open"] == 50.0


# ── validate_ohlcv ───────────────────────────────────────────────────────────

def test_validate_ohlcv_drops_zero_price():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {"ticker": "NESN", "date": "2024-01-02", "open": 0.0, "high": 105.0, "low": 0.0, "close": 103.0},
        {"ticker": "NESN", "date": "2024-01-03", "open": 103.0, "high": 104.0, "low": 102.0, "close": 103.5},
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history")
    assert len(clean) == 1
    assert rep.dropped == 1


def test_validate_ohlcv_drops_high_below_low():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {"ticker": "NESN", "date": "2024-01-02", "open": 100.0, "high": 95.0, "low": 98.0, "close": 99.0},
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history")
    assert len(clean) == 0
    assert rep.dropped == 1


def test_validate_ohlcv_flags_spike():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {"ticker": "NESN", "date": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        {"ticker": "NESN", "date": "2024-01-03", "open": 200.0, "high": 201.0, "low": 199.0, "close": 200.0},
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history", spike_pct=0.25)
    assert len(clean) == 2
    assert len(rep.spikes) == 1


def test_validate_ohlcv_clean_passthrough():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {"ticker": "NESN", "date": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        {"ticker": "NESN", "date": "2024-01-03", "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0},
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history")
    assert rep.ok
    assert rep.dropped == 0
    assert len(clean) == 2
```

- [ ] **Step 2: Run tests — expect ImportError (modules don't exist yet)**

```bash
cd /Users/andreapetretta/prisma-v2
uv run pytest backend/tests/unit/application/test_pipeline_etl.py -v 2>&1 | head -30
```
Expected: ImportError or ModuleNotFoundError for `backend.application.pipeline.etl`.

- [ ] **Step 3: Create pipeline module**

```bash
mkdir -p backend/application/pipeline
touch backend/application/pipeline/__init__.py
cp prisma_v3_seed/pipeline/etl.py backend/application/pipeline/etl.py
cp prisma_v3_seed/pipeline/load.py backend/application/pipeline/load.py
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest backend/tests/unit/application/test_pipeline_etl.py -v
```
Expected: 5 tests PASSED.

- [ ] **Step 5: Lint check**

```bash
ruff check backend/application/pipeline/ backend/tests/unit/application/test_pipeline_etl.py
ruff format --check backend/application/pipeline/ backend/tests/unit/application/test_pipeline_etl.py
```
Expected: no errors. If format issues: `ruff format backend/application/pipeline/ backend/tests/unit/application/test_pipeline_etl.py` then re-check.

- [ ] **Step 6: Commit**

```bash
git add backend/application/pipeline/ backend/tests/unit/application/test_pipeline_etl.py
git commit -m "$(cat <<'EOF'
feat(pipeline): add ETL normalize/validate/load helpers for V3 seed pipeline

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: EODHD Fundamentals Adapter

**Files:**
- Create: `backend/infrastructure/adapters/eodhd_fundamentals_adapter.py`
- Test: `backend/tests/unit/infrastructure/test_eodhd_adapter.py`

**Interfaces:**
- Produces:
  - `EodhdFundamentalsAdapter(api_key: str)` with `enabled: bool`
  - `async fetch_quarterly(ticker: str) -> list[dict]` — returns PIT-correct rows for `stock_fundamentals`
  - `EodhdFundamentalsAdapter.to_symbol(ticker: str) -> str` — `NESN → NESN.SW`

- [ ] **Step 1: Write failing tests (TDD)**

Create `backend/tests/unit/infrastructure/test_eodhd_adapter.py`:

```python
"""Unit tests for EODHD Fundamentals Adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit


def test_disabled_when_no_key():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter
    ad = EodhdFundamentalsAdapter(api_key="")
    assert not ad.enabled


def test_disabled_for_placeholder_key():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter
    ad = EodhdFundamentalsAdapter(api_key="your-eodhd-key")
    assert not ad.enabled


def test_enabled_with_real_key():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter
    ad = EodhdFundamentalsAdapter(api_key="abc123-real-key")
    assert ad.enabled


def test_to_symbol_adds_sw():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter
    assert EodhdFundamentalsAdapter.to_symbol("NESN") == "NESN.SW"


def test_to_symbol_keeps_existing_suffix():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter
    assert EodhdFundamentalsAdapter.to_symbol("NESN.SW") == "NESN.SW"


@pytest.mark.asyncio
async def test_fetch_quarterly_returns_empty_when_disabled():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter
    ad = EodhdFundamentalsAdapter(api_key="")
    result = await ad.fetch_quarterly("NESN")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_quarterly_returns_empty_on_http_error():
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter
    import httpx

    ad = EodhdFundamentalsAdapter(api_key="real-key-abc")
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await ad.fetch_quarterly("BADTICKER")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_quarterly_parses_minimal_eodhd_response():
    """Verify adapter parses a minimal EODHD JSON structure correctly."""
    from backend.infrastructure.adapters.eodhd_fundamentals_adapter import EodhdFundamentalsAdapter

    minimal_response = {
        "General": {"Sector": "Healthcare"},
        "Highlights": {"MarketCapitalizationMln": 250000},
        "Financials": {
            "Income_Statement": {"quarterly": {
                "2024-03-31": {"totalRevenue": "22000000000", "eps": "4.5", "filing_date": "2024-05-15"},
            }},
            "Balance_Sheet": {"quarterly": {
                "2024-03-31": {"totalStockholderEquity": "40000000000", "shortLongTermDebtTotal": "10000000000"},
            }},
            "Cash_Flow": {"quarterly": {
                "2024-03-31": {"freeCashFlow": "5000000000"},
            }},
        },
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = minimal_response

    ad = EodhdFundamentalsAdapter(api_key="real-key-abc")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        rows = await ad.fetch_quarterly("NESN")

    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "NESN"
    assert r["period_end"] is not None
    assert r["publish_date"] is not None  # PIT-date from filing_date
    assert r["period_type"] == "quarterly"
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
uv run pytest backend/tests/unit/infrastructure/test_eodhd_adapter.py -v 2>&1 | head -20
```
Expected: ImportError (adapter not yet in repo).

- [ ] **Step 3: Copy adapter**

```bash
cp prisma_v3_seed/adapters/eodhd_fundamentals_adapter.py \
   backend/infrastructure/adapters/eodhd_fundamentals_adapter.py
```

- [ ] **Step 4: Run tests — expect green**

```bash
uv run pytest backend/tests/unit/infrastructure/test_eodhd_adapter.py -v
```
Expected: all 8 tests PASSED.

If `test_fetch_quarterly_parses_minimal_eodhd_response` fails because `_derive()` expects specific EODHD field names not in the minimal fixture, read `backend/infrastructure/adapters/eodhd_fundamentals_adapter.py` lines around `_derive()` and adjust the fixture `minimal_response` dict to match the exact field names the adapter reads (e.g. `"filing_date"`, `"eps"`, etc.).

- [ ] **Step 5: Lint**

```bash
ruff check backend/infrastructure/adapters/eodhd_fundamentals_adapter.py \
           backend/tests/unit/infrastructure/test_eodhd_adapter.py
ruff format --check backend/infrastructure/adapters/eodhd_fundamentals_adapter.py \
                    backend/tests/unit/infrastructure/test_eodhd_adapter.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/infrastructure/adapters/eodhd_fundamentals_adapter.py \
        backend/tests/unit/infrastructure/test_eodhd_adapter.py
git commit -m "$(cat <<'EOF'
feat(adapters): add EODHD fundamentals adapter with PIT publish_date support

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Config Additions (backend/config.py)

**Files:**
- Modify: `backend/config.py`

**Interfaces:**
- Produces new `Settings` fields:
  - `eodhd_api_key: str = ""`
  - `dataset_source_fundamentals: str = "auto"`
  - `dataset_source_prices: str = "yfinance"`
  - `dataset_source_crypto: str = "cryptodatadownload"`
  - `seed_stocks_from: str = "2015-01-01"`
  - `seed_crypto_daily_from: str = "2017-01-01"`
  - `seed_crypto_hourly_from: str = "2020-01-01"`

- [ ] **Step 1: Read the end of backend/config.py to find the right insertion point**

```bash
tail -40 backend/config.py
```
Note the last field before the validators/methods.

- [ ] **Step 2: Add the new fields**

Open `backend/config.py` and add after the existing `glassnode_api_key` field (or at the end of the field block, before any validators):

```python
    # EODHD (eodhd.com) — Fundamentals + EOD, echte SIX-Coverage.
    # Free-Tier knapp (20 Calls/Tag); Seed braucht ggf. 1 Monat Paid.
    # Leer = EODHD-Adapter deaktiviert, kein HTTP-Call.
    eodhd_api_key: str = ""

    # Steuert, welche Fundamentals-Quelle der Feature-/Seed-Pfad nutzt.
    # auto  = verify_dataset_coverage.py hat den Sieger nach docs/dataset_coverage.md geschrieben
    # eodhd | fmp | simfin_us | yf_derived
    dataset_source_fundamentals: str = "auto"
    dataset_source_prices: str = "yfinance"
    dataset_source_crypto: str = "cryptodatadownload"

    # Trainings-/Seed-Tiefe (überschreibbar per ENV für Tests).
    seed_stocks_from: str = "2015-01-01"
    seed_crypto_daily_from: str = "2017-01-01"
    seed_crypto_hourly_from: str = "2020-01-01"
```

- [ ] **Step 3: Verify config still imports and passes existing tests**

```bash
uv run python -c "from backend.config import get_settings; s = get_settings(); print('eodhd_api_key:', repr(s.eodhd_api_key)); print('dataset_source_fundamentals:', s.dataset_source_fundamentals)"
uv run pytest backend/tests/unit/test_config.py -v
```
Expected: all pass, new fields visible with correct defaults.

- [ ] **Step 4: Lint**

```bash
ruff check backend/config.py && ruff format --check backend/config.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/config.py
git commit -m "$(cat <<'EOF'
feat(config): add V3 dataset source + EODHD key + seed depth settings

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Seed Scripts + GitHub Workflow

**Files:**
- Create: `scripts/verify_dataset_coverage.py`
- Create: `scripts/seed_historical_prices.py`
- Create: `scripts/seed_crypto_history.py`
- Create: `scripts/seed_fundamentals.py`
- Create: `.github/workflows/historical-seed.yml`

**Interfaces:**
- Consumes: `backend.application.pipeline.etl`, `backend.application.pipeline.load`, `backend.infrastructure.adapters.eodhd_fundamentals_adapter`, `backend.config.get_settings`
- Produces: `docs/dataset_coverage.md` (after running verify script)

- [ ] **Step 1: Copy seed scripts**

```bash
cp prisma_v3_seed/scripts/verify_dataset_coverage.py scripts/
cp prisma_v3_seed/scripts/seed_historical_prices.py scripts/
cp prisma_v3_seed/scripts/seed_crypto_history.py scripts/
cp prisma_v3_seed/scripts/seed_fundamentals.py scripts/
```

- [ ] **Step 2: Copy GitHub workflow**

```bash
cp prisma_v3_seed/workflows/historical-seed.yml .github/workflows/historical-seed.yml
```

- [ ] **Step 3: Verify seed scripts are importable (dry syntax check)**

```bash
uv run python -c "import ast, pathlib
for s in ['scripts/verify_dataset_coverage.py','scripts/seed_historical_prices.py','scripts/seed_fundamentals.py']:
    try:
        ast.parse(pathlib.Path(s).read_text())
        print(f'{s}: OK')
    except SyntaxError as e:
        print(f'{s}: SYNTAX ERROR {e}')
"
```
Expected: all three `OK`.

- [ ] **Step 4: Lint**

```bash
ruff check scripts/verify_dataset_coverage.py scripts/seed_historical_prices.py \
           scripts/seed_fundamentals.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_dataset_coverage.py scripts/seed_historical_prices.py \
        scripts/seed_crypto_history.py scripts/seed_fundamentals.py \
        .github/workflows/historical-seed.yml
git commit -m "$(cat <<'EOF'
feat(scripts): add V3 seed scripts and historical-seed GitHub workflow

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Run Alembic Migrations

**Files:**
- No file changes — DB operation only.

**Note:** Requires a running PostgreSQL. In development, use Docker:
```bash
docker compose up -d db
```
Or connect to the existing DB via `DATABASE_URL` env var.

- [ ] **Step 1: Check current alembic head**

```bash
cd /Users/andreapetretta/prisma-v2
uv run alembic current
```
Expected: `0030 (head)` or similar — the 0031–0035 migrations are pending.

- [ ] **Step 2: Run upgrade**

```bash
uv run alembic upgrade head
```
Expected output includes: `Running upgrade 0030 -> 0031`, ..., `Running upgrade 0034 -> 0035`.

- [ ] **Step 3: Verify tables exist**

```bash
uv run python -c "
import asyncio
from sqlalchemy import text
from backend.infrastructure.persistence.session import get_session_factory

async def check():
    factory = get_session_factory()
    async with factory() as s:
        for t in ['stock_price_history','stock_fundamentals','crypto_price_history','signal_outcomes','macro_rates']:
            r = await s.execute(text(f'SELECT COUNT(*) FROM {t}'))
            print(f'{t}: {r.scalar()} rows')

asyncio.run(check())
"
```
Expected: all 5 tables print `0 rows` (empty but exist).

- [ ] **Step 4: Commit (migrations are already committed in Task 2; this is just a checkpoint)**

No additional commit needed — the migration files were committed in Task 2.

---

## Task 8: Run Phase 0 Coverage Gate

**Files:**
- Produces: `docs/dataset_coverage.md`
- Modifies: `backend/config.py` (set `dataset_source_fundamentals` based on report)

- [ ] **Step 1: Run verify_dataset_coverage.py**

```bash
cd /Users/andreapetretta/prisma-v2
uv run python scripts/verify_dataset_coverage.py
```

If `EODHD_API_KEY` is not set, the EODHD probe returns 0 quarters (adapter disabled). That's OK — the script will still produce a report. Expected output includes a markdown table and a `## Empfehlung` section.

- [ ] **Step 2: Read the generated report**

```bash
cat docs/dataset_coverage.md
```

Check the `## Empfehlung` line:
- **`eodhd (CH)` passes (≥20 quarters, <20% nulls):** set `dataset_source_fundamentals = "eodhd"` in config
- **No source passes:** set `dataset_source_fundamentals = "simfin_us"` and add a note in the report that the US-Proxy methodology will be used for ML training (documented as a conscious choice per CHALLENGE 01)

- [ ] **Step 3: Fix dataset_source_fundamentals in backend/config.py**

Based on report outcome, edit `backend/config.py`:

**If EODHD passed:**
```python
dataset_source_fundamentals: str = "eodhd"
```

**If no CH source passed (most likely outcome with empty EODHD key):**
```python
dataset_source_fundamentals: str = "simfin_us"
```
And add to `docs/dataset_coverage.md` a note:
```
## Decision

CH-Fundamentals (EODHD, FMP) require a paid API key not yet available.
SimFin-US is used as the ML methodology dataset (academically reproducible,
clean PIT coverage). Swiss live signals use yfinance `.info` for approximate
fundamentals. This is documented explicitly per CHALLENGE 01.
```

- [ ] **Step 4: Lint check on modified config**

```bash
ruff check backend/config.py && ruff format --check backend/config.py
```

- [ ] **Step 5: Commit report + config fix**

```bash
git add docs/dataset_coverage.md backend/config.py
git commit -m "$(cat <<'EOF'
feat(phase-0): run dataset coverage gate, fix fundamentals source in config

docs/dataset_coverage.md shows coverage per provider.
dataset_source_fundamentals locked to empirically verified source (CHALLENGE 01).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Final Lint + Test + PR

**Files:**
- No new files — verification pass only.

- [ ] **Step 1: Run all unit tests**

```bash
cd /Users/andreapetretta/prisma-v2
uv run pytest backend/tests/unit -q
```
Expected: all tests pass (new tests added in Task 3 + 4 must be green).

- [ ] **Step 2: Full lint pass**

```bash
ruff check backend/ scripts/verify_dataset_coverage.py scripts/seed_historical_prices.py \
           scripts/seed_fundamentals.py
ruff format --check backend/
```

- [ ] **Step 3: Push branch**

```bash
git push -u origin feature/prisma-v3-phase-0
```

- [ ] **Step 4: Create PR**

```bash
gh pr create \
  --title "feat(v3): Phase 0 — dataset coverage gate + migrations 0031–0035" \
  --body "$(cat <<'EOF'
## Summary

- Copies PRISMA V3 spec + `prisma_v3_seed/` skeleton into repo
- Adds Alembic migrations 0031–0035 (stock_price_history, stock_fundamentals, crypto_price_history, signal_outcomes, macro_rates)
- Adds idempotent ETL pipeline (`backend/application/pipeline/etl.py` + `load.py`)
- Adds EODHD fundamentals adapter with PIT `publish_date` support
- Adds 4 seed scripts + historical-seed GitHub workflow
- Adds 7 new config fields (EODHD key, dataset sources, seed depths)
- Runs `scripts/verify_dataset_coverage.py` → `docs/dataset_coverage.md` (CHALLENGE 01 gate)
- Locks `dataset_source_fundamentals` in config based on empirical coverage result

## Test plan
- [ ] `uv run pytest backend/tests/unit -q` → all green
- [ ] `ruff check backend/` → no errors
- [ ] `docs/dataset_coverage.md` exists and contains empfehlung
- [ ] `uv run alembic current` shows `0035 (head)`
- [ ] `backend/config.py` `dataset_source_fundamentals` is not `"auto"` anymore

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Wait for CI green**

```bash
gh pr checks feature/prisma-v3-phase-0 --watch
```

---

## Phase 0 Acceptance Criteria

- [ ] `docs/dataset_coverage.md` exists and contains a `## Empfehlung` section
- [ ] `backend/config.py` field `dataset_source_fundamentals` is NOT `"auto"` — it's locked to the empirically tested winner (or `"simfin_us"` as documented fallback)
- [ ] `uv run alembic current` shows `0035 (head)`
- [ ] All 5 new tables exist in DB: `stock_price_history`, `stock_fundamentals`, `crypto_price_history`, `signal_outcomes`, `macro_rates`
- [ ] `uv run pytest backend/tests/unit -q` → all green (including new pipeline + adapter tests)
- [ ] PR merged to `main` with green CI

**Phase 0 complete → await OK before Phase 1 (Fundament: migrations applied, seed scripts run, FIX-01, FIX-06, macro_profiles.py)**
