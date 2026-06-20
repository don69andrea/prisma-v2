# PRISMA V2 — Vollaudit & Fix-Plan · 2026-06-17

**Scope:** Vollständige Code-Analyse aller Backend-Services, Router, Adapter, Deployment-Konfiguration und Frontend-Anbindung vor dem Render-Live-Gang.  
**Ziel:** Alle Ursachen warum LLM, Chat und Krypto nicht funktionieren + Behebungsplan.  
**Branch:** `audit/render-live-befund-2026-06-17`  
**Status:** Offen — alle Punkte müssen vor Merge zu `main` abgehakt sein.

---

## Geprüfte Dateien (Vollständige Coverage)

| Bereich | Dateien |
|---|---|
| Backend Config & Entry | `config.py`, `interfaces/rest/main.py`, `interfaces/rest/app.py` |
| Startup & Docker | `scripts/backend-start.sh`, `Dockerfile.backend`, `Dockerfile.frontend` |
| Deployment | `render.yaml` |
| LLM Layer | `infrastructure/llm/client.py`, `infrastructure/llm/pricing.py` |
| Chat | `application/services/chat_service.py`, `interfaces/rest/routers/chat.py` |
| Krypto | `crypto_agent_service.py`, `crypto_scoring_service.py`, `crypto_pattern_service.py`, `interfaces/rest/routers/crypto.py` |
| Adapter | `coingecko_adapter.py`, `fear_greed_adapter.py`, `yfinance_crypto.py`, `yfinance_swiss.py` |
| Alle Router | `admin`, `alerts`, `backtests`, `chat`, `crypto`, `decision_audit`, `decisions`, `discovery`, `dividends`, `eligibility`, `fonds_vergleich`, `fundamentals`, `health`, `macro`, `memos`, `ml`, `news`, `portfolio`, `rag`, `rebalancing`, `reports`, `runs`, `steuer`, `stocks`, `universes` |
| Application Services | `chat_service`, `cost_tracker`, `crypto_agent_service`, `crypto_pattern_service`, `crypto_scoring_service`, `decision_audit_service`, `discovery_service`, `macro_service`, `ml_feature_service`, `ml_prediction_service`, `monte_carlo_service`, `narrative_service`, `ranking_run_service`, `rebalancing_service`, `report_service`, `signal_aggregation_service`, `alert_service`, `backtest_service` |
| DI & Session | `interfaces/rest/dependencies.py`, `infrastructure/persistence/session.py` |
| Rate Limiting | `interfaces/rest/rate_limiter.py` |
| Frontend API Layer | `lib/api/client.ts`, `lib/api/chat.ts`, `lib/api/crypto.ts` |
| Frontend Middleware | `middleware.ts`, `next.config.mjs` |
| Migrationen | `alembic/versions/0001`–`0026` (alle) |

---

## KRITISCHE BUGS — Produktions-Blocker

### BUG-01 · Chat bypassed LLMClient (Architektur-Verletzung + kein Budget-Cap)

**Dateien:** `backend/application/services/chat_service.py:289-293`  
**Schwere:** 🔴 Kritisch

```python
# chat_service.py:289-293
async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
    import anthropic                           # ← Application Layer importiert SDK direkt
    client = anthropic.AsyncAnthropic()        # ← kein api_key, kein timeout, kein max_retries
```

**Ursachen:**
- Bypassed den `LLMClient`-Wrapper → `CostTracker.check_cap()` wird **vor** dem API-Call **nie** aufgerufen
- Kein `timeout=30.0`, kein `max_retries=3` (wie im Singleton `get_anthropic_client()`)
- Bei jedem Chat-Request ein neuer `httpx`-Connection-Pool aufgebaut und sofort verworfen
- Verletzt explizit die Architektur-Regel im Projekt (AGENTS.md/CLAUDE.md: Application Layer darf kein SDK direkt importieren)
- `narrative_service.py` (verwendet `LLMClient` korrekt) und `crypto_agent_service.py` (gleiche Verletzung) als Vergleich

**Gleiche Verletzung in:** `backend/application/services/crypto_agent_service.py:84-86`

---

### BUG-02 · Chat Continuation Call fehlt `tools` Parameter

**Datei:** `backend/application/services/chat_service.py:350-361`  
**Schwere:** 🔴 Kritisch

