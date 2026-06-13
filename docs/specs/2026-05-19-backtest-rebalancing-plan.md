# Backtest `_simulate_portfolio` — Drift + Monthly-Reset Plan

> **For agentic workers:** Implementiere diesen Plan Schritt für Schritt. Schritte nutzen Checkbox-Syntax (`- [ ]`) zum Tracking.

**Goal:** `_simulate_portfolio` an Backtest-Spec v1.1 §5 angleichen — Drift-Akkumulation pro Tag + monatlicher Reset auf 1/N am letzten Trading-Day jedes Kalendermonats. Heutiger naiver `returns.mean(axis=1)` ist mathematisch ein kontinuierlich rebalanciertes EW-Portfolio und entspricht NICHT der Spec.

**Architecture:** Reiner Service-internal-Refactor in `backend/application/services/backtest_service.py`. Kein neuer Port, kein DB-Schema-Change, kein REST-Layer-Touch. Helper `_monthly_rebalance_dates` als private static method. TDD: erst die zwei neuen Tests aus Spec §9.1 schreiben, dann Loop implementieren.

**Tech Stack:** Python 3.12, pandas, numpy, pytest, mypy strict, ruff.

**Spec:** `docs/specs/2026-05-12-backtest-service-light.md` §5, §9.1, §10

**Issue:** #140

---

## File Structure

| File | Verantwortlichkeit |
|---|---|
| `backend/application/services/backtest_service.py` (MOD) | `_monthly_rebalance_dates` (NEU) + `_simulate_portfolio` (REWRITE) |
| `backend/tests/unit/application/test_backtest_service.py` (MOD) | 2 neue Tests: Drift-Math + Monthly-Reset |
| `backend/tests/unit/application/test_backtest_portfolio_simulation.py` (NEU, optional) | Falls Trennung der Sim-Tests vom Service-Test sauberer ist |
| `backend/tests/integration/test_backtests_endpoint.py` (MOD) | Goldene Werte ggf. anpassen (Toleranz ±0.5% laut Spec §9.3) |
| `docs/AI-USAGE.md` (MOD) | Reflexions-Eintrag |

---

## Task 1: Helper `_monthly_rebalance_dates`

**Files:**
- Modify: `backend/application/services/backtest_service.py`

- [ ] **Step 1.1: Helper-Funktion implementieren**

Direkt unter `_simulate_portfolio` als zweite `@staticmethod`:

```python
@staticmethod
def _monthly_rebalance_dates(idx: pd.DatetimeIndex) -> set[pd.Timestamp]:
    """Letzter Trading-Day jedes Kalendermonats im Index.

    Deterministisch aus dem Index abgeleitet — keine Holiday-Calendar-Annahmen.
    Implementation per ``pd.Grouper(freq="ME")``.
    """
    grouped = pd.Series(idx, index=idx).groupby(pd.Grouper(freq="ME"))
    return set(grouped.last().dropna())
```

- [ ] **Step 1.2: Unit-Test**

In `test_backtest_service.py`:

```python
def test_monthly_rebalance_dates_picks_last_trading_day_per_month():
    # 3 Monate Trading-Days
    idx = pd.bdate_range("2025-01-01", "2025-03-31", tz="UTC")
    dates = BacktestService._monthly_rebalance_dates(idx)
    # Letzte Bday im Januar / Februar / März
    assert pd.Timestamp("2025-01-31", tz="UTC") in dates
    assert pd.Timestamp("2025-02-28", tz="UTC") in dates
    assert pd.Timestamp("2025-03-31", tz="UTC") in dates
    assert len(dates) == 3
```

- [ ] **Step 1.3: Edge-Case-Test: weniger als ein voller Monat**

```python
def test_monthly_rebalance_dates_single_partial_month():
    idx = pd.bdate_range("2025-01-05", "2025-01-20", tz="UTC")
    dates = BacktestService._monthly_rebalance_dates(idx)
    # `last()` im Grouper liefert immer den letzten verfügbaren Tag im Index
    # — bei nur 2 Wochen Januar ist das der 2025-01-20
    assert dates == {pd.Timestamp("2025-01-20", tz="UTC")}
```

