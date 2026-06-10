# SHAP Explainability Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the ML prediction endpoint to return SHAP values and render a futuristic animated Waterfall Chart on the Factsheet.

**Architecture:** After `model.predict_proba()` in `MLPredictionService`, call `shap.TreeExplainer` to compute per-feature contributions. Return them in the API response alongside the existing prediction. On the frontend, extend `MLPanel.tsx` with an SVG-based `SHAPWaterfallChart` component.

**Tech Stack:** Python `shap>=0.45`, existing XGBoost model, Next.js SVG/CSS animations, Tailwind CSS.

---

## File Map

| Action | Path |
|--------|------|
| Modify | `pyproject.toml` — add `shap>=0.45` |
| Modify | `backend/domain/value_objects/ml_prediction.py` — add `shap_values`, `shap_expected_value` |
| Modify | `backend/application/services/ml_prediction_service.py` — add SHAP calculation |
| Modify | `backend/interfaces/rest/schemas/ml_predict.py` — add `SHAPEntry`, extend `MLPredictResponse` |
| Modify | `backend/interfaces/rest/routers/ml.py` — map SHAP fields |
| Modify | `backend/tests/unit/application/test_ml_prediction_service.py` — new tests |
| Modify | `frontend/lib/api/ml.ts` — add SHAP types |
| Create | `frontend/components/factsheet/SHAPWaterfallChart.tsx` |
| Modify | `frontend/components/factsheet/MLPanel.tsx` — integrate SHAP chart |

---

## Task 1: Add `shap` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add shap to pyproject.toml**

In `pyproject.toml`, in the `dependencies` list, add after `"scikit-learn>=1.4",`:
```toml
    "shap>=0.45",
```

- [ ] **Step 2: Install the dependency**

```bash
cd /path/to/prisma-v2
uv sync
```
Expected: resolves without conflict.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add shap>=0.45 for XAI explainability"
```

---

## Task 2: Extend `MLPrediction` value object

**Files:**
- Modify: `backend/domain/value_objects/ml_prediction.py`

- [ ] **Step 1: Write failing test**

In `backend/tests/unit/domain/` create `test_ml_prediction_shap.py`:
```python
"""Tests für MLPrediction SHAP-Erweiterung."""
import pytest
from backend.domain.value_objects.ml_prediction import MLPrediction, SHAPEntry
from datetime import date


def _make_prediction(**kwargs) -> MLPrediction:
    defaults = dict(
        ticker="NESN",
        snapshot_date=date(2026, 1, 1),
        predicted_class=2,
        signal="OUTPERFORM",
        prob_bottom=0.1,
        prob_mid=0.2,
        prob_top=0.7,
        confidence=0.7,
        model_type="xgboost",
        features={"roe_zscore": 1.2},
        shap_values=[SHAPEntry(feature="roe_zscore", value=0.3, feature_value=1.2, label="Return on Equity")],
        shap_expected_value=0.1,
    )
    defaults.update(kwargs)
    return MLPrediction(**defaults)


def test_shap_entry_fields():
    entry = SHAPEntry(feature="roe_zscore", value=0.3, feature_value=1.2, label="Return on Equity")
    assert entry.feature == "roe_zscore"
    assert entry.value == 0.3
    assert entry.feature_value == 1.2
    assert entry.label == "Return on Equity"


def test_ml_prediction_has_shap_fields():
    pred = _make_prediction()
    assert len(pred.shap_values) == 1
    assert pred.shap_expected_value == 0.1