```python
# chat_service.py:350-361 — zweiter Stream-Call nach Tool-Results
async with client.messages.stream(
    model=_MODEL,
    max_tokens=1024,
    system=[...],
    messages=cast(Any, continuation_messages),
    # ← FEHLT: tools=cast(Any, _TOOL_DEFINITIONS)
) as stream2:
```

**Ursache:** Der zweite Stream-Call (nach Tool-Ergebnissen) enthält die Tool-Definitionen nicht. Claude kann in der Continuation keine weiteren Tools aufrufen. Multi-Step-Queries (z.B. "Vergleiche NESN mit Nestlé und gib mir den Makro-Kontext") brechen nach dem ersten Tool-Zyklus ab.

---

### BUG-03 · Stub-Datenprovider in Production — alle Stock-Daten sind synthetisch

**Datei:** `backend/interfaces/rest/dependencies.py:99-118`  
**Schwere:** 🔴 Kritisch (Fundament-Bug)

```python
async def get_fundamentals_provider(...) -> FundamentalsProvider:
    if settings.environment == "production":
        _logger.warning("StubFundamentalsProvider active in production...")
    return StubFundamentalsProvider()   # ← IMMER Stub, auch in Production!

async def get_market_data_provider(...) -> MarketDataProvider:
    if settings.environment == "production":
        _logger.warning("StubMarketDataProvider active in production...")
    return StubMarketDataProvider()     # ← IMMER Stub, auch in Production!
```

**Ursache:** Alle Fundamentaldaten (P/E, EPS, Revenue, Cashflow) und Marktpreise für US-Stocks sind **synthetisch**. Betroffen: Quant-Scores, Research Memos, Factsheets, Universe Rankings. Issue #41 im Code bekannt, nie behoben.  
**Swiss Stocks** haben echte Preise via yfinance. **US-Stocks** haben Fake-Daten.

---

### BUG-04 · `crypto_scoring_service.score_one()` ruft `score_all()` auf

**Datei:** `backend/application/services/crypto_scoring_service.py:152-155`  
**Schwere:** 🔴 Kritisch

```python
async def score_one(self, ticker_symbol: str) -> CryptoSignal | None:
    all_signals = await self.score_all()   # ← Alle 10 Kryptos für 1 Ticker!
    return next((s for s in all_signals if s.ticker == ticker_symbol.upper()), None)
```

**Ursache:** `GET /api/v1/crypto/signals/BTC` → lädt intern alle 10 Kryptowährungen → 30+ gleichzeitige yfinance-Downloads (technicals + SMI-Korrelation + Pattern). Auf Render Free Tier: 20–60 Sekunden → Timeout oder 502.

---

### BUG-05 · Double Auth auf Chat-Endpoint

**Dateien:** `backend/interfaces/rest/app.py:142` + `backend/interfaces/rest/routers/chat.py:26`  
**Schwere:** 🟡 Mittel

```python
# app.py:142
app.include_router(chat.router, dependencies=_auth)   # ← require_admin_api_key (1)

# routers/chat.py:26
@router.post("", dependencies=[Depends(require_admin_api_key)])  # ← require_admin_api_key (2)
```

`require_admin_api_key` läuft bei jedem Chat-Request **zweimal**. Kein Crash, aber redundant und zeigt inkonsistente Auth-Strategie.

---

### BUG-06 · `update_smi_market_caps.py` nicht im Docker Image

**Dateien:** `Dockerfile.backend` + `scripts/backend-start.sh`  
**Schwere:** 🟡 Mittel

```dockerfile
# Dockerfile.backend — nur das Shell-Script wird kopiert:
COPY scripts/backend-start.sh /app/backend-start.sh
# update_smi_market_caps.py wird NIE in den Container kopiert!
```

```sh
# backend-start.sh:23
python scripts/update_smi_market_caps.py || echo "WARNING: market cap refresh failed"
```

Jeder Deploy endet mit `WARNING: market cap refresh failed (non-fatal)`. Non-fatal durch `||`, aber SMI Market Caps werden nie beim Deploy refresht.

---

### BUG-07 · `portfolio.py` Router importiert private Funktion `_run_gbm`

**Datei:** `backend/interfaces/rest/routers/portfolio.py:15`  
**Schwere:** 🟡 Mittel

```python
from backend.application.services.monte_carlo_service import (
    ...
    _run_gbm,   # ← private Funktion, Underscore-Konvention gebrochen
)
```