---

## Task 2: `_simulate_portfolio` mit Drift + Monthly-Reset (TDD)

**Files:**
- Modify: `backend/application/services/backtest_service.py`
- Modify: `backend/tests/unit/application/test_backtest_service.py`

- [ ] **Step 2.1: Drift-Math-Test SCHREIBEN (rot) — Spec §9.1 Test b**

2 Assets × 5 Tage, deterministische Returns +10% / -5% / +5% / -2% / +1%. Handrechnung:

```
# Beide Assets identische Returns → Portfolio = identische Returns
# Kein Rebalancing (5 Tage < 1 Monat)
# Cumulative: 1.10 · 0.95 · 1.05 · 0.98 · 1.01 = ?
# = 1.10 * 0.95 = 1.045
# * 1.05         = 1.09725
# * 0.98         = 1.0753050
# * 1.01         = 1.0860580 (≈ 1.086058)
```

Test (asymmetrische Returns für Drift-Effekt — Asset A schwankt anders als B):

```python
def test_simulate_portfolio_drift_math_two_assets_five_days():
    """Spec §9.1 Test b: Drift-Math gegen Handrechnung."""
    idx = pd.bdate_range("2025-01-06", periods=5, tz="UTC")
    # Day-on-day Prices, so dass pct_change exakt die Spec-Returns liefert
    prices = pd.DataFrame(
        {
            # Asset A: +10%, -5%, +5%, -2%, +1%
            "A": [100.0, 110.0, 104.5, 109.725, 107.530, 108.605],
            # Asset B: +5%, +5%, -2%, +1%, 0%   (anders → Drift entsteht)
            "B": [100.0, 105.0, 110.25, 108.045, 109.125, 109.125],
        },
        index=pd.bdate_range("2025-01-03", periods=6, tz="UTC"),
    )
    series = BacktestService._simulate_portfolio(prices, ["A", "B"])
    # Handrechnung der Portfolio-Werte mit Drift (siehe Plan-Header §2.1):
    expected = [...]  # 6 Werte, präzise per NumPy berechnet
    pd.testing.assert_series_equal(
        series, pd.Series(expected, index=prices.index), rtol=1e-6
    )
```

**Hinweis für Implementer:** `expected`-Werte vor Implementation per separater Numpy-Berechnung erzeugen und im Test hartkodieren (Golden-Dataset-Style). Begründung: wenn Implementation gegen sich selbst geprüft wird, fängt der Test nichts.

- [ ] **Step 2.2: Monthly-Reset-Test SCHREIBEN (rot) — Spec §9.1 Test a**

```python
def test_simulate_portfolio_resets_to_equal_weight_after_month_end():
    """Spec §9.1 Test a: nach Monatsende Reset auf 50/50."""
    # 2 Monate Trading-Days, Asset A stark steigend (würde ohne Reset
    # Portfolio dominieren), Asset B flat
    idx = pd.bdate_range("2025-01-01", "2025-02-28", tz="UTC")
    n = len(idx)
    prices = pd.DataFrame(
        {
            "A": np.linspace(100, 200, n),  # +100% über 2 Monate
            "B": [100.0] * n,                # flat
        },
        index=idx,
    )
    series = BacktestService._simulate_portfolio(prices, ["A", "B"])

    # Ende Januar: A hat gedriftet → Gewicht > 50%. Reset würde auf 50/50 zurücksetzen.
    # Verifikation: Portfolio-Return am 1. Februar-Trading-Day muss approx (0.5 * ret_A + 0.5 * ret_B) sein,
    # nicht die gedrifteten Gewichte.
    feb_start = pd.Timestamp("2025-02-03", tz="UTC")
    feb_ret = series.loc[feb_start] / series.shift(1).loc[feb_start] - 1
    ret_a_feb = prices["A"].loc[feb_start] / prices["A"].shift(1).loc[feb_start] - 1
    ret_b_feb = 0.0
    expected_feb_ret = 0.5 * ret_a_feb + 0.5 * ret_b_feb
    assert abs(feb_ret - expected_feb_ret) < 1e-6, (
        f"Reset nicht ausgeführt: feb_ret={feb_ret}, expected={expected_feb_ret}"
    )
```

