# Phase 5: V4-4c Robustness & Stress-Test — Research

**Researched:** 2026-06-23
**Domain:** Quantitative Backtesting, Walk-Forward Validation, Python Harness Script
**Confidence:** HIGH — alle Kernfunde wurden live gegen die Codebase und yfinance verifiziert.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 Kein Tuning:** Feste, a-priori Parameter. Default-Trend-MA ist SMA(100) — bleibt Ankerpunkt. Kein nachträgliches Anpassen um Ergebnisse zu verbessern.
- **D-02 Echte Daten:** yfinance direkt. Falls Daten fehlen oder zu kurz: klar melden, NICHT synthetisch ersetzen. Mindestlänge: min_train=252 Tage + 1 OOS-Periode.
- **D-03 Kosten-Sensitivität:** 0.001, 0.002, 0.005. Primär BTC und ETH.
- **D-04 Regime-Splits:** Bear 2018 (2018-01-01–2018-12-31), Bull 2021 (2021-01-01–2021-12-31), Bear 2022 (2022-01-01–2022-12-31), Bull 2023-24 (2023-01-01–2024-12-31). Walk-Forward beibehalten, keine in-sample-Auswahl.
- **D-05 Volles Universum:** Alle 10 Coins: BTC-USD, ETH-USD, BNB-USD, SOL-USD, XRP-USD, ADA-USD, AVAX-USD, MATIC-USD, DOT-USD, LINK-USD. Coins mit unzureichenden Daten markiert, nicht synthetisch ersetzt.
- **D-06 Parameter-Stabilität:** Trend-Fenster [50, 75, 100, 150, 200] für SMA. Primär BTC, dann ETH.
- **D-07 Baselines:** Immer exposure-matched (berechnet in walkforward.py) + Buy&Hold (100% konstante Investitionsquote). Alle Ergebnisse netto nach Kosten.
- **D-08 Ehrliche Dokumentation:** Ergebnis in docs/PRISMA_V4_FORTSCHRITT.md, Abschnitt "V4-4c Robustheits-Harness". Edge-Klassifikation: robust / fragil / regime-abhängig. Falls fragil: klar kommunizieren.
- **D-09 Look-Ahead-Guard:** backend/application/backtest/guards.py gilt weiter. Tests deterministisch (kein random ohne Seed).
- **D-10 Harness-Struktur:** Einzelnes Skript `scripts/robustness_check.py`. Standalone, kein DB-Zugriff, yfinance direkt. Ausgabe: Konsolentabellen + Rückgabe als dict. Importierbar (testbar). Sections: KOSTEN / REGIME / UNIVERSUM / PARAMETER.
- **D-11 Kein Merge, kein /gsd-complete-milestone:** Execute nur wenn User "OK Execute" schreibt.

### Claude's Discretion

- Interne Hilfsfunktionen für Daten-Subset nach Datumsbereich
- Logging-Format der Tabellen (Rich-Library bevorzugt — verfügbar im Venv)
- Test-Fixtures für schnelle CI-Ausführung (synthetische Preise für Unit-Tests OK, echte Daten für Integrations-Tests)
- Reihenfolge der Ausgabe in FORTSCHRITT.md

### Deferred Ideas (OUT OF SCOPE)

- Minuten-Daten für robustere Vol-Schätzung
- Bootstrap-Konfidenzintervalle für Sharpe
- Direkte DB-Integration
</user_constraints>

---

## Summary

Phase 5 ist eine reine Analyse-Phase: Kein neues Feature, kein neuer Endpoint. Das Ziel ist ein einziges, standalone lauffähiges Python-Skript (`scripts/robustness_check.py`) das die bestehende `run_walkforward()`-Engine für 4 Stress-Dimensionen wiederverwendet und die Ergebnisse ehrlich dokumentiert.

Die Forschung bestätigt: Die Engine ist vollständig parametrisierbar ohne Änderungen an `walkforward.py`, `indicators.py` oder `consensus.py`. SMA-Window ist trivial injizierbar. Der costs-Parameter von `run_walkforward()` deckt Dimension 1 direkt ab. Regime-Splits erfordern einen spezifischen Ansatz: volle Preishistorie bis Regime-Ende herunterladen, Walk-Forward normal durchführen, OOS-Returns dann auf das Regime-Datum-Fenster zuschneiden. Die Vol-Forecast-Engine ist self-contained und braucht kein vortrainiertes Modell-Artefakt.

Die yfinance-Datenverfügbarkeit wurde live geprüft: Alle 10 Coins haben genug Daten für den vollständigen Universum-Test. Für Regime-Splits sind BTC und ETH vollständig abgedeckt (Bear 2018: 365 rows), während SOL, AVAX, DOT und MATIC für Bear 2018 null Daten haben (erst ab 2019-2020 gelistet) — diese müssen als "insufficient" dokumentiert werden, exakt wie in D-02 und D-05 vorgesehen.