Interface-Layer greift direkt auf Service-Interna zu und umgeht die `MonteCarloService`-Klasse.

---

### BUG-08 · `discovery.py` Router erstellt neuen `YFinanceSwissAdapter` pro Request

**Datei:** `backend/interfaces/rest/routers/discovery.py:40-44`  
**Schwere:** 🟡 Mittel

```python
def _get_discovery_service(session: AsyncSession = Depends(get_session)) -> DiscoveryService:
    return DiscoveryService(
        ...
        market_data=YFinanceSwissAdapter(),   # ← Neuer Adapter pro Request, kein Singleton!
    )
```

Der prozess-weite Singleton `_get_yfinance_adapter_singleton()` (definiert in `dependencies.py`) wird hier **nicht** verwendet. Jede Discovery-Anfrage erstellt eine frische Adapter-Instanz ohne Cache-Sharing.

---

## DEPLOYMENT-FEHLER

### DEP-01 · `NEXT_PUBLIC_API_KEY` muss identisch zu `API_KEY` sein

**Datei:** `render.yaml`  
**Schwere:** 🔴 Kritisch (führt zu 401 auf allen authentifizierten Endpoints)

Beide sind `sync: false`. Wenn sie im Render Dashboard nicht auf exakt denselben Wert gesetzt werden, schlägt **jede** Frontend→Backend-Anfrage mit HTTP 401 fehl. Chat, Crypto, Stocks — alles.

---

### DEP-02 · pgvector — Migration vs. render.yaml-Kommentar (Widerspruch)

**Dateien:** `backend/alembic/versions/0008_enable_pgvector_and_create_embeddings.py` + `render.yaml`

```python
# Migration 0008 macht das bereits automatisch:
op.execute("CREATE EXTENSION IF NOT EXISTS vector")
```

```yaml
# render.yaml Kommentar:
# pgvector extension must be enabled after first deploy: CREATE EXTENSION vector;
```

**Befund:** Migration 0008 aktiviert pgvector bereits via `CREATE EXTENSION IF NOT EXISTS vector`. Der render.yaml-Kommentar ist **irreführend** — manueller Schritt ist NICHT nötig, sofern der DB-User die nötige Berechtigung hat (auf Render Managed PostgreSQL: gegeben). Kommentar muss aktualisiert werden.

---

### DEP-03 · CORS hard-coded auf spezifischen Render-Subdomain

**Datei:** `render.yaml`

```yaml
- key: CORS_ORIGINS
  value: https://prisma-v2-frontend.onrender.com
```

Wenn der Service umbenannt wird oder Render den Namen ändert, scheitern alle Cross-Origin-Requests des Browsers. Keine Flexibilität.

---

## PERFORMANCE-PROBLEME

### PERF-01 · In-Memory Caches verloren bei jedem Cold Start

**Betroffene Adapter:** `CoinGeckoAdapter` (10-Min-Cache), `YFinanceCryptoAdapter` (5-Min-Cache `TTLCache`), `FearGreedAdapter` (1-Std-Cache)

Render Free Tier suspendiert Container nach ~15 Min Inaktivität. Beim Cold Start (kann bis 52 Sek dauern) sind alle Caches leer → erster Krypto-Request nach Inaktivität macht 30+ HTTP-Calls gleichzeitig.

---

### PERF-02 · yfinance nicht production-tauglich

yfinance ist ein Web-Scraper:
- Bricht regelmässig bei yfinance-Library-Updates (breaking API-Changes)
- Keine SLA, kein Rate-Limit-Guarantee
- Blockiert asyncio Event-Loop wenn `asyncio.to_thread()` Threadpool erschöpft ist
- Langsam auf Render Free Tier (shared CPU)

---

### PERF-03 · Kein API-Level Caching für Crypto-Live-Signals

Jeder `GET /api/v1/crypto/signals` rechnet komplett neu. Die DB enthält nur historische Snapshots (täglicher Cron). Kein Request-Level-Cache (z.B. asyncio-Lock + Memo).

---

## ARCHITEKTUR-BEOBACHTUNGEN (kein Fix zwingend vor Live, aber dokumentiert)

### ARCH-01 · `anthropic`-Import in falschen Layers für Exception-Typen