def test_ml_prediction_shap_defaults_empty():
    """shap_values hat sinnvollen Default (leere Liste)."""
    pred = MLPrediction(
        ticker="NESN",
        snapshot_date=date(2026, 1, 1),
        predicted_class=2,
        signal="OUTPERFORM",
        prob_bottom=0.1,
        prob_mid=0.2,
        prob_top=0.7,
        confidence=0.7,
        model_type="xgboost",
        features={},
    )
    assert pred.shap_values == []
    assert pred.shap_expected_value == 0.0
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest backend/tests/unit/domain/test_ml_prediction_shap.py -v
```
Expected: `ImportError` or `TypeError` — `SHAPEntry` not yet defined.

- [ ] **Step 3: Implement `SHAPEntry` + extend `MLPrediction`**

Replace contents of `backend/domain/value_objects/ml_prediction.py`:
```python
"""Domain Value Object: ML Prediction — Ergebnis des Return-Predictor-Modells."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar


@dataclass(frozen=True)
class SHAPEntry:
    """Ein einzelner SHAP-Wert für ein Feature."""
    feature: str           # technischer Name, z.B. "roe_zscore"
    value: float           # SHAP-Wert (positiv = Richtung OUTPERFORM)
    feature_value: float   # Roher Feature-Wert
    label: str             # Human-readable, z.B. "Return on Equity"


@dataclass(frozen=True)
class MLPrediction:
    """Vorhersage des Return-Predictor-Modells für einen Ticker.

    predicted_class: 0=Bottom, 1=Mid, 2=Top Quartil (12M-Forward-Return)
    signal: "UNDERPERFORM" | "NEUTRAL" | "OUTPERFORM"
    probabilities: Wahrscheinlichkeit je Klasse (0–1, Summe ≈ 1)
    confidence: max(probabilities) als Konfidenz-Maß
    shap_values: Top-8 Feature-Contributions, sortiert nach |value|
    shap_expected_value: Modell-Baseline (Durchschnitt über Trainingsdaten)
    """

    ticker: str
    snapshot_date: date
    predicted_class: int
    signal: str
    prob_bottom: float
    prob_mid: float
    prob_top: float
    confidence: float
    model_type: str
    features: dict[str, float]
    shap_values: list[SHAPEntry] = field(default_factory=list)
    shap_expected_value: float = 0.0

    _CLASS_TO_SIGNAL: ClassVar[dict[int, str]] = {0: "UNDERPERFORM", 1: "NEUTRAL", 2: "OUTPERFORM"}

    @classmethod
    def signal_for_class(cls, predicted_class: int) -> str:
        return cls._CLASS_TO_SIGNAL.get(predicted_class, "NEUTRAL")
```

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest backend/tests/unit/domain/test_ml_prediction_shap.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/domain/value_objects/ml_prediction.py backend/tests/unit/domain/test_ml_prediction_shap.py
git commit -m "feat(domain): add SHAPEntry + shap_values to MLPrediction value object"
```

---

## Task 3: Add SHAP calculation to `MLPredictionService`

**Files:**
- Modify: `backend/application/services/ml_prediction_service.py`
- Modify: `backend/tests/unit/application/test_ml_prediction_service.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/unit/application/test_ml_prediction_service.py`:
```python
from backend.domain.value_objects.ml_prediction import SHAPEntry

# --- SHAP Tests ---

def _make_shap_explainer_mock(shap_array: list[list[float]]) -> MagicMock:
    import numpy as np
    explainer = MagicMock()
    # shap_values returns array of shape (n_samples, n_features) for one class
    # For multi-class XGBoost: list of 3 arrays. We use class 2 (OUTPERFORM).
    explainer.shap_values.return_value = [
        np.zeros_like(shap_array),
        np.zeros_like(shap_array),
        np.array(shap_array),
    ]
    explainer.expected_value = [0.05, 0.1, 0.15]
    return explainer


@pytest.mark.asyncio
async def test_predict_includes_shap_values() -> None:
    """predict() gibt shap_values zurück wenn Modell XGBoost ist."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()
    model = _make_mock_model(predicted_class=2)
    shap_values_raw = [[0.3, -0.1, 0.2, 0.05, -0.05, 0.15, 0.08, -0.02,
                        0.01, 0.0, 0.0, 0.0, 0.0]]
    explainer = _make_shap_explainer_mock(shap_values_raw)

    with (
        patch("backend.application.services.ml_prediction_service._load_model",
              return_value=(model, "xgboost")),
        patch("backend.application.services.ml_prediction_service._build_shap_entries",
              return_value=(
                  [SHAPEntry("roe_zscore", 0.3, 1.2, "Return on Equity")],
                  0.15,
              )),
    ):
        service = MLPredictionService(feature_service=feature_svc)
        result = await service.predict("NESN")

    assert result is not None
    assert len(result.shap_values) == 1
    assert result.shap_values[0].feature == "roe_zscore"
    assert result.shap_expected_value == 0.15


