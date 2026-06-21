---
phase: 1
plan: "02"
subsystem: data-infrastructure
tags:
  - crypto
  - onchain
  - fear-greed
  - migrations
  - adapters
  - tdd
dependency_graph:
  requires:
    - "01-01 (crypto_universe table via migration 0037)"
  provides:
    - "crypto_onchain_history table (migration 0038)"
    - "market_sentiment table (migration 0039)"
    - "CoinMetricsAdapter.fetch_onchain() -> pd.DataFrame"
    - "FearGreedAdapter.fetch_history() -> pd.DataFrame"
  affects:
    - "backend/application/signals/factors.py (onchain_health_score — future plan)"
tech_stack:
  added:
    - "httpx.AsyncClient for both adapters (already in deps)"
  patterns:
    - "Async HTTP with context manager (httpx.AsyncClient)"
    - "Manual retry with exponential backoff (_RETRIES=2, _BASE_DELAY=1.0)"
    - "NULL fallback for unavailable coins (no raise on 404/empty)"
    - "UTC-aware datetime parsing (datetime.UTC alias)"
key_files:
  created:
    - "backend/alembic/versions/0038_crypto_onchain_history.py"
    - "backend/alembic/versions/0039_market_sentiment.py"
    - "backend/infrastructure/adapters/coin_metrics_adapter.py"
    - "backend/infrastructure/adapters/fear_greed_adapter.py"
    - "backend/tests/unit/infrastructure/test_coin_metrics_adapter.py"
    - "backend/tests/unit/infrastructure/test_fear_greed_adapter.py"
  modified: []
decisions:
  - "NULL-Fallback für nicht verfügbare Coins: 404 und leere Response geben leeren DataFrame zurück — kein Raise. Entspricht Plan-Anforderung."
  - "datetime.UTC alias statt timezone.utc (UP017 ruff fix) — Python 3.11+ Konvention."
  - "limit=0 für vollständige Fear&Greed History (nicht limit=2000 wie in Spec-Kommentar — limit=0 liefert API-seitig die gesamte History)."
  - "tx_volume auf None gesetzt: Feld ist nicht im Coin Metrics Community API Plan verfügbar (nur in Enterprise)."
metrics:
  duration: "5m 18s"
  completed_date: "2026-06-21"
  tasks_total: 2
  tasks_completed: 2
  files_created: 6
  files_modified: 0
  tests_added: 18
  tests_green: 18
---

# Phase 1 Plan 02: On-Chain + Fear&Greed Adapters + Migrations 0038/0039 Summary

**One-liner:** Migrations 0038/0039 (crypto_onchain_history + market_sentiment) plus CoinMetricsAdapter (httpx, NULL-Fallback) und FearGreedAdapter (Unix-Timestamp-Parsing via UTC) mit 18 TDD-Unit-Tests.

## Tasks

| ID   | Name                                    | Status | Commit  |
|------|-----------------------------------------|--------|---------|
| T01  | Migrations 0038 + CoinMetricsAdapter   | DONE   | 9ab00e7 |
| T02  | Migration 0039 + FearGreedAdapter       | DONE   | 05ee835 |

**TDD Commits:**
- `8e5c8c9` — test(01-02): add failing tests for CoinMetricsAdapter (RED)
- `9ab00e7` — feat(data): migration 0038 crypto_onchain + coin metrics adapter (GREEN)
- `e1bdabd` — test(01-02): add failing tests for FearGreedAdapter (RED)
- `05ee835` — feat(data): migration 0039 market_sentiment + fear&greed adapter (GREEN)

## What Was Built

### Migration 0038 — crypto_onchain_history

Tabelle mit On-Chain Metriken (coin_id FK auf crypto_universe, date als zusammengesetzter PK):
- `mvrv_z` (Float, nullable) — aus SplyMVRVCur
- `realized_cap` (Float, nullable) — aus RealizedCap
- `active_addresses` (Float, nullable) — aus AdrActCnt
- `tx_volume` (Float, nullable) — immer NULL (nicht im Community-Plan)
- `exchange_netflow` (Float, nullable) — FlowOutExNtv - FlowInExNtv
- `source` (String, default "coin_metrics")

### Migration 0039 — market_sentiment

Tabelle mit Fear & Greed Sentiment (date als PK):
- `fear_greed` (Integer, not null) — 0–100 Wert
- `fg_classification` (String, not null) — z.B. "Extreme Fear", "Greed"
- `source` (String, default "alternative_me")

### CoinMetricsAdapter

