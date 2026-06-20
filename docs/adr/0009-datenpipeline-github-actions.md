# ADR 0009: Datenpipeline-Migration — Render Docker-Cron-Jobs → GitHub Actions

- **Status**: Accepted
- **Datum**: 2026-06-19
- **Autor**: Andrea Petretta
- **Kontext**: Render Free-Tier Deploy, Datenpipeline SMI/Krypto/News
- **Supersedes**: Render Blueprint Cron-Job-Konfiguration (render.yaml, 4 Docker-basierte Cron-Services)

---

## Befund

### Problem 1: Yahoo Finance blockt Render-IPs (Hauptursache)

Alle datenladenden Scripts nutzen `yfinance` für SMI-20-Kurse, Krypto-Historien und Feature-Berechnungen. Yahoo Finance hat die IP-Ranges von Render.com auf eine Blockliste gesetzt:

```
HTTP Error 401: Invalid Crumb
Too Many Requests (429)
YFRateLimitError
```

Das betrifft *alle* Requests von Render-Servern — unabhängig von Request-Frequenz, User-Agent oder Session-Management. Lokale Ausführung und GitHub Actions Runner-IPs sind **nicht** betroffen.

**Konkrete Folge**: `stock_daily_snapshot.py`, `crypto_daily_snapshot.py` und `ml_feature_snapshot.py` konnten auf Render nie Marktdaten laden. Die DB-Tabellen `stock_signal_records`, `crypto_signals` und `ml_feature_vectors` blieben leer → `/api/v1/decisions` lieferte keine Signale.

### Problem 2: Render Docker-Cron-Jobs nicht auf Free-Tier unterstützt

`render.yaml` enthielt 4 Cron-Job-Definitionen mit `type: worker` + `buildFilter`. Render Free-Tier unterstützt keine Docker-basierten Cron-Services. Jeder Blueprint-Sync schlug fehl:

```
Error: received response code 400: new paid services not allowed
```

Das war seit dem ersten Deployment so — Blueprint-Sync war permanent rot, Cron-Jobs starteten nie.

### Problem 3: API_KEY-Validierung verhindert Script-Start

`backend/config.py` erzwingt `API_KEY` als Pflichtfeld wenn `ENVIRONMENT=production`:

```python
@model_validator(mode="after")
def _api_key_required_in_production(self) -> "Settings":
    if self.environment == "production":
        if not self.api_key:
            raise ValueError("API_KEY muss in der Production-Umgebung gesetzt sein")
```

