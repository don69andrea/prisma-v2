# PRISMA V2 — Vollständiger Audit-Befundbericht
**Terminal:** 2  
**Erstellt:** 2026-06-13  
**Methode:** 8 parallele Subagenten (Security, Performance/Async, Frontend/Backend-Contract, ML-Pipeline, Test-Qualität, Error-Handling, Business-Logic, CI/CD)  
**Status:** Befunde — noch nicht umgesetzt

---

## Übersicht

| Domain | KRITISCH | WARNUNG | INFO |
|--------|----------|---------|------|
| Security | 3 | 4 | 2 |
| ML-Pipeline | 4 | 4 | 2 |
| Business-Logic | 5 | 5 | 1 |
| Performance/Async | 3 | 5 | 3 |
| Error-Handling | 2 | 7 | 5 |
| Frontend/Backend-Contract | 4 | 2 | 4 |
| CI/CD & Deployment | 4 | 8 | 4 |
| Test-Qualität | 1 | 6 | 4 |
| **Total** | **26** | **41** | **25** |

---

## KRITISCHE BEFUNDE

---

### S-1 — NEXT_PUBLIC_API_KEY im Browser-Bundle exponiert
**Datei:** `frontend/lib/api/client.ts:2`, `render.yaml:72`  
**Problem:** `NEXT_PUBLIC_*`-Variablen werden von Next.js in das öffentliche JavaScript-Bundle eingebaut. Der Admin-API-Key ist damit für jeden Browser-Nutzer via DevTools sichtbar. Alle `require_admin_api_key`-geschützten Endpoints (Memos, Batch-Jobs, Rankings) sind damit de facto öffentlich.  
**Fix:** Separaten, limitierten Frontend-Key einführen (`NEXT_PUBLIC_FRONTEND_API_KEY ≠ API_KEY`). Der Admin-Key darf nie in einer `NEXT_PUBLIC_*`-Variable stehen.

---

### S-2 — Ticker-Parameter ohne Validierung in 3 Endpoints
**Dateien:** `backend/interfaces/rest/routers/fundamentals.py:26`, `dividends.py:26`, `reports.py:27`  
**Problem:** `ticker: str` ohne `Path(..., pattern=...)`. `stocks.py` hat das Pattern bereits (`^[A-Za-z0-9.\-]{1,12}$`), diese drei Endpoints nicht.  
**Fix:**
```python
ticker: str = Path(..., pattern=r"^[A-Za-z0-9.\-]{1,12}$")
```

---

### S-3 — f-String-SQL in 3 Embedding-Repositories
**Dateien:** `embedding_repository.py:139`, `news_repository.py:92`, `swiss_filing_repository.py:79`  
**Problem:** Vector-Query via f-String aufgebaut. Aktuell durch Float-Validierung sicher, aber fragiles Pattern das bei Refactoring zur echten Injection werden kann.  
**Fix:** SQL-Template via `.format()` mit festen Platzhaltern, nicht f-String. Filter-Conditionals als separate Variablen.

---

### ML-1 — Feature-Mismatch Training vs. Inference: Makro-Rate
**Datei:** `backend/application/services/ml_feature_service.py:330`, `scripts/train_return_predictor.py:453`  
**Problem:** Training: `snb_rate` ist market-aware (FED für US-Ticker, ECB für EU, SNB für CH). Inference: immer `_snb_rate_on(today)`. Das Modell lernt bei US-Titeln auf FED-Raten, bekommt bei Inference aber SNB-Raten — völlig andere Feature-Distribution. Vorhersagen für US/EU-Titel sind statistisch unbrauchbar.  
**Fix:** Entweder beide Seiten auf SNB vereinheitlichen, oder Inference ebenfalls market-aware machen.

---

### ML-2 — Feature-Mismatch Training vs. Inference: FX-Rate
**Datei:** `backend/application/services/ml_feature_service.py:308`, `scripts/train_return_predictor.py:460`  
**Problem:** Training: multi-currency (`USD/CHF` für US, `GBP/CHF` für UK, `EUR/CHF` für EU). Inference: immer `_current_chf_eur()` = EUR/CHF. Derselbe Bug wie ML-1, anderes Feature.  
**Fix:** Harmonisieren — beide Seiten auf EUR/CHF oder beide market-aware.

---

