# PRISMA V4-1 — Phasenplan: Daten + Signal-Engine (Spec + GSD-Auftragskontrakt)

**Status:** baubar · **Repo:** `don69andrea/prisma-v2` · **Branch-Ziel:** `feat/v4-1-signal-engine` (gegen `develop`)
**Konform zu:** `PRISMA_V2_AGENTS.md` (Spec-First, Test-First, Pydantic, kein Direkt-Push, CI grün, Coverage ≥80 %)
**Kontext:** `PRISMA_V4_PROJEKTPLAN.md` (Gesamtplan), `PRISMA_V4_AGENTS.md` (kommt NACH dieser Phase)
**Stand:** 2026-06-21

> **Diese Phase baut KEINE Agenten und KEIN UI.** Sie baut das deterministische Fundament (Daten + Signal-Engine
> + ehrlicher Backtest), auf dem die Agenten (V4-3) und das UI (V4-5) später aufsitzen. Das ist Absicht: erst die
> Zahlen, die stimmen, dann die Schicht, die sie erklärt.

---

## TEIL A · SPEC (Spec-First — vor Implementierung freigeben)

### A1 · Ziel
Eine getestete, deterministische **Signal-Engine** für ein Top-10-Krypto-Universum, die je Coin einen
`SignalVector` (Richtung BUY/HOLD/SELL + Größe) liefert — aus drei Schichten:
1. **WAS** (Faktor-Ranking), 2. **WANN** (Indikator-Konsens + Vol-Forecast-Sizing), 3. ehrlich **backgetestet**
(strikter Walk-Forward, exposure-matched Baseline, netto Kosten). Meta-Labeling ist in dieser Phase **vorbereitet,
aber optional** (eigener Schritt am Ende, darf entfallen ohne die Phase zu blockieren).

**Erfolgskriterium (messbar):** Reproduktion des PoC-Befunds in der Pipeline — die Engine-Strategie schlägt die
exposure-matched Baseline auf Sharpe **und** Calmar über das Top-10-Universum im Walk-Forward, netto Kosten.

### A2 · Scope / Nicht-Ziele
**In Scope:** Daten-Seed Top-10, On-Chain/Fear&Greed-Adapter, Indikatoren, Konsens-Voting, Vol-Forecast-Modell,
Sizing, Backtest-Engine-Härtung, `SignalVector`-API (read-only).
**Nicht-Ziele (bewusst NICHT in dieser Phase):** LLM-Agenten, UI/Frontend, Live-Order-Ausführung, Shorting,
News-RAG-Features (kommt V4-4), SMI-Umbau (bleibt unangetastet).

### A3 · Datenmodell / Schema-Änderungen (Migrationen 0037–0039)
> Bestehende Tabellen wiederverwenden wo möglich (`crypto_price_history`, `macro_rates`).

- **`crypto_universe`** (neu, falls nicht vorhanden): `coin_id` (PK), `symbol` (z. B. `BTC-USD`), `name`,
  `active` (bool), `added_at`. Seed: BTC, ETH, SOL, BNB, XRP, ADA, AVAX, DOGE, LINK, DOT.
- **`crypto_onchain_history`** (neu): `coin_id`, `date`, `mvrv_z`, `realized_cap`, `active_addresses`,
  `tx_volume`, `exchange_netflow`, `source`. PK (`coin_id`, `date`). Quelle: Coin Metrics Community.
- **`market_sentiment`** (neu): `date` (PK), `fear_greed`, `fg_classification`, `source`. Quelle: alternative.me.
- **`signal_outcomes`** (erweitern/neu): `coin_id`, `date`, `action`, `size_factor`, `sub_scores` (JSONB),
  `realized_fwd_return` (nullable, später befüllt) — für Backtest-Nachvollziehbarkeit.
- **`vol_forecast`** (neu): `coin_id`, `date`, `horizon`, `pred_vol`, `realized_vol` (nullable), `model_version`.

**Point-in-time-Pflicht:** Alle Tabellen führen das *Beobachtungsdatum*; kein Feature darf Daten > t verwenden
(Look-Ahead-Guard in Tests).

### A4 · Module (neu) — `backend/application/signals/`
| Datei | Verantwortung | Kern-Funktionen |
|---|---|---|
| `indicators.py` | technische Indikatoren, vektorisiert | `sma`, `ema`, `macd`, `rsi`, `bollinger`, `atr` |
| `consensus.py` | Schicht 2 Roh-Signal | `consensus_vote(df, cfg) -> Series[0/1]` (2-von-3 default) |
| `vol_forecast.py` | Schicht 3 Vol-Prognose | `fit_walkforward()`, `predict_vol(coin, date)` (HAR→LightGBM) |
| `sizing.py` | Positionsgröße | `vol_target_size(pred_vol, target, cap)`, `drawdown_brake()` |
| `factors.py` | Schicht 1 Ranking | `cross_sectional_momentum()`, `onchain_health_score()` |
| `meta_label.py` | *optional* Filter | `triple_barrier_labels()`, `fit_meta_classifier()` |
| `signal_service.py` | Orchestrierung 1–3 | `evaluate(coin, asof) -> SignalVector` |