Der erste Workflow-Run (PR #280, Trigger `workflow_dispatch`) setzte `ENVIRONMENT: production` aber nicht `API_KEY` → alle Seed-Scripts crashten mit `ValidationError` beim allerersten Import, bevor eine DB-Verbindung hergestellt wurde. Fehler in GitHub Actions:

```
pydantic_core.ValidationError: 1 validation error for Settings
  Value error, API_KEY muss in der Production-Umgebung gesetzt sein
```

### Problem 4: OOM-Restarts auf Render Free-Tier (512 MB RAM)

SQLAlchemy Connection Pool war auf `pool_size=10, max_overflow=20` konfiguriert. asyncpg-Connections belegen ~10 MB RAM each → 30 Connections × 10 MB = ~300 MB, plus FastAPI-Overhead → sporadische OOM-Kills auf dem 512 MB Free-Tier.

---

## Entscheidung

**GitHub Actions als vollständiger Cron-Ersatz für alle Datenpipeline-Jobs.**

Begründung:
- GitHub Actions Runner-IPs sind bei Yahoo Finance **nicht** geblockt
- 2 000 Free-Minuten pro Monat sind für täglich ~10 Minuten Build+Run ausreichend
- `workflow_dispatch` ermöglicht manuelles Triggern ohne Render-Paid-Plan
- Render Free-Tier bleibt ausschliesslich für die Web-API zuständig (kein Datenladen)

---

## Umsetzung

### 1. render.yaml — Alle Cron-Definitionen entfernt

**Vorher** (4 Docker-Cron-Services, nicht funktionsfähig auf Free-Tier):
```yaml
services:
  - type: worker
    name: prisma-news-ingestion
    buildFilter: { paths: ["backend/**"] }
    # ...
  - type: worker
    name: prisma-crypto-daily
    # ...
  - type: worker
    name: prisma-smi-market-caps
    # ...
  - type: worker
    name: prisma-stock-daily
    # ...
```

**Nachher**:
```yaml
# Cron Jobs laufen via GitHub Actions (.github/workflows/daily-data-seed.yml).
# Render Docker-Cron-Jobs sind auf dem Free-Tier nicht unterstützt und
# Yahoo Finance blockt Render-IPs — GitHub Actions IPs werden nicht geblockt.
```

### 2. `.github/workflows/daily-data-seed.yml` — Neuer 7-Job-Workflow

Datei: `.github/workflows/daily-data-seed.yml`

**Schedule** (Mo–Fr, UTC):

| Uhrzeit | Job |
|---------|-----|
| 04:00 | SMI Market Caps |
| 05:00 | ML Features (MLFeatureORM für alle 20 SMI-Ticker) |
| 06:00 | News Ingestion (RAG-Index) |
| 06:30 | Krypto Daily (10 Assets inkl. Fear & Greed) |
| 07:00 | Stock Daily — SMI-20 Signale seeden |
| 08:00 | Alert Engine — Nutzer-Alerts aus frischen Signalen |
| 22:00 Fr | Weekly ML Retrain (LightGBM, Artefakt-Upload) |

**`workflow_dispatch`** mit Job-Auswahl: `stock-daily`, `crypto-daily`, `news-ingestion`, `smi-market-caps`, `ml-features`, `alerts`, `ml-retrain`, `all-daily`

**Kritische env-Variablen** (alle als GitHub Secrets gesetzt):
```yaml
env:
  DATABASE_URL: ${{ secrets.RENDER_DATABASE_URL }}
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  VOYAGE_API_KEY: ${{ secrets.VOYAGE_API_KEY }}
  JWT_SECRET: ${{ secrets.JWT_SECRET }}
  API_KEY: ${{ secrets.API_KEY }}           # Pflichtfeld in production-Settings
  TWELVE_DATA_API_KEY: ${{ secrets.TWELVE_DATA_API_KEY }}
```

### 3. `backend/infrastructure/persistence/session.py` — Pool-Grösse reduziert

**Vorher**: `pool_size=10, max_overflow=20` → max. 30 Connections × ~10 MB = ~300 MB

**Nachher** (production):
```python
pool_size = 2      # max 5 Connections gesamt (~50 MB für Pool)
max_overflow = 3
```

### 4. Drei neue Datenquellen ohne Render-IP-Block

Um yfinance-Abhängigkeiten auf dem Render-Server selbst zu reduzieren, wurden drei neue Adapter eingeführt (PR #281):

| Adapter | Datei | Quelle | Verwendung |
|---------|-------|--------|------------|
| ECB FX | `ecb_fx_adapter.py` | ECB Statistical Data Warehouse | CHF/EUR, CHF/USD, CHF/GBP — kein API-Key |
| FRED | `fred_adapter.py` | St. Louis Fed CSV-Endpunkt | Schweizer CPI YoY — kein API-Key |
| Twelve Data | `twelve_data_adapter.py` | twelvedata.com REST-API | SMI-20 Live-Kurse via SIX Exchange — 800 Calls/Tag kostenlos |

`macro_service.py` und `ml_feature_service.py` rufen CHF/EUR jetzt vom ECB-Adapter ab statt via `yf.download("EURCHF=X")`.

### 5. Lokales DB-Seeding als Überbrückung

Da GitHub Actions erst nach dem Merge laufen, wurde die initiale Befüllung lokal durchgeführt:

```bash
# Extern auf Render-DB zeigen
export DATABASE_URL="postgresql+asyncpg://..."

# Lokal ausführen (yfinance funktioniert von lokalen IPs)
python backend/scripts/stock_daily_snapshot.py
python backend/scripts/crypto_daily_snapshot.py
```

---

## Architekturprinzip nach der Migration

```
┌─────────────────────────────────────────────────────┐
│  GitHub Actions (täglich Mo–Fr)                     │
│  Runner-IP nicht geblockt → yfinance funktioniert   │
│                                                     │
│  stock_daily_snapshot.py  →  PostgreSQL (Render)    │
│  crypto_daily_snapshot.py →  PostgreSQL (Render)    │
│  news_ingestion.py        →  pgvector (Render)      │
│  ml_feature_snapshot.py   →  PostgreSQL (Render)    │
└───────────────────────────┬─────────────────────────┘
                            │ Daten bereits in DB
                            ▼
┌─────────────────────────────────────────────────────┐
│  Render Free-Tier (API-Server)                      │
│  Kein yfinance-Aufruf für Kerndaten nötig           │
│                                                     │
│  GET /api/v1/decisions  → liest StockSignalRecord   │
│  GET /api/v1/macro      → ECB + SNB (nicht blocked) │
│  GET /api/v1/crypto     → liest CryptoSignal        │
└─────────────────────────────────────────────────────┘
```

---

## Konsequenzen

**Positiv:**
- Blueprint-Sync ist wieder grün (keine ungültigen Cron-Definitionen in render.yaml)
- Datenpipeline läuft zuverlässig auf Infrastruktur, auf der yfinance nicht geblockt ist
- OOM-Restarts eliminiert durch kleineren Connection-Pool
- Manuelles Triggern via `workflow_dispatch` ohne Render-Paid-Plan möglich
- Weekly ML-Retrain automatisiert (freitags 22:00 UTC)

**Negativ / Einschränkungen:**
- Daten sind max. ~1 Tag alt (kein Intraday-Update)
- Fällt GitHub aus: kein automatisches Seeding bis zum nächsten Tag
- `TWELVE_DATA_API_KEY` muss manuell als GitHub Secret und Render-Env-Var eingetragen werden, damit Live-Kurse via Twelve Data funktionieren

**Offen:**
- yfinance bleibt in `yfinance_swiss.py`, `yfinance_crypto.py` und `monte_carlo_service.py` als Infrastruktur-Adapter. Diese werden **nur von GitHub Actions** aufgerufen (Seeding) oder haben try/except-Fallbacks (Monte Carlo, Cointelligence). Eine vollständige Migration auf Twelve Data ist möglich, aber nicht kurzfristig nötig.

---

## Betroffene PRs

| PR | Inhalt |
|----|--------|
| [#280](https://github.com/don69andrea/prisma-v2/pull/280) | render.yaml Cron-Entfernung, daily-data-seed.yml, Pool-Fix, ml_is_fallback-Fix |
| [#281](https://github.com/don69andrea/prisma-v2/pull/281) | ECB + FRED + Twelve Data Adapter, macro_service + ml_feature_service migriert |
| [#282](https://github.com/don69andrea/prisma-v2/pull/282) | API_KEY im Workflow nachgetragen, tote _current_chf_eur()-Funktion entfernt |
