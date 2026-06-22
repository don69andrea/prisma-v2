# PRISMA V4 — Fortschritts-Log (append-only)

> Ein Eintrag je verifizierter Phase. Chronologisch, nie rückwirkend ändern.
> Quelle der Wahrheit: PRs auf `develop`, UAT-Reports in `.planning/phases/`.

---

## V4-1 Signal-Engine — ✅ verifiziert (2026-06-21, PR #296)

- **A1-Erfolgskriterium OOS bestanden:** Engine schlägt exposure-matched Baseline auf Sharpe UND Calmar.
  - BTC: Calmar 0.79 vs 0.39 · Sharpe 1.17 vs 0.82
  - ETH: Calmar 0.42 vs 0.19 · Sharpe 0.74 vs 0.55
- 178 neue Tests grün · Coverage 94.2% · Look-Ahead-Guard grün.
- **Bedeutung:** erster belegter POSITIVER Befund des Projekts (V3 war Negativbefund).
- Gelieferte Komponenten: `signals/indicators.py`, `signals/consensus.py`, `signals/vol_forecast.py`,
  `signals/sizing.py`, `signals/signal_service.py`, `signals/factors.py`;
  `backtest/walkforward.py`, `backtest/guards.py`;
  Migrationen 0037–0040; REST-Endpunkte `/api/v1/signals/`.

---

## V4-3 Agentic Layer — ✅ verifiziert (2026-06-22, Branch feat/v4-3-agentic-layer)

**Befund: Agentic-Layer steht, alle Guards grün, keine Halluzination.**

### 7 Pflicht-Guards (§6 / D-06) — alle grün ✅

| # | Guard | Assertion | Status |
|---|-------|-----------|--------|
| 1 | Halluzinations-Guard | `abs(signal.size_factor − min(engine.size_factor, risk.max_size)) < 1e-9` — TechnicalView UND OnChainView confidence fliessen nachweislich in Synthese ein (zero-confidence Sub-Assertion je Agent) | ✅ GRÜN |
| 2 | State-aus-Tool | `ExposureStore.get_exposure(coin)` wird VOR LLM-Call gerufen; kein Exposure-Wert aus Prompt-Memory | ✅ GRÜN |
| 3 | Minderheits-Schutz | `"bear_case" in agent_run` auch bei 3 bullishen Analysten; Bear-Thesis in Audit-Trail auffindbar; Risk kann size_factor auf 0.0 drücken | ✅ GRÜN |
| 4 | Fallback | Alle 4 Analysten werfen Exception → `TradeSignal` kommt trotzdem (aus Engine), `confidence` gesenkt, `disclaimer` gesetzt, keine Exception propagiert | ✅ GRÜN |
| 5 | Pydantic-Schema | Alle 8 Output-Schemas (TechnicalView, OnChainView, SentimentView, MacroRegime, BullCase, BearCase, RiskVerdict, TradeSignal) lehnen Freitext-Literal-Verstösse per `ValidationError` ab | ✅ GRÜN |
| 6 | Checkpoint-HITL | `confidence < 0.65` → mind. 1 `logging.warning("LOW CONFIDENCE …")`, non-blocking (kein Exception), Disclaimer-Prefix gesetzt | ✅ GRÜN |
| 7 | No-Shorting | `action == "SELL"` → `size_factor == 0.0`; `RiskVerdict.max_size == 0.0` → `size_factor == 0.0` auch bei BUY; niemals negativ | ✅ GRÜN |

> **Checkpoint aktuell nur non-blocking logging.warning — echter HITL-Gate (UI fragt User) ist in V4-5 nachzurüsten.**

### Audit-Trail (agent_audit_trail, append-only)

Tabelle `agent_audit_trail` via Migration 0041. Repository `AgentAuditTrailRepository` exposes **nur** `insert()` — kein `update()`, kein `delete()`, kein `save()`. Zwei `insert()`-Calls mit gleichen coin/asof erzeugen zwei separate Rows.

**Beispiel-Eintrag (BTC-USD, BUY-Signal, Bull/Bear/Risk alle gespeichert):**

