# Audit & Fix Plan — 2026-06-13

Branch: `fix/security-performance-audit`  
Erstellt durch: Paralleler 4-Agenten-Audit (Deployment, Security, Contract, ML/DB)  
Status: 🔄 IN PROGRESS

---

## Übersicht

| Domain | Kritisch | Warnung | Info |
|--------|----------|---------|------|
| Deployment/CI | 4 | 6 | 4 |
| Security | 4 | 8 | 7 |
| Frontend/Backend Contract | 3 | 4 | 5 |
| ML/DB Pipeline | 2 | 7 | 3 |
| **Total** | **13** | **25** | **19** |

---

## KRITISCHE FIXES (alle müssen vor Merge erledigt sein)

### K-1 — llm-smoke.yml: falsches working-directory
- **Datei:** `.github/workflows/llm-smoke.yml:23`
- **Problem:** `working-directory: backend` gesetzt, aber `pyproject.toml` liegt im Repo-Root → Smoke-Tests haben NIE funktioniert
- **Fix:** `working-directory: backend` entfernen (oder auf `.` setzen)
- **Status:** ⬜ TODO

### K-2 — CD deployt ohne CI-Gate
- **Datei:** `.github/workflows/cd-render.yml:5`
- **Problem:** `push: branches: [main]` startet CD parallel zu CI → defekter Code geht direkt auf Render
- **Fix:** `workflow_run` Dependency auf CI-Workflow hinzufügen: CD wartet bis CI erfolgreich
- **Status:** ⬜ TODO

### K-3 — ANTHROPIC_API_KEY ohne Boot-Guard
- **Datei:** `backend/config.py:18`
- **Problem:** Default `""`, kein Validator wie bei `api_key` → App startet healthy, crasht beim ersten LLM-Call mit 500
- **Fix:** `@field_validator("anthropic_api_key")` der in Production `""` ablehnt (analog zu `_api_key_required_in_production`)
- **Status:** ⬜ TODO

### K-4 — Port hardcoded 8000, ignoriert Render's `$PORT`
- **Datei:** `scripts/backend-start.sh:16`
- **Problem:** `uvicorn ... --port 8000` — Render setzt `$PORT` dynamisch, App muss darauf lauschen
- **Fix:** `--port ${PORT:-8000}`
- **Status:** ⬜ TODO

### K-5 — `/api/v1/chat` vollständig unauthentifiziert + ausserhalb Budget-Tracking
- **Datei:** `backend/interfaces/rest/routers/chat.py:17`
- **Problem:** Jeder kann beliebig viele Claude-Requests absetzen; Kosten landen NICHT im CostTracker/llm_call_log
- **Fix:** `_auth: None = Depends(require_admin_api_key)` als Parameter hinzufügen
- **Status:** ⬜ TODO

### K-6 — Vector-Embedding f-String SQL in 3 Repositories
- **Dateien:**
  - `backend/infrastructure/persistence/repositories/embedding_repository.py:135`
  - `backend/infrastructure/persistence/repositories/news_repository.py:88`
  - `backend/infrastructure/persistence/repositories/swiss_filing_repository.py:75`
- **Problem:** `f"... ('{vector_str}'::vector ...)"` — float-Array direkt per f-String in SQL interpoliert. NaN/Inf brechen PostgreSQL; external compromise von VoyageAI könnte theoretisch Injection erlauben
- **Fix:** Alle float-Werte mit `math.isfinite()` validieren vor dem SQL-String-Bau; `.8f`-Format verwenden statt `str(x)` (verhindert `nan`/`inf` als Literale)
- **Status:** ⬜ TODO

### K-7 — Webhook-SSRF via `POST /alerts`
- **Dateien:**
  - `backend/interfaces/rest/routers/alerts.py:47`
  - `backend/infrastructure/adapters/notification_adapter.py:49`
- **Problem:** `AlertCreateRequest.target` ist plain `str`, kein URL-Format-Check → `channel=WEBHOOK, target=http://169.254.169.254/...` möglich → SSRF auf Cloud-Metadata
- **Fix:** Pydantic-Feld ändern auf `AnyHttpUrl` mit Custom Validator: nur `https://`-Schema, Private-IPs blocken (RFC 1918: 10.x, 172.16-31.x, 192.168.x, 169.254.x, 127.x)
- **Status:** ⬜ TODO

### K-8 — Discovery `partial_profile` vollständiger Feldname-Mismatch
- **Dateien:**
  - `frontend/lib/api/discovery.ts:43` — erwartet `PartialProfile { beruf, ziel, risiko, brands }`
  - `backend/interfaces/rest/schemas/investor_profile.py:66` — liefert `InvestorProfileResponse { session_id, risk_profile, sector_affinity, time_horizon, investment_goal, confidence_score, onboarding_complete }`