**Primary recommendation:** Harness als isoliertes Modul bauen, das `run_walkforward_with_details()` konsumiert und metric-Slicing auf Regime-Ebene intern durchführt. Pattern aus `scripts/compare_sentiment_backtest.py` direkt übernehmen.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Preisdaten abrufen | Harness-Script | yfinance (extern) | Standalone, kein DB-Zugriff (D-10) |
| Signal-Berechnung | Harness-Script (vectorized) | backend/application/signals/ | Bestehende Funktionen wiederverwenden, KEIN signal_service.evaluate() |
| Walk-Forward Backtest | backend/application/backtest/walkforward.py | — | Unverändert; alle 4 Dimensionen nutzen exakt dieselbe Engine |
| Regime-Date-Slicing | Harness-Script (Hilfsfunktion) | — | Neue Hilfsfunktion, nicht in Engine einbauen |
| Metriken berechnen | backend/application/backtest/walkforward.py | — | _sharpe, _calmar, _max_drawdown bereits exportiert |
| Tabellen-Output | Harness-Script (Rich) | — | Rich ist im Venv verfügbar (v15.0.0) |
| Dokumentation | docs/PRISMA_V4_FORTSCHRITT.md | — | Append-only, D-08 |
| Tests | backend/tests/unit/ + integration/ | — | Unit-Tests mit synthetischen Daten; Integrations-Tests mit echten yfinance-Daten |

---

## Standard Stack

### Core — alle bereits im Projekt und Venv installiert

| Library | Verfügbare Version | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| yfinance | 1.4.1 [VERIFIED: pip3 show] | OHLCV-Datendownload | D-02: echte Daten, kein DB-Zugriff |
| pandas | 3.0.3 [VERIFIED: pip3 show] | DataFrame-Operationen, Index-Slicing | Backbone aller bestehenden Module |
| numpy | 2.2.6 [VERIFIED: pip3 show] | Numerische Berechnungen | Backbone aller bestehenden Module |
| rich | 15.0.0 [VERIFIED: pip3 show] | Konsolentabellen (Rich.Table) | Im Venv vorhanden; konsistentes, lesbares Output |
| scikit-learn | 1.9.0 [VERIFIED: pip3 show] | LinearRegression in vol_forecast | Bereits verwendet |
| lightgbm | 4.6.0 [VERIFIED: pip3 show] | Optionaler LGBM-Zweig in vol_forecast | Bereits verwendet |

### Supporting — aus bestehendem Backend direkt importierbar

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `backend.application.signals.indicators` | — | sma(), rsi(), macd() | Signal-Berechnung für alle Dimensionen |
| `backend.application.signals.consensus` | — | consensus_vote() | 2-of-3 Voting |
| `backend.application.signals.sizing` | — | vol_target_size() | Sizing-Faktor für Positionen |
| `backend.application.signals.vol_forecast` | — | fit_walkforward(), realized_vol() | Vol-Modell für Sizing |
| `backend.application.backtest.walkforward` | — | run_walkforward_with_details() + interne Metriken | Kern der Engine |
| `backend.application.backtest.guards` | — | assert_no_lookahead() | Look-Ahead-Verifikation in Tests |

**Installation:** Keine neuen Pakete nötig. Alles bereits verfügbar.

---

## Package Legitimacy Audit

Keine neuen Pakete werden installiert. Alle verwendeten Bibliotheken sind bereits im Venv vorhanden und Teil des bestehenden Projekts.

| Package | Registry | Age | Source Repo | Disposition |
|---------|----------|-----|-------------|-------------|
| yfinance | PyPI | ~8 Jahre | github.com/ranaroussi/yfinance | Approved — bereits im Projekt |
| rich | PyPI | ~6 Jahre | github.com/Textualize/rich | Approved — bereits im Projekt |
| pandas | PyPI | ~15 Jahre | github.com/pandas-dev/pandas | Approved — bereits im Projekt |
| numpy | PyPI | ~20 Jahre | github.com/numpy/numpy | Approved — bereits im Projekt |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
*slopcheck war bei Research-Time nicht installierbar. Alle Pakete sind bereits im Projekt seit Phasen 1-4 verifiziert.*

---

## Architecture Patterns

### System Architecture Diagram

```
yfinance.download(coin, start, end)
        │
        ▼
  pd.DataFrame(close)
        │
        ├─────────────────────────────────────────────────┐
        ▼                                                 ▼
  build_signals(close, ma_window)              Preishistorie für BaH
   │  sma(close, window)                           │
   │  rsi(close)                                   │
   │  macd(close)                                  │
   │  consensus_vote(signals_df)                   │
   │  realized_vol() → vol_target_size()           │
   └─→ positions: pd.Series                        │
        │                                          │
        ▼                                          ▼
  run_walkforward_with_details(                run_walkforward(
    prices, positions, costs=X)                 prices, all_ones, costs=0.0001)
        │                                           │
        ▼                                           │
  details["net_returns"]                            │
        │                                           │
  [Regime-Slice, wenn Dimension 2]                  │
        │                                           │
        ▼                                           ▼
  _sharpe(net) / _calmar(net) / _max_dd(net)   BaH_sharpe / BaH_calmar
        │                                           │
        └────────────────┬──────────────────────────┘
                         ▼
               RobustnessResult(dataclass)
                         │
                         ▼
                  Rich.Table output
                  + Rückgabe als dict
                         │
                         ▼
           docs/PRISMA_V4_FORTSCHRITT.md (append)
```

