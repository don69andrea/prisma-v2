# Monte Carlo 3a Retirement Simulator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/portfolio/simulator` page where users enter a 3a portfolio + monthly contribution and see 10'000 GBM simulations as a futuristic fan-chart with P5/P50/P95 bands.

**Architecture:** New `MonteCarloService` in Application layer fetches volatility via `YFinanceSwissAdapter` and ML-predicted returns via `MLPredictionService`, runs vectorized GBM simulations with NumPy, exposes `POST /api/v1/portfolio/monte-carlo`. Frontend renders a custom SVG fan-chart with animated draw-on effect.

**Tech Stack:** Python, NumPy (vectorized GBM), FastAPI, Next.js, SVG animations, Tailwind CSS.

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/application/services/monte_carlo_service.py` |
| Create | `backend/interfaces/rest/schemas/monte_carlo.py` |
| Modify | `backend/interfaces/rest/routers/portfolio.py` — add route |
| Modify | `backend/interfaces/rest/app.py` — no change needed (portfolio router already registered) |
| Create | `backend/tests/unit/application/test_monte_carlo_service.py` |
| Create | `frontend/lib/api/montecarlo.ts` |
| Create | `frontend/components/portfolio/MonteCarloFanChart.tsx` |
| Create | `frontend/app/portfolio/simulator/page.tsx` |
| Create | `frontend/app/portfolio/simulator/SimulatorClient.tsx` |

---

## Task 1: `MonteCarloService` — Core Logic

**Files:**
- Create: `backend/application/services/monte_carlo_service.py`
- Create: `backend/tests/unit/application/test_monte_carlo_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/application/test_monte_carlo_service.py`:
```python
"""Unit-Tests für MonteCarloService."""

from __future__ import annotations

import pytest
import numpy as np
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.unit

from backend.application.services.monte_carlo_service import (
    MonteCarloService,
    MonteCarloInput,
    HoldingWeight,
    MonteCarloResult,
)


def _make_input(**kwargs) -> MonteCarloInput:
    defaults = dict(
        holdings=[HoldingWeight(ticker="NESN.SW", weight=0.6), HoldingWeight(ticker="NOVN.SW", weight=0.4)],
        monthly_contribution=588.0,
        years=30,
        initial_value=0.0,
        n_simulations=100,  # small for tests
    )
    defaults.update(kwargs)
    return MonteCarloInput(**defaults)


def _make_service() -> MonteCarloService:
    """Service mit gemockten externen Adaptern."""
    return MonteCarloService()


@pytest.mark.asyncio
async def test_simulate_returns_result_shape() -> None:
    """Result enthält p5/p50/p95 mit korrekter Länge."""
    svc = _make_service()
    inp = _make_input(years=5, n_simulations=50)

    with (
        patch.object(svc, "_fetch_return_params", new_callable=AsyncMock,
                     return_value=(
                         np.array([0.0005, 0.0004]),
                         np.array([0.012, 0.011]),
                         np.array([[1.0, 0.4], [0.4, 1.0]]),
                     )),
    ):
        result = await svc.simulate(inp)

    assert isinstance(result, MonteCarloResult)
    assert len(result.p5) == 5 * 12
    assert len(result.p50) == 5 * 12
    assert len(result.p95) == 5 * 12
    assert len(result.final_distribution) == 50
    assert 0.0 <= result.prob_positive_return <= 1.0
    assert result.contribution_total == pytest.approx(588.0 * 5 * 12)
    assert result.months == 60


@pytest.mark.asyncio
async def test_p50_above_p5_below_p95() -> None:
    """P5 <= P50 <= P95 für jeden Zeitpunkt."""
    svc = _make_service()
    inp = _make_input(years=3, n_simulations=200)

    with patch.object(svc, "_fetch_return_params", new_callable=AsyncMock,
                      return_value=(
                          np.array([0.0004]),
                          np.array([0.01]),
                          np.array([[1.0]]),
                      )):
        inp_single = _make_input(
            holdings=[HoldingWeight(ticker="NESN.SW", weight=1.0)],
            years=3,
            n_simulations=200,
        )
        result = await svc.simulate(inp_single)

    for p5, p50, p95 in zip(result.p5, result.p50, result.p95):
        assert p5 <= p50 <= p95


