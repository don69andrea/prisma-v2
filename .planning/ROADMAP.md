# PRISMA V4 — Roadmap

**Project:** PRISMA  
**Updated:** 2026-06-23

## Phases

### Phase 1: V4-1 Signal-Engine

**Goal:** Deterministic, tested Signal Engine for Top-10 crypto universe that reproduces the PoC finding (strategy beats exposure-matched baseline on Sharpe AND Calmar in walk-forward, net costs).  
**Branch:** `feat/v4-1-signal-engine`  
**Spec:** `docs/PRISMA_V4-1_PHASENPLAN_Signal-Engine.md`  
**Status:** in-progress  
**Plans:** 7 plans

Plans:

- [ ] 01-01-PLAN.md — Wave 1a: Crypto universe + OHLCV seed
- [ ] 01-02-PLAN.md — Wave 1b+1c: On-chain + Fear&Greed adapters
- [ ] 01-03-PLAN.md — Wave 2a: Indicators + 2-of-3 consensus (test-first)
- [ ] 01-04-PLAN.md — Wave 2b+2c: Factors + walk-forward vol forecast
- [ ] 01-05-PLAN.md — Wave 3: Vol-targeting sizing + SignalVector service
- [ ] 01-06-PLAN.md — Wave 4: Strict walk-forward backtest engine
- [ ] 01-07-PLAN.md — Wave 5: Read-only REST API (3 endpoints)

Includes:

- Crypto data seed (Top-10 OHLCV + On-Chain + Fear&Greed)
- `backend/application/signals/` (indicators, consensus, vol_forecast, sizing, factors, signal_service)
- `backend/application/backtest/` (walkforward + guards)
- 3 read-only REST endpoints
- All A7 test cases green, Coverage ≥ 80%

### Phase 2: V4-2 Meta-Labeling

**Goal:** Binary meta-classifier ("take trade now / skip") that filters the V4-1 consensus signal, with an honest walk-forward comparison against the always-trade baseline (negative finding is a valid result).
**Branch:** `feat/v4-2-meta-labeling`
**Status:** planned
**Plans:** 4 plans

Plans:
**Wave 1**

- [ ] 02-01-PLAN.md — Wave A: Triple-Barrier + Trend-Scan labels + shift-safe meta features (TDD)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 02-02-PLAN.md — Wave B: Meta-classifier (LogReg + LGBM fallback) + embargoed walk-forward (TDD)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 02-03-PLAN.md — Wave C: walkforward.py meta_filter param + MetaLabelReport schema (TDD)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 02-04-PLAN.md — Wave D: GET /api/v1/signals/meta-label/{coin} + coverage gate ≥ 80%

### Phase 3: V4-3 Agentic Layer

**Goal:** LLM Agentic Layer on top of the deterministic Signal Engine — six interpreting/debating agents (Technical, OnChain, Sentiment-stub, MacroRegime, Bull/Bear, Risk) plus a hybrid-orchestrated SignalDirector that synthesizes a Pydantic `TradeSignal`, persists every run to an immutable audit trail, and is exposed via `GET /api/v1/agent-signal/{coin}`. Agents interpret/explain but compute nothing (iron rule); all 7 §6/D-06 mandatory tests green, coverage ≥ 80%.
**Branch:** `feat/v4-3-agentic-layer`
**Spec:** `docs/PRISMA_V4_AGENTS.md`
**Status:** planned
**Plans:** 6/6 plans complete

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Agent Pydantic schemas (agent_schemas.py) + schema tests (TDD)

**Wave 2** *(blocked on Wave 1)*

- [x] 03-02-PLAN.md — Migration 0041 + AgentAuditTrail ORM + append-only repository (TDD)

**Wave 3** *(blocked on Wave 1)*

- [x] 03-03-PLAN.md — Four Analyst agents: Technical, OnChain, Sentiment-stub (real F&G), MacroRegime (TDD)

**Wave 4** *(blocked on Waves 1+3)*

- [x] 03-04-PLAN.md — Bull/Bear Research + RiskAgent via Claude Tool-Use (state-from-tool, no-shorting) (TDD)

**Wave 5** *(blocked on Waves 1-4)*

