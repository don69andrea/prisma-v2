---
phase: 04-v4-4-rag-sentiment-planned
plan: "06"
subsystem: signal-director
tags: [sentiment, veto, size-scaling, tdd, d-06]
dependency_graph:
  requires: ["04-01", "04-02", "04-05"]
  provides: ["sentiment-veto-in-synthesize", "downside-only-size-scaling"]
  affects: ["backend/application/agents/signal_director.py"]
tech_stack:
  added: []
  patterns: ["get_settings() singleton (C-03)", "sentiment_enabled guard (C-04)", "downside-only scaling (D-06)"]
key_files:
  created: []
  modified:
    - backend/application/agents/signal_director.py
    - backend/config.py
    - backend/tests/integration/test_agent_mandatory_suite.py
decisions:
  - "sentiment_enabled defaults to False (C-04) — zero behavior change until backtest (04-07) justifies enabling"
  - "Veto uses get_settings() singleton (C-03), never Settings() directly"
  - "Downside-only: positive score hat keinerlei Amplifikationseffekt (Pitfall 7)"
  - "Veto blockt nur BUY; SELL wird nie hochgestuft; HOLD ist idempotent"
metrics:
  duration: "5 min"
  completed: "2026-06-22"
  tasks_completed: 2
  files_modified: 3
---

# Phase 04 Plan 06: Sentiment Veto + Downside-only Size Scaling Summary

Sentiment-Veto und downside-only Size-Scaling in `SignalDirector._synthesize()` eingebaut (TDD), beide hinter `SENTIMENT_ENABLED` (default false, C-04) per D-06. Mandatory-Suite mit 4 neuen Tests auf 11 Tests erweitert, alle grün.

## Tasks

| # | Name | Status | Commit |
|---|------|--------|--------|
| 1 | _synthesize() veto + downside-only size scaling (D-06) | DONE | 82c5c90 |
| 2 | Extend mandatory suite with 4 D-06 sentiment-wiring tests | DONE | 82c5c90 |

## What Was Built

### backend/config.py
- `sentiment_enabled: bool = False` zur `Settings`-Klasse hinzugefügt (C-04 default-off)

### backend/application/agents/signal_director.py
- `from backend.config import get_settings` Import hinzugefügt (C-03)
- Veto-Block nach `action = _action_from_engine(engine_signal.action)`:
  ```python
  _settings = get_settings()
  if _settings.sentiment_enabled and senti.veto:
      action = "HOLD"
  ```
- Size-Scaling nach dem No-Shorting-Clamp:
  ```python
  if _settings.sentiment_enabled and senti.score < 0:
      size_factor = size_factor * (1 + senti.score * 0.3)
      size_factor = max(0.0, size_factor)
  ```

### backend/tests/integration/test_agent_mandatory_suite.py
- 4 neue Tests (D-06 #8-11):
  - `test_d06_8_sentiment_veto_enabled_buy_becomes_hold` — SENTIMENT_ENABLED=true + veto=True + BUY → HOLD
  - `test_d06_9_sentiment_veto_disabled_no_override` — SENTIMENT_ENABLED=false + veto=True → BUY bleibt BUY
  - `test_d06_10_sentiment_negative_score_reduces_size` — score=-0.5 → size * 0.85
  - `test_d06_11_sentiment_positive_score_no_amplification` — score=+0.5 → size unverändert

## Verification

```
pytest backend/tests/integration/test_agent_mandatory_suite.py -x -q
11 passed in 0.15s
```

Alle 7 bestehenden D-06-Tests plus 4 neue = 11 Tests grün.

## Deviations from Plan

Keine — Plan exakt wie beschrieben ausgeführt.

## Threat Flags

Keine neuen Sicherheits-relevanten Surfaces eingeführt. `sentiment_enabled=False` default verhindert unbeabsichtigte Aktivierung.

## Self-Check: PASSED

- [x] `backend/application/agents/signal_director.py` enthält `get_settings()`, `senti.veto`, `senti.score * 0.3`
- [x] Keine direkte `Settings()`-Instantiierung hinzugefügt
- [x] `pytest backend/tests/integration/test_agent_mandatory_suite.py -x` = 11 Tests grün
- [x] Bestehende 7 D-06-Tests alle noch vorhanden und grün
- [x] Commit 82c5c90 vorhanden
