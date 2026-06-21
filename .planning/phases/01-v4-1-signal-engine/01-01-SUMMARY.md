---
phase: 01-v4-1-signal-engine
plan: "01"
subsystem: database
tags: [alembic, yfinance, crypto, ohlcv, asyncio, retry, tdd, pandas]

requires: []

provides:
  - crypto_universe table with 10 seeded Top-10 coins (BTC/ETH/SOL/BNB/XRP/ADA/AVAX/DOGE/LINK/DOT)
  - CryptoPriceAdapter with async OHLCV backfill via yfinance (asyncio.to_thread)
  - validate_coverage() method (≥200 rows, max gap 3 trading days)
  - TDD test suite for CryptoPriceAdapter (12 unit tests, no live network)

affects:
  - 01-02 (OnChainAdapter depends on crypto_universe coin_ids)
  - 01-03 (FearGreedAdapter depends on market_sentiment table pattern)
  - 01-04 (indicators.py depends on OHLCV data from CryptoPriceAdapter)
  - all subsequent signal modules

tech-stack:
  added: []
  patterns:
    - "asyncio.to_thread for all yfinance sync calls (no run_in_executor)"
    - "_RETRIES=2, _BASE_DELAY=1.0, exponential backoff via manual loop"
    - "Alembic op.bulk_insert() for seed data in upgrade()"
    - "TDD Red-Green: test commit before implementation commit"

key-files:
  created:
    - backend/alembic/versions/0037_crypto_universe.py
    - backend/infrastructure/adapters/crypto_price_adapter.py
    - backend/tests/unit/infrastructure/test_crypto_price_adapter.py
  modified: []

key-decisions:
  - "Migration 0037 revises 0022 (latest existing migration)"
  - "CryptoPriceAdapter handles MultiIndex columns from yfinance via droplevel(1, axis=1)"
  - "validate_coverage() checks calendar day gaps (df.index.diff().dt.days) not trading day gaps — simpler, still catches meaningful data holes"
  - "auto_adjust=True in yfinance.download to avoid Adj Close disambiguation issues"

patterns-established:
  - "CryptoPriceAdapter pattern: _transform() separates column mapping from fetch logic"
  - "All adapters use asyncio.to_thread for sync I/O, not run_in_executor"

requirements-completed:
  - "Seed Top-10 crypto universe in DB"
  - "OHLCV backfill since 2017 via yfinance"
  - "Coverage check: ≥200 days per coin, no gap >3 days"

duration: 3min
completed: "2026-06-21"
---

# Phase 1 Plan 01: Crypto Universe + Price Adapter Summary

**Alembic Migration 0037 seeds Top-10 crypto universe; CryptoPriceAdapter liefert OHLCV-Backfill via yfinance mit asyncio.to_thread, exponentialem Retry und Coverage-Validierung.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-21T13:40:24Z
- **Completed:** 2026-06-21T13:43:27Z
- **Tasks:** 2 (T01: Migration, T02: Adapter TDD)
- **Files modified:** 3

## Accomplishments

- Alembic Migration 0037 erstellt: `crypto_universe`-Tabelle mit 10 geseedeten Coins (BTC/ETH/SOL/BNB/XRP/ADA/AVAX/DOGE/LINK/DOT), revises 0022
- `CryptoPriceAdapter` implementiert: `fetch_ohlcv()` via `asyncio.to_thread(yfinance.download, ...)`, Spalten-Mapping (Open→open etc.), symbol-Spalte, exponentieller Retry
- `validate_coverage()` implementiert: ValueError bei <200 Zeilen oder Lücke >3 Tage
- TDD-Zyklus vollständig: RED-Commit (12 Tests fehlschlagend) → GREEN-Commit (alle 12 grün)
- ruff und mypy strict sauber

## Task Commits

1. **T01: Migration 0037 crypto_universe** - `4ff0b12` (feat)
2. **T02 RED: Failing tests für CryptoPriceAdapter** - `378d813` (test)
3. **T02 GREEN: CryptoPriceAdapter Implementierung** - `9714825` (feat)

## Files Created/Modified

- `backend/alembic/versions/0037_crypto_universe.py` — Alembic Migration 0037; create_table + bulk_insert 10 Coins; downgrade drop_table
- `backend/infrastructure/adapters/crypto_price_adapter.py` — CryptoPriceAdapter mit fetch_ohlcv(), validate_coverage(), _transform()
- `backend/tests/unit/infrastructure/test_crypto_price_adapter.py` — 12 Unit-Tests (column mapping, symbol, retry, backoff, coverage)

## Decisions Made

- `auto_adjust=True` in yfinance.download gesetzt, um Adj-Close-Disambiguierungsprobleme bei MultiIndex zu vermeiden
- MultiIndex-Behandlung in `_transform()` via `droplevel(1, axis=1)` — yfinance gibt bei neueren Versionen manchmal MultiIndex zurück
- Calendar-Day-Gap-Check (nicht Trading-Day-Gap) in `validate_coverage()` — einfacher und ausreichend für Datenintegritätszwecke

## Deviations from Plan

Keine — Plan wurde exakt wie spezifiziert ausgeführt.

## Issues Encountered

Keine.

## Known Stubs

Keine — alle Felder vollständig implementiert, keine Placeholder-Werte.

## Threat Flags

Keine neuen Sicherheitsflächen eingeführt. Migration schreibt nur statische Seed-Daten. Adapter liest nur öffentliche Marktdaten.

## Next Phase Readiness

- Plan 01-01 vollständig abgeschlossen
- `crypto_universe`-Tabelle bereit für OnChain-Adapter (Plan 01-02)
- `CryptoPriceAdapter` kann sofort von Backfill-Scripts genutzt werden
- Kein Blocker für Wave-1-Parallelisierung (01-02, 01-03)

---
*Phase: 01-v4-1-signal-engine*
*Completed: 2026-06-21*
