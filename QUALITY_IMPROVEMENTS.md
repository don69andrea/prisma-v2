# PRISMA V2 — Quality Improvements Plan
**Branch:** `feature/quality-improvements`  
**Erstellt:** 2026-06-13  
**Status:** In Arbeit — diese Datei ist die einzige Wahrheit über was noch aussteht

---

## Übersicht nach Priorität

| # | Priorität | Bereich | Datei(en) | Status |
|---|-----------|---------|-----------|--------|
| 1 | P1 | Frontend | `discover-client.tsx` | ✅ Erledigt |
| 2 | P1 | Frontend | `fonds-client.tsx` | ✅ Erledigt |
| 3 | P1 | Backend | `ml_feature_service.py` | ✅ Erledigt |
| 4 | P1 | Backend | `cost_tracker.py` | ✅ Erledigt |
| 5 | P2 | Backend | `signal_aggregation_service.py` + `config.py` | ✅ Erledigt |
| 6 | P2 | Backend | `ranking_run_service.py` | ✅ Erledigt |
| 7 | P2 | Backend | `investor_profile.py` + `profile_classifier.py` + `discovery_service.py` | ✅ Erledigt |
| 8 | P2 | Backend+DB | InvestorProfile Dimensionen + Migration | ✅ Erledigt |
| 9 | P2 | Frontend | `SteuerPanel.tsx` + `steuer-client.tsx` | ✅ Erledigt |
| 10 | P2 | Backend | `monte_carlo_service.py` + `MonteCarloFanChart.tsx` | ✅ Erledigt |
| 11 | P2 | Backend | `fonds_vergleich_service.py` | ✅ Erledigt |
| 12 | P2 | Backend | `macro_service.py` | ✅ Erledigt |
| 13 | P2 | Frontend | `portfolio-client.tsx` + `fonds-client.tsx` | ✅ Erledigt |
| 14 | P3 | Backend | `chat_service.py` | ✅ Erledigt |
| 15 | P3 | Frontend | `SHAPWaterfallChart.tsx` | ✅ Erledigt |
| 16 | P3 | Backend | `portfolio_agent.py` + `steuer_agent.py` | ✅ Erledigt |

---

## Detailplan pro Task

---

### #1 — DiscoverClient: Stille catch-Exception
**Datei:** `frontend/app/discover/discover-client.tsx`  
**Problem:** `catch () => {}` auf Zeile ~116 — API-Fehler wird verschluckt, User sieht leere UI

**Was zu ändern:**
- `catch () => {}` → `catch (err) { setError(err instanceof Error ? err.message : "Laden fehlgeschlagen") }`
- `const [error, setError] = useState<string | null>(null)` State hinzufügen
- Unter dem Loading-Check: wenn `error` gesetzt → Error-Card anzeigen (rotes Alert mit Retry-Button)
- Retry-Button: `onClick={() => { setError(null); router.refresh() }}`

---

### #2 — FondsClient: Error-State bei API-Fehler
**Datei:** `frontend/app/fonds/fonds-client.tsx`  
**Problem:** Wenn `listFonds` fehlschlägt, bleibt UI im Loading-Zustand hängen

**Was zu ändern:**
- `useQuery` für Fonds-Listing: `onError` Callback ergänzen oder `isError`/`error` aus useQuery destructuren
- Wenn `isError`: Error-Banner über der Fonds-Liste anzeigen: "Fondsliste konnte nicht geladen werden"
- Wenn `isPending` ohne Daten nach Timeout: Fallback auf leere Liste mit Hinweis

---

### #3 — ml_feature_service: Staleness-Warnung
**Datei:** `backend/application/services/ml_feature_service.py`  
**Problem:** Makrodaten (SNB/ECB/FED Zinsen, FX-Kurse) sind als statische Listen bis max. 2025-03 hartcodiert. Kein Update-Mechanismus, kein Hinweis wenn Daten veraltet.

**Was zu ändern:**
- Konstante `_MACRO_DATA_LAST_UPDATED = date(2025, 6, 13)` am Dateianfang ergänzen
- Funktion `_check_macro_staleness()` die warnt wenn `date.today() - _MACRO_DATA_LAST_UPDATED > timedelta(days=7)`
- Diese Funktion in `__init__` oder beim ersten Aufruf von `build_features()` aufrufen
- Logger-Warning: `"Makro-Daten sind %d Tage alt. Bitte SNB/ECB/FED Listen in ml_feature_service.py aktualisieren."`
- Kommentar zu JEDER hartcodierten Liste ergänzen: `# ACHTUNG: Manuell gepflegt — zuletzt aktualisiert: YYYY-MM-DD`

