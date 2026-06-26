# PRISMA V4 — Deployment Runbook

**Version:** v4.0  
**Ziel:** Release PR #308 (develop → main) in Produktion bringen.  
**Wichtig:** Schritte b–f berühren Produktion / Live-DB. NICHT durch Claude ausführen lassen — manuell abarbeiten.

---

## Schritt a — Release-PR im UI mergen

1. Öffne https://github.com/don69andrea/prisma-v2/pull/308
2. Prüfe: CI zeigt **5/5 grün** (Backend Unit Tests, Backend Integration Tests, Backend Lint & Typecheck, Frontend Lint & Build, Frontend E2E Playwright).
3. Merge-Button klicken → **"Merge pull request"** (Merge-Commit, kein Squash).
4. Warte bis GitHub "Pull request successfully merged" zeigt.

---

## Schritt b — Tag setzen

```bash
git checkout main
git pull --ff-only
git tag -a v4.0 -m "PRISMA V4 release — feature-complete (V4-1 bis V4-6)"
git push origin v4.0
```

Verifizieren:
```bash
git tag -l "v4.0"
# → v4.0
```

---

## Schritt c — Render-Deployment

Render deployt **automatisch** sobald main aktualisiert ist (`autoDeploy: true` in `render.yaml` für beide Services).

**Backend** (`prisma-v2-backend`):  
- Render baut das Docker-Image neu.
- `backend-start.sh` läuft automatisch: `alembic upgrade head` → dann `uvicorn`.
- Migrationen 0037–0048 werden dabei angewendet (idempotent, falls schon vorhanden).

**Frontend** (`prisma-v2-frontend`):  
- Next.js-Bundle wird mit aktuellem `NEXT_PUBLIC_API_URL` neu gebaut.

**Manueller Re-Deploy** (falls Auto-Deploy nicht anspringt):
1. https://dashboard.render.com → Service `prisma-v2-backend` → **"Manual Deploy" → "Deploy latest commit"**
2. Gleich für `prisma-v2-frontend`.

**Deploy-Fortschritt beobachten:**  
Render Dashboard → Service → Tab "Events" — warte auf `Your service is live`.

---

## Schritt d — DB-Migrationen gegen Live-Postgres

Die Migrationen laufen automatisch in `backend-start.sh` beim Containerstart (Schritt c).  
Falls ein Fehler auftritt oder manueller Lauf nötig ist:

```bash
# Voraussetzung: prod DATABASE_URL setzen (aus Render Dashboard → prisma-v2-db → "Connection")
export DATABASE_URL="postgresql+asyncpg://<user>:<pass>@<host>/<db>?sslmode=require"

# Migrationen anwenden
cd ~/prisma-v2
alembic upgrade head
```

Erwartete neue Migrationen (falls DB noch auf Stand vor V4):
```
0037_crypto_universe
0038_crypto_onchain_history
0039_market_sentiment
0040_vol_forecast
0041_agent_audit_trail
0042_widen_news_source_column
0043_hitl_confirmations
0044_signal_outcomes
0045_live_performance_metrics
0046_model_registry
0047_paper_trading_log
0048_drift_flags
```

Aktuellen Stand prüfen:
```bash
alembic current
# → sollte "0048_drift_flags (head)" zeigen
```

---

## Schritt e — Daten seeden in der Live-DB

### e.1 — Crypto-Universum (automatisch via Migration 0037)

Migration `0037_crypto_universe` enthält `op.bulk_insert` mit den Top-10 Coins (BTC-USD, ETH-USD, SOL-USD, BNB-USD, …). Wird beim ersten `alembic upgrade head` automatisch eingefügt — **kein separater Seed-Befehl nötig**.

Verifizieren (psql oder Render Query Tool):
```sql
SELECT symbol, name, active FROM crypto_universe ORDER BY coin_id;
-- Erwarte: 10 Zeilen (BTC-USD bis LINK-USD)
```

### e.2 — Agent Audit Trail seeden (echte SignalDirector-Runs)

Voraussetzung: Backend ist deployed und erreichbar.

```bash
# API-Modus (bevorzugt) — triggert echten SignalDirector via Live-Backend
export BACKEND_URL="https://prisma-v2-backend.onrender.com"
export API_KEY="<dein-API-Key aus Render Dashboard>"
python scripts/seed_crypto_audit_trail.py
```

Fallback (Demo-Modus, falls Backend nicht erreichbar):
```bash
export SEED_DEMO_ONLY=1
export DATABASE_URL="postgresql+asyncpg://<user>:<pass>@<host>/<db>?sslmode=require"
python scripts/seed_crypto_audit_trail.py
# ACHTUNG: Demo-Einträge sind mit "[DEMO-DATEN]" markiert — Ehrlichkeitsregel.
```

### e.3 — Kurshistorie (OHLCV)

Die Kurshistorie wird vom Operations-Worker und den API-Endpunkten on-demand via yfinance befüllt.  
Für ein initiales Voraufladen der OHLCV-Daten kann der Operations-Worker einmalig gestartet werden (siehe Schritt f).