### ML-3 — Keine Feature-Name-Validierung beim Modell-Laden
**Datei:** `backend/application/services/ml_prediction_service.py:48`  
**Problem:** `_load_model()` liest `return_predictor_latest.json` mit gespeicherten `feature_names`, vergleicht diese aber nicht mit dem aktuellen `FEATURE_NAMES`. Bei Code-Änderungen lädt das alte Modell mit falscher Feature-Reihenfolge und prediziert Unsinn ohne Fehlermeldung.  
**Fix:**
```python
stored = meta.get("feature_names", [])
current = list(MLFeatureVector.FEATURE_NAMES)
if stored != current:
    raise ValueError(f"Feature-Mismatch: Modell={stored}, Code={current}")
```

---

### ML-4 — Makrodaten 365 Tage veraltet
**Datei:** `backend/application/services/ml_feature_service.py:28`  
**Problem:** `_MACRO_DATA_LAST_UPDATED = date(2025, 6, 13)`. Heute: `2026-06-13`. SNB/ECB/FED-Einträge enden bei März 2026. Alle Zinssatz-Features basieren auf einem Jahr alten Werten.  
**Fix:** Datensätze auf aktuellen Stand bringen (SNB: 0.0% seit 2025-03-19, ECB: 0.75% seit 2026-03-06, FED: 3.50% seit 2026-03-18) und `_MACRO_DATA_LAST_UPDATED = date(2026, 6, 13)` setzen.

---

### BL-1 — Negative P/E-Ratio wird als "teuer" eingestuft
**Datei:** `backend/domain/services/swiss_quant_scorer.py:70`  
**Problem:** `_score_pe(-10.0)` gibt `25.0` zurück (weil `-10 < 15` → True → 100.0 ... nein, laut Code geht es durch alle `if pe < X`-Checks und landet bei dem niedrigsten Wert). Verlustunternehmen (negative EPS → negativer P/E) werden als quasi-günstig oder teuer eingestuft statt als nicht-scorebar.  
**Fix:**
```python
if pe is None: return 50.0
if pe <= 0: return 0.0  # Verlustunternehmen
```

---

### BL-2 — Race Condition zwischen check_cap_atomic und record()
**Datei:** `backend/application/services/cost_tracker.py:53`  
**Problem:** `check_cap_atomic()` gibt den Advisory Lock frei, bevor `record()` aufgerufen wird. Zwei parallele Prozesse können beide den Check bestehen und gemeinsam das Budget überschreiten.  
**Fix:** `check_and_record()` als atomare Methode: Record innerhalb desselben Locks ausführen.

---

### BL-3 — Signal-Aggregation: fehlende Signale nicht umverteilt
**Datei:** `backend/application/services/signal_aggregation_service.py:80`  
**Problem:** Wenn ML-Modell nicht verfügbar, wird `ml_score=50.0` (Fallback-Neutral) mit vollem Gewicht 0.35 eingerechnet. Der Composite-Score wird systematisch Richtung 50.0 gezogen. Korrekt wäre: Gewichte der verfügbaren Signale auf 1.0 normieren.  
**Fix:** Dynamische Gewichts-Normalisierung basierend auf verfügbaren Signalen.

---

### BL-4 — Verrechnungssteuer hardcoded als 35%
**Datei:** `backend/application/agents/steuer_agent.py:133`  
**Problem:** `"Verrechnungssteuer (35%)"` im Fallback-Text. Die Schweizer Verrechnungssteuer beträgt seit 2021 **15%** (nicht 35%). Falsche Steuerinformation an Nutzer.  
**Fix:** `VERRECHNUNGSSTEUER_RATE = 0.15` als Konstante, Fallback-Text dynamisch.

---

### BL-5 — onboarding_complete ohne Consistency-Validator
**Datei:** `backend/domain/entities/investor_profile.py`  
**Problem:** Ein Profil kann `onboarding_complete=True` haben während alle anderen Felder noch auf Defaults stehen. Keine Pydantic-Validierung die das verhindert.  
**Fix:**
```python
@model_validator(mode="after")
def _check_onboarding_consistency(self) -> "InvestorProfile":
    if self.onboarding_complete and self.risk_profile == "moderate":
        raise ValueError("onboarding_complete=True aber risk_profile ist noch default")
    return self
```

---