@pytest.mark.asyncio
async def test_predict_shap_empty_on_non_xgboost() -> None:
    """Bei model_type != xgboost/lightgbm: shap_values bleibt leer."""
    feature_svc = AsyncMock()
    feature_svc.build_features.return_value = _make_feature_vector()
    model = _make_mock_model(predicted_class=1)

    with patch("backend.application.services.ml_prediction_service._load_model",
               return_value=(model, "unknown")):
        service = MLPredictionService(feature_service=feature_svc)
        result = await service.predict("NESN")

    assert result is not None
    assert result.shap_values == []
    assert result.shap_expected_value == 0.0
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest backend/tests/unit/application/test_ml_prediction_service.py::test_predict_includes_shap_values backend/tests/unit/application/test_ml_prediction_service.py::test_predict_shap_empty_on_non_xgboost -v
```
Expected: FAIL — `_build_shap_entries` not defined.

- [ ] **Step 3: Implement SHAP calculation**

Replace full `backend/application/services/ml_prediction_service.py`:
```python
"""Application Service: ML Prediction — lädt Modell und gibt Vorhersage zurück."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from backend.application.services.ml_feature_service import MLFeatureService
from backend.domain.value_objects.ml_prediction import MLPrediction, SHAPEntry
from backend.domain.value_objects.ml_feature_vector import MLFeatureVector

_logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
_LATEST_MODEL = _MODELS_DIR / "return_predictor_latest.joblib"
_LATEST_META = _MODELS_DIR / "return_predictor_latest.json"

_model_cache: Any = None
_model_type_cache: str = "unknown"

_FEATURE_LABELS: dict[str, str] = {
    "quant_score": "Quant-Gesamtscore",
    "score_rendite": "Score Rendite",
    "score_sicherheit": "Score Sicherheit",
    "score_wachstum": "Score Wachstum",
    "score_substanz": "Score Substanz",
    "return_12m": "12M Return",
    "vol_30d": "30-Tage Volatilität",
    "rsi_14": "RSI (14)",
    "snb_rate": "SNB Leitzins",
    "chf_eur": "CHF/EUR Kurs",
}
_TOP_N_SHAP = 8


def _load_model() -> tuple[Any, str]:
    global _model_cache, _model_type_cache
    if _model_cache is not None:
        return _model_cache, _model_type_cache

    import joblib

    if not _LATEST_MODEL.exists():
        raise FileNotFoundError(
            f"Kein trainiertes Modell gefunden unter {_LATEST_MODEL}. "
            "Bitte zuerst `python scripts/train_return_predictor.py` ausführen."
        )

    _model_cache = joblib.load(_LATEST_MODEL)
    _model_type_cache = "unknown"

    import json

    if _LATEST_META.exists():
        with _LATEST_META.open() as f:
            meta = json.load(f)
        _model_type_cache = meta.get("model_type", "unknown")

    _logger.info("Return-Predictor geladen: %s (%s)", _LATEST_MODEL.name, _model_type_cache)
    return _model_cache, _model_type_cache


def _build_shap_entries(
    model: Any,
    x: np.ndarray,
    feature_names: list[str],
    features_dict: dict[str, float],
    predicted_class: int,
) -> tuple[list[SHAPEntry], float]:
    """Berechnet SHAP-Werte für den predicted_class und gibt Top-N zurück.

    Gibt leere Liste zurück wenn SHAP-Berechnung fehlschlägt.
    """
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        raw = explainer.shap_values(x)

        # XGBoost multi-class: raw ist Liste von 3 Arrays (eine pro Klasse)
        if isinstance(raw, list) and len(raw) > predicted_class:
            class_shap = raw[predicted_class][0]
            expected_value = float(
                explainer.expected_value[predicted_class]
                if hasattr(explainer.expected_value, "__len__")
                else explainer.expected_value
            )
        else:
            # Binary oder Single-Output
            class_shap = np.array(raw).flatten()
            expected_value = float(
                explainer.expected_value
                if not hasattr(explainer.expected_value, "__len__")
                else explainer.expected_value[0]
            )

        # Sortieren nach Absolutbetrag, Top-N nehmen
        indexed = sorted(
            enumerate(class_shap), key=lambda t: abs(t[1]), reverse=True
        )[:_TOP_N_SHAP]

        entries = [
            SHAPEntry(
                feature=feature_names[i],
                value=round(float(v), 4),
                feature_value=round(features_dict.get(feature_names[i], 0.0), 4),
                label=_FEATURE_LABELS.get(feature_names[i], feature_names[i]),
            )
            for i, v in indexed
        ]
        return entries, round(expected_value, 4)

    except Exception:
        _logger.warning("SHAP-Berechnung fehlgeschlagen — wird übersprungen", exc_info=True)
        return [], 0.0


class MLPredictionService:
    """Führt Inferenz mit dem Return-Predictor-Modell durch."""

    def __init__(self, feature_service: MLFeatureService | None = None) -> None:
        self._feature_service = feature_service or MLFeatureService()

    async def predict(self, ticker: str) -> MLPrediction | None:
        """Gibt eine ML-Vorhersage mit SHAP-Erklärung zurück.

        Returns None wenn Features nicht verfügbar.
        Raises FileNotFoundError wenn kein Modell vorhanden.
        """
        feature_vector = await self._feature_service.build_features(ticker)
        if feature_vector is None:
            return None

        model, model_type = _load_model()
        features_dict = feature_vector.to_feature_dict()
        feature_names = list(feature_vector.FEATURE_NAMES)
        x = np.array([[features_dict[n] for n in feature_names]], dtype=np.float32)

        pred_class = int(model.predict(x)[0])
        try:
            probas = model.predict_proba(x)[0]
            prob_bottom = float(probas[0])
            prob_mid = float(probas[1])
            prob_top = float(probas[2])
        except (AttributeError, IndexError):
            prob_bottom = 1.0 if pred_class == 0 else 0.0
            prob_mid = 1.0 if pred_class == 1 else 0.0
            prob_top = 1.0 if pred_class == 2 else 0.0

        confidence = max(prob_bottom, prob_mid, prob_top)

        # SHAP nur für Tree-Modelle (XGBoost/LightGBM)
        if model_type in ("xgboost", "lightgbm"):
            shap_entries, shap_expected = _build_shap_entries(
                model, x, feature_names, features_dict, pred_class
            )
        else:
            shap_entries, shap_expected = [], 0.0

        return MLPrediction(
            ticker=ticker.upper(),
            snapshot_date=date.today(),
            predicted_class=pred_class,
            signal=MLPrediction.signal_for_class(pred_class),
            prob_bottom=round(prob_bottom, 4),
            prob_mid=round(prob_mid, 4),
            prob_top=round(prob_top, 4),
            confidence=round(confidence, 4),
            model_type=model_type,
            features=features_dict,
            shap_values=shap_entries,
            shap_expected_value=shap_expected,
        )
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest backend/tests/unit/application/test_ml_prediction_service.py -v
```
Expected: all PASS (including existing tests).

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/ml_prediction_service.py backend/tests/unit/application/test_ml_prediction_service.py
git commit -m "feat(ml): calculate SHAP values in MLPredictionService — Top-8 per prediction"
```

---

## Task 4: Extend API schema + router

**Files:**
- Modify: `backend/interfaces/rest/schemas/ml_predict.py`
- Modify: `backend/interfaces/rest/routers/ml.py`

- [ ] **Step 1: Update `MLPredictResponse` schema**

Replace `backend/interfaces/rest/schemas/ml_predict.py`:
```python
"""Pydantic-Schemas für ML Prediction API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MLPredictRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Swiss ticker (z.B. NESN)")


