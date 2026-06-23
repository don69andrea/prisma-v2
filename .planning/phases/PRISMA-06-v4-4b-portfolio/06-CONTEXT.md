---
phase: 06-v4-4b-portfolio
goal: Portfolio-level allocation over the PIT Top-10 crypto universe with honest walk-forward backtest
branch: feat/v4-4b-portfolio
v4_phase: V4-4b
---

# Phase 06 — V4-4b: Portfolio-Layer

## Ziel

Portfolio-Allokation über das dynamische Top-10-Krypto-Universum:
- Vol-Targeting auf Portfolio-Ebene
- Korrelations-aware Caps (max 40% pro Coin)
- Gesamt-Exposure-Limit (max 80%)
- Drawdown-Bremse auf Portfolio-Ebene
- Ehrlicher Walk-Forward-Backtest gegen Buy&Hold-Korb + exposure-matched

## Universum-Kriterium (POINT-IN-TIME, zentrales Design-Prinzip)

Ein Coin ist ab dem **ersten Tag eligible**, an dem sein **trailing-30-Tage-Durchschnitt
des Dollar-Volumens** (close × volume) **≥ $100M** ist.

**BTC/ETH sind _ALWAYS_IN** — keine Mindest-Vol-Anforderung.

Fallback (nur wenn PIT zu Datenproblemen führt): fixer Stichtag, dann ehrlich als
"Membership-Snapshot, Vor-Stichtag-Ergebnisse selektionsbehaftet" gekennzeichnet.

## Erfolgskriterien (Честно — kein Tuning)

- Portfolio-Sharpe > equal-weight Buy&Hold-Korb UND > exposure-matched Basket.
- Portfolio-MaxDD < Buy&Hold MaxDD des Korbs.
- Negative Ergebnisse werden genauso ehrlich dokumentiert.

## Plan (5 Steps)

| Plan | Inhalt | Human-Verify |
|------|--------|-------------|
| 06-01 | `backend/application/backtest/universe.py` — PIT Membership | nein |
| 06-02 | `backend/application/backtest/portfolio.py` — Allocator | nein |
| 06-03 | `backend/application/backtest/portfolio_walkforward.py` | nein |
| 06-04 | REST `GET /api/v1/backtest/portfolio` + `PortfolioBacktestReport` schema | nein |
| 06-05 | `docs/PRISMA_V4_FORTSCHRITT.md` — V4-4b Eintrag + **Human-Verify** | **JA — STOP** |

## Qualitäts-Gates

- Keine Parameter-Optimierung (Kostenrate, Caps, Vol-Target sind feste Konstanten).
- Look-Ahead-Guard: position an t+1 nutzt nur Daten ≤ t.
- PIT-Guard: coin nicht vor `first_eligible_date` im Backtest.
- Coverage ≥ 80 % für neue Dateien.