@pytest.mark.asyncio
async def test_weights_must_sum_to_one() -> None:
    """Gewichte die nicht 1.0 ergeben → ValueError."""
    svc = _make_service()
    inp = MonteCarloInput(
        holdings=[HoldingWeight(ticker="NESN.SW", weight=0.6)],
        monthly_contribution=500.0,
        years=5,
        initial_value=0.0,
        n_simulations=50,
    )
    with pytest.raises(ValueError, match="weights"):
        await svc.simulate(inp)


@pytest.mark.asyncio
async def test_prob_positive_return_bounds() -> None:
    """prob_positive_return liegt immer zwischen 0 und 1."""
    svc = _make_service()
    inp = _make_input(years=1, n_simulations=100)

    with patch.object(svc, "_fetch_return_params", new_callable=AsyncMock,
                      return_value=(
                          np.array([0.0003, 0.0002]),
                          np.array([0.015, 0.013]),
                          np.array([[1.0, 0.3], [0.3, 1.0]]),
                      )):
        result = await svc.simulate(inp)

    assert 0.0 <= result.prob_positive_return <= 1.0
    assert 0.0 <= result.prob_500k <= 1.0
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest backend/tests/unit/application/test_monte_carlo_service.py -v
```
Expected: `ImportError` — module not yet created.

- [ ] **Step 3: Implement `MonteCarloService`**

Create `backend/application/services/monte_carlo_service.py`:
```python
"""Application Service: Monte Carlo 3a Retirement Simulator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import numpy as np

_logger = logging.getLogger(__name__)

_TARGET_500K = 500_000.0


@dataclass(frozen=True)
class HoldingWeight:
    ticker: str
    weight: float


@dataclass(frozen=True)
class MonteCarloInput:
    holdings: list[HoldingWeight]
    monthly_contribution: float
    years: int
    initial_value: float = 0.0
    n_simulations: int = 10_000


@dataclass(frozen=True)
class MonteCarloResult:
    p5: list[float]
    p50: list[float]
    p95: list[float]
    final_distribution: list[float]
    prob_positive_return: float
    prob_500k: float
    contribution_total: float
    months: int


class MonteCarloService:
    """Simuliert 3a-Wealth-Paths via Geometric Brownian Motion."""

    async def simulate(self, inp: MonteCarloInput) -> MonteCarloResult:
        """Führt N Simulationen durch und gibt Percentile-Pfade zurück."""
        total_weight = sum(h.weight for h in inp.holdings)
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(
                f"Gewichte müssen 1.0 ergeben, ist: {total_weight:.3f}"
            )

        mu_arr, sigma_arr, corr_matrix = await self._fetch_return_params(inp.holdings)
        return _run_gbm(inp, mu_arr, sigma_arr, corr_matrix)

    async def _fetch_return_params(
        self, holdings: list[HoldingWeight]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Holt historische Returns + ML-Predictions für jeden Ticker.

        Returns (mu_daily, sigma_daily, correlation_matrix).
        Fällt auf konservative Defaults zurück wenn Daten fehlen.
        """
        from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
        from backend.application.services.ml_prediction_service import MLPredictionService

        adapter = YFinanceSwissAdapter()
        ml_service = MLPredictionService()
        n = len(holdings)

        mu_list: list[float] = []
        sigma_list: list[float] = []
        returns_matrix: list[np.ndarray] = []

        for h in holdings:
            hist_mu, hist_sigma, hist_returns = await _fetch_ticker_params(adapter, h.ticker)
            ml_mu = await _fetch_ml_mu(ml_service, h.ticker)
            # Blend: 50% historisch, 50% ML-Prediction
            blended_mu = 0.5 * hist_mu + 0.5 * ml_mu
            mu_list.append(blended_mu)
            sigma_list.append(hist_sigma)
            returns_matrix.append(hist_returns)

        # Korrelationsmatrix aus historischen Returns
        if n > 1:
            min_len = min(len(r) for r in returns_matrix)
            trimmed = np.column_stack([r[-min_len:] for r in returns_matrix])
            corr_matrix = np.corrcoef(trimmed, rowvar=False)
        else:
            corr_matrix = np.array([[1.0]])

        return np.array(mu_list), np.array(sigma_list), corr_matrix