- **Problem:** Kein einziges Feld stimmt überein → alle `partial_profile`-Zugriffe liefern `undefined` im Frontend
- **Fix:** TypeScript-Interface `PartialProfile` und `CompleteDiscoveryResponse.profile` auf die tatsächliche Backend-Struktur anpassen: Felder umbenennen auf `risk_profile`, `investment_goal`, `onboarding_complete` etc.
- **Status:** ⬜ TODO

### K-9 — Backtest-Series Typ-Mismatch: `string[]` vs `number[]`
- **Dateien:**
  - `frontend/lib/api/backtest.ts:16` — `series.prisma/universe/benchmark: string[]`
  - `backend/interfaces/rest/schemas/backtest.py:34` — `prisma/universe/benchmark: list[Decimal]` → JSON-Zahl
- **Problem:** Frontend erwartet Strings für Chart-Rendering, bekommt Numbers → möglicherweise NaN in Charts
- **Fix:** TypeScript-Types auf `number[]` ändern
- **Status:** ⬜ TODO

### K-10 — Event Loop blockiert: `_fetch_chf_eur()` in MacroService (sync yfinance-Call)
- **Datei:** `backend/application/services/macro_service.py:172`
- **Problem:** `chf_eur = _fetch_chf_eur()` — direkter `yf.Ticker(...).history()` Call im async Context ohne `asyncio.to_thread` → blockiert alle anderen Coroutinen für 1-3s
- **Fix:** `chf_eur = await asyncio.to_thread(_fetch_chf_eur)`
- **Status:** ⬜ TODO

### K-11 — Event Loop blockiert: `_current_chf_eur()` in ml_feature_service (sync yfinance-Call)
- **Datei:** `backend/application/services/ml_feature_service.py:287`
- **Problem:** `chf_eur=_current_chf_eur()` in async `build_features()` → gleicher Bug
- **Fix:** `chf_eur=await asyncio.to_thread(_current_chf_eur)`
- **Status:** ⬜ TODO

### K-12 — `TOOL_API_KEY` Default `""` → /api/v1/runs komplett öffentlich
- **Datei:** `backend/interfaces/rest/dependencies.py:215`
- **Problem:** `if not settings.tool_api_key: return` → wenn Key im Dashboard nicht gesetzt, ist /runs Auth disabled. Alle Ranking-Daten öffentlich.
- **Fix:** Production-Warning-Log wenn `tool_api_key` leer ist; in `config.py` `tool_api_key` mit Production-Validator versehen analog zu `api_key`
- **Status:** ⬜ TODO

### K-13 — CORS: Middleware-Reihenfolge falsch + CORS_ORIGINS nicht gesetzt
- **Dateien:**
  - `backend/interfaces/rest/app.py:109-116` — `LLMRateLimiterMiddleware` liegt aussen, 429-Responses haben keine CORS-Header
  - `render.yaml:41-42` — `CORS_ORIGINS: sync: false` → Default `localhost:3000` in Production
  - `render.yaml:73-74` — `NEXT_PUBLIC_API_URL: sync: false` → Frontend baut mit `localhost:8000`
  - `backend/interfaces/rest/exception_handlers.py:82-91` — 402-Response ohne CORS-Header
- **Fix:**
  - `app.py`: CORSMiddleware zuletzt hinzufügen (→ outermost)
  - `render.yaml`: `CORS_ORIGINS=https://prisma-v2-frontend.onrender.com` und `NEXT_PUBLIC_API_URL=https://prisma-v2-backend.onrender.com` als `value:`
  - `exception_handlers.py`: `Access-Control-Allow-Origin: *` zu 402-Response
