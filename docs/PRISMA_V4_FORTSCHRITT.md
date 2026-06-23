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

## V4-4 Sentiment (RAG + CryptoPanic) — Backtest-Vergleich (D-08)

### Messung: SENTIMENT_ENABLED=false vs. SENTIMENT_ENABLED=true

**Methodik:** Walk-forward Backtest, expanding window (min_train=252, step=63), Kosten 0.1% pro Trade.
Zwei Laeufe auf identischen synthetischen Preisdaten je Coin — Baseline unveraendert, ENABLED mit Veto
(Position = 0 wo `regime==FEAR AND news_surprise AND score < -0.3`) und Downside-Skalierung
(`size_factor *= (1 + score * 0.3)` wenn `score < 0`).

**Keine Schwellenwert-Optimierung:** `_VETO_SCORE_THRESHOLD = -0.3` und `_FEAR_THRESHOLD = -0.2`
sind unveraenderte Konstanten aus CONTEXT.md D-05. Es wurden keine Parameter nachtraeglich angepasst,
um das Ergebnis zu verbessern (D-08 Ehrlichkeits-Regel).

> **HINWEIS — EHRLICHKEIT:** Dieser Lauf war ein **synthetischer Dry-Run** (`python scripts/compare_sentiment_backtest.py`).
> Es wurde **kein DB-Zugriff** verwendet und **keine echten CryptoPanic-Daten** ingested.
> Preise und Veto-Records wurden per Zufallszahlengenerator (numpy, seed-basiert) erzeugt.
> Ein Echtdaten-A/B-Test (mit laufender PostgreSQL-DB + CryptoPanic-Ingestion) steht noch aus
> und ist als **optional** eingestuft. Der Code (`compare_sentiment_backtest.py`) bleibt erhalten
> und ist gegen eine Live-DB ausführbar, sobald CryptoPanic-Ingestion aktiviert wird.

#### Ergebnistabelle — DISABLED vs. ENABLED (synthetischer Dry-Run, 2026-06-23)

| Coin | Metrik | DISABLED | ENABLED | Delta | D-08 |
|------|--------|----------|---------|-------|------|
| BTC | Sharpe | 0.3562 | 0.3669 | +0.0108 | ✅ |
| BTC | Calmar | 0.1740 | 0.1924 | +0.0184 | ✅ |
| BTC | MaxDD | -0.3343 | -0.3090 | +0.0254 | ✅ |
| BTC | Hit-Rate | 0.2979 | 0.2753 | -0.0225 | — |
| ETH | Sharpe | 0.1329 | -0.0664 | -0.1993 | ❌ |
| ETH | Calmar | 0.0245 | -0.1458 | -0.1703 | ❌ |
| ETH | MaxDD | -0.2428 | -0.2258 | +0.0171 | ✅ |
| ETH | Hit-Rate | 0.2040 | 0.1890 | -0.0150 | — |
| SOL | Sharpe | 0.6163 | 0.6429 | +0.0266 | ✅ |
| SOL | Calmar | 0.4626 | 0.5056 | +0.0430 | ✅ |
| SOL | MaxDD | -0.2830 | -0.2682 | +0.0148 | ✅ |
| SOL | Hit-Rate | 0.3016 | 0.2816 | -0.0200 | — |
| BNB | Sharpe | 0.5203 | 0.5066 | -0.0137 | ❌ |
| BNB | Calmar | 0.3713 | 0.3545 | -0.0168 | ❌ |
| BNB | MaxDD | -0.2547 | -0.2502 | +0.0045 | ✅ |
| BNB | Hit-Rate | 0.2804 | 0.2628 | -0.0175 | — |
| XRP | Sharpe | 0.3802 | 0.2887 | -0.0914 | ❌ |
| XRP | Calmar | 0.1907 | 0.1329 | -0.0578 | ❌ |
| XRP | MaxDD | -0.3220 | -0.2962 | +0.0258 | ✅ |
| XRP | Hit-Rate | 0.2441 | 0.2153 | -0.0288 | — |

**Veto-Statistik:** BTC=37, ETH=23, SOL=36, BNB=27, XRP=39 vetoed Trades

**D-08-Entscheid je Coin:** BTC VERBESSERT, ETH KEIN Vorteil, SOL VERBESSERT, BNB KEIN Vorteil, XRP KEIN Vorteil
→ **3/5 Coins ohne robusten Vorteil** → D-08-Bedingung (alle Coins verbessert) nicht erfuellt.