### A5 · Backtest-Engine — `backend/application/backtest/`
- `walkforward.py`: Expanding-Window, Embargo = Horizont, **exposure-matched Baseline**, Netto-Kosten (0.1 %),
  Slippage-Parameter. Outputs: Equity, Sharpe/Calmar/MaxDD, Per-Fold-Tabelle, Trade-Liste, CI/N.
- `guards.py`: Look-Ahead-Guard (assert: Feature@t nutzt nur ≤ t−1).

### A6 · API (read-only, FastAPI) — `backend/interfaces/rest/routers/signals.py`
| Endpoint | Zweck | Response (Pydantic) |
|---|---|---|
| `GET /api/v1/signals` | aktuelle Signale Top-10 | `list[SignalVector]` |
| `GET /api/v1/signals/{coin}` | Detail inkl. sub_scores | `SignalVector` |
| `GET /api/v1/backtest/{coin}` | Backtest-Kennzahlen+Equity | `BacktestReport` |

```python
class SignalVector(BaseModel):
    coin: str
    asof: date
    action: Literal["BUY", "HOLD", "SELL"]          # SELL = cash, kein Shorting
    size_factor: float = Field(ge=0.0, le=1.5)
    consensus: str                                   # z.B. "3/3"
    sub_scores: dict[str, float]                     # ma, macd, rsi, bb, vol_pred, momentum_rank, onchain
    confidence: float = Field(ge=0.0, le=1.0)
    disclaimer: str = "Entscheidungsunterstützung, kein Anlagerat."

class BacktestReport(BaseModel):
    coin: str; cagr: float; sharpe: float; max_dd: float; calmar: float
    beats_exposure_matched: bool
    n_trades: int; equity_curve: list[tuple[date, float]]
```

### A7 · Test-Cases (Pflicht, Test-First für Domain-Logik)
1. **Indikator-Korrektheit**: `rsi`/`macd`/`bollinger` vs. Referenz (`ta`-Lib) auf Sample, Δ < 1e-6.
2. **Look-Ahead-Guard**: Signal@t nutzt nie Daten@t (shift-Check, automatisiert).
3. **Konsens-Logik**: 2-von-3-Voting korrekt (Wahrheitstabelle).
4. **Vol-Forecast Walk-Forward**: OOS-R² > 0 vs konstante Baseline auf ≥ 2 Coins (PoC-Reproduktion).
5. **Sizing**: `size_factor` ∈ [0, cap]; höhere pred_vol → kleinere Größe (Monotonie).
6. **Backtest-Baselines**: exposure-matched + buy&hold werden berechnet; `beats_exposure_matched` korrekt gesetzt.
7. **Netto-Kosten**: Turnover × Kosten wird abgezogen (Strategie-Return < Brutto bei Umschichtung).
8. **No-Shorting**: `action=="SELL"` ⇒ Ziel-Exposure 0, nie negativ.
9. **API-Schema**: alle Endpunkte geben valide Pydantic-Modelle (kein Freitext).
10. **Coverage-Gate**: ≥ 80 %.

### A8 · Definition of Done
Alle A7-Tests grün · CI grün · Coverage ≥ 80 % · Backtest reproduziert PoC-Befund (Erfolgskriterium A1) ·
PR gegen `develop` offen, dokumentiert in `docs/AI-USAGE.md`. **Merge macht Andrea im UI.**

---

## TEIL B · PLAN-AS-CONTRACT (Ausführung — Subagents, keine Improvisation)

> Frischer Subagent pro Schritt. Jeder liest zuerst: `AGENTS.md` → `CLAUDE.md` → diese Spec → seinen Schritt.
> Bei Fehlschlag: stoppen, melden, auf Freigabe warten. Jeder Schritt = eigener atomarer Commit.

### Wave 0 — Setup (Orchestrator)
```bash
git checkout develop && git pull
git checkout -b feat/v4-1-signal-engine
pip install lightgbm ta --break-system-packages
```

### Wave 1 — Daten (parallelisierbar: 1a‖1b‖1c)
- **1a · DataAgent — Universum+Preise.** Migration `0037_crypto_universe`, Seed Top-10, OHLCV-Backfill seit
  2017 (yfinance + CryptoDataDownload-Fallback) in `crypto_price_history`. Tests: Coverage-Gate (jede Coin
  ≥ N Tage), keine Lücken > 3 Tage. Commit: `feat(data): seed top-10 crypto universe + ohlcv backfill`.
- **1b · DataAgent — On-Chain.** Migration `0038_crypto_onchain`, Coin-Metrics-Community-Adapter (MVRV-Z,
  realized cap, active addr, netflow). Tests: Adapter-Mapping, Fallback bei fehlender Coin. Commit:
  `feat(data): add coin metrics onchain adapter + table`.