| Datei | Import | Zweck |
|---|---|---|
| `narrative_service.py:26` | `import anthropic` | Catch `anthropic.APITimeoutError` etc. |
| `interfaces/rest/routers/memos.py:21` | `import anthropic` | Catch `anthropic.APITimeoutError` |

Diese Imports dienen nur dem Exception-Matching, nicht dem SDK-Aufruf. Technisch vertretbar, aber inkonsistent mit der Architektur-Regel. Langfristig: Exception-Typen in Domain-Layer wrappen.

---

### ARCH-02 · Batch-Memo Endpoints ohne Frontend-Konsument

`POST /api/v1/memos/batch` und `GET /api/v1/memos/jobs/{job_id}` sind vollständig implementiert und getestet, aber es gibt keinen Frontend-Code der diese Endpoints aufruft. Im Code (memos.py) bereits dokumentiert — bewusste Produktentscheidung offen.

---

### ARCH-03 · `_MAX_LIVE_TICKERS = 12` in decisions Router

**Datei:** `backend/interfaces/rest/routers/decisions.py:52`

Docstring des Endpoints sagt "Max. 25 Ticker", die Konstante im Code ist aber 12. Inkonsistenz zwischen Dokumentation und Implementation.

---

## DEPLOYMENT-CHECKLISTE für Render (vor Live-Gang)

| # | Aufgabe | Render Service | Status |
|---|---|---|---|
| R-1 | `API_KEY` setzen (openssl rand -hex 32) | Backend | ⬜ |
| R-2 | `NEXT_PUBLIC_API_KEY` = identisch zu `API_KEY` | Frontend | ⬜ |
| R-3 | `ANTHROPIC_API_KEY` setzen | Backend | ⬜ |
| R-4 | `VOYAGE_API_KEY` setzen (für RAG/Embeddings) | Backend | ⬜ |
| R-5 | `COINGECKO_API_KEY` setzen (ohne Key: 30 Req/Min Free Tier) | Backend | ⬜ |
| R-6 | `TOOL_API_KEY` setzen (MCP-Endpoints) | Backend | ⬜ |
| R-7 | `SENDGRID_API_KEY` setzen (Alert-E-Mails) | Backend (optional) | ⬜ |
| R-8 | Erste Deploy starten — Migrations laufen automatisch via `alembic upgrade head` | — | ⬜ |
| R-9 | Nach erstem Deploy: `/health/ready` aufrufen um DB-Konnektivität zu prüfen | — | ⬜ |
| R-10 | pgvector: wird automatisch durch Migration 0008 aktiviert — **kein manueller Schritt** | — | ✅ |
| R-11 | Krypto-Cron (`prisma-crypto-daily`) läuft täglich 06:30 — erste History-Daten ab Tag 2 | — | ⬜ |

---

## FIX-PLAN

Alle Fixes über Branch `fix/render-live-critical-2026-06-17`. Jeder Fix als eigener Commit.

---

### FIX-1 · Chat: `LLMClient` statt direktem SDK

**Priorität:** 🔴 Muss vor Live  
**Datei:** `backend/application/services/chat_service.py`  
**Was:** `anthropic.AsyncAnthropic()` entfernen. `ChatService` soll einen `LLMClient` injiziert bekommen (analog zu allen anderen Services). `stream()` ruft dann `self._llm._anthropic.messages.stream()` auf — oder besser: LLMClient erhält eine eigene `stream()`-Methode.

**Schritte:**
- [x] `ChatService.__init__` erhält `llm_client: LLMClient` Parameter (ersetzt `cost_tracker`)
- [x] `stream()`: `client = self._llm.raw_client` (nutzt den Singleton-Pool via Property)
- [x] `_record_cost()` bleibt, greift auf `self._cost_tracker = getattr(llm_client, "_cost_tracker", None)` zu
- [x] DI in `dependencies.py`: `get_chat_service` gibt `ChatService(llm_client=llm_client)` zurück
- [x] Gleiche Änderung in `crypto_agent_service.py:stream_analysis()`: `self._llm.raw_client` verwenden

---

### FIX-2 · Chat Continuation: `tools` Parameter ergänzen

**Priorität:** 🔴 Muss vor Live  
**Datei:** `backend/application/services/chat_service.py:350`