### EH-1 — CostTracker.record() nach erfolgreichem LLM-Call
**Datei:** `backend/infrastructure/llm/client.py:92`  
**Problem:** Wenn `record()` fehlschlägt (DB-Timeout), wird die Exception propagiert. Der LLM-Call war bereits erfolgreich, aber der User sieht einen 500er. Schlimmer: Das Budget wird nicht aktualisiert → Kostenüberschreitung möglich.  
**Fix:** `record()` darf nicht propagieren. Im LLM-Client:
```python
try:
    await self._cost_tracker.record(...)
except Exception:
    _logger.exception("CRITICAL: Cost-Tracking fehlgeschlagen — Budget-Cap wird nicht aktualisiert!")
    # Nicht re-raise
```

---

### CD-1 — Dockerfile.backend: COPY models/ schlägt fehl
**Datei:** `Dockerfile.backend:41`  
**Problem:** `COPY models/ models/` — das `models/`-Verzeichnis ist nicht im Repository (nur die `.joblib`-Datei ist committed, nicht das Verzeichnis als Verzeichnis in Git). Docker-Build schlägt fehl, kein Deployment möglich.  
**Fix:** `mkdir -p models/` im Repo oder die COPY-Zeile anpassen.

---

### CD-2 — Migration-Fehler → Endlos-Restart-Loop
**Datei:** `scripts/backend-start.sh:10`  
**Problem:** `set -e` + `alembic upgrade head` ohne Fehlerbehandlung. Bei fehlerhafter Migration crasht der Container, Render startet nach 10s neu, gleicher Fehler, keine Benachrichtigung, Deployment steckt fest.  
**Fix:**
```bash
if ! alembic upgrade head; then
  echo "ERROR: Migration fehlgeschlagen — Container stoppt ohne Restart-Loop"
  exit 1
fi
```

---

### P-1 — N+1-Queries bei Rankings-Export
**Datei:** `backend/interfaces/rest/routers/runs.py:122`  
**Problem:** `get_by_ticker()` in for-Schleife — bei 100 Rankings = 100 sequentielle DB-Queries.  
**Fix:** `asyncio.gather()` für parallele Lookups + Stock-Map aufbauen.

---

### P-2 — build_dataset() blockiert Event Loop
**Datei:** `backend/application/services/ml_feature_service.py:364`  
**Problem:** Synchrone Methode ruft `yf.download()` direkt auf (kein `asyncio.to_thread`). Blockiert den gesamten Event Loop für mehrere Minuten beim Training.  
**Fix:** Methode zu `async def` umwandeln, yfinance-Calls via `asyncio.to_thread()`.

---

### FC-1 — list[Decimal] → NaN in Frontend-Charts
**Dateien:** `backend/interfaces/rest/schemas/backtest.py:34`, `frontend/lib/api/backtest.ts:16`  
**Problem:** Backend serialisiert `list[Decimal]` als JSON-Strings (z.B. `"123.45"`). Frontend typisiert als `number[]`. Chart-Bibliothek bekommt Strings → NaN → leere Charts.  
**Fix:** TypeScript-Types auf `number[]` korrigieren, oder Backend explizit zu `float` casten.

---

## WARNUNGEN (Auswahl wichtigster)

---

### W-EH-1 — Discovery-Service: alle Scoring-Fehler auf DEBUG-Level
**Datei:** `backend/application/services/discovery_service.py:93`  
**Problem:** `_logger.debug(...)` für Quant-Score-Fehler. In Production ist Debug-Logging aus. Bei yfinance-Ausfall sieht niemand warum alle Stocks gefiltert werden.  
**Fix:** `_logger.warning(..., exc_info=True)`

---

### W-EH-2 — Alert-Preis-Check schluckt alle Exceptions
**Datei:** `backend/application/services/alert_service.py:106`  
**Problem:** `except Exception: return False` ohne Logging. yfinance-Timeout → Alert "feuert nicht" — User denkt Bedingung nicht erfüllt.  
**Fix:** `_logger.warning("Preis-Check %s fehlgeschlagen: %s", alert.id, exc)`

---

### W-EH-3 — Startup-Crash wenn Alert-Scheduler fehlschlägt
**Datei:** `backend/interfaces/rest/app.py:52`  
**Problem:** `scheduler.start()` ohne try/except. DB-Verbindungsfehler beim Start → gesamte App startet nicht.  
**Fix:** Try/except mit Fallback (App läuft ohne Scheduler, warning geloggt).