class SHAPEntryResponse(BaseModel):
    feature: str
    value: float
    feature_value: float
    label: str


class MLPredictResponse(BaseModel):
    ticker: str
    snapshot_date: date
    predicted_class: int = Field(..., ge=0, le=2)
    signal: str = Field(..., description="UNDERPERFORM | NEUTRAL | OUTPERFORM")
    prob_bottom: float = Field(..., ge=0.0, le=1.0)
    prob_mid: float = Field(..., ge=0.0, le=1.0)
    prob_top: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_type: str
    features: dict[str, float]
    shap_values: list[SHAPEntryResponse] = Field(default_factory=list)
    shap_expected_value: float = 0.0
```

- [ ] **Step 2: Update router to map SHAP fields**

In `backend/interfaces/rest/routers/ml.py`, replace the return statement in `predict()`:
```python
    return MLPredictResponse(
        ticker=result.ticker,
        snapshot_date=result.snapshot_date,
        predicted_class=result.predicted_class,
        signal=result.signal,
        prob_bottom=result.prob_bottom,
        prob_mid=result.prob_mid,
        prob_top=result.prob_top,
        confidence=result.confidence,
        model_type=result.model_type,
        features=result.features,
        shap_values=[
            SHAPEntryResponse(
                feature=e.feature,
                value=e.value,
                feature_value=e.feature_value,
                label=e.label,
            )
            for e in result.shap_values
        ],
        shap_expected_value=result.shap_expected_value,
    )
