# PRISMA V4 — Requirements

**Source:** docs/PRISMA_V4_PROJEKTPLAN.md + docs/PRISMA_V35_MASTERPLAN.md  
**Date:** 2026-06-21

## Functional Requirements

1. **Signal Engine** — deterministic, tested, no LLM numbers
   - Layer 1: Cross-sectional momentum ranking + on-chain health score per coin
   - Layer 2: MA/MACD/RSI/Bollinger consensus vote (2-of-3) → BUY/HOLD/SELL
   - Layer 3: Vol-forecast ML → vol-targeting sizing factor
   - Output: `SignalVector` (Pydantic) per coin with action, size_factor, sub_scores

2. **Backtesting** — strict walk-forward, exposure-matched baseline, netto costs
   - Expanding-window walk-forward (no purged CV)
   - Mandatory baselines: buy&hold + exposure-matched
   - Net costs: 0.1% per trade
   - Output: `BacktestReport` with Sharpe/Calmar/MaxDD + equity curve

3. **Crypto Universe** — Top-10 (BTC/ETH/SOL/BNB/XRP/ADA/AVAX/DOGE/LINK/DOT)
   - OHLCV history since 2017 (yfinance + CryptoDataDownload fallback)
   - On-chain data (Coin Metrics Community: MVRV-Z, realized cap, active addr, netflow)
   - Fear & Greed Index (alternative.me, historical)

4. **REST API** — 3 read-only endpoints
   - GET /api/v1/signals — current signals for all coins
   - GET /api/v1/signals/{coin} — detail with sub_scores
   - GET /api/v1/backtest/{coin} — backtest report

## Non-Functional Requirements

- Coverage ≥ 80% (CI gate)
- No LLM in signal computation (deterministic only)
- SELL = cash (never negative exposure, no shorting)
- Look-ahead guard: Signal@t uses only data ≤ t-1
- Pydantic on all public interfaces
- Branch Protection: feature-branch + PR, CI green before merge

## Out of Scope (this phase)

- LLM agents (V4-3)
- UI/Frontend (V4-5)
- News-RAG features (V4-4)
- SMI/3a changes
- Live order execution