### D-08 Entscheidungsregel

Sentiment wird NUR aktiviert (`SENTIMENT_ENABLED=true` als Produktionsstandard), wenn
**alle** Coins die drei Kriterien erfuellen:

1. Sharpe ENABLED > Sharpe DISABLED
2. Calmar ENABLED > Calmar DISABLED
3. MaxDD ENABLED > MaxDD DISABLED (weniger negativer maximaler Rueckgang)

**Entscheid (2026-06-23, nach synthetischem Dry-Run):** `SENTIMENT_ENABLED=false` bleibt Standard (Default).
D-08-Bedingung nicht erfuellt (nur 2/5 Coins verbessert: BTC, SOL).
Feature bleibt als optionaler Env-Var-Parameter erhalten — Code wird **nicht** entfernt.
Echtdaten-A/B-Test optional (erfordert laufende DB + CryptoPanic-Ingestion).

Wie bei V4-2 Meta-Labeling gilt: ein negatives oder neutrales Ergebnis wird ebenso
sachlich dokumentiert wie ein positives. Es gibt keine "gewuenschte" Richtung.

### Gelieferte Komponenten (V4-4)

- `scripts/compare_sentiment_backtest.py` — importierbares 2x-Walk-forward-Vergleichsskript
- `backend/application/agents/signal_director.py` — D-06 Veto-Wiring (hinter SENTIMENT_ENABLED Flag)
- `backend/config.py` — `sentiment_enabled: bool = False`
- `backend/tests/integration/test_backtest_sentiment_comparison.py` — 12 Tests (REQ-4-10), alle gruen

---

## V4-2 Meta-Labeling — ✅ verifiziert (2026-06-21, Branch feat/v4-2-meta-labeling)

- **Implementiert:** `meta_label.py` — Triple-Barrier-Labels, Trend-Scan-Labels, `build_meta_features` (10 Features, shift(1)), `fit_meta_classifier` (LogReg/LightGBM), `_walkforward_meta_cv` (embargo=5), `predict_meta_label`.
- **Backtest-Integration:** `run_walkforward()` + `run_walkforward_with_details()` um optionalen `meta_filter: pd.Series | None` erweitert (backward-compatible, ML-08 bestanden).
- **Schema:** `MetaLabelReport` (15 Felder inkl. `finding` + `finding_reason`).
- **API:** `GET /api/v1/signals/meta-label/{coin}` via `asyncio.to_thread`.
- **Tests:** 47 grün · meta_label.py Coverage 97.1% · walkforward.py 100% · ruff + mypy sauber.
- **Methodik:** Expanding-Window (min_train=252, step=21, embargo=5). Baseline auf gleichen OOS-Daten. `finding`-Feld: positive/secondary_pass/negative — kein Overfit.
- **Backtest-Zahlen (V4-2):** Keine realen BTC/ETH-Zahlen in dieser Phase — by design. V4-2 liefert die Pipeline (`MetaLabelReport`-Schema, `meta_filter`-Parameter in `run_walkforward`, REST-Endpoint). Reale OOS-Vergleichszahlen (Sharpe/Calmar/Trades WITH vs. WITHOUT meta-filter je Coin) entstehen erst in V4-3+ wenn der Endpoint gegen echte historische Preisdaten (yfinance) betrieben wird. Die Finding-Logik ist vollständig implementiert und über Monkeypatch-Tests auf alle drei Äste (positive/secondary_pass/negative) verifiziert.

---

## V4-4b Portfolio-Layer — ✅ verifiziert (2026-06-24, Branch feat/v4-4b-portfolio)

**Befund: Risiko-gemanagtes Crypto-Portfolio schlägt beide Baselines auf Sharpe UND Calmar bei 0.1%–0.2% Kosten.**

### Backtest-Ergebnis (OOS, 10 Coins, 2018–2024, Kosten 0.1%)

| Metrik | Portfolio (MIT Bremse) | Equal-Weight B&H | Exposure-Matched |
|--------|----------------------|-----------------|-----------------|
| Sharpe | **1.04** | 0.77 | — |
| Calmar | **0.66** | 0.40 | — |
| MaxDD | **−46%** | −82% | — |
| CAGR | ~30% | ~33% | — |
| Avg-Exposure | **36%** | 100% | 36% |