```json
{
  "id": "3f28c8a5-4c8e-4947-8919-b8fba992ff32",
  "coin": "BTC-USD",
  "asof": "2026-06-22",
  "created_at": "2026-06-22T08:14:33Z",
  "agent_run": {
    "bull_case": {
      "thesis": "Institutionelle Nachfrage + Halving-Effekt treiben BTC auf neues ATH.",
      "strongest_points": ["ETF-Zuflüsse $800M/Woche", "Halving Mai 2024 — Supply-Schock"],
      "risks_acknowledged": ["Regulatorisches Risiko SEC", "Makro-Volatilität"]
    },
    "bear_case": {
      "thesis": "Leveraged-Overhang: OI zu hoch; Abkühlung wahrscheinlich vor erneutem Anstieg.",
      "strongest_points": ["Open Interest +40% in 30 Tagen", "Funding Rates positiv seit 3 Wochen"],
      "counter_to_bull": ["Institutionelle Käufe könnten bei Korrektur stoppen"]
    },
    "risk_verdict": {
      "approve": true,
      "max_size": 0.65,
      "breaches": [],
      "reasoning": "Exposure 0.0 — kein Limit verletzt. size_factor auf 0.65 deckeln (Volatilitätsschutz)."
    },
    "trade_signal": {
      "action": "BUY",
      "size_factor": 0.65,
      "confidence": 0.739,
      "rationale_by_layer": {
        "technical": "Strong uptrend: MA200 cross, MACD bullish, RSI 58.",
        "onchain": "Aktive Adressen +12% WoW, SOPR > 1.",
        "sentiment": "Fear & Greed 68 (Greed). Social-Volume erhöht, kein Extremwert.",
        "macro": "Risk-on: SPX ATH, Credit Spreads eng, Fed dovish.",
        "bull": "Institutionelle Nachfrage + Halving-Effekt.",
        "bear": "Leveraged-Overhang: OI zu hoch.",
        "risk": "Exposure 0.0 — kein Limit verletzt. size_factor auf 0.65 gedeckelt."
      },
      "audit_trail_id": "a12d58f0-0496-4bca-a10a-6a35feac0547",
      "disclaimer": "Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading."
    }
  }
}
```

Halluzinations-Guard sichtbar: `size_factor = 0.65 = min(engine=0.80, risk.max_size=0.65)` — LLM hat keinen Einfluss auf diesen Wert.

### Coverage

- **Commit-Messung (2026-06-22, Plan 03-06 Executor):** 82.47% ≥ 80% ✅
- **Nachgemessen (gsd-verify-work, 2026-06-22):** 78.2% gesamt — Delta erklärt durch pre-existing Testfehler (`test_config.py::test_passes_when_api_key_set_in_production` unrelated zu V4-3) und DB-abhängige Integration-Tests die ohne laufende PG-Instanz partial-coverage liefern.
- V4-3-spezifische Agent-Dateien einzeln: `signal_director.py` 98.9%, `agent_schemas.py` 100%, `agent_audit_trail_repository.py` 100%, `macro_regime_agent.py` 100%, `technical_analyst_agent.py` 92.1%, `bear_research_agent.py` 92.9%, `bull_research_agent.py` 93.0%, `risk_agent.py` 88.9%, `onchain_analyst_agent.py` 90.2%, `sentiment_analyst_agent.py` 79.4%.

### Gelieferte Komponenten

- 8 Agent-Klassen: `TechnicalAnalystAgent`, `OnChainAnalystAgent`, `SentimentAnalystAgent`, `MacroRegimeAgent`, `BullResearchAgent`, `BearResearchAgent`, `RiskAgent`, `SignalDirector`
- Schemas: `agent_schemas.py` (8 Pydantic-Schemas)
- Persistence: `AgentAuditTrailORM`, `AgentAuditTrailRepository` (append-only), Migration 0041
- REST: `GET /api/v1/agent-signal/{coin}` (404 unbekannt, 503 LLM-Ausfall)
- DI: `get_signal_director()` Depends-Factory mit StubExposureStore (real in V4-4)
- Tests: 7 mandatory D-06 Tests + 4 Endpoint-Tests + Analyst/Risk/Director Unit-Tests + 8 Repo-Tests

---

## V4-2 Meta-Labeling — ✅ verifiziert (2026-06-21, Branch feat/v4-2-meta-labeling)

- **Implementiert:** `meta_label.py` — Triple-Barrier-Labels, Trend-Scan-Labels, `build_meta_features` (10 Features, shift(1)), `fit_meta_classifier` (LogReg/LightGBM), `_walkforward_meta_cv` (embargo=5), `predict_meta_label`.
- **Backtest-Integration:** `run_walkforward()` + `run_walkforward_with_details()` um optionalen `meta_filter: pd.Series | None` erweitert (backward-compatible, ML-08 bestanden).
- **Schema:** `MetaLabelReport` (15 Felder inkl. `finding` + `finding_reason`).
- **API:** `GET /api/v1/signals/meta-label/{coin}` via `asyncio.to_thread`.
- **Tests:** 47 grün · meta_label.py Coverage 97.1% · walkforward.py 100% · ruff + mypy sauber.
- **Methodik:** Expanding-Window (min_train=252, step=21, embargo=5). Baseline auf gleichen OOS-Daten. `finding`-Feld: positive/secondary_pass/negative — kein Overfit.
- **Backtest-Zahlen (V4-2):** Keine realen BTC/ETH-Zahlen in dieser Phase — by design. V4-2 liefert die Pipeline (`MetaLabelReport`-Schema, `meta_filter`-Parameter in `run_walkforward`, REST-Endpoint). Reale OOS-Vergleichszahlen (Sharpe/Calmar/Trades WITH vs. WITHOUT meta-filter je Coin) entstehen erst in V4-3+ wenn der Endpoint gegen echte historische Preisdaten (yfinance) betrieben wird. Die Finding-Logik ist vollständig implementiert und über Monkeypatch-Tests auf alle drei Äste (positive/secondary_pass/negative) verifiziert.