- [ ] **Step 2.3: Implementation (grün)**

Komplett-Rewrite von `_simulate_portfolio`:

```python
@staticmethod
def _simulate_portfolio(prices: pd.DataFrame, tickers: list[str]) -> pd.Series:
    """Equal-Weight-Portfolio mit Drift + monatlichem Reset auf 1/N.

    Spec: docs/specs/2026-05-12-backtest-service-light.md §5

    Edge-Cases:
    - Late-Listing: Spec §5 dokumentiert Look-Ahead-Bias. Diese Light-Variante
      nimmt statisches Universum für die ganze Periode an.
    - Delisting: `ffill()` vor `pct_change()` (Approximation, OK für MVP).
    - <1 voller Monat: kein Reset, reine Drift.
    - Keine verfügbaren Ticker: Flat-Serie (1.0).
    """
    available = [t for t in tickers if t in prices.columns]
    if not available:
        return pd.Series([1.0] * len(prices), index=prices.index)

    sub = prices[available].ffill()
    returns = sub.pct_change().fillna(0.0)
    n = len(available)
    rebalance_dates = BacktestService._monthly_rebalance_dates(prices.index)

    weights = np.full(n, 1.0 / n)
    portfolio_returns: list[float] = []

    for date in prices.index:
        daily_ret = float((weights * returns.loc[date].values).sum())
        portfolio_returns.append(daily_ret)

        # Drift: Gewichte um Tagesperformance verschieben
        weights = weights * (1.0 + returns.loc[date].values)
        total = weights.sum()
        if total > 0:
            weights = weights / total
        else:
            weights = np.full(n, 1.0 / n)  # Fallback bei pathologischen Daten

        # Monatlicher Reset auf 1/N am letzten Trading-Day des Monats
        if date in rebalance_dates:
            weights = np.full(n, 1.0 / n)

    return (1.0 + pd.Series(portfolio_returns, index=prices.index)).cumprod()
```

- [ ] **Step 2.4: Tests aus 2.1 + 2.2 ausführen, beide grün**

```bash
pytest backend/tests/unit/application/test_backtest_service.py -k "drift_math or resets_to_equal_weight" -v
```

---

## Task 3: Bestehende Tests + Golden-Dataset prüfen

**Files:**
- Verify: `backend/tests/unit/application/test_backtest_service.py`
- Verify: `backend/tests/integration/test_backtests_endpoint.py`
- Verify: `backend/tests/fixtures/backtest/perfect_strategy.json` (falls existiert)

- [ ] **Step 3.1: Volle Test-Suite laufen lassen**

```bash
pytest backend/tests/unit/application/test_backtest_service.py -v
pytest backend/tests/integration/test_backtests_endpoint.py -v
```

- [ ] **Step 3.2: Bei Failures: Erwartungswerte gegen neue Implementation prüfen**

Erwartung: das bestehende `returns.mean(axis=1)`-Verhalten ist für `<1 Monat`-Tests identisch (kein Reset → reine Drift). Für längere Perioden weichen die Werte ab. Anpassung der Goldenen-Werte nur, wenn Spec-Konformität gegeben ist — nie blind auf neuen Output kalibrieren ohne Begründung.

- [ ] **Step 3.3: Toleranz im Golden-Dataset prüfen (Spec §9.3)**

±0.5% ist die initial-Toleranz. Wenn der erste Run grün läuft, kann auf ±0.1% verschärft werden (in Folge-PR).

---

## Task 4: Manuelle Verifikation der Backtest-Light-Akzeptanz

**Files:**
- Run: Live-API gegen Backend

