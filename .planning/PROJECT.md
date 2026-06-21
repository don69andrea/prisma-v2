# PRISMA V4 — Project Context

**Project Code:** PRISMA  
**Repo:** don69andrea/prisma-v2  
**Created:** 2026-06-21  
**Stack:** Python 3.13 / FastAPI / PostgreSQL+pgvector / Next.js 14 / Anthropic Claude

## What We're Building

PRISMA V4 is an **explainable 3-layer signal system** for crypto spot trading (BUY/HOLD/SELL).
Pivot from V3's failed return-prediction ML to evidence-based architecture:

- **Layer 1 (WHAT):** Cross-sectional momentum + on-chain factor ranking
- **Layer 2 (WHEN):** Indicator consensus (MA+MACD+RSI vote) + meta-labeling filter
- **Layer 3 (HOW MUCH):** Vol-forecast ML → vol-targeting sizing

On top: Agentic AI layer (TradingAgents-style: Analyst → Bull/Bear → Risk → Director).

## Key Decisions (locked from V3 learnings)

- **SELL = cash only** (no shorting ever)
- **Crypto spot is core universe** (BTC/ETH/Top-10); SMI stays as display-only
- **LLMs NEVER compute numbers** — all numbers from deterministic Signal Engine or tools
- **Pydantic on every agent output** — no LLM freetext to frontend
- **Strict walk-forward only** — no purged CV, no in-sample results as success
- **Coverage ≥ 80%** — CI gate, non-negotiable
- **Feature-branches + PRs** — Branch Protection active, no direct push to main/develop

## PoC Evidence (docs/research/)

- BTC: Calmar 1.31 vs exposure-matched 0.60 — timing adds real value
- ETH: Calmar 0.57 vs 0.29 — same pattern
- Combo vote (2-of-3 MA+MACD+RSI): BTC Sharpe 1.50, Calmar 1.38
- Vol OOS-R²: BTC +52%, ETH +31% — vol IS learnable

## Key Docs

- `docs/PRISMA_V35_MASTERPLAN.md` — Vision + PoC evidence
- `docs/PRISMA_V4_PROJEKTPLAN.md` — Full V4 plan
- `docs/PRISMA_V4_AGENTS.md` — Agent architecture
- `docs/PRISMA_V4-1_PHASENPLAN_Signal-Engine.md` — Phase V4-1 spec + contract
- `docs/research/` — PoC scripts + results
- `docs/AGENTS.md` — Repo rules (Spec-First, Test-First, Pydantic, CI)
- `CLAUDE.md` — Claude Code conventions
