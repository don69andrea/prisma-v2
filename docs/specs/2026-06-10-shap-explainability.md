# Spec: SHAP Explainability Layer

**Issue:** #70 (to be created)
**Date:** 2026-06-10
**Author:** Andrea Petretta
**Status:** Planned

---

## Ziel

Jede ML-Prediction (OUTPERFORM / NEUTRAL / UNDERPERFORM) zeigt nicht nur das Label, sondern welche Quant-Faktoren die Entscheidung getrieben haben — via SHAP Waterfall Chart auf dem Factsheet. Beantwortet: *"Warum sagt PRISMA OUTPERFORM?"*

---

## Nicht-Ziele

- SHAP für andere Modelle (nur XGBoost Return Predictor)
- Global Feature Importance View (nur per-prediction, lokal)
- SHAP Beeswarm / Summary Plots
- Retraining-Trigger via SHAP Drift

---

## Architektur

### Backend

**`ml_prediction_service.py`** (erweitern):
- Nach `model.predict_proba()` sofort `shap.TreeExplainer(model).shap_values(X)` aufrufen
- Top-8 Features nach Absolutbetrag sortiert zurückgeben
- Kein separater API-Call — SHAP-Werte kommen im bestehenden Prediction-Response mit

**Schema `MLPredictionResponse`** (erweitern):
```python
class SHAPEntry(BaseModel):
    feature: str          # z.B. "roe_zscore"
    value: float          # SHAP-Wert (positiv = Richtung OUTPERFORM)
    feature_value: float  # Roher Feature-Wert (z.B. 0.18 für ROE)
    label: str            # Human-readable, z.B. "Return on Equity"

class MLPredictionResponse(BaseModel):
    # ... bestehende Felder ...
    shap_values: list[SHAPEntry]          # Top-8, sortiert nach |value|
    shap_expected_value: float            # Baseline (Modell-Durchschnitt)
```

**Dependency:** `shap>=0.45` zu `pyproject.toml` hinzufügen.

### API

Kein neuer Endpoint — bestehender `GET /api/v1/stocks/{ticker}/ml-prediction` gibt `shap_values` zusätzlich zurück.

### Frontend (Factsheet ML-Prediction Panel, Issue #59)

**SHAP Waterfall Chart:**
- Rein in SVG/React gebaut (keine externe Chart-Library)
- Layout: Baseline-Bar unten (`shap_expected_value`), dann gestapelte Balken pro Feature
- Grün (#00ff88 Neon) = positiver SHAP-Wert (pushed Richtung OUTPERFORM)
- Rot (#ff4466 Neon) = negativer SHAP-Wert (zieht Richtung UNDERPERFORM)
- Endwert-Bar oben = Predicted Score
- Tooltip on hover: Feature-Name + Wert + Erklärung

**Futuristische UX:**
- Glassmorphism-Container mit `backdrop-blur`
- Balken animieren beim Mount (Breite wächst von 0 → Endwert, 600ms ease-out)
- Neon-Glow auf Balken via `box-shadow` / SVG `filter: drop-shadow`
- Header: *"Why OUTPERFORM?"* mit Gradient-Text
- Badge: Konfidenz-Score als Neon-Ring-Chart (Donut, 40px)

---

## Datenfluss

```
Factsheet Page
  → GET /api/v1/stocks/{ticker}/ml-prediction
  → MLPredictionService.predict(ticker)
      → model.predict_proba(X)
      → TreeExplainer.shap_values(X)
      → SHAPEntry[] aufbauen
  ← MLPredictionResponse { signal, confidence, shap_values, shap_expected_value }
  → SHAPWaterfallChart component rendert
```

---

## Tests

- Unit: `test_ml_prediction_service.py` — `shap_values` im Response, korrekte Sortierung, Top-8 Limit
- Unit: SHAP-Werte summieren zu `(predicted_score - expected_value)` (SHAP-Additivitäts-Property)
- Frontend: Snapshot-Test der SVG-Ausgabe mit Mock-SHAP-Daten

---

## Akademischer Impact

Direkte Antwort auf *"Black Box"-Kritik* an ML-Systemen — zentrales Thema im BI-Modul. SHAP ist State-of-the-Art in Explainable AI (XAI) und zeigt, dass PRISMA nicht nur predicted, sondern begründet.