async def _fetch_ticker_params(
    adapter: object, ticker: str
) -> tuple[float, float, np.ndarray]:
    """Holt historische Tagesrenditen und berechnet mu/sigma."""
    try:
        import yfinance as yf

        raw = await asyncio.to_thread(yf.download, ticker, period="1y", progress=False)
        if raw.empty or "Close" not in raw.columns:
            raise ValueError("Keine Daten")
        prices = raw["Close"].dropna().values
        daily_returns = np.diff(np.log(prices))
        mu = float(np.mean(daily_returns))
        sigma = float(np.std(daily_returns))
        return mu, max(sigma, 0.005), daily_returns
    except Exception:
        _logger.warning("Keine Marktdaten für %s — verwende Defaults", ticker)
        rng = np.random.default_rng(42)
        return 0.0003, 0.012, rng.normal(0.0003, 0.012, 252)


async def _fetch_ml_mu(ml_service: object, ticker: str) -> float:
    """ML-Predicted annualisierter Return → täglicher Return."""
    try:
        result = await ml_service.predict(ticker)  # type: ignore[attr-defined]
        if result is None:
            return 0.0003
        # signal → annualisierter Return: OUTPERFORM=10%, NEUTRAL=5%, UNDERPERFORM=0%
        annual_map = {"OUTPERFORM": 0.10, "NEUTRAL": 0.05, "UNDERPERFORM": 0.0}
        annual = annual_map.get(result.signal, 0.05)
        return annual / 252
    except Exception:
        return 0.0003