**Langfristig (nicht Teil dieses Tasks):** Echte API-Integration via FRED / SNB Data Portal.

---

### #4 — cost_tracker: PostgreSQL Advisory Lock
**Datei:** `backend/application/services/cost_tracker.py`  
**Problem:** `asyncio.Lock()` ist nur innerhalb eines Prozesses wirksam. Bei mehreren Backend-Instanzen (Render.com horizontal scaling) kann Budget-Cap überschritten werden.

**Was zu ändern:**
- `check_cap()` Methode: nach dem in-process Lock zusätzlich DB-seitigen Check via Repository
- Neuer Port-Methode `CostLogRepository.try_reserve_budget(estimated_usd) -> bool` 
- Implementierung via `SELECT pg_try_advisory_xact_lock(hash)` + atomare Summen-Abfrage
- Wenn `try_reserve_budget` False zurückgibt → `BudgetCapExceeded` werfen
- Fallback: wenn Advisory Lock nicht verfügbar (Repository-Implementation hat es nicht) → bisheriges Verhalten, aber Warning loggen

**Konkrete Änderungen:**
```
cost_tracker.py: check_cap() um Repository-Call erweitern
domain/repositories/cost_log_repository.py: try_reserve_budget() Methode zum Port hinzufügen
infrastructure/persistence/repositories/cost_log_repository.py: pg_try_advisory_xact_lock implementieren
```

---

### #5 — signal_aggregation_service: Gewichte externalisieren
**Datei:** `backend/application/services/signal_aggregation_service.py` + `backend/config.py`  
**Problem:** `_QUANT_WEIGHT = 0.45`, `_ML_WEIGHT = 0.35`, `_MACRO_WEIGHT = 0.20` hartcodiert — kein A/B-Testing möglich

**Was zu ändern:**
- `config.py`: drei neue Felder `signal_quant_weight: float = 0.45`, `signal_ml_weight: float = 0.35`, `signal_macro_weight: float = 0.20`
- Validierung: `@field_validator` prüft dass Summe der drei Gewichte == 1.0 (±0.001)
- `signal_aggregation_service.py`: Konstanten durch Config-Werte ersetzen
- Service-Konstruktor erhält `settings: Settings` via DI

---

### #6 — ranking_run_service: Per-Modell Try/Catch
**Datei:** `backend/application/services/ranking_run_service.py`  
**Problem:** 5 Modelle werden in einem Dict gebaut — crasht ein Modell, fällt der gesamte Run aus

**Was zu ändern:**
```python
# Vorher:
per_model = {
    "quality_classic": QualityClassicModel().run(fundamentals),
    ...
}

# Nachher:
per_model: dict[str, list] = {}
for model_name, model_fn in _MODELS.items():
    try:
        per_model[model_name] = model_fn()
    except Exception as exc:
        _logger.error("Modell %s fehlgeschlagen in Run %s: %s", model_name, run.id, exc)
        # Run läuft weiter mit den verbleibenden Modellen
```
- `_MODELS: dict[str, Callable]` als Konstante am Dateianfang
- Wenn 0 Modelle erfolgreich: Run-Status auf `"failed"` setzen, Exception werfen
- Run-Result enthält `failed_models: list[str]` für spätere Diagnose

---

### #7 — InvestorProfile: sector_hint + financial_knowledge nutzen
**Dateien:**
- `backend/domain/entities/investor_profile.py`
- `backend/application/services/profile_classifier.py`  
- `backend/application/services/discovery_service.py`
- `backend/interfaces/rest/schemas/investor_profile.py`

**Problem:**
1. `classify_turn1()` gibt `sector_hint` zurück, aber Entity hat kein Feld dafür → Wert geht verloren
2. `financial_knowledge` im Entity vorhanden, aber `discovery_service.py` nutzt es nicht

**Was zu ändern:**
- `investor_profile.py`: Feld `sector_hint: str | None = None` ergänzen
- Wer immer Turn1-Klassifikation anwendet: `profile.sector_hint = result.sector_hint`
- `discovery_service.py`: `sector_hint` als zusätzliches Sektor-Signal nutzen:
  - Wenn `sector_affinity` leer UND `sector_hint` gesetzt → `sector_hint` als Fallback verwenden
- `financial_knowledge` → `result_limit` anpassen: low=10 Titel, medium=20, high=30
- Schema `InvestorProfileResponse`: `sector_hint` ergänzen

---

### #8 — InvestorProfile: Neue Dimensionen + DB-Migration
**Dateien:**
- `backend/domain/entities/investor_profile.py`
- `backend/interfaces/rest/schemas/investor_profile.py`
- `backend/alembic/versions/0020_extend_investor_profile.py` (neu)
- `backend/infrastructure/persistence/models/investor_profile.py`
- `backend/application/services/profile_classifier.py`