---

## Schritt f — Operations-Worker starten

Der Operations-Worker (`backend/infrastructure/workers/operations_worker.py`) führt täglich die V4-6-Jobs aus:
- `SignalEvaluationJob` (04:00 UTC)
- `RetrainingJob` (05:00 UTC)
- `DriftMonitor` (05:30 UTC)
- `PaperTradingLogWriter.fill_outcomes` (06:15 UTC)

### Option 1: Manueller Einmal-Lauf (Test / initialer Seed)

```bash
# Lokal mit prod DATABASE_URL:
export DATABASE_URL="postgresql+asyncpg://<user>:<pass>@<host>/<db>?sslmode=require"
export ANTHROPIC_API_KEY="<key>"
export VOYAGE_API_KEY="<key>"
cd ~/prisma-v2
python -m backend.infrastructure.workers.operations_worker --once
```

### Option 2: Dauerbetrieb via Render Background Worker

Der Worker ist **noch nicht** in `render.yaml` als separater Service eingetragen. Um ihn dauerhaft auf Render laufen zu lassen:

1. Render Dashboard → **"New" → "Background Worker"**
2. Einstellungen:
   - **Name:** `prisma-v2-operations-worker`
   - **Repository:** `don69andrea/prisma-v2`
   - **Branch:** `main`
   - **Runtime:** Docker
   - **Dockerfile:** `./Dockerfile.backend`
   - **Docker Command:** `python -m backend.infrastructure.workers.operations_worker`
   - **Environment Variables:** `DATABASE_URL` (aus DB), `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`

Alternativ: `render.yaml` um folgenden Block erweitern und via PR auf main deployen:

```yaml
- type: worker
  name: prisma-v2-operations-worker
  runtime: docker
  dockerfilePath: ./Dockerfile.backend
  branch: main
  plan: free
  dockerCommand: python -m backend.infrastructure.workers.operations_worker
  envVars:
    - key: DATABASE_URL
      fromDatabase:
        name: prisma-v2-db
        property: connectionString
    - key: ANTHROPIC_API_KEY
      sync: false
    - key: VOYAGE_API_KEY
      sync: false
    - key: ENVIRONMENT
      value: production
    - key: PYTHONPATH
      value: /app
```

---

## Schritt g — Env-Variablen setzen

Alle `sync: false`-Variablen müssen **manuell** im Render Dashboard gesetzt werden:

| Variable | Service | Beschreibung |
|----------|---------|--------------|
| `ANTHROPIC_API_KEY` | Backend, Operations-Worker | Claude API Key (nie im Code) |
| `VOYAGE_API_KEY` | Backend, Operations-Worker | VoyageAI Embedding Key (CryptoPanic-RAG) |
| `API_KEY` | Backend | Admin-API-Key (`openssl rand -hex 32`) |
| `NEXT_PUBLIC_API_KEY` | Frontend | Muss identisch mit `API_KEY` im Backend sein |
| `SENDGRID_API_KEY` | Backend | Alert-E-Mails (optional) |
| `TOOL_API_KEY` | Backend | MCP-Tool-Authentifizierung (optional) |
| `CRYPTOPANIC_API_KEY` | Backend | CryptoPanic-News (optional — ohne Key: öffentliche API) |

Setzen: Render Dashboard → Service → "Environment" → Variable hinzufügen → "Save Changes".

---

## Schritt h — Live-Smoke-Test-Checkliste

Nach Deploy: folgende Checks manuell im Browser / via curl durchführen.

```bash
BASE="https://prisma-v2-backend.onrender.com"
```

| # | Check | Erwartet |
|---|-------|----------|
| 1 | `GET $BASE/health` | `{"status": "ok", ...}` — kein 503 |
| 2 | `GET $BASE/health/pipeline` | Pipeline-Status sichtbar |
| 3 | Frontend `https://prisma-v2-frontend.onrender.com/crypto` laden | Seite rendert, kein Blank-Screen |
| 4 | `/crypto` → Coin auswählen → Explainability-Panel | Zeigt echte Reasoning-Daten aus `agent_audit_trail` (nicht "[DEMO-DATEN]") |
| 5 | `/crypto` → Backtest-Panel | Rendern ohne Fehler, Metriken sichtbar |
| 6 | `/crypto` → Portfolio-Panel | Allokationen rendern |
| 7 | HITL-Gate testen | Signal mit `confidence < 0.65` triggert Checkpoint-Dialog im Browser |
| 8 | Admin-Dashboard `/admin` | Lädt mit gültigem `API_KEY`-Header |

```bash
# Schnell-Check via curl:
curl -s $BASE/health | python3 -m json.tool
curl -s $BASE/health/pipeline | python3 -m json.tool
```

---

## Rollback

Falls der Deploy kritische Fehler produziert:

```bash
# Auf Render: vorherigen Deploy aktivieren
# Render Dashboard → Service → "Events" → früheren Deploy → "Rollback to this deploy"

# Oder via Git-Tag:
git checkout main
git revert HEAD --no-edit
git push origin main
```