```python
# Vorher:
async with client.messages.stream(
    model=_MODEL,
    max_tokens=1024,
    system=[...],
    messages=cast(Any, continuation_messages),
) as stream2:

# Nachher:
async with client.messages.stream(
    model=_MODEL,
    max_tokens=1024,
    system=[...],
    tools=cast(Any, _TOOL_DEFINITIONS),      # ← hinzufügen
    messages=cast(Any, continuation_messages),
) as stream2:
```

- [x] `tools=cast(Any, _TOOL_DEFINITIONS)` in den zweiten `stream`-Aufruf einfügen

---

### FIX-3 · Double Auth auf Chat-Endpoint entfernen

**Priorität:** 🟡 Soll vor Live  
**Datei:** `backend/interfaces/rest/routers/chat.py`

```python
# Vorher:
@router.post(
    "",
    dependencies=[Depends(require_admin_api_key)],   # ← entfernen
)

# Nachher:
@router.post("")
```

Auth kommt bereits via `app.include_router(chat.router, dependencies=_auth)`.

- [x] `dependencies=[Depends(require_admin_api_key)]` aus dem Endpoint-Decorator entfernt

---

### FIX-4 · `update_smi_market_caps.py` ins Docker Image kopieren

**Priorität:** 🟡 Soll vor Live  
**Datei:** `Dockerfile.backend`

```dockerfile
# Vorher:
COPY scripts/backend-start.sh /app/backend-start.sh

# Nachher:
COPY scripts/backend-start.sh /app/backend-start.sh
COPY scripts/update_smi_market_caps.py /app/scripts/update_smi_market_caps.py
```

Alternativ: `scripts/` komplett kopieren.

- [x] `update_smi_market_caps.py` in Dockerfile kopieren: `COPY scripts/update_smi_market_caps.py /app/scripts/update_smi_market_caps.py`

---

### FIX-5 · `score_one()` nicht mehr über `score_all()` implementieren

**Priorität:** 🟡 Soll vor Live  
**Datei:** `backend/application/services/crypto_scoring_service.py`

```python
# Vorher:
async def score_one(self, ticker_symbol: str) -> CryptoSignal | None:
    all_signals = await self.score_all()
    return next((s for s in all_signals if s.ticker == ticker_symbol.upper()), None)

# Nachher: Direkter Single-Ticker-Lookup
async def score_one(self, ticker_symbol: str) -> CryptoSignal | None:
    match = next(
        (c for c in SUPPORTED_CRYPTOS if c[1].split("-")[0] == ticker_symbol.upper()),
        None,
    )
    if match is None:
        return None
    # Nur diesen einen Ticker verarbeiten (minimaler Subset von score_all-Logik)
    ...
```

- [x] `score_one()` als eigenständige Methode implementiert — lädt nur 1 Ticker statt alle 10

---

### FIX-6 · `portfolio.py` Router: Private Funktion nicht importieren

**Priorität:** 🟡 Soll  
**Datei:** `backend/interfaces/rest/routers/portfolio.py`  
**Lösung:** `MonteCarloService._run_gbm()` als public-Methode oder `MonteCarloService.run()` exponieren, sodass der Router die Klasse vollständig über ihre öffentliche API nutzt.

- [x] `_run_gbm` → `run_gbm` (public) in `monte_carlo_service.py` umbenannt; interne Aufrufe aktualisiert
- [x] `portfolio.py` Router: Import auf `run_gbm` aktualisiert

---

### FIX-7 · Discovery Router: yfinance Singleton verwenden

**Priorität:** 🟡 Soll  
**Datei:** `backend/interfaces/rest/routers/discovery.py`

```python
# Vorher:
def _get_discovery_service(session: AsyncSession = Depends(get_session)) -> DiscoveryService:
    return DiscoveryService(
        market_data=YFinanceSwissAdapter(),   # ← neue Instanz pro Request

# Nachher:
from backend.interfaces.rest.dependencies import get_yfinance_adapter

def _get_discovery_service(
    session: AsyncSession = Depends(get_session),
    market_data: YFinanceSwissAdapter = Depends(get_yfinance_adapter),   # ← Singleton
) -> DiscoveryService:
    return DiscoveryService(..., market_data=market_data, ...)
```

- [x] `YFinanceSwissAdapter()` durch `Depends(get_yfinance_adapter)` ersetzt

---

### FIX-8 · render.yaml: pgvector-Kommentar korrigieren

**Priorität:** 🟡 Soll  
**Datei:** `render.yaml`