### Recommended Project Structure

```
scripts/
└── robustness_check.py        # Neues Harness-Skript (einzige neue Datei)

backend/tests/unit/application/
└── test_robustness_harness.py # Unit-Tests (synthetische Daten, schnell)

backend/tests/integration/
└── test_robustness_integration.py  # Optional: echte yfinance-Daten (langsam)

docs/
└── PRISMA_V4_FORTSCHRITT.md   # Append-only, neuer Abschnitt "V4-4c"
```

### Pattern 1: Vectorized Signal Building (kein signal_service.evaluate())

**Was:** Das Harness baut Signale vektoriell über die komplette Preisserie, ohne den asynchronen `signal_service.evaluate()` zu verwenden. Dieser ist für Live-Berechnungen per Coin/Datum gedacht, nicht für Backtests.

**Wann:** Immer im Harness-Kontext.

```python
# Source: Verifiziert gegen backend/application/signals/ (live getestet 2026-06-23)
def build_signals(close: pd.Series, ma_window: int = 100) -> pd.Series:
    """Build vol-targeted consensus signal series (shift(1) applied)."""
    from backend.application.signals.indicators import sma, rsi, macd
    from backend.application.signals.consensus import consensus_vote
    from backend.application.signals.sizing import vol_target_size
    from backend.application.signals.vol_forecast import realized_vol

    sma_val = sma(close, window=ma_window)
    rsi_14 = rsi(close, window=14)
    _, _, macd_hist = macd(close)

    # shift(1) auf die binären Signale BEVOR consensus — Look-Ahead-sicher
    ma_s = (close > sma_val).astype(float).shift(1).fillna(0.0)
    rsi_s = (rsi_14 > 50).astype(float).shift(1).fillna(0.0)
    macd_s = (macd_hist > 0).astype(float).shift(1).fillna(0.0)

    signals_df = pd.DataFrame({
        "ma_signal": ma_s,
        "rsi_signal": rsi_s,
        "macd_signal": macd_s,
    })
    consensus = consensus_vote(signals_df)

    # Vol-Targeting: rolling 21-Tage-Vol als Näherung (kein per-Step fit nötig)
    rv = realized_vol(close)
    rolling_vol = rv.rolling(21).mean().shift(1).fillna(0.60)
    size_factors = rolling_vol.apply(lambda v: vol_target_size(v, target_vol=0.60, cap=1.5))

    return consensus.astype(float) * size_factors
```

### Pattern 2: Regime-Split Approach

**Was:** Volle Preishistorie bis Regime-Ende herunterladen, Walk-Forward normal durchführen, OOS-Returns auf Regime-Datumsfenster zuschneiden, dann Metriken berechnen.

**Warum:** Die Alternative (nur Regime-Daten herunterladen) hat das Problem, dass für einen 1-Jahr-Zeitraum (365 Tage) der Walk-Forward erst ab Tag 252 OOS-Daten liefert — das wären nur ~113 OOS-Handelstage. Korrekte Methode: Trainingsdaten aus Vorjahren inklusive lassen, nur die Metriken auf das Regime-Fenster beziehen.

```python
# Source: Verifiziert live (2026-06-23), Bear 2022 Ergebnis: Sharpe=-1.967 vs Baseline=-1.074
def _run_regime(
    coin: str,
    regime_start: str,
    regime_end: str,
    costs: float = 0.001,
    ma_window: int = 100,
    data_start: str = "2015-01-01",
) -> dict:
    """Walk-Forward mit vollem Trainings-Verlauf; OOS-Metriken nur auf Regime-Fenster."""
    from backend.application.backtest.walkforward import (
        run_walkforward_with_details, _sharpe, _calmar, _max_drawdown
    )

    raw = yf.download(coin, start=data_start, end=regime_end, progress=False, auto_adjust=True)
    if len(raw) < 315:  # min_train(252) + step(63)
        return {"status": "insufficient", "rows": len(raw)}

    close = raw["Close"].squeeze()
    close.index = close.index.tz_localize("UTC")
    prices_df = pd.DataFrame({"close": close})
    signals = build_signals(close, ma_window=ma_window)

    details = run_walkforward_with_details(prices_df, signals, costs=costs)
    net = details["net_returns"]
    baseline = details["baseline_returns"]

    # Auf Regime-Fenster zuschneiden
    mask = (net.index >= regime_start) & (net.index <= regime_end)
    regime_net = net[mask]
    regime_base = baseline[mask]

    if len(regime_net) < 21:  # Mindestzahl OOS-Punkte im Regime
        return {"status": "no_oos_in_regime", "rows": len(regime_net)}

    return {
        "status": "ok",
        "strategy_sharpe": _sharpe(regime_net),
        "strategy_calmar": _calmar(regime_net),
        "strategy_max_dd": _max_drawdown(regime_net),
        "baseline_sharpe": _sharpe(regime_base),
        "baseline_calmar": _calmar(regime_base),
        "oos_rows": len(regime_net),
    }
```