- [x] 03-05-PLAN.md — SignalDirector hybrid orchestration + fallback + HITL checkpoint + audit persist (TDD)

**Wave 6** *(blocked on Waves 1-5)*

- [x] 03-06-PLAN.md — GET /api/v1/agent-signal/{coin} + all 7 mandatory tests + coverage gate ≥ 80% (TDD)

### Phase 4: V4-4 RAG Sentiment

**Goal:** Upgrade `SentimentAnalystAgent` from the Fear&Greed-only V4-3 stub to a real Krypto-News-RAG system: CryptoPanic articles ingested into the existing pgvector corpus, retrieved per-coin, interpreted by the LLM for `news_surprise` only (§0 Iron Rule), with score and veto computed deterministically in Python. Sentiment feeds `TradeSignal` as a downside-only size feature and a HOLD veto, both behind `SENTIMENT_ENABLED` (default false), and a 2× walk-forward backtest measures the impact honestly (negative/neutral finding is valid — D-08).
**Branch:** `feat/v4-4-rag-sentiment`
**Spec:** `docs/PRISMA_V4_AGENTS.md` §3.3 + `.planning/phases/PRISMA-04-v4-4-rag-sentiment-planned/04-CONTEXT.md` (D-01..D-08)
**Status:** planned
**Plans:** 4/7 plans executed

Plans:
**Wave 1** *(blockers + RED test stubs — runs first, blocks everything)*

- [x] 04-01-PLAN.md — Domain/repo/schema/config blockers: _VALID_SOURCES + NewsRetrievalResult.url + find_nearest TTL + SentimentLLMOutput + sentiment_enabled (TDD)
- [x] 04-02-PLAN.md — Migration 0042 (widen source VARCHAR) + all Wave-0 RED test stubs

**Wave 2** *(blocked on Wave 1)*

- [x] 04-03-PLAN.md — CryptoPanicAdapter: free-API JSON → RawCryptoPanicArticle, retry/backoff, []-on-malformed (TDD)

**Wave 3** *(blocked on Wave 2)*

- [x] 04-04-PLAN.md — NewsIngestionService.ingest_cryptopanic(): source=CRYPTOPANIC, votes in chunk metadata, 7-day TTL, dedup (TDD)

**Wave 4** *(blocked on Waves 1-3)*

- [ ] 04-05-PLAN.md — SentimentAnalystAgent body: RAG + D-03 score + LLM news_surprise + D-05 veto + sources; RAG prompt rewrite (TDD)

**Wave 5** *(blocked on Wave 4)*

- [ ] 04-06-PLAN.md — SignalDirector._synthesize() veto→HOLD + downside-only size scaling behind SENTIMENT_ENABLED + 4 mandatory tests (TDD)

**Wave 6** *(blocked on Waves 4-5)*

- [ ] 04-07-PLAN.md — compare_sentiment_backtest.py 2× walk-forward + honest FORTSCHRITT reporting (human-verify)

### Phase 5: V4-4c Robustness & Stress-Test

**Goal:** Ehrliche Robustheitsprüfung des V4-1-Edge. KEINE neuen Features. Harness-Skript + Report in docs/PRISMA_V4_FORTSCHRITT.md. 4 Stress-Dimensionen: Kosten-Sensitivität, Regime-Splits, Volles Universum, Parameter-Stabilität.
**Branch:** `feat/v4-4c-robustness`
**Status:** planned
**Plans:** 1/3 plans executed

Plans:
**Wave 1** *(standalone harness — no dependencies)*

- [x] 05-01-PLAN.md — scripts/robustness_check.py: 4 stress dimensions + Rich console tables

**Wave 2** *(blocked on Wave 1)*

- [ ] 05-02-PLAN.md — backend/tests/unit/application/test_robustness_harness.py: 7 deterministic test classes (TDD)

**Wave 3** *(blocked on Waves 1+2, human-verify)*

- [ ] 05-03-PLAN.md — docs/PRISMA_V4_FORTSCHRITT.md: V4-4c section with real numbers + Edge-Klassifikation (human-verify)

### Phase 6: V4-5 UI (planned)

Signal dashboard, explainability panel, indicator charts, backtest view.

### Phase 7: V4-6 Begleitdoku (planned)

Negative + positive findings document for the professor.