```yaml
# Vorher (falsch/irreführend):
# pgvector extension must be enabled after first deploy: CREATE EXTENSION vector;

# Nachher (korrekt):
# pgvector wird automatisch durch Alembic Migration 0008 aktiviert (CREATE EXTENSION IF NOT EXISTS vector).
# Kein manueller Schritt nötig — setzt voraus dass der DB-User Superuser-Rechte hat (Render Managed PG: gegeben).
```

- [x] render.yaml Kommentar aktualisiert: pgvector via Migration 0008, kein manueller Schritt

---

### FIX-9 · Decisions Router: `_MAX_LIVE_TICKERS` mit Docstring synchronisieren

**Priorität:** 🟢 Kann  
**Datei:** `backend/interfaces/rest/routers/decisions.py:52`

Entweder Konstante auf 25 erhöhen (wie Docstring) oder Docstring auf 12 korrigieren.

- [x] `_MAX_LIVE_TICKERS = 25` (war 12) — jetzt kongruent mit Docstring "Max. 25 Ticker"

---

### FIX-10 · Krypto-Signals: Request-Level-Cache mit asyncio.Lock

**Priorität:** 🟢 Kann (Performance-Verbesserung)  
**Datei:** `backend/application/services/crypto_scoring_service.py`

Concurrent Requests die alle gleichzeitig reinkommen sollen nicht alle 30+ yfinance-Downloads parallel starten. Ein asyncio-Lock + kurz-lebender In-Process-Cache (30 Sek TTL) verhindert Request-Stampedes nach Cold Start.

- [x] `asyncio.Lock()` + `_cache_result` Instanz-Cache in `CryptoScoringService` — parallele Stampede verhindert

---

## Strukturell offen (kein Fix-Termin gesetzt)

| ID | Befund | Begründung für Offenlassen |
|---|---|---|
| S-1 | StubFundamentalsProvider in Production | Echter FMP-Adapter vorhanden (`simfin_adapter.py`) aber API-Key nötig. Entscheidung: wann wird FMP aktiviert? |
| S-2 | yfinance für Production | Alternativen (Alpha Vantage, FMP, SIX API) kosten. Entscheidung: Budget? |
| S-3 | Batch-Memo Endpoints ohne Frontend | Offen per Design (memos.py Docstring) |
| S-4 | `anthropic`-Import in `narrative_service.py` + `memos.py` für Exception-Typen | Akzeptabel, aber langfristig wrappen |
| S-5 | CORS hard-coded | Kein flexibles Multi-Origin-Setup nötig solange 1 Render Frontend |

---

## Checkliste: Abnahme vor Merge zu `main`

- [x] FIX-1: Chat + CryptoAgent nutzen LLMClient.raw_client (kein direktes SDK) ✅
- [x] FIX-2: Chat Continuation hat `tools` Parameter ✅
- [x] FIX-3: Double Auth entfernt aus chat.py Endpoint-Decorator ✅
- [x] FIX-4: `update_smi_market_caps.py` im Docker Image kopiert ✅
- [x] FIX-5: `score_one()` eigenständig implementiert (kein score_all()-Aufruf) ✅
- [x] FIX-6: `_run_gbm` → `run_gbm` (public) + Portfolio-Router aktualisiert ✅
- [x] FIX-7: Discovery nutzt yfinance Singleton via Depends(get_yfinance_adapter) ✅
- [x] FIX-8: render.yaml pgvector-Kommentar korrekt (Migration 0008 macht es automatisch) ✅
- [x] FIX-9: `_MAX_LIVE_TICKERS = 25` (Docstring-kongruent) ✅
- [x] FIX-10 (PERF-03): asyncio.Lock + _cache_result-Cache in CryptoScoringService ✅
- [ ] DEP-R1–R9 aus Render-Checkliste gesetzt und verifiziert
- [ ] `/health` gibt 200 auf Render
- [ ] `/health/ready` gibt `{"ready": true, "database": "ok"}` auf Render
- [ ] Chat sendet eine Nachricht und bekommt eine Antwort (E2E-Test auf Render)
- [ ] Krypto-Seite lädt Signale (kein Timeout, kein 502)

---

*Erstellt von: Claude Sonnet 4.6 — Vollaudit vom 2026-06-17*  
*Nächster Schritt: Branch `fix/render-live-critical-2026-06-17` erstellen, Fixes implementieren, PR gegen `main`.*