- **Status:** ⬜ TODO (diese Fixes sind in PR #153 bereits vorhanden, hier nochmals anwenden)

---

## WARNUNGEN (vor Release fixen)

### W-1 — 24+ LLM/Daten-Endpoints ohne Auth
- **Datei:** `backend/interfaces/rest/app.py:125-148`
- **Problem:** memos/generate, decisions, portfolio/allocate, backtests, macro, discovery etc. komplett öffentlich
- **Fix-Strategie:** Global API-Key Guard als Default-Dependency für alle Router, explizit öffentliche Endpoints (health, discovery public parts) ausgenommen
- **Status:** ⬜ TODO (komplex, separater PR sinnvoll)

### W-2 — Monte Carlo ohne Rate-Limit + Event Loop blockierend
- **Datei:** `backend/interfaces/rest/routers/portfolio.py:99`
- **Problem:** `POST /portfolio/monte-carlo` mit `n_simulations <= 50000`, läuft synchron, kein Rate-Limit
- **Fix:** `await asyncio.to_thread(run_monte_carlo, ...)` + `/api/v1/portfolio/monte-carlo` in `_LLM_PREFIXES` des Rate-Limiters
- **Status:** ⬜ TODO

### W-3 — Rate-Limiter unvollständig
- **Datei:** `backend/interfaces/rest/rate_limiter.py:20`
- **Problem:** `/decisions/explain`, `/news/ingest`, `/backtests`, `/stocks/{ticker}/report.pdf` fehlen in `_LLM_PREFIXES`
- **Fix:** Diese Pfade ergänzen
- **Status:** ⬜ TODO

### W-4 — Ticker-Parameter ohne Regex-Constraint
- **Dateien:** `routers/stocks.py:33,87,105`, `routers/decision_audit.py:47`, `routers/macro.py`
- **Problem:** `ticker: str` ohne Pattern → beliebige Strings an yfinance
- **Fix:** `ticker: str = Path(..., pattern=r"^[A-Z0-9.\-]{1,12}$")`
- **Status:** ⬜ TODO

### W-5 — Exception Handler gibt `Access-Control-Allow-Origin: *` (500er überschreiben CORS-Policy)
- **Datei:** `backend/interfaces/rest/exception_handlers.py:65`
- **Problem:** `handle_unhandled_exception` hardcodet `*` statt Origin aus Request zu spiegeln
- **Fix:** Origin-Header aus Request lesen, gegen `settings.cors_origins` validieren
- **Status:** ⬜ TODO

### W-6 — `VOYAGE_API_KEY` leer → RAG-Endpoints crashen mit 500
- **Datei:** `render.yaml:49-50`
- **Problem:** `sync: false` → Key muss manuell gesetzt werden. Ohne Key → `RuntimeError` bei erstem Embedding-Call
- **Fix:** Kommentar in render.yaml präzisieren: Key MUSS im Dashboard gesetzt sein. Backend `get_voyage_client()` sollte HTTP 503 statt 500 zurückgeben wenn Key fehlt
- **Status:** ⬜ TODO

### W-7 — `FMP_API_KEY` toter Config-Eintrag
- **Datei:** `render.yaml:52-53`
- **Problem:** In render.yaml deklariert, nicht in `config.py`, nirgendwo im Runtime-Code verwendet
- **Fix:** Aus render.yaml entfernen
- **Status:** ⬜ TODO

### W-8 — ml_features ORM & Migration fehlen 9 Feature-Spalten (Schema-Drift)
- **Dateien:**
  - `backend/alembic/versions/0016_create_ml_features.py` — nur 12 Spalten
  - `backend/infrastructure/persistence/models/ml_features.py` — nur 12 Spalten
  - `backend/application/services/ml_feature_service.py:FEATURE_NAMES` — 19 Features
- **Problem:** Wenn ein Feature-Store-Repository implementiert wird, schlägt es mit `ProgrammingError: column "return_6m" does not exist` fehl
- **Fehlende Spalten:** `return_6m, return_3m, vol_90d, price_to_52w_high, vol_trend, macd_hist, bb_position, return_1m, drawdown_12m`
- **Fix:** Migration `0020_add_ml_feature_columns.py` erstellen + ORM-Klasse aktualisieren (alle neuen Spalten `nullable=True`)
- **Status:** ⬜ TODO

### W-9 — 7 ORM-Modelle nicht in `alembic/env.py` importiert
- **Datei:** `backend/alembic/env.py`
- **Problem:** `alembic autogenerate` ist blind für: AlertORM, DecisionAuditLogORM, MLFeatureORM, NewsORM, NewsSourceORM, RankingRunORM, SwissFilingORM, UniverseORM
- **Fix:** Alle ORM-Klassen in `target_metadata` importieren
- **Status:** ⬜ TODO

### W-10 — SNB/ECB/Fed-Zinssätze 12+ Monate veraltet
- **Datei:** `backend/application/services/ml_feature_service.py:25-96`
- **Problem:** Letzter SNB-Eintrag `2025-06-19`, letzter ECB-Eintrag `2025-06-05`, letzter Fed-Eintrag `2025-03-20` → Features für aktuelle Inferenz nutzen veraltete Werte
- **Fix:** Zinssatz-Tabellen auf aktuellen Stand (2026-06-13) bringen
- **Status:** ⬜ TODO

### W-11 — `drawdown_12m` NaN-Risiko bei Zero-Preisen
- **Datei:** `backend/application/services/ml_feature_service.py:206`
- **Problem:** `(window - rolling_max) / rolling_max` → Division by Zero wenn `rolling_max == 0` → NaN im Feature-Vektor → undefiniertes Modell-Verhalten
- **Fix:** Guard: `rolling_max.replace(0, float("nan"))` vor Division + `fillna(0.0)` nach `.min()`
- **Status:** ⬜ TODO

### W-12 — `Decimal(0) or None`-Bug
- **Datei:** `backend/application/services/ml_feature_service.py:595`
- **Problem:** `Decimal(str(info.get("marketCap") or 0)) or None` → `Decimal(0)` ist falsy → valider 0-CHF Market Cap wird zu `None`
- **Fix:** `Decimal(str(info.get("marketCap") or 0)) if info.get("marketCap") is not None else None`
- **Status:** ⬜ TODO

### W-13 — CD ohne CI-Gate (bereits K-2, aber auch `release.yml` betroffen)
- **Datei:** `.github/workflows/release.yml`
- **Problem:** `release.yml` übergibt kein `--build-arg NEXT_PUBLIC_API_URL` → GHCR-Image hat `localhost:8000` eingebaut
- **Fix:** `--build-arg NEXT_PUBLIC_API_URL=https://prisma-v2-backend.onrender.com` in release.yml
- **Status:** ⬜ TODO

### W-14 — Stocks `total` ist `len(items)`, nicht echter DB-COUNT
- **Datei:** `backend/interfaces/rest/routers/stocks.py:78`
- **Problem:** `total=len(items)` statt `SELECT COUNT(*)` → UI-Pagination zeigt falsche Seitenzahl
- **Fix:** COUNT-Query hinzufügen oder `total` aus Response entfernen und ehrlich dokumentieren
- **Status:** ⬜ TODO

### W-15 — Stilles Abschneiden bei >12 Tickern in `/decisions/live`
- **Datei:** `backend/interfaces/rest/routers/decisions.py:31`
- **Problem:** `_MAX_LIVE_TICKERS = 12`, keine Warnung im Response → Frontend weiss nicht dass Daten fehlen
- **Fix:** 400-Response wenn `len(tickers) > _MAX_LIVE_TICKERS`
- **Status:** ⬜ TODO

---

## INFO (nice-to-have)

- **I-1:** SimFin-API-Key im Klartext in `docs/ml-training.md:454` → rotieren falls echter Key
- **I-2:** `models/` nicht in Render `buildFilter` → neues Modell triggert keinen Auto-Deploy
- **I-3:** `model_path` im `return_predictor_latest.json` zeigt auf lokalen macOS-Pfad
- **I-4:** Kein `.dockerignore` → langsame Docker-Builds lokal
- **I-5:** ML-Modell-Dateien (`.joblib`) in Git ohne LFS
- **I-6:** Kein Feature-Name-Validierung beim Modell-Laden (trainierte Features ≠ aktuelle FEATURE_NAMES wäre silent wrong)
- **I-7:** `market_cap_chf: string | null` in `discovery.ts:27` — Backend liefert `Decimal` → JSON-Zahl, Frontend typisiert als `string`
- **I-8:** `portfolio.ts:46` kennt `mean_variance`-Methode nicht (Backend unterstützt sie)

---

## Implementierungs-Reihenfolge

### Runde 1 (dieser Branch — alle parallel implementiert):
- Alle K-1 bis K-13 ✓
- W-2, W-3, W-4, W-5, W-6 (Backend-Code-Fixes)
- W-7 (render.yaml cleanup)
- W-8, W-9 (Alembic/ORM)
- W-10 (Zinssätze aktualisieren)
- W-11, W-12 (ML edge cases)
- W-13 (release.yml)
- W-14, W-15 (API contract)

### Runde 2 (separater PR — W-1: globale Auth):
- 24+ Endpoints mit Auth versehen braucht sorgfältige Abwägung welche öffentlich bleiben

---

## Agent-Assignments (Parallel-Implementation)

| Agent | Dateien |
|-------|---------|
| A: CI/CD & Deploy | `.github/workflows/llm-smoke.yml`, `cd-render.yml`, `release.yml`, `scripts/backend-start.sh`, `render.yaml`, `backend/config.py` |
| B: Security Backend | `routers/chat.py`, `routers/alerts.py`, `notification_adapter.py`, `dependencies.py`, `rate_limiter.py`, `exception_handlers.py`, Ticker-Regex in stocks/decisions/decision_audit/macro routers |
| C: Performance Backend | `embedding_repository.py`, `news_repository.py`, `swiss_filing_repository.py`, `macro_service.py`, `ml_feature_service.py`, `routers/portfolio.py` (monte carlo), `app.py` (CORS middleware order) |
| D: Frontend Contract | `frontend/lib/api/discovery.ts`, `frontend/lib/api/backtest.ts`, `frontend/lib/api/decisions.ts` |
| E: Alembic/ORM | `backend/alembic/env.py`, neue Migration `0020_add_ml_feature_columns.py`, `backend/infrastructure/persistence/models/ml_features.py` |
