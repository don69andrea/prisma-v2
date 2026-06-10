# Spec: Monte Carlo 3a Retirement Simulator

**Issue:** #71 (to be created)
**Date:** 2026-06-10
**Author:** Andrea Petretta
**Status:** Planned

---

## Ziel

Nutzer geben ihr 3a-Portfolio (Tickers + Gewichte) und eine monatliche Einzahlung ein. PRISMA simuliert 10'000 Wealth-Paths über bis zu 30 Jahre (Geometric Brownian Motion + Korrelationsmatrix) und zeigt P5/P50/P95-Bänder als Fan-Chart. Beantwortet: *"Was habe ich in 30 Jahren?"*

---

## Nicht-Ziele

- Steueroptimierung (→ SteuerAgent, Issue #58)
- Live-Marktdaten für Simulation (historische Parameter reichen)
- Mehrere Szenarien gleichzeitig vergleichen (v1)
- Inflation-Adjustment (CHF CPI — zukünftiges Feature)

---

## Architektur

### Backend — `MonteCarloService`

**Neue Datei:** `backend/application/services/monte_carlo_service.py`

```python
@dataclass(frozen=True)
class MonteCarloInput:
    holdings: list[HoldingWeight]   # {ticker: str, weight: float}, sum=1.0
    monthly_contribution: float     # CHF, default 588 (7'056/12)
    years: int                      # 1–40, default 30
    initial_value: float            # CHF, default 0
    n_simulations: int              # default 10_000

@dataclass(frozen=True)
class MonteCarloResult:
    p5: list[float]                 # len = years*12, monthly wealth path P5
    p50: list[float]
    p95: list[float]
    final_distribution: list[float] # 10k Endwerte für Histogramm
    prob_positive_return: float     # P(Endwert > contribution_total)
    prob_500k: float                # P(Endwert > 500_000 CHF)
    contribution_total: float       # Einfache Summe aller Einzahlungen
    months: int                     # years * 12
```

**Algorithmus:**
1. Für jeden Ticker: historische Tagesrenditen (252 Tage via YFinanceSwissAdapter) → `μ` (mean daily return) + `σ` (std dev)
2. ML-Forward-Return aus `MLPredictionService` → adjustiert `μ` (blend: 0.5 * historical + 0.5 * ml_predicted)
3. Korrelationsmatrix der Holdings aus historischen Renditen (Numpy/Scipy)
4. Cholesky-Zerlegung der Korrelationsmatrix für korrelierte Zufallszahlen
5. GBM pro Monat: `S_{t+1} = S_t * exp((μ - 0.5σ²)Δt + σ√Δt * Z)` mit `Z ~ N(0,1)` korreliert
6. Monatliche Einzahlung wird am Monatsanfang addiert
7. Portfolio-Wert = gewichtete Summe der Einzeltitel-Werte
8. N=10'000 Simulationen, Percentile berechnen

**Performance:** Numpy-Vektorisierung — alle 10'000 Pfade als Matrix berechnen, nicht in einem Loop.

### API

```
POST /api/v1/portfolio/monte-carlo
Body: MonteCarloInput
Response: MonteCarloResult
```

Kein Streaming (Berechnung <3s mit Numpy-Vektorisierung).

### Frontend — `/portfolio/simulator`

**Layout (zwei Spalten, responsive):**

**Links — Eingabe-Panel (Glassmorphism-Card):**
- Portfolio-Builder: Ticker-Input + Gewichts-Slider per Holding, Auto-Normalize auf 100%
- Monatliche Einzahlung: Slider CHF 0–2'000, Label zeigt aktuellen Wert live
- Jahre: Zeitstrahl-Slider 1–40, Markierungen bei 10/20/30 Jahren
- Startkapital: Zahl-Input CHF
- *"Swiss 3a Max: CHF 7'056 / Jahr"* Hint-Badge

**Rechts — Fan-Chart (SVG/D3-ähnlich, custom):**
- P5–P95-Band: gefüllter Bereich in `rgba(100, 50, 255, 0.2)` (Lila)
- P50-Linie: Neon-Weiss, `stroke-width: 2`, Glow-Filter
- Contribution-Linie: gestrichelt, Grau (was man ohne Rendite hätte)
- X-Achse: Jahre, Y-Achse: CHF (logarithmisch optional)
- Hover: vertikale Cursor-Linie, Tooltip mit P5/P50/P95 am jeweiligen Jahr

**Futuristische UX:**
- **Simulate-Button:** Puls-Animation (Neon-Ring expandiert), während POST läuft
- **Endwert-Counter:** P50-Endwert animiert hoch (CountUp.js oder custom RAF-Loop), 1.5s
- **Probability-Badges:**
  - *"87% Chance CHF 500k+"* — Neon-Grün Badge
  - *"Kapital × 4.2 im Median"* — Lila Badge
- **Konfetti-Trigger:** Bei P50 > CHF 1M ein subtiler Partikel-Effekt (canvas-confetti, 1x)
- Beim ersten Render: Chart fährt von links nach rechts auf (SVG `stroke-dasharray` Animation)

---

## Validierungen

- Gewichte müssen 100% ergeben (Auto-Normalize mit Warning wenn manuell)
- Min. 1 Holding, max. 10
- `years` 1–40
- `monthly_contribution` ≥ 0

---

## Tests

- Unit: `test_monte_carlo_service.py` — P50 liegt im erwarteten Bereich (stochastisch, tolerance), `prob_positive_return` ∈ [0,1], Korrelationsmatrix positiv definit
- Unit: Contribution-Total korrekt berechnet
- Integration: API-Endpoint gibt valide `MonteCarloResult` zurück

---

## Akademischer + VIAC Impact

Visualisiert Unsicherheit ehrlich (Bänder statt Punktprognose) — das ist financial modelling best practice. Direkt relevant für VIAC 3a: beantwortet die Kernfrage jedes Langzeit-Investors.