- Endpoint: `https://community-api.coinmetrics.io/v4/timeseries/asset-metrics`
- Keine Authentifizierung erforderlich (Community API)
- Feldmapping: SplyMVRVCur→mvrv_z, RealizedCap→realized_cap, AdrActCnt→active_addresses, FlowOutExNtv-FlowInExNtv→exchange_netflow
- NULL-Fallback: 404 und leere Response → leerer DataFrame (kein Raise)
- ISO-8601-Timestamp-Parsing (Nanozeitsekunden werden abgeschnitten)

### FearGreedAdapter

- Endpoint: `https://api.alternative.me/fng/?limit=0&format=json`
- limit=0 = vollständige History (nicht paginiert)
- Unix-Timestamp → date via `datetime.fromtimestamp(int(ts), tz=UTC).date()`
- DataFrame [date, fear_greed, fg_classification]

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Falsches strptime-Format für ISO-8601-Timestamp**
- **Found during:** T01 GREEN-Phase (erster Test-Lauf)
- **Issue:** Format `%Y-%m-%dT%H:%MZ` hat keine Sekunden; nach Abschneiden der Nanozeitsekunden hat der String `"2024-01-01T00:00:00Z"` das Format mit Sekunden
- **Fix:** Format auf `%Y-%m-%dT%H:%M:%SZ` korrigiert
- **Files modified:** `backend/infrastructure/adapters/coin_metrics_adapter.py`
- **Commit:** 9ab00e7 (im gleichen Commit)

**2. [Rule 1 - Bug] ruff UP017: timezone.utc statt datetime.UTC alias**
- **Found during:** T01 ruff-Check
- **Issue:** Python 3.11+ bevorzugt `datetime.UTC` (ruff rule UP017)
- **Fix:** Import von `UTC` statt `timezone`, `timezone.utc` → `UTC`
- **Files modified:** `backend/infrastructure/adapters/coin_metrics_adapter.py`
- **Commit:** 9ab00e7 (im gleichen Commit)

**3. [Rule 1 - Bug] Test-Assertion mit np.int64**
- **Found during:** T02 GREEN-Phase (Test `test_fetch_history_extracts_value_as_int`)
- **Issue:** `isinstance(np.int64(25), int | float)` ist False in Python 3.12+ (numpy-Typen erben nicht mehr von Python-Builtins)
- **Fix:** Test-Assertion auf `int | float | np.integer` erweitert (kommentiert: "numpy int auch ok")
- **Files modified:** `backend/tests/unit/infrastructure/test_fear_greed_adapter.py`
- **Commit:** 05ee835 (im gleichen Commit)

**4. [Kontextuell] 01-01 Prerequisite-Dateien eingebunden**
- **Situation:** Worktree-Branch startete von `cdea99e` (vor 01-01), `git merge feat/v4-1-signal-engine` scheiterte wegen .planning-Konflikten
- **Fix:** `git checkout feat/v4-1-signal-engine -- <files>` für die 3 Code-Dateien aus 01-01 (0037-Migration, CryptoPriceAdapter, test_crypto_price_adapter) verwendet. Keine .planning/-Dateien kopiert.
- **Begründung:** Plan-Kontext gibt an "Plan 01-01 was just completed and merged" — Dateien waren auf feat/v4-1-signal-engine, mussten manuell in Worktree übernommen werden.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `tx_volume: None` | `coin_metrics_adapter.py:170` | Feld nicht im Coin Metrics Community API enthalten (nur Enterprise). Geplant: immer NULL. Migration-Spalte existiert für zukünftige Enterprise-Integration. |

## Threat Flags

Keine neuen Security-relevanten Endpunkte oder Auth-Paths eingeführt. Beide Adapter nutzen öffentliche Read-Only APIs ohne Credentials.

## Verification Results

```
18 passed in 0.14s
ruff: All checks passed (2 files)
mypy: Success, no issues found (2 files)
```

## Self-Check: PASSED

Files created:
- FOUND: backend/alembic/versions/0038_crypto_onchain_history.py
- FOUND: backend/alembic/versions/0039_market_sentiment.py
- FOUND: backend/infrastructure/adapters/coin_metrics_adapter.py
- FOUND: backend/infrastructure/adapters/fear_greed_adapter.py
- FOUND: backend/tests/unit/infrastructure/test_coin_metrics_adapter.py
- FOUND: backend/tests/unit/infrastructure/test_fear_greed_adapter.py

Commits verified:
- FOUND: 8e5c8c9 (RED CoinMetrics)
- FOUND: 9ab00e7 (GREEN CoinMetrics + 0038)
- FOUND: e1bdabd (RED FearGreed)
- FOUND: 05ee835 (GREEN FearGreed + 0039)
