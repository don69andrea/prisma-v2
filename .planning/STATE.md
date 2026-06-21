# PRISMA — Project State

**Last updated:** 2026-06-21  
**Current phase:** 1 (V4-1 Signal-Engine)  
**Status:** Planning

## What's Done

- ✅ V3 negative finding documented (return prediction fails)
- ✅ PoC proof: Vol learnable (OOS-R² BTC 52%), combo-vote beats exposure-matched baseline
- ✅ V4 docs committed to docs/ (MASTERPLAN, PROJEKTPLAN, AGENTS, V4-1 PHASENPLAN)
- ✅ Codebase mapped (.planning/codebase/ — 7 docs, 883 lines)
- ✅ GSD project initialized (PROJECT.md, REQUIREMENTS.md, ROADMAP.md)

## Active Branch

`docs/prisma-v4-plan` (merged to develop as PR #292)

## Next Step

`/gsd-plan-phase 1` → Build Phase V4-1 Signal-Engine

## Key Context

- Highest migration: 0022 (need 0037-0039 for crypto tables)
- No `backend/application/signals/` yet — full new build
- `signal_aggregation_service.py` and `signal_validation_service.py` exist for SMI — must NOT break
- `steuer_agent.py` = gold standard pattern for new agents
- yfinance_swiss.py = extension point for crypto adapter