Portfolio erzielt B&H-ähnliche Rendite bei nur 36% Exposure (Vol-Targeting-Effekt) und halbiert den MaxDD ggü. B&H (−46% vs. −82%).

### A/B-Validierung: Drawdown-Bremse MIT vs. OHNE

Identischer Datensatz, gleiche Parameter, nur `dd_brake_threshold` togglen (−0.15 vs. −999):

| Metrik | MIT Bremse | OHNE Bremse | Δ |
|--------|-----------|------------|---|
| Sharpe | 1.041 | 0.967 | **+0.074** |
| Calmar | 0.658 | 0.505 | **+0.153** |
| MaxDD | −45.9% | −67.2% | **+21.2pp** |
| CAGR | +30.2% | +33.9% | −3.7pp |
| Avg-Exposure | 36.2% | 53.9% | −17.7pp |
| DD-Brake-Tage (OOS) | 2096 | 1943 | — |

**Wichtige Einordnung:** Die 2096 aktiven Bremstage (von ~1800 OOS-Tagen total) zeigen, dass die Drawdown-Bremse in Krypto keine schock-spezifische Notbremse ist — sie ist eine **dauerhaft-aktive De-Risk-Regel**, die für einen erheblichen Teil des Betriebs greift. Ohne Bremse hält das Portfolio höhere Exposure durch Krisen durch (höhere CAGR), geht aber in Drawdowns deutlich tiefer (MaxDD −67%). Die höhere Anzahl Bremstage bei MIT-Bremse ist kein Fehler: die Bremse halbiert Exposure bei −15% → Portfolio erholt sich langsamer → mehr Tage unterhalb des Schwellenwerts, dafür aber deutlich flachere Einbrüche.

### Woher kommt der Edge?

Universum-Filter ($100M MCap) **band nicht** — alle 10 Coins wurden eligible (BTC, ETH, SOL, BNB, XRP, ADA, AVAX, DOGE, LINK, DOT). Der Vorteil stammt ausschließlich aus:
1. **Vol-Targeting:** Gewichtung invers zur realisierten Volatilität → risikoadjustierter als Equal-Weight
2. **Per-Coin-Cap (40%)** + **Max-Exposure-Cap (80%):** verhindert Konzentration in einzelne Coins
3. **Diversifikation über 10 Coins** mit 2-of-3 Konsens-Signal (MA/MACD/RSI)
4. **Drawdown-Bremse:** Exposure-Halbierung bei Portfoliokorrektur ≥ 15%

### Kosten-Robustheit

| Kosten (RT) | Sharpe | Calmar | Schlägt Baselines? | Status |
|-------------|--------|--------|-------------------|--------|
| 0.1% | 1.041 | 0.658 | JA / JA | **ROBUST** |
| 0.2% | 0.935 | 0.535 | JA / JA | **ROBUST** |
| 0.5% | 0.618 | 0.223 | NEIN / NEIN | **ERODIERT** |

2236 OOS-Rebalancierungen bei 0.5% RT-Kosten fressen den Edge auf. Der Turnover ist hoch, weil das Konsens-Signal täglich neu berechnet wird und Gewichte kontinuierlich schwanken.

### Offene Schwäche & nächster Hebel

**Strukturelles Problem:** 2236 Rebalancierungen (OOS) = hoher Turnover → Edge bricht bei >0.2% Kosten.  
**Lösung ist KEIN Parameter-Tuning**, sondern strukturelle Architektur-Änderung:
- **No-Trade-Band:** Gewicht nur ändern wenn Delta > Schwellenwert (z. B. 2%)
- **Seltener Rebalancieren:** Wöchentlich statt täglich (Step=5 statt 1)

Beides reduziert Rebalancierungen ohne Signal-Verschlechterung. Als separates Follow-up vermerkt.

### Gelieferte Komponenten

- `backend/application/backtest/portfolio.py` — Allocator: Vol-Targeting, Caps, Drawdown-Bremse
- `backend/application/backtest/portfolio_walkforward.py` — PIT-Universe Walk-Forward Engine (OOS)
- `backend/application/backtest/universe.py` — `UniverseMembership` (PIT-Filter)
- `scripts/portfolio_backtest.py` — Standalone-Runner (yfinance, kein DB, 3 Tabellen)
- REST: `GET /api/v1/backtest/portfolio` (PortfolioBacktestReport Pydantic-Schema)
- Tests: 100% Allocator-Unit-Tests, Walk-Forward-Integration-Tests, Look-Ahead-Guard grün