def _run_gbm(
    inp: MonteCarloInput,
    mu_arr: np.ndarray,
    sigma_arr: np.ndarray,
    corr_matrix: np.ndarray,
) -> MonteCarloResult:
    """Vectorized GBM — alle Simulationen als Matrix."""
    n_assets = len(inp.holdings)
    n_months = inp.years * 12
    n_sim = inp.n_simulations
    weights = np.array([h.weight for h in inp.holdings])
    dt = 21  # trading days per month

    # Cholesky für korrelierte Zufallszahlen
    try:
        L = np.linalg.cholesky(corr_matrix)
    except np.linalg.LinAlgError:
        L = np.eye(n_assets)

    # Monatliche GBM-Parameter
    mu_m = mu_arr * dt
    sigma_m = sigma_arr * np.sqrt(dt)

    # Simulation: shape (n_sim, n_months, n_assets)
    rng = np.random.default_rng()
    z_raw = rng.standard_normal((n_sim, n_months, n_assets))
    z_corr = z_raw @ L.T  # Korrelation einbringen

    # Log-Returns pro Monat
    log_ret = (mu_m - 0.5 * sigma_m ** 2) + sigma_m * z_corr  # (n_sim, n_months, n_assets)

    # Portfolio-Wert Pfade
    portfolio = np.zeros((n_sim, n_months))
    current_value = np.full(n_sim, inp.initial_value)

    for t in range(n_months):
        asset_factor = np.exp(log_ret[:, t, :])          # (n_sim, n_assets)
        portfolio_return = asset_factor @ weights          # (n_sim,)
        current_value = current_value * portfolio_return + inp.monthly_contribution
        portfolio[:, t] = current_value

    # Percentile-Pfade
    p5 = np.percentile(portfolio, 5, axis=0).tolist()
    p50 = np.percentile(portfolio, 50, axis=0).tolist()
    p95 = np.percentile(portfolio, 95, axis=0).tolist()
    final = portfolio[:, -1]

    contribution_total = inp.monthly_contribution * n_months
    prob_positive = float(np.mean(final > contribution_total))
    prob_500k = float(np.mean(final > _TARGET_500K))

    return MonteCarloResult(
        p5=[round(v, 2) for v in p5],
        p50=[round(v, 2) for v in p50],
        p95=[round(v, 2) for v in p95],
        final_distribution=[round(float(v), 2) for v in final],
        prob_positive_return=round(prob_positive, 4),
        prob_500k=round(prob_500k, 4),
        contribution_total=round(contribution_total, 2),
        months=n_months,
    )
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest backend/tests/unit/application/test_monte_carlo_service.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/monte_carlo_service.py backend/tests/unit/application/test_monte_carlo_service.py
git commit -m "feat(application): MonteCarloService — GBM 10k simulations with Cholesky correlation"
```

---

## Task 2: API Schema + Route

**Files:**
- Create: `backend/interfaces/rest/schemas/monte_carlo.py`
- Modify: `backend/interfaces/rest/routers/portfolio.py`

- [ ] **Step 1: Create schema**

Create `backend/interfaces/rest/schemas/monte_carlo.py`:
```python
"""Pydantic-Schemas für Monte Carlo API."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class HoldingWeightRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=12)
    weight: float = Field(..., gt=0.0, le=1.0)


class MonteCarloRequest(BaseModel):
    holdings: list[HoldingWeightRequest] = Field(..., min_length=1, max_length=10)
    monthly_contribution: float = Field(588.0, ge=0.0, le=10_000.0)
    years: int = Field(30, ge=1, le=40)
    initial_value: float = Field(0.0, ge=0.0)
    n_simulations: int = Field(10_000, ge=100, le=50_000)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "MonteCarloRequest":
        total = sum(h.weight for h in self.holdings)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Gewichte müssen 1.0 ergeben (ist {total:.3f})")
        return self


class MonteCarloResponse(BaseModel):
    p5: list[float]
    p50: list[float]
    p95: list[float]
    final_distribution: list[float]
    prob_positive_return: float
    prob_500k: float
    contribution_total: float
    months: int
```

- [ ] **Step 2: Add route to `portfolio.py`**

At the bottom of `backend/interfaces/rest/routers/portfolio.py`, add:
```python
from backend.application.services.monte_carlo_service import (
    MonteCarloService,
    HoldingWeight,
    MonteCarloInput,
)
from backend.interfaces.rest.schemas.monte_carlo import MonteCarloRequest, MonteCarloResponse


@router.post(
    "/monte-carlo",
    response_model=MonteCarloResponse,
    summary="Monte Carlo 3a Retirement Simulator",
    description=(
        "Simuliert N Wealth-Paths (GBM + Korrelationsmatrix) für ein Portfolio "
        "über 1–40 Jahre. Gibt P5/P50/P95-Bänder zurück. "
        "Keine Anlageberatung."
    ),
)
async def monte_carlo(req: MonteCarloRequest) -> MonteCarloResponse:
    svc = MonteCarloService()
    inp = MonteCarloInput(
        holdings=[HoldingWeight(ticker=h.ticker, weight=h.weight) for h in req.holdings],
        monthly_contribution=req.monthly_contribution,
        years=req.years,
        initial_value=req.initial_value,
        n_simulations=req.n_simulations,
    )
    try:
        result = await svc.simulate(inp)
    except ValueError as exc:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return MonteCarloResponse(
        p5=result.p5,
        p50=result.p50,
        p95=result.p95,
        final_distribution=result.final_distribution,
        prob_positive_return=result.prob_positive_return,
        prob_500k=result.prob_500k,
        contribution_total=result.contribution_total,
        months=result.months,
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/interfaces/rest/schemas/monte_carlo.py backend/interfaces/rest/routers/portfolio.py
git commit -m "feat(api): POST /api/v1/portfolio/monte-carlo endpoint"
```

---

## Task 3: Frontend API + Fan Chart Component

**Files:**
- Create: `frontend/lib/api/montecarlo.ts`
- Create: `frontend/components/portfolio/MonteCarloFanChart.tsx`

- [ ] **Step 1: Create `montecarlo.ts`**

Create `frontend/lib/api/montecarlo.ts`:
```typescript
import { apiFetch } from './client';

export interface HoldingWeightInput {
  ticker: string;
  weight: number;
}

export interface MonteCarloRequest {
  holdings: HoldingWeightInput[];
  monthly_contribution: number;
  years: number;
  initial_value?: number;
  n_simulations?: number;
}

export interface MonteCarloResponse {
  p5: number[];
  p50: number[];
  p95: number[];
  final_distribution: number[];
  prob_positive_return: number;
  prob_500k: number;
  contribution_total: number;
  months: number;
}

export async function runMonteCarlo(req: MonteCarloRequest): Promise<MonteCarloResponse> {
  return apiFetch<MonteCarloResponse>('/api/v1/portfolio/monte-carlo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
```

- [ ] **Step 2: Create `MonteCarloFanChart.tsx`**

Create `frontend/components/portfolio/MonteCarloFanChart.tsx`:
```tsx
'use client';

import { useEffect, useRef } from 'react';

interface Props {
  p5: number[];
  p50: number[];
  p95: number[];
  contributionLine: number[];
  years: number;
}

const W = 600;
const H = 320;
const PAD = { top: 20, right: 20, bottom: 40, left: 70 };
const INNER_W = W - PAD.left - PAD.right;
const INNER_H = H - PAD.top - PAD.bottom;

function scaleX(i: number, total: number) {
  return PAD.left + (i / (total - 1)) * INNER_W;
}

function scaleY(v: number, minV: number, maxV: number) {
  return PAD.top + INNER_H - ((v - minV) / (maxV - minV)) * INNER_H;
}

function toPath(values: number[], minV: number, maxV: number) {
  return values
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${scaleX(i, values.length).toFixed(1)},${scaleY(v, minV, maxV).toFixed(1)}`)
    .join(' ');
}

function toArea(top: number[], bottom: number[], minV: number, maxV: number) {
  const forward = top.map(
    (v, i) => `${i === 0 ? 'M' : 'L'}${scaleX(i, top.length).toFixed(1)},${scaleY(v, minV, maxV).toFixed(1)}`
  );
  const backward = [...bottom]
    .reverse()
    .map(
      (v, i) => `L${scaleX(bottom.length - 1 - i, bottom.length).toFixed(1)},${scaleY(v, minV, maxV).toFixed(1)}`
    );
  return [...forward, ...backward, 'Z'].join(' ');
}

function formatCHF(v: number) {
  if (v >= 1_000_000) return `CHF ${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `CHF ${(v / 1_000).toFixed(0)}k`;
  return `CHF ${v.toFixed(0)}`;
}

export function MonteCarloFanChart({ p5, p50, p95, contributionLine, years }: Props) {
  const pathRef = useRef<SVGPathElement>(null);

  useEffect(() => {
    if (!pathRef.current) return;
    const len = pathRef.current.getTotalLength();
    pathRef.current.style.strokeDasharray = `${len}`;
    pathRef.current.style.strokeDashoffset = `${len}`;
    pathRef.current.style.transition = 'stroke-dashoffset 1.8s ease-in-out';
    requestAnimationFrame(() => {
      if (pathRef.current) pathRef.current.style.strokeDashoffset = '0';
    });
  }, [p50]);

  const allValues = [...p5, ...p95, ...contributionLine];
  const minV = Math.min(...allValues, 0);
  const maxV = Math.max(...allValues) * 1.05;

  const n = p50.length;
  const yTicks = 5;
  const xLabelStep = Math.max(1, Math.floor(years / 5));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id="fanGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.1" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Y grid lines */}
      {Array.from({ length: yTicks }).map((_, i) => {
        const v = minV + ((maxV - minV) * i) / (yTicks - 1);
        const y = scaleY(v, minV, maxV);
        return (
          <g key={i}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke="#1e293b" strokeWidth="1" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize="10" fill="#475569">
              {formatCHF(v)}
            </text>
          </g>
        );
      })}

      {/* X axis labels */}
      {Array.from({ length: Math.ceil(years / xLabelStep) + 1 }).map((_, i) => {
        const yr = i * xLabelStep;
        if (yr > years) return null;
        const monthIdx = Math.min(yr * 12, n - 1);
        const x = scaleX(monthIdx, n);
        return (
          <text key={i} x={x} y={H - PAD.bottom + 16} textAnchor="middle" fontSize="10" fill="#475569">
            {yr}J
          </text>
        );
      })}

      {/* Fan area P5–P95 */}
      <path d={toArea(p95, p5, minV, maxV)} fill="url(#fanGrad)" />

      {/* P5 line */}
      <path d={toPath(p5, minV, maxV)} fill="none" stroke="#4f46e5" strokeWidth="1" strokeOpacity="0.6" strokeDasharray="4 3" />

      {/* P95 line */}
      <path d={toPath(p95, minV, maxV)} fill="none" stroke="#7c3aed" strokeWidth="1" strokeOpacity="0.6" strokeDasharray="4 3" />

      {/* Contribution baseline */}
      <path
        d={toPath(contributionLine, minV, maxV)}
        fill="none"
        stroke="#475569"
        strokeWidth="1.5"
        strokeDasharray="6 4"
      />

      {/* P50 median — animated draw-on */}
      <path
        ref={pathRef}
        d={toPath(p50, minV, maxV)}
        fill="none"
        stroke="white"
        strokeWidth="2.5"
        filter="url(#glow)"
      />

      {/* Legend */}
      <g transform={`translate(${PAD.left + 8}, ${PAD.top + 8})`}>
        <line x1="0" x2="20" y1="6" y2="6" stroke="white" strokeWidth="2.5" />
        <text x="24" y="10" fontSize="9" fill="#cbd5e1">Median (P50)</text>
        <rect x="0" y="18" width="20" height="8" fill="url(#fanGrad)" rx="2" />
        <text x="24" y="27" fontSize="9" fill="#94a3b8">P5–P95 Band</text>
        <line x1="0" x2="20" y1="40" y2="40" stroke="#475569" strokeWidth="1.5" strokeDasharray="6 4" />
        <text x="24" y="44" fontSize="9" fill="#64748b">Einzahlungen</text>
      </g>
    </svg>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/montecarlo.ts frontend/components/portfolio/MonteCarloFanChart.tsx
git commit -m "feat(frontend): MonteCarloFanChart SVG with animated draw-on P50 line"
```

---

## Task 4: Simulator Page

**Files:**
- Create: `frontend/app/portfolio/simulator/page.tsx`
- Create: `frontend/app/portfolio/simulator/SimulatorClient.tsx`

- [ ] **Step 1: Create page**

Create `frontend/app/portfolio/simulator/page.tsx`:
```tsx
import type { Metadata } from 'next';
import { SimulatorClient } from './SimulatorClient';

export const metadata: Metadata = {
  title: 'PRISMA — 3a Retirement Simulator',
};

export default function SimulatorPage() {
  return <SimulatorClient />;
}
```

- [ ] **Step 2: Create `SimulatorClient.tsx`**

Create `frontend/app/portfolio/simulator/SimulatorClient.tsx`:
```tsx
'use client';

import { useState, useCallback } from 'react';
import { Loader2, Sparkles, TrendingUp } from 'lucide-react';

import { runMonteCarlo, type MonteCarloResponse, type HoldingWeightInput } from '@/lib/api/montecarlo';
import { MonteCarloFanChart } from '@/components/portfolio/MonteCarloFanChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const DEFAULT_HOLDINGS: HoldingWeightInput[] = [
  { ticker: 'NESN.SW', weight: 0.4 },
  { ticker: 'NOVN.SW', weight: 0.3 },
  { ticker: 'ABBN.SW', weight: 0.3 },
];

function formatCHF(v: number) {
  if (v >= 1_000_000) return `CHF ${(v / 1_000_000).toFixed(2)}M`;
  return `CHF ${v.toLocaleString('de-CH', { maximumFractionDigits: 0 })}`;
}

export function SimulatorClient() {
  const [holdings, setHoldings] = useState<HoldingWeightInput[]>(DEFAULT_HOLDINGS);
  const [contribution, setContribution] = useState(588);
  const [years, setYears] = useState(30);
  const [result, setResult] = useState<MonteCarloResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalWeight = holdings.reduce((s, h) => s + h.weight, 0);

  const handleSimulate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runMonteCarlo({ holdings, monthly_contribution: contribution, years });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler bei der Simulation');
    } finally {
      setLoading(false);
    }
  }, [holdings, contribution, years]);

  const updateWeight = (i: number, w: number) => {
    setHoldings((prev) => prev.map((h, idx) => (idx === i ? { ...h, weight: w } : h)));
  };
  const updateTicker = (i: number, t: string) => {
    setHoldings((prev) => prev.map((h, idx) => (idx === i ? { ...h, ticker: t.toUpperCase() } : h)));
  };

  const contributionLine = result
    ? Array.from({ length: result.months }, (_, i) => contribution * (i + 1))
    : [];

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-purple-400" />
            3a Retirement Simulator
          </h1>
          <p className="text-slate-400 text-sm">
            10'000 Monte-Carlo-Simulationen · Geometric Brownian Motion · Swiss 3a
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* LEFT: Input Panel */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="bg-slate-900/80 border-slate-800 backdrop-blur-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-slate-300">Portfolio</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {holdings.map((h, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      value={h.ticker}
                      onChange={(e) => updateTicker(i, e.target.value)}
                      className="w-28 font-mono text-sm bg-slate-800 border-slate-700"
                      placeholder="NESN.SW"
                    />
                    <input
                      type="range"
                      min={0.05}
                      max={0.9}
                      step={0.05}
                      value={h.weight}
                      onChange={(e) => updateWeight(i, parseFloat(e.target.value))}
                      className="flex-1 accent-purple-500"
                    />
                    <span className="w-10 text-right text-sm tabular-nums text-purple-300">
                      {Math.round(h.weight * 100)}%
                    </span>
                  </div>
                ))}
                <div className={cn('text-xs text-right', Math.abs(totalWeight - 1) > 0.01 ? 'text-red-400' : 'text-emerald-400')}>
                  Gesamt: {Math.round(totalWeight * 100)}%
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/80 border-slate-800 backdrop-blur-sm">
              <CardContent className="pt-4 space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Monatliche Einzahlung</span>
                    <span className="font-medium text-purple-300">CHF {contribution}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={2000}
                    step={50}
                    value={contribution}
                    onChange={(e) => setContribution(Number(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                  <div className="text-[10px] text-slate-600">Swiss 3a Max: CHF 7'056 / Jahr</div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Anlagehorizont</span>
                    <span className="font-medium text-purple-300">{years} Jahre</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={40}
                    step={1}
                    value={years}
                    onChange={(e) => setYears(Number(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                  <div className="flex justify-between text-[10px] text-slate-600">
                    <span>1J</span><span>10J</span><span>20J</span><span>30J</span><span>40J</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Button
              onClick={handleSimulate}
              disabled={loading || Math.abs(totalWeight - 1) > 0.01}
              className="w-full bg-purple-600 hover:bg-purple-500 text-white font-semibold py-3 relative overflow-hidden group"
              style={{ boxShadow: loading ? '0 0 20px rgba(168,85,247,0.5)' : undefined }}
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" />Simuliere...</>
              ) : (
                <><Sparkles className="h-4 w-4 mr-2" />Jetzt simulieren</>
              )}
              <div className="absolute inset-0 bg-white/10 scale-x-0 group-hover:scale-x-100 transition-transform origin-left" />
            </Button>

            {error && <p className="text-sm text-red-400 text-center">{error}</p>}
          </div>

          {/* RIGHT: Chart + Stats */}
          <div className="lg:col-span-3 space-y-4">
            {result ? (
              <>
                {/* Stats */}
                <div className="grid grid-cols-2 gap-3">
                  <Card className="bg-slate-900/60 border-emerald-500/20" style={{ boxShadow: '0 0 20px rgba(16,185,129,0.1)' }}>
                    <CardContent className="pt-4 space-y-1">
                      <p className="text-xs text-slate-500">Median-Endvermögen</p>
                      <p className="text-2xl font-bold text-emerald-400 tabular-nums">
                        {formatCHF(result.p50[result.p50.length - 1])}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="bg-slate-900/60 border-purple-500/20" style={{ boxShadow: '0 0 20px rgba(168,85,247,0.1)' }}>
                    <CardContent className="pt-4 space-y-1">
                      <p className="text-xs text-slate-500">P95-Endvermögen</p>
                      <p className="text-2xl font-bold text-purple-400 tabular-nums">
                        {formatCHF(result.p95[result.p95.length - 1])}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge
                    className="bg-emerald-950 border-emerald-500/40 text-emerald-300 text-xs"
                  >
                    {Math.round(result.prob_positive_return * 100)}% Chance positiver Return
                  </Badge>
                  <Badge
                    className="bg-purple-950 border-purple-500/40 text-purple-300 text-xs"
                  >
                    {Math.round(result.prob_500k * 100)}% Chance CHF 500k+
                  </Badge>
                  <Badge className="bg-slate-800 border-slate-700 text-slate-400 text-xs">
                    Einzahlungen total: {formatCHF(result.contribution_total)}
                  </Badge>
                </div>

                {/* Fan Chart */}
                <Card className="bg-slate-900/60 border-slate-800">
                  <CardContent className="pt-4">
                    <MonteCarloFanChart
                      p5={result.p5}
                      p50={result.p50}
                      p95={result.p95}
                      contributionLine={contributionLine}
                      years={years}
                    />
                  </CardContent>
                </Card>
              </>
            ) : (
              <Card className="bg-slate-900/40 border-slate-800 border-dashed h-64 flex items-center justify-center">
                <div className="text-center text-slate-600">
                  <TrendingUp className="h-10 w-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Simulation starten →</p>
                </div>
              </Card>
            )}
          </div>
        </div>

        <p className="text-[10px] text-slate-700 text-center">
          Simulationsergebnisse basieren auf historischen Daten und ML-Prognosen. Keine Anlageberatung. PRISMA V2.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add simulator link to nav**

In `frontend/app/nav-links.tsx`, find the portfolio nav section and add:
```tsx
{ href: '/portfolio/simulator', label: '3a Simulator' },
```
(Exact insertion depends on current nav structure — find the portfolio section and append.)

- [ ] **Step 4: Commit**

```bash
git add frontend/app/portfolio/simulator/ frontend/app/nav-links.tsx
git commit -m "feat(frontend): /portfolio/simulator — Monte Carlo 3a fan-chart page"
```

---

## Task 5: Lint + Test

- [ ] **Step 1: Backend lint**

```bash
ruff check backend/
ruff format --check backend/
```

- [ ] **Step 2: Full unit tests**

```bash
pytest backend/tests/unit -q
```
Expected: all pass.

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
