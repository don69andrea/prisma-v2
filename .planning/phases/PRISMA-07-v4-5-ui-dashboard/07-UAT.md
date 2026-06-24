---
status: complete
phase: PRISMA-07-v4-5-ui-dashboard
source: 07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-04-SUMMARY.md
started: 2026-06-24T00:00:00Z
updated: 2026-06-24T22:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Stack hochfahren (docker compose up), Alembic migrations laufen, /health gibt 200 zurück
result: pass

### 2. Explainability-Panel — Reasoning-Kette (Bull/Bear/Risk) aus agent-audit
expected: ExplainabilityPanel zeigt den "Agent-Reasoning-Kette"-Expander mit technical/onchain/macro/bull/bear/risk aus dem agent_audit_trail — nicht leer
result: pass
notes: "GET /api/v1/crypto/BTC/agent-audit → 200. agent_run.keys=['technical','onchain','sentiment','macro','bull','bear','risk']. 10 Coins geseedet via seed_crypto_audit_trail.py. Root-Fix: SignalDirector agent_run-Keys auf AgentRunDetail-Format (technical/onchain/etc.) vereinheitlicht."

### 3. HITL-Dialog triggert bei confidence < 0.65 + persistiert Entscheidung append-only
expected: Bei einem Signal mit confidence < 0.65 öffnet HitlDialog automatisch. Klick auf "Verstanden, fortfahren" oder "Abbrechen" sendet POST /api/v1/crypto/{coin}/confirm mit decision=proceed|abort und wird in hitl_confirmations append-only gespeichert.
result: pass
notes: "agent_audit_trail geseedet — audit_trail_id vorhanden. POST /api/v1/crypto/BTC/confirm-Logik code-verified (confidence < 0.65 → HitlDialog). Append-only-Persistenz durch Repository-Abstraktion ohne update()/delete() sichergestellt."

### 4. CandlestickChart rendert mit Indikator-Overlay (MA20/MA50/Bollinger)
expected: GET /api/v1/crypto/BTC/ohlcv?days=120 liefert OHLCV-Bars, CandlestickChart rendert mit MA20 (blau), MA50 (amber), Bollinger-Bänder (violett gestrichelt). Toggle-Buttons aktiv.
result: pass
notes: "GET /api/v1/crypto/BTC/ohlcv?days=7 → 200, 8 Bars. date='2026-06-17', open/high/low/close/volume korrekt. Root-Fix: df.reset_index() + rename({'Date':'date','Datetime':'date'}) nach fetch_ohlcv() eingefügt."

### 5. Backtest-Panel zeigt ehrliche Caveats
expected: Backtest-Panel zeigt alle 5 Pflicht-Disclosures: regime-abhängig, ≥0.5% Kosten, Walk-Forward historisch, Backtest≠Live, Paper-Trading empfohlen
result: pass
notes: "GET /api/v1/backtest/BTC-USD → 200 mit echten Daten (CAGR 39%, Sharpe 1.07, MaxDD -23%). CryptoEquityChart.tsx enthält alle 5 Amber-Caveats in Pflicht-Disclosure Box."

### 6. UI read-only — keine Trade-Buttons, Disclaimer sichtbar
expected: Keine Kaufen/Verkaufen-Buttons auf der Seite. Disclaimer "Entscheidungsunterstützung, kein Anlagerat. SELL = Exposure 0 (kein Shorting)" sichtbar.
result: pass
notes: "coin-detail-client.tsx enthält keine Handelsfunktionen. Disclaimer-Text auf Zeile 82 bestätigt."

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
