# PRISMA V4 — Roadmap

**Project:** PRISMA  
**Updated:** 2026-06-21

## Phases

### Phase 1: V4-1 Signal-Engine
**Goal:** Deterministic, tested Signal Engine for Top-10 crypto universe that reproduces the PoC finding (strategy beats exposure-matched baseline on Sharpe AND Calmar in walk-forward, net costs).  
**Branch:** `feat/v4-1-signal-engine`  
**Spec:** `docs/PRISMA_V4-1_PHASENPLAN_Signal-Engine.md`  
**Status:** in-progress

Includes:
- Crypto data seed (Top-10 OHLCV + On-Chain + Fear&Greed)
- `backend/application/signals/` (indicators, consensus, vol_forecast, sizing, factors, signal_service)
- `backend/application/backtest/` (walkforward + guards)
- 3 read-only REST endpoints
- All A7 test cases green, Coverage ≥ 80%

### Phase 2: V4-2 Meta-Labeling (planned)
Triple-Barrier / Trend-Scan labels + classifier "take trade now?". Tested vs always-trade baseline.

### Phase 3: V4-3 Agentic Layer (planned)
TechnicalAnalyst, OnChain, Sentiment, Bull/Bear, Risk, SignalDirector agents.

### Phase 4: V4-4 RAG Sentiment (planned)
News/Fear&Greed → Sentiment feature/veto in Layer 2.

### Phase 5: V4-5 UI (planned)
Signal dashboard, explainability panel, indicator charts, backtest view.

### Phase 6: V4-6 Begleitdoku (planned)
Negative + positive findings document for the professor.