---

### W-P-1 — Discovery: 200 yfinance-Calls ohne Cache
**Datei:** `backend/application/services/discovery_service.py:89`  
**Problem:** Bei jedem Discovery-Request werden bis zu 200 Fundamentals frisch von yfinance geladen. Kein Cache, hohe Latenz.  
**Fix:** In-Memory oder Redis Cache mit 1h TTL für Fundamentals.

---

### W-P-2 — Rate Limiter fehlt für /portfolio/monte-carlo
**Datei:** `backend/interfaces/rest/rate_limiter.py:20`  
**Problem:** CPU-intensive Monte Carlo Simulation (bis 50k Paths) nicht im `_LLM_PREFIXES` Set.  
**Fix:** `/api/v1/portfolio/monte-carlo` zu Rate-Limiter hinzufügen.

---

### W-BL-1 — Ranking Tie-Breaking Bug
**Datei:** `backend/application/services/ranking_aggregator.py:94`  
**Problem:** Zwei Ticker mit gleichem Score bekommen Rang 1 und 1, nächster Ticker bekommt Rang 3 statt 2 (Dense-Ranking falsch implementiert).  
**Fix:** Separate Rank-Variable korrekt hochzählen.

---

### W-BL-2 — zip(strict=False) bei Signal-Aggregation
**Datei:** `backend/application/services/signal_aggregation_service.py:146`  
**Problem:** Bei asyncio.gather-Längen-Mismatch werden letzte Ticker still ignoriert.  
**Fix:** `strict=True` verwenden.

---

### W-CD-1 — .dockerignore fehlt
**Problem:** Docker-Image enthält `.git`, `__pycache__`, alle `.joblib`-Dateien. Unnötig groß, langsame Builds.  
**Fix:** `.dockerignore` im Repository-Root erstellen.

---

### W-CD-2 — workflow_dispatch bypassed CI-Gate
**Datei:** `.github/workflows/cd-render.yml:24`  
**Problem:** Manueller Trigger (`workflow_dispatch`) deployt auch wenn CI failed.  
**Fix:** Explizite Bestätigungs-Input für Skip-CI-Check.

---

### W-CD-3 — Health-Check prüft nur Liveness
**Datei:** `backend/interfaces/rest/routers/health.py:14`  
**Problem:** `/health` gibt 200 auch wenn DB down ist. Render denkt Service ist OK.  
**Fix:** Separater `/health/ready` Endpoint der DB-Connectivity prüft.

---

### W-FC-1 — 4 neue InvestorProfile-Felder fehlen im TypeScript
**Dateien:** `frontend/lib/api/discovery.ts:13`, `backend/interfaces/rest/schemas/investor_profile.py:34`  
**Problem:** `sector_hint`, `investment_amount`, `esg_preference`, `income_preference` wurden im Backend implementiert, aber `InvestorProfileResponse`-TypeScript-Interface nicht aktualisiert. Alle Felder sind `undefined` im Frontend.  
**Fix:** TypeScript-Interface um die 4 Felder erweitern.

---

### W-FC-2 — EligibilityResponse.reason nicht typisiert
**Datei:** `frontend/lib/api/eligibility.ts:5`  
**Problem:** Backend sendet `reason: str`, Frontend-Interface hat das Feld nicht. Eligibility-Begründungen werden nie angezeigt.  
**Fix:** `reason: string` zum TypeScript-Interface hinzufügen.

---

### W-FC-3 — mean_variance Portfolio-Methode im Frontend unbekannt
**Datei:** `frontend/lib/api/portfolio.ts:46`  
**Problem:** Backend akzeptiert `method: "score_weighted" | "risk_parity" | "mean_variance"`. Frontend-Union-Type hat `"mean_variance"` nicht.  
**Fix:** Union-Type erweitern.

---

### W-T-1 — spec= fehlt bei ~68 AsyncMock-Aufrufen
**Datei:** Alle Test-Dateien in `backend/tests/unit/application/`  
**Problem:** `AsyncMock()` ohne `spec=` beantwortet beliebige Methoden mit neuen MagicMocks. Interface-Fehler werden nicht erkannt.  
**Fix:** Systematisches Hinzufügen von `spec=ConcreteClass` zu allen AsyncMock-Aufrufen.