### Pattern 3: Buy&Hold Baseline

**Was:** Buy&Hold = `run_walkforward()` mit `signals = pd.Series(1.0, index=close.index)` und minimalen Kosten (einmaliger Kauf, `costs=0.0` oder `costs=0.0001`). Da `avg_exposure=1.0` und `baseline = avg_exposure * daily_ret`, ist exposure-matched Baseline für Buy&Hold identisch mit der Strategie selbst.

```python
# Source: Verifiziert live (2026-06-23) — avg_exposure=0.9997 bei all-ones Signal
def _buy_and_hold_sharpe(close: pd.Series) -> tuple[float, float]:
    """Reiner Buy&Hold-Sharpe und -Calmar (100% investiert, kein Timing)."""
    from backend.application.backtest.walkforward import run_walkforward_with_details, _sharpe, _calmar
    prices_df = pd.DataFrame({"close": close})
    bah_signals = pd.Series(1.0, index=close.index)
    details = run_walkforward_with_details(prices_df, bah_signals, costs=0.0001)
    return _sharpe(details["net_returns"]), _calmar(details["net_returns"])
```

### Pattern 4: Skript-Struktur (aus compare_sentiment_backtest.py)

Das bestehende `scripts/compare_sentiment_backtest.py` gibt das exakte Muster vor:
- Dataclasses für Ergebnisse
- Kern-Funktion importierbar (returns dict/dataclass)
- `if __name__ == "__main__"`: `sys.exit(asyncio.run(main()))` — aber das Harness ist NICHT async (kein signal_service.evaluate()), daher direkt `if __name__ == "__main__": main()`
- Konsolenausgabe über print() oder Rich (Rich bevorzugt, da für Tabellen lesbarer)

### Anti-Patterns to Avoid

- **signal_service.evaluate() im Harness:** Ist async und pro-Coin/pro-Datum, nicht für vektorisierte Backtests geeignet. IMMER die direkten Indicator-Funktionen + walkforward.py nutzen.
- **Regime-Slice OHNE vorherige Trainingsperiode:** Nur 365 Tage runterladen für Bear 2018 gibt nach min_train=252 nur ~113 OOS-Punkte. Immer ab data_start='2015-01-01' downloaden, bis regime_end, dann Regime-Slice auf OOS-Returns anwenden.
- **vol_forecast.fit_walkforward() im Hauptpfad der Harness:** Der fit dauert mehrere Sekunden pro Coin (expanding window über Jahre). Für die einfache Harness reicht der rolling_vol-Näherungsansatz (Pattern 1). Nur wenn volle Reproduzierbarkeit des V4-1-Edges gewünscht ist, fit_walkforward() einsetzen.
- **Ergebnisse verschweigen:** Falls ein Coin "insufficient data" hat oder der Edge in einem Regime negativ ist — klar dokumentieren, nicht weglassen (D-01, D-08).
- **print()-statt-logging:** AGENTS.md §8 verbietet print() in Produktionscode. Das Harness ist ein Script (kein Service-Code), daher ist print/Rich-Console vertretbar. Für Library-Funktionen dennoch logging verwenden.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sharpe-Ratio-Berechnung | Eigene Formel | `walkforward._sharpe()` | Bereits implementiert, annualisiert, Edge-Cases (std=0) behandelt |
| Calmar-Ratio | Eigene Formel | `walkforward._calmar()` | Bereits implementiert (nutzt _cagr + _max_drawdown) |
| Max Drawdown | Eigene Formel | `walkforward._max_drawdown()` | Bereits implementiert, clip(lower=0) berücksichtigt |
| Konsolentabellen | Manuelle Strings | Rich.Table | Rich ist im Venv (v15.0.0); viel lesbarer als f-string-Tabellen |
| Look-Ahead-Check | Correlation selbst berechnen | `guards.assert_no_lookahead()` | Bereits implementiert mit Threshold 0.999 |
| Kostenberechnung | Manueller Turnover | `costs`-Parameter in `run_walkforward()` | Bereits implementiert: `turnover * costs` |

**Key insight:** Die gesamte Quantlogik (Sharpe, Calmar, MaxDD, Kosten, Baseline) ist bereits in `walkforward.py` implementiert. Das Harness ist NUR eine Orchestrations-Schicht.

---

## Verified Data Availability (yfinance 1.4.1)

[VERIFIED: yfinance live-check 2026-06-23]