**Neue Dimensionen:**
```
investment_amount: Literal["under_10k", "10k_100k", "over_100k"] = "10k_100k"
esg_preference: Literal["yes", "no", "indifferent"] = "indifferent"
income_preference: Literal["dividends", "growth", "balanced"] = "balanced"
```

**Anpassungen:**
- Entity: 3 neue Felder mit Defaults
- Schema: in CreateRequest + Response ergänzen
- Discovery-Service: 
  - `esg_preference="yes"` → nur ESG-konforme Titel (Feld auf SwissStock prüfen ob vorhanden)
  - `income_preference="dividends"` → Dividend-Yield Schwelle als Bonus-Score
- Alembic-Migration: 3 neue VARCHAR-Spalten mit Defaults
- `calculate_confidence()`: neue Felder erhöhen Score (je 0.05 pro gesetztem Feld)
- Profil-Classifier: `classify_turn_amount()`, `classify_turn_esg()`, `classify_turn_income()` als statische Methoden

---

### #9 — SteuerPanel: Konfigurierbare Parameter
**Dateien:**
- `frontend/components/factsheet/SteuerPanel.tsx`
- `backend/interfaces/rest/routers/steuer.py` (Parameter-Schema prüfen)

**Problem:** Hardcodierte Parameter `privatperson`, `10 Jahre` sind nicht durch UI anpassbar

**Was zu ändern:**
- `SteuerPanel.tsx`: Neue UI-Sektion "Steuer-Parameter" vor dem Berechnen-Button
  - Dropdown: Steuerprofil (`privatperson`, `unternehmen`, `vorsorge_3a`)
  - Slider oder Dropdown: Haltedauer (1 / 3 / 5 / 10 / 20 Jahre)
  - Optional: Kantonsfeld (Freitext oder Dropdown mit CH-Kantonen)
- State: `const [steuerProfil, setSteuerProfil] = useState<"privatperson"|"unternehmen"|"vorsorge_3a">("privatperson")`
- State: `const [haltedauer, setHaltedauer] = useState<number>(10)`
- API-Call: Parameter mitschicken statt hartcodiert im Service
- Backend: `steuer.py` Router prüfen ob Parameter schon akzeptiert werden, sonst Schema erweitern

---

### #10 — monte_carlo_service: Cholesky-Warnung + DI
**Dateien:**
- `backend/application/services/monte_carlo_service.py`
- `frontend/components/portfolio/MonteCarloFanChart.tsx`
- `backend/interfaces/rest/routers/portfolio.py` (Response-Schema)

**Problem:**
1. Bei nicht-PSD Korrelationsmatrix → stille Degradation zur Unabhängigkeit
2. `MLPredictionService()` ohne DI instantiiert

**Was zu ändern:**
- `monte_carlo_service.py`:
  - Return-Typ um `correlation_degraded: bool` erweitern
  - `_cholesky()` gibt Tuple `(matrix, degraded: bool)` zurück
  - `MLPredictionService` per Konstruktor-Parameter übergeben (mit Default None)
- Response-Schema: `correlation_degraded: bool = False` ergänzen
- `MonteCarloFanChart.tsx`:
  - Wenn `correlation_degraded=True`: gelbes Info-Banner unter Chart: "Korrelationsdaten unvollständig — Simulation ohne Titelkorrelationen berechnet"

---

### #11 — fonds_vergleich_service: Dynamische Risk-Free Rate
**Datei:** `backend/application/services/fonds_vergleich_service.py`  
**Problem:** `_RISK_FREE_RATE = 0.01` hardcodiert — inkonsistent mit dynamischen SNB-Rates in ml_feature_service

**Was zu ändern:**
- `_RISK_FREE_RATE` Konstante entfernen
- Service-Konstruktor: `risk_free_rate: float | None = None` Parameter
- Wenn `None`: SNB-Rate via `ml_feature_service._snb_rate_on(date.today())` lesen
- Sharpe-Berechnung nutzt dann den aktuellen SNB-Leitzins
- Kommentar: Erklärung welche Rate warum verwendet wird

---

### #12 — macro_service: Async-Fix + robusteres PMI-Parsing
**Datei:** `backend/application/services/macro_service.py`  
**Probleme:**
1. `_fetch_chf_eur()` ist synchron (yfinance), wird in async Context aufgerufen → Event-Loop blockiert
2. PMI-Parsing via fragile Regex