---

### W-T-2 — Integration-Tests ohne per-Test-Rollback
**Datei:** `backend/tests/integration/conftest.py:12`  
**Problem:** Keine automatische DB-Bereinigung zwischen Tests. Tests können voneinander abhängen.  
**Fix:** `truncate_*` Fixtures als Standard-Autouse-Fixture konfigurieren.

---

## INFO (Auswahl)

- **I-ML-1:** `_current_chf_eur()` Fallback hardcoded `0.93` (2025-Wert) — für 2026 veraltet
- **I-ML-2:** yfinance EUR/CHF für 2026 nutzt `_rates.get(year, 0.93)` Fallback statt letzten bekannten Wert
- **I-BL-1:** Zero-Dividende (0.0%) erhält Score 25.0, `None` (Daten fehlen) 50.0 — asymmetrisch
- **I-BL-2:** Rebalancing: negative Positionen (Leerverkäufe) werden akzeptiert ohne Warnung
- **I-CD-1:** `alembic.ini` Fallback-URL zeigt auf Docker-Compose-Host `db:5432` — in Render nie erreichbar
- **I-CD-2:** Dependencies mit `>=` statt exakten Versionen — Minor-Bumps unbemerkt
- **I-T-1:** `UniverseService` hat keine Test-Datei
- **I-T-2:** ~25 Tests mit `assert X is not None` ohne Wert-Checks
- **I-T-3:** 20-30 repetitive Tests ohne `@pytest.mark.parametrize`
- **I-S-1:** CORS `allow_methods=["*"]` erlaubt alle HTTP-Methoden — einschränken auf GET/POST
- **I-S-2:** Discovery öffentlich + LLM-backed: 10 req/min Rate Limit für Budget-Abuse potenziell zu schwach
- **I-FC-1:** `FundamentalsRead` in `stock.py` nicht verwendet (Duplikat von `FundamentalsResponse` in `fundamentals.py`)

---

## Implementierungsreihenfolge

### Sofort-Fixes (< 1h je, unabhängig voneinander)
```
S-2    Ticker-Regex in fundamentals.py, dividends.py, reports.py
ML-4   Makrodaten auf 2026-06-13 aktualisieren
BL-4   Verrechnungssteuer 35% → 15% korrigieren
CD-1   Dockerfile.backend: models/-Verzeichnis fix
W-FC-1 TypeScript-Interface: 4 neue InvestorProfile-Felder
W-FC-2 EligibilityResponse.reason im Frontend typisieren
W-FC-3 mean_variance zur Portfolio-Union hinzufügen
```

### Diese Woche (1-4h je)
```
S-1    NEXT_PUBLIC_API_KEY-Strategie überdenken
ML-1   Feature-Mismatch snb_rate harmonisieren
ML-2   Feature-Mismatch FX-Rate harmonisieren
ML-3   Feature-Name-Validierung beim Modell-Laden
BL-1   Negative P/E → Score 0.0
BL-3   Signal-Aggregation Gewichts-Normierung
EH-1   CostTracker.record() nicht propagieren
CD-2   Migration-Fehler: Endlos-Loop verhindern
W-EH-1 Discovery: DEBUG → WARNING mit exc_info
W-EH-2 Alert: Exception-Logging ergänzen
W-CD-1 .dockerignore erstellen
FC-1   Backtest: list[Decimal] → number[] Fix
```

### Nächster Sprint (> 4h)
```
BL-2   Race Condition check_cap_atomic + record() atomar machen
BL-5   Consistency-Validators InvestorProfile
P-1    N+1-Queries Rankings-Export
P-2    build_dataset() async
W-P-1  Fundamentals-Cache (Redis/In-Memory)
W-BL-1 Ranking Tie-Breaking
W-T-1  spec= zu allen AsyncMock-Aufrufen
W-T-2  Integration-Test-Rollback
W-CD-2 workflow_dispatch CI-Gate
W-CD-3 /health/ready Endpoint
S-3    f-String-SQL refaktorieren
```

---

*Erstellt von Terminal 2 via 8-Agenten-Parallelanalyse. Terminal 3 hat separat doc/audit-fix-plan-2026-06-13.md erstellt (anderer Scope).*
