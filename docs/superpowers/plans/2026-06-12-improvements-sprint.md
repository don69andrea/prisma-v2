# PRISMA V2 — Improvements Sprint Plan

**Erstellt:** 2026-06-12  
**Ziel:** Alle ausstehenden Verbesserungen nach dem ML-Overhaul implementieren

---

## Aufgaben (geordnet nach Priorität)

### 1. CLAUDE.md Status aktualisieren (~5 Min)

**Datei:** `CLAUDE.md` — Status-Tabelle

Neue Zeilen einfügen:
```
| ML-Overhaul: 163 Ticker, 19 Features, SimFin | Andrea | main | ✅ DONE |
```
R2.5-1 Status auf IN PROGRESS setzen.

---

### 2. Failing Unit-Tests fixen (~20 Min)

**Fehler 1: `test_get_context_uses_fallback_narrative_without_llm`**

- Datei: `backend/tests/unit/application/test_macro_service.py`
- Problem: `ctx.inflation_ch` ist `0.3` statt `None` — der MacroService gibt Fallback-Wert zurück wenn die SNB-API nicht erreichbar ist
- Fix: Test-Assertion anpassen — entweder `assert ctx.inflation_ch is None or ctx.inflation_ch == 0.3` ODER die SNB-Inflation-Funktion mocken

Der richtige Fix ist, `_fetch_swiss_inflation` auch zu mocken:
```python
patch("backend.application.services.macro_service._fetch_swiss_inflation", new=AsyncMock(return_value=None))
patch("backend.application.services.macro_service._fetch_swiss_pmi", new=AsyncMock(return_value=None))
```

**Fehler 2: `test_non_3a_account_marks_all_as_eligible`**

- Datei: `backend/tests/unit/application/test_rebalancing_service.py`
- Problem: `step.is_3a_eligible` ist `False` statt `True` wenn `is_3a_account=False`
- Fix: RebalancingService lesen, `is_3a_eligible`-Logik verstehen, Test oder Implementation korrigieren

---

### 3. Alte Modell-Dateien aufräumen (~5 Min)

**Dateien löschen:**
- `models/return_predictor_lightgbm_20260612_120527.joblib` (alter Test-Lauf)
- `models/return_predictor_xgboost_20260611_165331.joblib` (vorheriger Tag)
- `models/return_predictor_xgboost_20260612_171721.joblib` (v2 ohne SimFin)
- `models/dataset_preview.csv` (Debug-Datei)

**Behalten:**
- `models/return_predictor_latest.joblib` (→ aktuelles LightGBM mit SimFin)
- `models/return_predictor_lightgbm_20260612_175826.joblib` (aktuelles Modell, zur Sicherheit)
- `models/return_predictor_latest.json`

---

### 4. Delisted Ticker aus Trainings-Universe entfernen (~10 Min)

**Datei:** `scripts/train_return_predictor.py`

Aus `DEFAULT_TICKERS` entfernen:
- `"HELN"` — delisted
- `"DUFN"` — delisted
- `"SOFN"` — delisted
- `"CSGN"` — Credit Suisse, seit 2023 delisted
- `"MBTN"` — delisted

Aus `EU_TICKERS_NL` entfernen:
- `"ING.AS"` — kein yfinance-Preis verfügbar
- `"DSM.AS"` — delisted/keine Daten

Aus `EU_TICKERS_IT` entfernen:
- `"STM.MI"` — rate-limited / unzuverlässig

Commit danach.

---

### 5. Optuna Hyperparameter-Tuning starten (~60 Min Training, Background)

Im Hintergrund starten:
```bash
LOG=/tmp/train_optuna_$(date +%Y%m%d_%H%M%S).log
nohup python3 scripts/train_return_predictor.py \
    --market all --years 8 \
    --simfin-key b0f8e6ee-7dca-4ff4-96c0-799a9503cd00 \
    --tune \
    > "$LOG" 2>&1 &
```

Dann mit anderen Tasks weitermachen. Nach Abschluss: neues Modell committen + pushen.

---

### 6. SHAP Explainability Backend (~45 Min)

**Dependency:** `pip install shap>=0.45 --break-system-packages`  
Zu `pyproject.toml` unter `[project.dependencies]` hinzufügen.

**Datei:** `backend/domain/value_objects/ml_prediction.py`

Neues Value Object hinzufügen:
```python
@dataclass(frozen=True)
class SHAPEntry:
    feature: str         # Feature-Name (z.B. "drawdown_12m")
    value: float         # SHAP-Wert (positiv = Richtung Top-Klasse)
    feature_value: float # Roher Feature-Wert
    label: str           # Human-readable Label
```

`MLPrediction` erweitern um:
```python
shap_values: list[SHAPEntry] = field(default_factory=list)
shap_expected_value: float | None = None
```

**Human-readable Labels** (in `ml_prediction_service.py`):
```python
FEATURE_LABELS = {
    "quant_score": "PRISMA Score",
    "score_rendite": "Rendite-Score",
    "score_sicherheit": "Sicherheits-Score",
    "score_wachstum": "Wachstums-Score",
    "score_substanz": "Substanz-Score",
    "return_12m": "12M Rendite",
    "return_6m": "6M Rendite",
    "return_3m": "3M Rendite",
    "return_1m": "1M Rendite",
    "vol_30d": "Volatilität 30T",
    "vol_90d": "Volatilität 90T",
    "rsi_14": "RSI (14)",
    "price_to_52w_high": "Preis / 52W-Hoch",
    "vol_trend": "Volumen-Trend",
    "macd_hist": "MACD Histogramm",
    "bb_position": "Bollinger-Position",
    "drawdown_12m": "Max. Drawdown 12M",
    "snb_rate": "Leitzins",
    "chf_eur": "CHF/EUR",
}
```