**Was zu ändern:**
- `_fetch_chf_eur()`: `asyncio.to_thread(yf.download, ...)` statt direkter Call
- Gesamten `_fetch_chf_eur` in `async def` umwandeln
- PMI-Parsing: zweiten Fallback-Pattern aus `procure.ch` + klarere Logging-Messages
- Bei PMI-Parse-Failure: Warning mit URL und gefundenem Text loggen (nicht nur silent Fallback)
- `_FALLBACK_PMI_CH = 45.5` mit Kommentar versehen: wann dieser Wert zuletzt validiert wurde

---

### #13 — Portfolio/Fonds: Gewicht-Validierung
**Dateien:**
- `frontend/app/portfolio/portfolio-client.tsx`
- `frontend/app/fonds/fonds-client.tsx`

**Problem:** User kann Gewichte auf >100% setzen, keine Validierung

**Was zu ändern:**
- `totalWeight = positions.reduce((sum, p) => sum + p.weight, 0)`
- Wenn `totalWeight > 100`: roter Fehlerbalken unter der Tabelle: "Gesamtgewichtung: 107% — maximal 100% erlaubt"
- "Analyse starten"-Button disabled wenn `totalWeight > 100 || totalWeight === 0`
- Grüner Indikator wenn `totalWeight === 100`, gelb wenn <100

---

### #14 — chat_service: Tool-Dispatch Plugin-Registry
**Datei:** `backend/application/services/chat_service.py`  
**Problem:** 350-Zeilen-Monolith mit Inline-Imports, N+1 Session-Pattern, 500-char Truncation ohne Warnung

**Was zu ändern:**
- `ToolHandler = Callable[[dict, AsyncSession], Awaitable[str]]` Type-Alias
- `_TOOL_REGISTRY: dict[str, ToolHandler] = {}` am Dateianfang
- `@register_tool("search_stocks")` Decorator-Funktion
- Alle Tool-Handler als separate Funktionen extrahieren (aktuell inline in Switch-Case)
- DB-Session einmal pro Request öffnen, an alle Handler weitergeben
- `result_str[:500]` → `result_str[:2000]` + Logging wenn truncated
- Imports aller Service-Klassen an Dateianfang (nicht inline)

---

### #15 — SHAPWaterfallChart: Responsive
**Datei:** `frontend/components/factsheet/SHAPWaterfallChart.tsx`  
**Problem:** `MAX_BAR_WIDTH=180` hardcodiert → bricht auf kleinen Screens

**Was zu ändern:**
- `useRef<HTMLDivElement>` auf Container
- `useEffect` + `ResizeObserver`: containerWidth messen
- `maxBarWidth = Math.min(180, containerWidth * 0.6)`
- Bars skalieren relativ zu `maxBarWidth`

---

### #16 — portfolio_agent + steuer_agent: Datengeleitete Fallbacks
**Dateien:**
- `backend/application/agents/portfolio_agent.py`
- `backend/application/agents/steuer_agent.py`

**Problem:**
- `portfolio_agent._fallback_narrative()`: Boilerplate-Text ohne Portfolio-Daten
- `steuer_agent._fallback()`: Generische Steuerinfo ohne Ticker-Kontext

**Was zu ändern:**
- `portfolio_agent._fallback_narrative(portfolio_data)`:
  - Tatsächliche Positionen und Gewichte aus `portfolio_data` interpolieren
  - "Ihr Portfolio besteht aus {N} Positionen. Grösste Position: {ticker} ({weight}%)."
  - Nicht mehr generischer Boilerplate
- `steuer_agent._fallback(ticker, profil, jahre)`:
  - Ticker, Profil-Typ und Haltedauer in Fallback-Text einbauen
  - "Für {ticker} als {profil} gilt: Haltedauer {jahre} Jahre — Verrechnungssteuer 35% rückforderbar."
  - Weniger generisch, mehr kontextspezifisch

---

## Investorprofil — Berufsfrage (separater Kontext)
**Frage:** Bringt die Berufsfrage etwas?  
**Antwort:** Nur wenn `sector_hint` aus Turn 1 ins Profil gespeichert und im Discovery-Service genutzt wird (Task #7).  
**Empfehlung:** Mit Task #8 (neue Dimensionen) wird Turn 1 auf direktes Finanzwissen-Self-Assessment umgestellt (Dropdown statt Freitext → kein LLM-Call nötig). Die Berufsfrage kann optional bleiben oder entfernt werden.

---

## Implementierungsreihenfolge

```
P1: #1 → #2 → #3 → #4   (alle unabhängig, parallel möglich)
P2: #5 → #6              (unabhängig)
    #7 → #8              (#8 baut auf #7 auf)
    #9                   (unabhängig)
    #10 → #11 → #12      (unabhängig voneinander)
    #13                  (unabhängig)
P3: #14 → #15 → #16      (alle unabhängig)
```