```

Also add the import at the top of `ml.py`:
```python
from backend.interfaces.rest.schemas.ml_predict import MLPredictRequest, MLPredictResponse, SHAPEntryResponse
```

- [ ] **Step 3: Commit**

```bash
git add backend/interfaces/rest/schemas/ml_predict.py backend/interfaces/rest/routers/ml.py
git commit -m "feat(api): extend ML prediction response with SHAP fields"
```

---

## Task 5: Frontend — API types + `SHAPWaterfallChart`

**Files:**
- Modify: `frontend/lib/api/ml.ts`
- Create: `frontend/components/factsheet/SHAPWaterfallChart.tsx`

- [ ] **Step 1: Update `ml.ts` types**

Replace `frontend/lib/api/ml.ts`:
```typescript
import { apiFetch } from './client';

export type MLSignal = 'OUTPERFORM' | 'NEUTRAL' | 'UNDERPERFORM';

export interface SHAPEntry {
  feature: string;
  value: number;        // positive = pushes toward OUTPERFORM
  feature_value: number;
  label: string;
}

export interface MLPredictResponse {
  ticker: string;
  snapshot_date: string;
  predicted_class: number;
  signal: MLSignal;
  prob_bottom: number;
  prob_mid: number;
  prob_top: number;
  confidence: number;
  model_type: string;
  features: Record<string, number>;
  shap_values: SHAPEntry[];
  shap_expected_value: number;
}

export async function getMLPrediction(ticker: string): Promise<MLPredictResponse> {
  return apiFetch<MLPredictResponse>('/api/v1/ml/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
  });
}
```

- [ ] **Step 2: Create `SHAPWaterfallChart.tsx`**

Create `frontend/components/factsheet/SHAPWaterfallChart.tsx`:
```tsx
'use client';

import { useEffect, useRef } from 'react';
import type { SHAPEntry } from '@/lib/api/ml';

interface Props {
  shapValues: SHAPEntry[];
  expectedValue: number;
  signal: 'OUTPERFORM' | 'NEUTRAL' | 'UNDERPERFORM';
}

const MAX_BAR_WIDTH = 180; // px

