---
title: CONCERNS
last_mapped: 2026-06-21
---

# Technical Debt & Concerns — PRISMA V4-1 Context

## V4-1 Aufbau-Lücken (noch nicht im Repo)

### Module die komplett neu gebaut werden müssen
- `backend/application/signals/` — existiert NICHT (indicators, consensus, vol_forecast, sizing, factors, meta_label, signal_service)
- `backend/application/backtest/` — existiert NICHT als separates Modul; Backtest-Logik liegt in `backend/application/services/backtest_service.py` (SMI-orientiert, muss für Walk-Forward / exposure-matched Baseline erweitert werden)
- `backend/interfaces/rest/routers/signals.py` — existiert NICHT (drei neue read-only Endpunkte)

### Datenbank-Migrationen ausstehend (nach 0022)
Letzte existierende Migration: `0022_fix_swiss_rag_embedding_dim.py`

Geplante neue Migrationen für V4-1:
- `0037_crypto_universe` — `crypto_universe` Tabelle (coin_id, symbol, name, active, added_at)
- `0038_crypto_onchain` — `crypto_onchain_history` Tabelle (coin_id, date, mvrv_z, realized_cap, active_addresses, tx_volume, exchange_netflow, source)
- `0039_market_sentiment` — `market_sentiment` Tabelle (date PK, fear_greed, fg_classification, source)
- `0040_signal_tables` — `signal_outcomes` + `vol_forecast` Tabellen

⚠️ Nummern 0023–0036 sind ggf. in anderen (noch nicht gemergten) Branches belegt — vor Erstellen der Migrationen prüfen: `git log --all --oneline | grep alembic`.

### Python-Abhängigkeiten fehlen
- `lightgbm` — nicht in `pyproject.toml`, muss unter `[project.dependencies]` eingetragen werden
- `ta` — technische Indikatoren Bibliothek, nicht in `pyproject.toml`
- Installationsbefehl für lokale Entwicklung: `pip install lightgbm ta --break-system-packages` (oder via pyproject.toml + `pip install -e ".[dev]"`)

---

## Kritische Risiken für V4-1

### 1. Look-Ahead-Guard (KRITISCH)
Das grösste methodische Risiko. Jeder Feature-Wert an Zeitpunkt `t` darf ausschliesslich Daten ≤ `t-1` verwenden. Ein versehentlicher `shift(0)` statt `shift(1)` in pandas führt zu unrealistisch guten Backtest-Ergebnissen ohne Fehlermeldung.

**Gegenmassnahme:** `backend/application/backtest/guards.py` mit automatisiertem Test (A7.2 in der Spec). Muss als CI-Gate laufen.

### 2. Datenverfügbarkeit Coin Metrics
- Community API liefert kostenlos MVRV-Z, Realized Cap, Active Addresses für BTC/ETH
- Für kleinere Coins (ADA, AVAX, DOT etc.) ist die Abdeckung dünner
- Fallback: On-Chain-Faktor ist gewichtet/optional für Coins ohne Coverage — kein Hard-Block

### 3. yfinance Rate-Limits beim Backfill
- Top-10-Krypto seit 2017 = ~3.300 Datenpunkte/Coin
- yfinance limitiert aggressive Batch-Requests — Backfill braucht exponential Backoff
- CryptoDataDownload als Fallback für historische CSV-Daten (bereits in PoC verwendet)

### 4. Overfitting im Vol-Modell
- HAR-Baseline ist der Anker: LightGBM wird nur deployed wenn OOS-R² > HAR
- Parameter MÜSSEN a priori fixiert sein (wie im PoC) — keine Grid-Search ohne Walk-Forward-Gate
- Alle `vol_forecast`-Experimente schreiben ihren `model_version`-String in DB

### 5. Migrations-Nummernkollision
- Branches `feature/prisma-v3-migration-0036`, `feature/prisma-v3-phase-*` und `feature/prisma-v3-ml-overlay` existieren remote und könnten Migrationen 0023–0036 belegen
- Vor Erstellen neuer Migrationen: `git fetch --all && git log --all --oneline -- "backend/alembic/versions/*.py" | sort`

---

## Bestehende Tech Debt (aus docs/OPEN_ITEMS.md, relevant für V4-1)

| Datei | Problem | V4-1-Relevanz |
|-------|---------|----------------|
| `narrative_service.py:402` | Race-Condition Job-Status (TOCTOU) | Niedrig (unberührt in V4-1) |
| `backtest_service.py` | SMI-orientiert, kein Walk-Forward, keine exposure-matched Baseline | **HOCH** — backtest/ muss neu strukturiert werden |
| `monte_carlo_service.py:124` | `dt=21` undokumentiert | Niedrig |
| `portfolio.py:42` | `YFinanceSwissAdapter` kein Request-Cache | Niedrig (Krypto-Adapter ist neu) |

---

## Security-Profil

- **Credentials:** Alle Keys via `backend/config.py` (pydantic-settings) aus `.env` — NICHT committed
  - `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `DATABASE_URL`, `API_KEY`, `TOOL_API_KEY`
  - Coin Metrics Community API: kein Key notwendig (öffentlich, rate-limited)
  - yfinance: kein Key notwendig
- **Production-Guard:** `_api_key_required_in_production()` bricht Boot ab wenn Keys fehlen
- **pgvector Embeddings:** 1536-dim (VoyageAI) für Swiss RAG — Crypto-Signal-Tabellen brauchen keine Embeddings in V4-1
- **CORS:** Via `cors_origins` ENV konfiguriert, default `localhost:3000`
- **API-Auth:** `X-API-Key` Header auf Admin-Endpoints; neue `/api/v1/signals` Endpunkte sind read-only, kein Auth erforderlich (Designentscheidung aus Spec A6)

---

## Performance-Profil

- **Backend:** Vollständig async (asyncpg + FastAPI async routes + `asyncio.to_thread()` für Sync-Libs)
- **yfinance-Calls:** Müssen via `asyncio.to_thread()` gewrappt werden (bestehende Konvention)
- **LightGBM Walk-Forward:** Kann mehrere Minuten dauern — als Background-Task oder einmalig beim Server-Start per Cronjob, Ergebnis in `vol_forecast`-Tabelle persistieren
- **LLM-Calls (V4-3, spätere Phase):** Prompt-Caching aktiv, Haiku für Analyst-Agenten, Sonnet für Synthese

---

## Coverage-Gate

- Pflicht: ≥80% (`fail_under = 80` in `pyproject.toml [tool.coverage.report]`)
- Neue `backend/application/signals/` und `backend/application/backtest/` Module müssen vollständig abgedeckt sein
- Adaptoren (Coin Metrics, Fear&Greed, yfinance) sind typischerweise von Coverage ausgenommen (externe I/O), ähnlich wie `simfin_adapter.py`

---

## Fragilste Stellen im Bestand (nicht anfassen in V4-1)

- `backend/application/agents/` (steuer_agent, macro_agent, portfolio_agent) — funktionieren, werden in V4-3 erweitert, in V4-1 NICHT berühren
- `backend/alembic/versions/0008_enable_pgvector_and_create_embeddings.py` — pgvector Extension-Setup ist idempotent, aber sensibel
- `frontend/app/decision/` — bestehendes SMI-Signal-UI, bleibt unberührt bis V4-5
- `backend/application/services/signal_validation_service.py` — neu in develop (Commit `b252d6b`), noch wenig Test-Coverage