- **1c · DataAgent — Sentiment.** Migration `0039_market_sentiment`, alternative.me Fear&Greed-Adapter
  (historisch). Tests: Parsing, Datums-Join. Commit: `feat(data): add fear&greed sentiment adapter`.

### Wave 2 — Signal-Engine-Kern (nach Wave 1; 2a→2b, 2c parallel)
- **2a · SignalAgent — Indikatoren+Konsens.** `indicators.py` + `consensus.py`. **Test-First** (A7.1, A7.3).
  Referenz: PoC `indicator_backtest.py`. Commit: `feat(signals): indicators + 2-of-3 consensus voting`.
- **2b · SignalAgent — Faktoren.** `factors.py` (cross-sectional Momentum-Rang, On-Chain-Health-Score). Tests:
  Ranking-Determinismus. Commit: `feat(signals): cross-sectional momentum + onchain factor`.
- **2c · MLAgent — Vol-Forecast.** `vol_forecast.py` (HAR-Baseline → LightGBM), Walk-Forward. **Test A7.4**
  (OOS-R² > 0). Schreibt `vol_forecast`-Tabelle. Commit: `feat(signals): walk-forward volatility forecast model`.

### Wave 3 — Sizing + Service (nach Wave 2)
- **3a · SignalAgent — Sizing.** `sizing.py` (Vol-Targeting + Drawdown-Bremse). Tests A7.5, A7.8. Commit:
  `feat(signals): vol-targeting sizing + drawdown brake`.
- **3b · SignalAgent — Orchestrierung.** `signal_service.py` → `evaluate()` gibt `SignalVector`. Tests:
  Integration Schicht 1–3. Commit: `feat(signals): signal service producing SignalVector`.

### Wave 4 — Backtest-Härtung (nach Wave 3)
- **4 · BacktestAgent.** `walkforward.py` + `guards.py`: Expanding-Window, exposure-matched Baseline, Netto-Kosten,
  Per-Fold-Report, Look-Ahead-Guard. **Tests A7.2, A7.6, A7.7.** Erzeugt Backtest-Report über Top-10 →
  **Erfolgskriterium A1 prüfen**. Commit: `feat(backtest): strict walk-forward engine + look-ahead guard`.

### Wave 5 — API (nach Wave 4)
- **5 · ApiAgent.** `routers/signals.py` (3 read-only Endpunkte), OpenAPI-Typen. Test A7.9. Commit:
  `feat(api): read-only signals + backtest endpoints`.

### Wave 6 — *optional* Meta-Labeling (darf entfallen)
- **6 · MLAgent.** `meta_label.py`: Triple-Barrier/Trend-Scan-Labels + Klassifikator, gegen „immer-traden"
  getestet. Nur wenn Wave 1–5 grün & Zeit. Commit: `feat(signals): optional meta-labeling filter`.

### Wave 7 — Gate + PR (Orchestrator)
```bash
python -m pytest backend/tests/ --cov=backend --cov-fail-under=80
# AI-USAGE.md Eintrag ergänzen
git push origin feat/v4-1-signal-engine
# PR gegen develop öffnen, CI grün abwarten. Merge: Andrea im UI.
```

---

## TEIL C · Sub-Agent-Rollen (GSD-Mapping)
| GSD-Auftrag | PRISMA-Rolle | Waves |
|---|---|---|
| `DataAgent` | Seed/Adapter/Migrationen/Coverage | 1a, 1b, 1c |
| `SignalAgent` | Indikatoren, Faktoren, Sizing, Service | 2a, 2b, 3a, 3b |
| `MLAgent` | Vol-Forecast (+ optional Meta-Label) | 2c, (6) |
| `BacktestAgent` | Walk-Forward, Baselines, Guards | 4 |
| `ApiAgent` | read-only Endpunkte | 5 |
| `Orchestrator` (du) | Branch, Waves koordinieren, Gate, PR | 0, 7 |

**GSD-Befehle:** `/gsd-discuss-phase` (diese Spec bestätigen) → `/gsd-plan-phase` → `/gsd-execute-phase`
(Waves als parallele Pläne) → `/gsd-verify-work` (A7-Tests + A1-Erfolgskriterium) → `/gsd-ship` (PR).

---

## TEIL D · Risiken dieser Phase
- **Datenlücken Top-10** (junge Coins < 2017) → Coverage-Gate akzeptiert variable Startdaten, Walk-Forward
  respektiert je Coin den Verfügbarkeitsbeginn.
- **Coin-Metrics-Coverage** dünn jenseits BTC/ETH → On-Chain-Faktor optional/gewichtet, kein Hard-Block.
- **Overfitting Vol-Modell** → feste Features (HAR), Walk-Forward Pflicht, LightGBM nur wenn es HAR OOS schlägt.
- **Reproduktion schlägt fehl** (Engine ≠ PoC) → Diff gegen `prisma_v35_poc/` als Debugging-Anker.

---

*PRISMA V4-1 Phasenplan · 2026-06-21 · Andrea Petretta · FHNW BI Modul FS 2026*