| Coin | Start-Datum | Ende | Rows | Gesamt-Test OK? | Bear 2018 | Bull 2021 | Bear 2022 | Bull 2023-24 |
|------|------------|------|------|-----------------|-----------|-----------|-----------|--------------|
| BTC-USD | 2015-01-01 | 2026-06-23 | 4192 | OK | OK (364 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| ETH-USD | 2017-11-09 | 2026-06-23 | 3149 | OK | OK (364 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| BNB-USD | 2017-11-09 | 2026-06-23 | 3149 | OK | OK (364 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| SOL-USD | 2020-04-10 | 2026-06-23 | 2266 | OK | **INSUFFICIENT** (0 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| XRP-USD | 2017-11-09 | 2026-06-23 | 3149 | OK | OK (364 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| ADA-USD | 2017-11-09 | 2026-06-23 | 3149 | OK | OK (364 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| AVAX-USD | 2020-07-13 | 2026-06-23 | 2103 | OK | **INSUFFICIENT** (0 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| MATIC-USD | 2019-04-28 | **2025-03-24** | 2158 | OK* | **INSUFFICIENT** (0 rows) | OK (364 rows) | OK (364 rows) | Partial (Ende 2025-03) |
| DOT-USD | 2020-08-20 | 2026-06-23 | 2134 | OK | **INSUFFICIENT** (0 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |
| LINK-USD | 2017-11-09 | 2026-06-23 | 3149 | OK | OK (364 rows) | OK (364 rows) | OK (364 rows) | OK (730 rows) |

**Wichtige Befunde:**

1. **MATIC-USD ist delisted** (Polygon Network wurde zu POL umgebrandet). yfinance liefert Daten nur bis 2025-03-24. POL-USD ist unter yfinance nicht verfügbar. Für die Phase: MATIC-USD verwenden bis 2025-03-24 (2158 rows vorhanden, reicht für Universum-Test und Bull 2023-24 bis Ende 2024). Klar als "endet 2025-03-24, kein Bull 2023-24 vollständig" dokumentieren.

2. **Regime Bear 2018:** Nur BTC, ETH, BNB, XRP, ADA, LINK verfügbar. SOL, AVAX, MATIC, DOT → "insufficient" (listet 2019-2020). Harness muss das explizit als "n/a — erst gelistet ab [Datum]" ausgeben.

3. **Mindestdaten-Check:** min_train(252) + step(63) = 315 Rows. Alle Coins mit >=315 Rows gesamt können in Dimension 3 (Universum) laufen.

---

## Common Pitfalls

### Pitfall 1: Regime-Slice auf zu wenige OOS-Punkte

**Was geht schief:** Wenn nur Regime-Daten (z.B. Bear 2018, 364 rows) heruntergeladen werden und min_train=252, step=63 gesetzt sind, liefert Walk-Forward nur ~113 OOS-Tage statt 364. Metriken werden über zu wenige Punkte berechnet.

**Warum:** walkforward.py setzt die ersten min_train Zeilen als Trainingsperiode; OOS beginnt erst danach.

**Wie vermeiden:** Immer volle Preishistorie bis Regime-Ende herunterladen (ab `data_start='2015-01-01'`), dann nach Ausführung von `run_walkforward_with_details()` nur die `net_returns` auf das Regime-Fenster zuschneiden.

**Warning signs:** Wenn `len(regime_net_returns) < 200` bei einem 1-Jahr-Regime — Daten prüfen.

### Pitfall 2: Timezone-Mismatch bei yfinance-Index

**Was geht schief:** `yfinance.download()` gibt einen timezone-naiven DatetimeIndex zurück (in neueren Versionen). `run_walkforward_with_details()` reindext signals auf close.index ohne Timezone-Check — aber `signal_service.evaluate()` macht explizite UTC-Konvertierung. Im Harness muss dieser Schritt manuell erfolgen.

**Warum:** `pd.Timestamp` Vergleiche mit gemischten tz-Zuständen werfen TypeError oder geben falsche Ergebnisse.

**Wie vermeiden:** Nach yfinance-Download immer:
```python
close.index = pd.DatetimeIndex(close.index).tz_localize("UTC")
```
Konsistent für alle Coins im Harness durchführen.

**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes` oder leere Regime-Slices.

### Pitfall 3: vol_forecast.fit_walkforward() Runtime

**Was geht schief:** `fit_walkforward()` für alle 10 Coins mit voller Preishistorie (2015–2025) benötigt ~30-60 Sekunden pro Coin durch den expanding-window LightGBM-Fit. Für 10 Coins × 5 Fenster × Dimensionen → sehr lange Harness-Laufzeit.

**Wie vermeiden:** Im Harness die einfachere rolling-vol-Näherung verwenden (rolling(21).std() × shift(1), fallback 0.60). Das entspricht weitgehend dem V4-1-Edge (rolling vol ≈ HAR-Modell für Trend-following-Kontext). Falls volle Reproduzierbarkeit gewünscht, `fit_walkforward()` einmalig pro Coin cachen.

**Warning signs:** Harness läuft >5 Minuten ohne Ausgabe.

### Pitfall 4: yfinance Download-Fehler bei Netzwerkproblemen

**Was geht schief:** yfinance 1.4.1 kann bei Netzwerkproblemen oder Rate-Limiting leere DataFrames zurückgeben ohne Exception.

**Wie vermeiden:** Nach jedem Download prüfen:
```python
if len(df) == 0:
    print(f"[WARN] {coin}: No data downloaded — insufficient")
    continue
```
Im Harness: Coins mit 0 Rows klar als "download failed" markieren, nicht als "insufficient data". Unterschied ist wichtig für die Dokumentation.

**Warning signs:** `len(df) == 0` bei Coin, der laut Tabelle oben Daten haben sollte.

### Pitfall 5: MATIC-USD Daten-Ende

**Was geht schief:** MATIC-USD liefert Daten nur bis 2025-03-24 (Delisting wegen Umbenennung zu POL). Bull 2023-24 endet per Definition 2024-12-31 → MATIC-USD deckt diesen Zeitraum ab, aber nicht danach.

**Wie vermeiden:** Im Harness regime_end='2024-12-31' für Bull 2023-24 verwenden (nicht 2025-12-31). MATIC-USD ist für alle 4 Regimes testbar (Bear 2018 ausgenommen wegen frühem Listing).

**Warning signs:** `yf.download('MATIC-USD', end='2026-01-01')` gibt weniger Rows als erwartet.

---

## Code Examples

### Dimension 1: Kosten-Sensitivität

```python
# Source: Verifiziert live (2026-06-23) mit echten BTC-USD Daten
# Ergebnis: costs=0.001 Sharpe=1.238, costs=0.002 Sharpe=1.179, costs=0.005 Sharpe=1.000

@dataclass(frozen=True)
class CostResult:
    coin: str
    cost_level: float
    strategy_sharpe: float
    strategy_calmar: float
    strategy_max_dd: float
    baseline_sharpe: float
    baseline_calmar: float
    bah_sharpe: float
    bah_calmar: float
    beats_exposure_matched: bool

def run_cost_sensitivity(
    coins: list[str],
    cost_levels: list[float] = [0.001, 0.002, 0.005],
    ma_window: int = 100,
    data_start: str = "2015-01-01",
) -> list[CostResult]:
    results = []
    for coin in coins:
        raw = yf.download(coin, start=data_start, progress=False, auto_adjust=True)
        if len(raw) < 315:
            continue
        close = raw["Close"].squeeze()
        close.index = pd.DatetimeIndex(close.index).tz_localize("UTC")
        prices_df = pd.DataFrame({"close": close})
        signals = build_signals(close, ma_window=ma_window)
        bah_sharpe, bah_calmar = _buy_and_hold_sharpe(close)

        for cost in cost_levels:
            details = run_walkforward_with_details(prices_df, signals, costs=cost)
            net = details["net_returns"]
            baseline = details["baseline_returns"]
            results.append(CostResult(
                coin=coin, cost_level=cost,
                strategy_sharpe=_sharpe(net), strategy_calmar=_calmar(net),
                strategy_max_dd=_max_drawdown(net),
                baseline_sharpe=_sharpe(baseline), baseline_calmar=_calmar(baseline),
                bah_sharpe=bah_sharpe, bah_calmar=bah_calmar,
                beats_exposure_matched=details["beats_exposure_matched"],
            ))
    return results
```

### Dimension 4: Parameter-Stabilität (SMA-Fenster)

```python
# Source: Verifiziert live (2026-06-23)
# SMA(50): Sharpe=1.149, SMA(100): Sharpe=1.163, SMA(200): Sharpe=0.858
# Wichtig: 100 ist nur leicht besser als 50 — kein klarer Cherry-Pick

def run_parameter_stability(
    coins: list[str] = ["BTC-USD", "ETH-USD"],
    ma_windows: list[int] = [50, 75, 100, 150, 200],
    costs: float = 0.001,
) -> list[dict]:
    results = []
    for coin in coins:
        raw = yf.download(coin, start="2015-01-01", progress=False, auto_adjust=True)
        close = raw["Close"].squeeze()
        close.index = pd.DatetimeIndex(close.index).tz_localize("UTC")
        prices_df = pd.DataFrame({"close": close})

        for window in ma_windows:
            signals = build_signals(close, ma_window=window)
            details = run_walkforward_with_details(prices_df, signals, costs=costs)
            results.append({
                "coin": coin, "ma_window": window,
                "default": window == 100,  # Ankerpunkt markieren
                "sharpe": details["strategy_sharpe"],
                "calmar": details["strategy_calmar"],
                "max_dd": details["strategy_max_dd"],
                "beats": details["beats_exposure_matched"],
            })
    return results
```

### Rich-Tabellen-Output Pattern

```python
# Source: Codebase-Pattern (scripts/compare_sentiment_backtest.py), angepasst
from rich.console import Console
from rich.table import Table

def print_cost_table(results: list[CostResult]) -> None:
    console = Console()
    table = Table(title="Dimension 1: Kosten-Sensitivität (BTC-USD, ETH-USD)")
    table.add_column("Coin", style="bold")
    table.add_column("Kosten")
    table.add_column("Sharpe (Strat)", justify="right")
    table.add_column("Sharpe (ExpMatch)", justify="right")
    table.add_column("Calmar (Strat)", justify="right")
    table.add_column("MaxDD", justify="right")
    table.add_column("Edge?", justify="center")

    for r in results:
        edge = "[green]JA[/green]" if r.beats_exposure_matched else "[red]NEIN[/red]"
        table.add_row(
            r.coin, f"{r.cost_level*100:.1f}%",
            f"{r.strategy_sharpe:.3f}", f"{r.baseline_sharpe:.3f}",
            f"{r.strategy_calmar:.3f}", f"{r.strategy_max_dd:.3f}",
            edge,
        )
    console.print(table)
```

---

## Runtime State Inventory

Diese Phase baut ein neues Skript; kein Rename, kein Refactor. Kein Runtime-State betroffen.

**Stored data:** None — das Harness schreibt keine Daten in die DB (D-10: standalone, kein DB-Zugriff).
**Live service config:** None.
**OS-registered state:** None.
**Secrets/env vars:** None — yfinance benötigt keinen API-Key.
**Build artifacts:** None.

---

## Architecture Patterns — Signal-Pipeline im Harness vs. signal_service.evaluate()

Die bestehende `signal_service.evaluate()` Funktion ist **nicht** für das Harness geeignet:
- Sie ist `async` (per CLAUDE.md Konvention via `asyncio.to_thread`)
- Sie berechnet Signale nur für einen einzigen Zeitpunkt (asof: date) statt über eine ganze Zeitreihe
- Sie macht einen per-Datum Lookup des letzten Wertes

Das Harness muss die Signale **vektoriell** über die komplette Preisserie aufbauen. Die Low-Level-Funktionen (`sma()`, `rsi()`, `macd()`, `consensus_vote()`, `vol_target_size()`) sind dafür direkt importierbar — genau so, wie es `test_signal_engine.py` bereits für Tests macht.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| In-sample Parameter-Optimierung | Walk-Forward OOS (min_train=252, step=63) | Kein Leakage, realistische Schätzung |
| Bruttorendite als Ergebnis | Nettorendite (costs=0.001 Standard) | Kostenbereinigt; ehrlicher |
| Nur Sharpe als Metrik | Sharpe + Calmar + MaxDD + beats_exposure_matched | Vollständiges Bild |
| Einzelner BTC-Test | 10-Coin-Universum, 4 Regime, 5 MA-Fenster | Robustheit bewertbar |

**Deprecated/outdated:**
- Kein direktes yfinance im Application Service (AGENTS.md §8: `yfinance direkt im Application-Service aufrufen` ist verboten). Das Harness ist ein Script, nicht ein Service — dort ist direktes yfinance erlaubt (D-10).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | rolling(21).std() als vol-Näherung ist hinreichend reproduzierbar für den V4-1-Edge | Architecture Patterns Pattern 1 | Edge könnte sich leicht von V4-1 unterscheiden — Harness-Ergebnisse sind dann leicht anders als FORTSCHRITT V4-1 |
| A2 | MATIC-USD yfinance-Daten bis 2025-03-24 sind verlässlich und lückenlos | Data Availability Table | Mögliche Lücken könnten Regime-Tests verzerren |
| A3 | yfinance 1.4.1 liefert konsistent adjustierte Close-Preise (auto_adjust=True) | Standard Stack | Fehler in Split-Anpassung könnten unrealistische Returns erzeugen |

**Verifikation:** A1 wurde live getestet (SMA(50) Sharpe=1.149 vs SMA(100) Sharpe=1.163 — Differenz <2%). Kein signifikantes Problem erwartet.

---

## Open Questions

1. **Vol-Forecast-Nutzung in Dimension 3 (Universum)**
   - Was wir wissen: `fit_walkforward()` liefert bessere Vol-Schätzung als rolling-Näherung
   - Was unklar ist: Für alle 10 Coins ist `fit_walkforward()` zeitintensiv (~5-10 Min gesamt)
   - Empfehlung: Rolling-Näherung für Universums-Dimension; explizit im Report dokumentieren, dass das eine vereinfachte Vol-Schätzung ist

2. **MATIC-USD Naming in Report**
   - Was wir wissen: MATIC wurde zu POL umbenannt; Daten enden 2025-03-24
   - Was unklar ist: Ob im Report MATIC oder POL als Coin-Name erscheinen soll
   - Empfehlung: "MATIC-USD (→POL, Daten bis 2025-03-24)" im Report verwenden

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 (System) | Harness-Script | ✓ | 3.13.3 | — |
| yfinance | Alle 4 Dimensionen | ✓ | 1.4.1 | — |
| pandas | Alle Berechnungen | ✓ | 3.0.3 | — |
| numpy | Alle Berechnungen | ✓ | 2.2.6 | — |
| rich | Tabellen-Output | ✓ | 15.0.0 | print()-basierte Tabellen |
| scikit-learn | vol_forecast.py (LinearRegression) | ✓ | 1.9.0 | — |
| lightgbm | vol_forecast.py (optionaler LGBM-Zweig) | ✓ | 4.6.0 | HAR-Fallback bereits implementiert |
| Netzwerkzugang | yfinance Downloads | Unbekannt zur Test-Zeit | — | Synthetische Daten NUR für Unit-Tests (D-02) |

**Missing dependencies with no fallback:** keine.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (im Venv) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest backend/tests/unit/application/test_robustness_harness.py -q` |
| Full suite command | `pytest backend/tests/unit/ -q -m unit` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-03 | cost_sensitivity() gibt Ergebnisse für 3 Kostenstufen zurück | unit | `pytest test_robustness_harness.py::TestCostSensitivity -x` | ❌ Wave 0 |
| D-04 | run_regime() schneidet OOS korrekt auf Regime-Fenster zu | unit | `pytest test_robustness_harness.py::TestRegimeSplit -x` | ❌ Wave 0 |
| D-05 | Coins mit unzureichenden Daten werden als "insufficient" markiert | unit | `pytest test_robustness_harness.py::TestUniversumInsufficient -x` | ❌ Wave 0 |
| D-06 | build_signals() mit verschiedenen ma_windows gibt unterschiedliche Sharpe | unit | `pytest test_robustness_harness.py::TestParameterStability -x` | ❌ Wave 0 |
| D-07 | Buy&Hold-Baseline korrekt berechnet (avg_exposure ≈ 1.0) | unit | `pytest test_robustness_harness.py::TestBuyAndHold -x` | ❌ Wave 0 |
| D-09 | Look-Ahead-Guard: build_signals() wendet shift(1) auf binäre Signale an | unit | `pytest test_robustness_harness.py::TestNoLookAhead -x` | ❌ Wave 0 |
| D-10 | robustness_check.py ist importierbar und gibt dict zurück | unit | `pytest test_robustness_harness.py::TestImportable -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/unit/application/test_robustness_harness.py -q`
- **Per wave merge:** `pytest backend/tests/unit/ -q -m unit`
- **Phase gate:** Full unit suite grün vor `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/unit/application/test_robustness_harness.py` — alle 7 Requirements oben
- [ ] Synthetische Fixture (trending prices 600+ rows, ma_window-parametrierbar)
- [ ] Framework install: bereits vorhanden (kein Gap)

---

## Security Domain

Diese Phase hat keinen Security-Scope. Keine Authentifizierung, keine Nutzer-Inputs, keine API-Endpunkte, keine Datenbankzugriffe. Das Harness ist ein lokales Analyse-Skript.

Einziger relevanter Punkt: Kein API-Key in Code (AGENTS.md §1 Regel 5). yfinance benötigt keinen API-Key — konform.

---

## Project Constraints (from CLAUDE.md)

- `asyncio.to_thread()` für Sync-ML-Code in async Contexten (NICHT im Harness nötig — Harness ist sync)
- Kein `yfinance` direkt im Application-Service — im Script OK (D-10 explizit erlaubt)
- `print()` statt `logging` in Scripts grundsätzlich vertretbar; in Library-Code Logging verwenden
- TDD-Pflicht: Tests vor Implementierung (D-09 explizit)
- Kein `random` ohne Seed (D-09)
- Kein direkter Push auf `main` oder `develop` (PR-Pflicht)

---

## Sources

### Primary (HIGH confidence)

- `backend/application/backtest/walkforward.py` — vollständig gelesen; run_walkforward, run_walkforward_with_details, _sharpe, _calmar, _max_drawdown, costs-Parameter verifiziert [VERIFIED: Codebase]
- `backend/application/signals/indicators.py` — sma(close, window) Signatur verifiziert [VERIFIED: Codebase]
- `backend/application/signals/vol_forecast.py` — fit_walkforward() standalone-Betrieb verifiziert (kein externer Artifact nötig) [VERIFIED: live getestet]
- `backend/application/signals/consensus.py`, `sizing.py` — Volltext gelesen [VERIFIED: Codebase]
- `scripts/compare_sentiment_backtest.py` — Skript-Pattern für das Harness [VERIFIED: Codebase]

### Secondary (MEDIUM confidence)

- yfinance Datenverfügbarkeit — live geprüft für alle 10 Coins (2026-06-23) [VERIFIED: yfinance 1.4.1 live download]
- Regime-Coverage — live geprüft für alle 4 Regimes × 6 Coins [VERIFIED: yfinance 1.4.1 live download]
- Cost-Sensitivity-Ergebnisse — live berechnet (BTC-USD 2017-2024): costs=0.001 Sharpe=1.238, costs=0.002 Sharpe=1.179, costs=0.005 Sharpe=1.000 [VERIFIED: live getestet]
- SMA-Fenster-Ergebnisse — live berechnet (BTC-USD 2017-2022): SMA(50)=1.149, SMA(100)=1.163, SMA(200)=0.858 [VERIFIED: live getestet]

### Tertiary (LOW confidence)

- MATIC-USD → POL-USD Umbenennung — aus yfinance-Download-Ergebnis erschlossen (Daten enden 2025-03-24); POL-USD unter yfinance nicht verfügbar [VERIFIED: yfinance live, aber offizieller Rename-Status ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — alle Pakete im Venv verifiziert
- yfinance-Datenverfügbarkeit: HIGH — live geprüft für alle Coins und Regime
- Harness-Architektur: HIGH — Pipeline live getestet (Build-Signal + WF + Regime-Slice)
- Test-Strategie: HIGH — Muster aus bestehendem test_walkforward.py und test_signal_engine.py
- Vol-Forecast-Näherung: MEDIUM — rolling-Näherung statt fit_walkforward() kann minimale Abweichungen erzeugen

**Research date:** 2026-06-23
**Valid until:** 2026-07-23 (yfinance API stabil, aber Daten-Endpunkte können sich ändern)