- [ ] **Step 4.1: Backend starten, Backtest gegen Stub-Provider laufen lassen**

```bash
# In separater Shell
docker-compose up postgres
poetry run uvicorn backend.interfaces.rest.app:app --reload
```

- [ ] **Step 4.2: Backtest via curl auslösen, Response-Shape verifizieren**

```bash
# Erstmal einen ModelRun holen / erstellen
curl -X POST http://localhost:8000/api/v1/runs -H "Content-Type: application/json" \
     -d '{"universe_id": "<UUID>"}'
# Mit der returned model_run_id:
curl -X POST http://localhost:8000/api/v1/backtests/run -H "Content-Type: application/json" \
     -d '{
       "model_run_id": "<UUID>",
       "start_date": "2025-01-01",
       "end_date": "2025-12-31",
       "top_n": 3,
       "benchmark_ticker": "^SSMI"
     }'
```

Sanity-Check der Response: 3 Portfolio-Kurven, alle ≥ 0, monoton-ähnlich, Reset-Effekt sichtbar an Monatsenden (nicht-perfekt-glatter Verlauf).

---

## Task 5: AI-USAGE-Eintrag

**Files:**
- Modify: `docs/AI-USAGE.md`

- [ ] **Step 5.1: Eintrag im Format aus existierenden Einträgen**

```markdown
## 2026-MM-DD · feat(quant): _simulate_portfolio mit Drift + Monthly-Reset (#140)
- **Agent**: Claude Code / <Model>
- **Scope**: `_simulate_portfolio` an Backtest-Spec v1.1 §5 angeglichen — naiver
  `returns.mean(axis=1)` ersetzt durch echte Drift-Akkumulation pro Tag +
  monatlichen Reset auf 1/N. Neuer Helper `_monthly_rebalance_dates`. Drift-Math-
  Test mit Handrechnung gegen 5-Tage-Sequenz, Reset-Test gegen 2-Monats-Sequenz.
- **Was gut lief**: ...
- **Was nicht klappte**: ...
- **Nachbearbeitung nötig bei**: ...
- **Autor**: Fabia
```

---

## Task 6: PR vorbereiten

- [ ] **Step 6.1: Verifikation** (siehe `Verifikation vor Abschluss`)

```bash
ruff check backend/
mypy backend/ --strict
pytest backend/tests/unit/application/test_backtest_service.py -v
pytest backend/tests/integration/test_backtests_endpoint.py -v
pytest backend/ --cov=backend.application.services.backtest_service --cov-report=term-missing
```

Coverage `_simulate_portfolio` + `_monthly_rebalance_dates` ≥ 95%.

- [ ] **Step 6.2: Commit + Push**

Commit-Message-Stil:

```
feat(quant): _simulate_portfolio mit Drift + Monthly-Reset (closes #140)

- Helper `_monthly_rebalance_dates` (letzter Trading-Day pro Monat via pd.Grouper)
- `_simulate_portfolio` rewrite: Drift-Akkumulation pro Tag + Reset auf 1/N
  am letzten Trading-Day jedes Kalendermonats (Spec §5)
- Drift-Math-Test: 5-Tage-Sequenz gegen NumPy-Handrechnung
- Reset-Test: 2-Monats-Sequenz mit stark divergierenden Asset-Returns
- AI-USAGE-Eintrag
```

- [ ] **Step 6.3: PR via `gh pr create`** mit Body, der Spec-Referenz, Akzeptanzkriterien-Checklist und Test-Output enthält.

---

## Bewusste Nicht-Ziele

- **Echtes Re-Ranking pro Monat** (Spec §11.1): Out of scope, 5-10× Aufwand. Folge-Slice.
- **Walk-Forward-Universe**: Out of scope (Spec §17 Backlog).
- **Vectorize**: Loop-Variante ist deutlich lesbarer als vectorized via `np.where`. Performance OK für ≤50 Ticker × 5J. Falls später Hot-Path, eigenes Vectorize-Issue mit Drift-Math-Test als Regression-Guard.