export function SHAPWaterfallChart({ shapValues, expectedValue, signal }: Props) {
  const barsRef = useRef<(HTMLDivElement | null)[]>([]);

  // Animate bars on mount
  useEffect(() => {
    barsRef.current.forEach((bar, i) => {
      if (!bar) return;
      bar.style.width = '0px';
      bar.style.transition = `width 600ms ease-out ${i * 60}ms`;
      requestAnimationFrame(() => {
        const target = bar.dataset.targetWidth ?? '0px';
        bar.style.width = target;
      });
    });
  }, [shapValues]);

  if (!shapValues.length) return null;

  const maxAbs = Math.max(...shapValues.map((e) => Math.abs(e.value)), 0.01);

  const signalGradient =
    signal === 'OUTPERFORM'
      ? 'from-purple-900/40 to-emerald-950/40'
      : signal === 'UNDERPERFORM'
      ? 'from-purple-900/40 to-red-950/40'
      : 'from-purple-900/40 to-slate-900/40';

  return (
    <div className={`rounded-xl border border-purple-500/20 bg-gradient-to-br ${signalGradient} backdrop-blur-sm p-4 space-y-3`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold tracking-widest text-purple-300 uppercase">
          Why {signal}?
        </h4>
        <span className="text-[10px] text-slate-500">
          baseline {expectedValue > 0 ? '+' : ''}{expectedValue.toFixed(3)}
        </span>
      </div>

      {/* Bars */}
      <div className="space-y-2">
        {shapValues.map((entry, i) => {
          const pct = Math.abs(entry.value) / maxAbs;
          const barPx = Math.round(pct * MAX_BAR_WIDTH);
          const isPos = entry.value >= 0;

          return (
            <div key={entry.feature} className="flex items-center gap-2 group">
              {/* Label */}
              <span className="w-36 shrink-0 text-[11px] text-slate-300 truncate text-right">
                {entry.label}
              </span>

              {/* Bar container — positive right, negative left */}
              <div className="flex-1 flex items-center">
                {isPos ? (
                  <>
                    <div className="w-px h-4 bg-slate-600" />
                    <div
                      ref={(el) => { barsRef.current[i] = el; }}
                      data-target-width={`${barPx}px`}
                      className="h-3 rounded-r-full"
                      style={{
                        width: 0,
                        background: 'linear-gradient(90deg, #00ff8866, #00ff88)',
                        boxShadow: '0 0 8px #00ff8866',
                      }}
                    />
                  </>
                ) : (
                  <div className="flex items-center justify-end" style={{ width: `${barPx + 1}px` }}>
                    <div
                      ref={(el) => { barsRef.current[i] = el; }}
                      data-target-width={`${barPx}px`}
                      className="h-3 rounded-l-full"
                      style={{
                        width: 0,
                        background: 'linear-gradient(270deg, #ff446666, #ff4466)',
                        boxShadow: '0 0 8px #ff446666',
                      }}
                    />
                    <div className="w-px h-4 bg-slate-600" />
                  </div>
                )}
              </div>

              {/* Value */}
              <span
                className={`w-14 shrink-0 text-[11px] tabular-nums font-medium ${
                  isPos ? 'text-emerald-400' : 'text-red-400'
                }`}
              >
                {isPos ? '+' : ''}{entry.value.toFixed(3)}
              </span>

              {/* Tooltip on hover */}
              <div className="hidden group-hover:block absolute z-10 mt-8 rounded-lg bg-slate-900 border border-slate-700 p-2 text-xs text-slate-300 pointer-events-none shadow-xl">
                <strong>{entry.label}</strong>: {entry.feature_value.toFixed(3)}
                <br />
                SHAP: {isPos ? '+' : ''}{entry.value.toFixed(4)}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-slate-600 pt-1 border-t border-slate-800">
        SHAP — Shapley Additive Explanations
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/ml.ts frontend/components/factsheet/SHAPWaterfallChart.tsx
git commit -m "feat(frontend): add SHAPWaterfallChart component with neon animations"
```

---

## Task 6: Integrate SHAP chart into `MLPanel.tsx`

**Files:**
- Modify: `frontend/components/factsheet/MLPanel.tsx`

- [ ] **Step 1: Update `MLPanel.tsx`**

Replace the full file `frontend/components/factsheet/MLPanel.tsx`:
```tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { BrainCircuit, Sparkles } from 'lucide-react';

import { getMLPrediction, type MLSignal } from '@/lib/api/ml';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { SHAPWaterfallChart } from './SHAPWaterfallChart';

const SIGNAL_CONFIG: Record<MLSignal, { variant: 'success' | 'warning' | 'outline'; label: string; glow: string }> = {
  OUTPERFORM:   { variant: 'success',  label: 'Outperform',   glow: 'shadow-[0_0_20px_rgba(0,255,136,0.3)]' },
  NEUTRAL:      { variant: 'warning',  label: 'Neutral',      glow: 'shadow-[0_0_20px_rgba(255,170,0,0.3)]' },
  UNDERPERFORM: { variant: 'outline',  label: 'Underperform', glow: 'shadow-[0_0_20px_rgba(255,68,102,0.3)]' },
};

function ConfidenceRing({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const r = 16;
  const circumference = 2 * Math.PI * r;
  const dash = (pct / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center w-10 h-10">
      <svg width="40" height="40" className="-rotate-90">
        <circle cx="20" cy="20" r={r} fill="none" stroke="#334155" strokeWidth="3" />
        <circle
          cx="20" cy="20" r={r} fill="none"
          stroke="#a855f7"
          strokeWidth="3"
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round"
          style={{ filter: 'drop-shadow(0 0 4px #a855f7)' }}
        />
      </svg>
      <span className="absolute text-[9px] font-bold text-purple-300">{pct}%</span>
    </div>
  );
}

function ProbBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

interface Props {
  ticker: string;
}

export function MLPanel({ ticker }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['ml-predict', ticker],
    queryFn: () => getMLPrediction(ticker),
    retry: false,
  });

  const cfg = data ? SIGNAL_CONFIG[data.signal] ?? SIGNAL_CONFIG.NEUTRAL : null;

  return (
    <Card className={cn('transition-shadow duration-500', cfg?.glow)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-muted-foreground" />
          ML-Prediction
          {data?.shap_values.length ? (
            <Sparkles className="h-3 w-3 text-purple-400 ml-auto" />
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <div className="h-20 rounded-lg bg-muted animate-pulse" />}
        {isError && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Kein ML-Modell verfügbar oder keine Marktdaten.
          </p>
        )}
        {data && cfg && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant={cfg.variant}>{cfg.label}</Badge>
              <div className="flex items-center gap-2">
                <ConfidenceRing confidence={data.confidence} />
                <span className="text-xs text-muted-foreground">
                  {new Date(data.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' })}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <ProbBar label="Outperform (Top 25%)" value={data.prob_top}    color="bg-emerald-500" />
              <ProbBar label="Neutral (Mid 50%)"    value={data.prob_mid}    color="bg-amber-500" />
              <ProbBar label="Underperform (Bot 25%)" value={data.prob_bottom} color="bg-slate-400" />
            </div>
            {data.shap_values.length > 0 && (
              <SHAPWaterfallChart
                shapValues={data.shap_values}
                expectedValue={data.shap_expected_value}
                signal={data.signal}
              />
            )}
            <p className="text-[10px] text-muted-foreground border-t pt-2">
              ML-Modell ({data.model_type}) — keine Anlageberatung.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/factsheet/MLPanel.tsx
git commit -m "feat(frontend): integrate SHAPWaterfallChart into MLPanel with confidence ring"
```

---

## Task 7: Lint + full test run

- [ ] **Step 1: Lint Backend**

```bash
ruff check backend/
ruff format --check backend/
```
Expected: no errors.

- [ ] **Step 2: Full unit test run**

```bash
pytest backend/tests/unit -q
```
Expected: all pass.

- [ ] **Step 3: TypeScript type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Final commit if any lint fixes applied**

```bash
git add -p
git commit -m "chore: lint fixes after SHAP implementation"
```