**Datei:** `backend/application/services/ml_prediction_service.py`

In `predict()` nach `model.predict_proba()`:
```python
import shap
explainer = shap.TreeExplainer(model)
shap_vals = explainer.shap_values(x_2d)  # shape: (1, n_features, n_classes) oder (n_classes, 1, n_features)
# Top-Klasse = Klasse 2 (OUTPERFORM)
# shap_vals für top-Klasse: shap_vals[2][0] oder shap_vals[0, :, 2]
top_class_shap = ...  # je nach SHAP-Version
expected_val = explainer.expected_value[2] if isinstance(explainer.expected_value, list) else explainer.expected_value

entries = []
for i, fname in enumerate(FEATURE_NAMES):
    entries.append(SHAPEntry(
        feature=fname,
        value=float(top_class_shap[i]),
        feature_value=float(x_2d[0, i]),
        label=FEATURE_LABELS.get(fname, fname),
    ))
entries.sort(key=lambda e: abs(e.value), reverse=True)
shap_entries = entries[:8]  # Top-8
```

**Datei:** `backend/interfaces/rest/schemas/ml.py` (oder wo MLPredictionResponse liegt)

Schema erweitern:
```python
class SHAPEntryResponse(BaseModel):
    feature: str
    value: float
    feature_value: float
    label: str

class MLPredictionResponse(BaseModel):
    # ... bestehende Felder ...
    shap_values: list[SHAPEntryResponse] = []
    shap_expected_value: float | None = None
```

**Tests:** `backend/tests/unit/application/test_ml_prediction_service.py`
- `shap_values` im Response vorhanden
- Maximal 8 Einträge
- Sortiert nach `|value|` absteigend

---

### 7. SHAP Waterfall Chart Frontend (~45 Min)

**Datei:** `frontend/components/SHAPWaterfallChart.tsx`

SVG-basierter Waterfall Chart (keine externe Library):
- Grün (#00ff88) = positiver SHAP-Wert (→ OUTPERFORM)
- Rot (#ff4466) = negativer SHAP-Wert (→ UNDERPERFORM)
- Glassmorphism-Container
- Balken animieren beim Mount (600ms ease-out)
- Tooltip on hover

**Datei:** `frontend/lib/api/ml.ts` (oder wo der ML-API-Client liegt)

Response-Type um `shap_values` erweitern.

**Integration:** In das bestehende ML-Prediction-Panel auf dem Factsheet `/stocks/[ticker]` einbauen.

---

### 8. Fundamentals Widget Backend (~20 Min)

**Datei:** `backend/interfaces/rest/routers/stocks.py`

Neuen Endpoint hinzufügen:
```python
@router.get("/{ticker}/fundamentals", response_model=FundamentalsRead)
async def get_fundamentals(ticker: str, db: AsyncSession = Depends(get_db)):
    stock = await stock_repo.get_by_ticker(db, ticker.upper())
    if stock is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    
    fund = _stub_fundamentals(ticker)  # oder via MLFeatureService
    return FundamentalsRead(
        ticker=ticker.upper(),
        pe_ratio=fund.pe_ratio,
        pb_ratio=fund.pb_ratio,
        dividend_yield=fund.dividend_yield,
        disclaimer="Näherungswerte. Keine Anlageberatung."
    )
```

**Datei:** `backend/interfaces/rest/schemas/stock.py`

Schema hinzufügen:
```python
class FundamentalsRead(BaseModel):
    ticker: str
    pe_ratio: float | None
    pb_ratio: float | None
    dividend_yield: float | None
    disclaimer: str
```

---

### 9. Fundamentals Widget Frontend (~25 Min)

**Datei:** `frontend/components/FundamentalsCard.tsx`

Glassmorphism-Card mit:
- KGV (P/E Ratio)
- KBV (P/B Ratio)  
- Dividendenrendite (%)
- `—` für null-Felder
- Kleiner Disclaimer

**Integration:** In `frontend/app/stocks/[ticker]/page.tsx` einbauen.

---

### 10. Alles committen und pushen

```bash
git add -A
git commit -m "feat: SHAP explainability + Fundamentals Widget + Bug-Fixes + Cleanup"
git push origin main
```

Dann Render-Deployment triggern (manuell im Dashboard).

---

## Reihenfolge

```
1. CLAUDE.md Update (5 min)
2. Failing Tests fixen (20 min)
3. Modell-Cleanup (5 min)
4. Delisted Ticker entfernen (10 min)
5. Optuna im Hintergrund starten (startet Training, geht sofort weiter)
6. SHAP Backend (45 min)
7. SHAP Frontend (45 min)
8. Fundamentals Backend (20 min)
9. Fundamentals Frontend (25 min)
10. Commit + Push + Deploy (~10 min)
```

**Geschätzte Gesamtzeit:** ~3 Stunden (Optuna läuft parallel im Hintergrund)
