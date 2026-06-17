# PRISMA V2 — Backend Deep Audit
**Datum:** 2026-06-17  
**Scope:** Backend-Architektur, Deployment-Konfiguration, Frontend-Anbindung  
**Status:** Fix-Plan aktiv

---

## Inhaltsverzeichnis
- [Kritische Bugs](#kritische-bugs-produktions-blocker)
- [Mittlere Probleme](#mittlere-probleme)
- [Strukturelle Fundament-Probleme](#strukturelle-fundament-probleme)
- [Deployment-Checkliste](#deployment-checkliste)
- [Fix-Plan](#fix-plan)

---

## Kritische Bugs (Produktions-Blocker)

### BUG 1 — Chat: Application Layer importiert Anthropic direkt, bypassed LLMClient
**Datei:** `backend/application/services/chat_service.py:289-293`

```python
import anthropic  # VERBOTEN laut AGENTS.md/CLAUDE.md
client = anthropic.AsyncAnthropic()  # Kein api_key, kein timeout, kein max_retries
```

- Bypassed den `LLMClient`-Wrapper → kein `check_cap()` VOR dem API-Call
- Kein `timeout=30.0`, kein `max_retries=3` (wie in `get_anthropic_client()` Singleton)
- Bei jedem Chat-Request ein neuer HTTP-Connection-Pool wird aufgebaut und sofort weggeworfen
- Verletzt explizit die Architektur-Regel: Application Layer darf kein SDK direkt importieren
- Gleiche Verletzung in `crypto_agent_service.py:86` (für Streaming)

---

### BUG 2 — Chat: Continuation Call nach Tool-Use fehlt `tools`-Parameter
**Datei:** `backend/application/services/chat_service.py:350-361`

```python
async with client.messages.stream(
    model=_MODEL,
    max_tokens=1024,
    system=[...],
    messages=cast(Any, continuation_messages),
    # FEHLT: tools=cast(Any, _TOOL_DEFINITIONS)
) as stream2:
```

Der zweite Stream-Call (nach Tool-Ergebnissen) sendet die Tool-Definitionen **nicht** mit. Claude kann in der Continuation keine weiteren Tools aufrufen. Alle Multi-Step-Queries (z.B. „Vergleiche NESN mit Nestlé und gib mir den Makro-Kontext") brechen nach dem ersten Tool-Zyklus ab.

---

### BUG 3 — Stub-Datenprovider in Production (Fundament-Bug)
**Datei:** `backend/interfaces/rest/dependencies.py:99-118`

```python
async def get_fundamentals_provider(...) -> FundamentalsProvider:
    if settings.environment == "production":
        _logger.warning("StubFundamentalsProvider active in production...")
    return StubFundamentalsProvider()  # IMMER STUB, auch in Production!

async def get_market_data_provider(...) -> MarketDataProvider:
    if settings.environment == "production":
        _logger.warning("StubMarketDataProvider active in production...")
    return StubMarketDataProvider()  # IMMER STUB, auch in Production!
```

Das ist der fundamentalste Bug. Alle Stock-Fundamentaldaten (P/E, EPS, Revenue, Gewinn), alle Marktpreise für US-Stocks — alles synthetisch/fake in Production. Quant-Scores für US-Aktien basieren auf erfundenen Werten. Issue #41 ist im Code anerkannt aber nie behoben worden.

---

### BUG 4 — Crypto: `score_one()` ruft `score_all()` auf
**Datei:** `backend/application/services/crypto_scoring_service.py:152-155`

```python
async def score_one(self, ticker_symbol: str) -> CryptoSignal | None:
    all_signals = await self.score_all()  # Alle 10 Kryptos für 1 Ticker!
```

`GET /api/v1/crypto/signals/{ticker}` lädt intern alle 10 Kryptowährungen: 30+ gleichzeitige yfinance-Downloads. Auf Render Free Tier dauert das 20–60 Sekunden → Timeout oder 502.

---

### BUG 5 — `update_smi_market_caps.py` nicht im Docker Image
**Dateien:** `Dockerfile.backend` + `scripts/backend-start.sh`

```dockerfile
COPY scripts/backend-start.sh /app/backend-start.sh
# update_smi_market_caps.py wird NIE kopiert!
```

Aber in `backend-start.sh`:
```bash
python scripts/update_smi_market_caps.py || echo "WARNING: market cap refresh failed"
```

Das Script existiert nicht im Container. Non-fatal (`||`), aber jeder Deploy endet mit einer WARNING in Render's Logs.

---

### BUG 6 — Double Auth auf Chat-Endpoint
**Dateien:** `backend/interfaces/rest/app.py:142` + `backend/interfaces/rest/routers/chat.py:26`

`require_admin_api_key` wird pro Chat-Request zweimal ausgeführt: einmal durch `app.include_router(chat.router, dependencies=_auth)` und einmal durch den Decorator `dependencies=[Depends(require_admin_api_key)]` am Endpoint selbst. Kein Crash, aber ein Zeichen von inkonsistenter Auth-Strategie.

---

## Mittlere Probleme

### M1 — pgvector Extension muss manuell aktiviert werden
**Datei:** `render.yaml:5-6`

```yaml
# pgvector extension must be enabled after first deploy: CREATE EXTENSION vector;
```

Wenn das nach dem ersten Render-Deploy nicht manuell gemacht wird, crashen alle RAG-, Embedding- und News-Retrieval-Endpoints.

---

### M2 — yfinance ist nicht production-tauglich

yfinance ist ein Web-Scraper, kein offizielles API:
- Bricht regelmässig bei yfinance-Updates
- Keine SLA und keine Rate-Limit-Guarantees
- Langsam auf Render Free Tier (blocking I/O in Thread-Pool)
- Gibt gelegentlich leere DataFrames zurück → Krypto-Scoring liefert keine Daten

---

### M3 — CORS Hard-coded auf eine spezifische Render-Subdomain
**Datei:** `render.yaml`

```yaml
- key: CORS_ORIGINS
  value: https://prisma-v2-frontend.onrender.com
```

Wenn der Service umbenannt wird oder die Render-URL sich ändert, blockiert der Browser alle Frontend→Backend-Requests.

---

### M4 — In-Memory Caches gehen bei jedem Cold Start verloren

CoinGecko-Cache (10 Min) und yfinance-Cache (5 Min) sind instanz-gebunden. Render Free Tier suspendiert Container nach Inaktivität. Bei Cold Start: alle Caches leer → erster Krypto-Request 30–60 Sekunden.

---

### M5 — Kein API-Key-Check vor Chat-Streaming

`ChatService.stream()` liest den `ANTHROPIC_API_KEY` implizit via Anthropic-SDK aus der Umgebung. Wenn der Key falsch ist, kommt erst **nach** dem Streaming-Start eine Exception — der Frontend-User sieht „Interner Fehler" mitten im Stream.

---

## Strukturelle Fundament-Probleme

### F1 — Architektur-Verletzung: Application Layer importiert SDKs direkt

Zwei Dateien verstossen gegen die dokumentierte Hexagonal-Architecture-Regel (AGENTS.md/CLAUDE.md):
- `chat_service.py`: `import anthropic` + `anthropic.AsyncAnthropic()`
- `crypto_agent_service.py`: `import anthropic` + `anthropic.AsyncAnthropic()`

Alle anderen Services (NarrativeService, UniverseSuggestionService, etc.) halten die Regel korrekt ein. Chat und CryptoAgent wurden offensichtlich unter Zeitdruck nachgebaut.

---

### F2 — Kein Real-Time Caching-Layer für Crypto

Krypto-Signale werden nicht zwischen User-Requests gecacht. Jeder `GET /api/v1/crypto/signals` rechnet komplett neu (yfinance + CoinGecko + Fear&Greed). Die DB enthält nur historische Snapshots vom täglichen Cron — nicht die Live-Daten die beim User-Request berechnet werden.

---

### F3 — US-Stocks haben null echte Daten

Alles was `get_fundamentals_provider()` oder `get_market_data_provider()` braucht (Rankings, Factsheets, Memos für US-Stocks) läuft auf synthetischen Daten. Swiss Stocks über yfinance haben echte Preise, aber US-Stocks nicht.

---

### F4 — ML-Modelle im Docker Image aber kein Deployment-Smoke-Test

`models/` enthält `.joblib` Dateien (LightGBM, XGBoost). Das Dockerfile kopiert `models/`. Aber es gibt keinen Test beim Start ob die Modelle ladbar sind. Wenn ein Modell korrupt ist, crasht nur der ML-Endpoint — nicht beim Startup.

---

## Deployment-Checkliste

| Variable | Render Service | Status |
|----------|---------------|--------|
| `API_KEY` | Backend | `sync: false` → manuell setzen |
| `NEXT_PUBLIC_API_KEY` | Frontend | `sync: false` → identischer Wert wie `API_KEY` |
| `ANTHROPIC_API_KEY` | Backend | `sync: false` → manuell setzen |
| `VOYAGE_API_KEY` | Backend | `sync: false` → für RAG |
| `COINGECKO_API_KEY` | Backend | `sync: false` → ohne Key: Free Tier (5 Req/Min) |
| pgvector Extension | DB | manuell: `CREATE EXTENSION vector;` nach erstem Deploy |

---

## Fix-Plan

### Priorität 1 — Render-Live-Gang (ohne diese läuft gar nichts)

- [ ] **P1.1** Alle `sync: false` Env-Vars im Render Dashboard setzen (`NEXT_PUBLIC_API_KEY == API_KEY`)
- [ ] **P1.2** pgvector Extension manuell aktivieren nach DB-Erstellung (`CREATE EXTENSION vector;`)
- [ ] **P1.3** `scripts/update_smi_market_caps.py` ins Dockerfile kopieren **oder** Zeile aus `backend-start.sh` entfernen

### Priorität 2 — Chat reparieren

- [ ] **P2.1** `chat_service.py`: `anthropic.AsyncAnthropic()` durch injizierten `LLMClient` ersetzen (wie alle anderen Services) — behebt BUG 1 + F1 teilweise
- [ ] **P2.2** `chat_service.py`: Zweiten Stream-Call mit `tools=cast(Any, _TOOL_DEFINITIONS)` ergänzen — behebt BUG 2
- [ ] **P2.3** `crypto_agent_service.py`: gleiche LLMClient-Injektion wie P2.1 — behebt F1 vollständig
- [ ] **P2.4** Double-Auth auf Chat-Endpoint bereinigen (einen der beiden `require_admin_api_key`-Calls entfernen) — behebt BUG 6

### Priorität 3 — Krypto reparieren

- [ ] **P3.1** `score_one()`: Direkter Single-Ticker-Lookup implementieren, nicht `score_all()` aufrufen — behebt BUG 4
- [ ] **P3.2** Asyncio-Lock oder DB-basiertes Caching für Live-Signale einführen — behebt F2

### Priorität 4 — Fundament

- [ ] **P4.1** Echten `FundamentalsProvider` (FMP-Adapter ist vorhanden) in Production aktivieren — `StubFundamentalsProvider` aus Production entfernen — behebt BUG 3 + F3
- [ ] **P4.2** yfinance-Abhängigkeit durch stabileres API ersetzen oder Circuit-Breaker mit Fallback auf DB-Snapshot einführen — behebt M2
- [ ] **P4.3** CORS-Origin aus `render.yaml` in eine Env-Var auslagern — behebt M3
- [ ] **P4.4** ML-Modell-Smoke-Test beim Startup einführen — behebt F4

---

## Fazit

Das Fundament (Hexagonal-Architecture, DI-Chain, Alembic-Migrationen, Docker-Setup) ist solide. Die beiden grossen Schmerzen sind:

1. **Chat bypassed den LLMClient** → fragil, kein Cap-Check, kein Timeout
2. **Komplettes Fehlen echter Fundamentaldaten in Production** → alle US-Stock-Scores sind synthetisch

Das Krypto-Modul hat echte Daten (yfinance/CoinGecko), ist aber Performance-mässig unfertig für Production. Die meisten Probleme sind behebbar ohne Fundament-Umbau — ausser dem Stub-Provider-Problem, das echte externe API-Anbindung braucht.
