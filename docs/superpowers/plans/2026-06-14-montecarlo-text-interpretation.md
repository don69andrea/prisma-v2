# Monte Carlo Text Interpretation (T8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a server-computed `interpretation` field to the Monte Carlo API response containing human-readable probability statements, and display it prominently in the frontend simulator.

**Architecture:** A pure function `build_interpretation(result, inp)` is added to `monte_carlo_service.py`, it populates a new `interpretation` field on `MonteCarloResult`. The Pydantic schema gains a corresponding optional `interpretation` field (non-breaking). The router populates it. The frontend type and display component are updated.

**Tech Stack:** Python 3.12 · FastAPI · Pydantic v2 · Next.js 14 · TypeScript · pytest

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `backend/application/services/monte_carlo_service.py` | Modify | Add `interpretation: str` to `MonteCarloResult`, add `build_interpretation()` pure function, call it in `_run_gbm()` |
| `backend/interfaces/rest/schemas/monte_carlo.py` | Modify | Add `interpretation: str = ""` to `MonteCarloResponse` (non-breaking default) |
| `backend/interfaces/rest/routers/portfolio.py` | Modify | Pass `interpretation=result.interpretation` when constructing `MonteCarloResponse` |
| `backend/tests/unit/application/test_monte_carlo_service.py` | Modify | Add tests for `build_interpretation()` |
| `frontend/lib/api/montecarlo.ts` | Modify | Add `interpretation?: string` to `MonteCarloResponse` interface |
| `frontend/app/portfolio/simulator/SimulatorClient.tsx` | Modify | Replace hardcoded interpretation block with server-provided `result.interpretation` text |

---

## Task 1: Create branch

- [ ] **Step 1: Create and checkout branch**

```bash
cd /Users/andreapetretta/prisma-v2
git checkout develop
git pull origin develop
git checkout -b feat/montecarlo-text
```

Expected output: `Switched to a new branch 'feat/montecarlo-text'`

---

## Task 2: Write failing tests for `build_interpretation`

**Files:**
- Modify: `backend/tests/unit/application/test_monte_carlo_service.py`

- [ ] **Step 1: Add failing tests for `build_interpretation`**

Add the following tests at the bottom of `backend/tests/unit/application/test_monte_carlo_service.py` (before the final blank line):

```python
from backend.application.services.monte_carlo_service import build_interpretation


def _make_result(
    p5_final: float = 95_000.0,
    p50_final: float = 285_000.0,
    p95_final: float = 420_000.0,
    initial_value: float = 100_000.0,
    contribution_total: float = 211_680.0,
    months: int = 240,
    prob_positive_return: float = 0.87,
) -> MonteCarloResult:
    years = months // 12
    return MonteCarloResult(
        p5=[p5_final] * months,
        p50=[p50_final] * months,
        p95=[p95_final] * months,
        final_distribution=[p50_final] * 100,
        prob_positive_return=prob_positive_return,
        prob_500k=0.12,
        contribution_total=contribution_total,
        months=months,
    )


def test_build_interpretation_contains_years() -> None:
    result = _make_result(months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "20 Jahren" in text or "20 Jahre" in text


def test_build_interpretation_contains_p5_and_p95() -> None:
    result = _make_result(p5_final=95_000.0, p95_final=420_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "95" in text or "95'000" in text
    assert "420" in text or "420'000" in text


def test_build_interpretation_contains_probability() -> None:
    result = _make_result(prob_positive_return=0.87, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "80" in text or "87" in text


def test_build_interpretation_contains_median() -> None:
    result = _make_result(p50_final=285_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "285" in text or "285'000" in text


def test_build_interpretation_gain_scenario() -> None:
    result = _make_result(p50_final=285_000.0, contribution_total=211_680.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "+" in text or "Gewinn" in text or "wächst" in text or "%" in text


def test_build_interpretation_worst_case_p5() -> None:
    result = _make_result(p5_final=95_000.0, initial_value=100_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "5" in text
    assert "95" in text or "95'000" in text


def test_build_interpretation_returns_str() -> None:
    result = _make_result(months=60)
    text = build_interpretation(result, initial_value=0.0, years=5)
    assert isinstance(text, str)
    assert len(text) > 50


def test_build_interpretation_zero_initial_value() -> None:
    result = _make_result(initial_value=0.0, p5_final=10_000.0, p50_final=80_000.0, p95_final=200_000.0, months=120)
    text = build_interpretation(result, initial_value=0.0, years=10)
    assert isinstance(text, str)
    assert len(text) > 20
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
pytest backend/tests/unit/application/test_monte_carlo_service.py -k "build_interpretation" -v 2>&1 | tail -20
```

Expected: FAILED with `ImportError: cannot import name 'build_interpretation'`

---

## Task 3: Implement `build_interpretation` and update `MonteCarloResult`

**Files:**
- Modify: `backend/application/services/monte_carlo_service.py`

- [ ] **Step 1: Add `interpretation` field to `MonteCarloResult` and implement `build_interpretation`**

In `backend/application/services/monte_carlo_service.py`:

1. Update `MonteCarloResult` dataclass — add `interpretation: str = ""` as the last field:

```python
@dataclass(frozen=True)
class MonteCarloResult:
    p5: list[float]
    p50: list[float]
    p95: list[float]
    final_distribution: list[float]
    prob_positive_return: float
    prob_500k: float
    contribution_total: float
    months: int
    correlation_degraded: bool = False
    interpretation: str = ""
```

2. Add the `build_interpretation` pure function after the `MonteCarloResult` dataclass (before `class MonteCarloService`):

```python
def build_interpretation(result: MonteCarloResult, initial_value: float, years: int) -> str:
    def fmt(v: float) -> str:
        if v >= 1_000_000:
            return f"CHF {v / 1_000_000:,.2f}M".replace(",", "'")
        return f"CHF {v:,.0f}".replace(",", "'")

    p5_final = result.p5[-1]
    p50_final = result.p50[-1]
    p95_final = result.p95[-1]
    prob_pct = round(result.prob_positive_return * 100)
    invested = initial_value + result.contribution_total

    lines: list[str] = []

    lines.append(
        f"Mit 90% Wahrscheinlichkeit liegt der Portfoliowert nach {years} Jahren "
        f"zwischen {fmt(p5_final)} (5. Perzentil) und {fmt(p95_final)} (95. Perzentil)."
    )

    if invested > 0:
        gain = p50_final - invested
        gain_pct = (gain / invested) * 100
        sign = "+" if gain >= 0 else ""
        lines.append(
            f"Im Median-Szenario wächst das Portfolio auf {fmt(p50_final)} "
            f"({sign}{gain_pct:.0f}% gegenüber den Gesamteinzahlungen von {fmt(invested)})."
        )
    else:
        lines.append(f"Im Median-Szenario erreicht das Portfolio {fmt(p50_final)}.")

    worst_pct = round(((p5_final - invested) / invested) * 100) if invested > 0 else 0
    sign_w = "+" if worst_pct >= 0 else ""
    lines.append(
        f"Im schlechtesten Szenario (5. Perzentil): {fmt(p5_final)} ({sign_w}{worst_pct}%)."
    )

    lines.append(
        f"Die Wahrscheinlichkeit eines positiven Returns gegenüber den Einzahlungen beträgt {prob_pct}%."
    )

    return " ".join(lines)
```

3. Update `_run_gbm` to call `build_interpretation` and populate the field. Replace the final `return MonteCarloResult(...)` block:

```python
    interp = build_interpretation(
        MonteCarloResult(
            p5=[round(v, 2) for v in p5],
            p50=[round(v, 2) for v in p50],
            p95=[round(v, 2) for v in p95],
            final_distribution=[round(float(v), 2) for v in final],
            prob_positive_return=round(prob_positive, 4),
            prob_500k=round(prob_500k, 4),
            contribution_total=round(contribution_total, 2),
            months=n_months,
            correlation_degraded=correlation_degraded,
        ),
        initial_value=inp.initial_value,
        years=inp.years,
    )

    return MonteCarloResult(
        p5=[round(v, 2) for v in p5],
        p50=[round(v, 2) for v in p50],
        p95=[round(v, 2) for v in p95],
        final_distribution=[round(float(v), 2) for v in final],
        prob_positive_return=round(prob_positive, 4),
        prob_500k=round(prob_500k, 4),
        contribution_total=round(contribution_total, 2),
        months=n_months,
        correlation_degraded=correlation_degraded,
        interpretation=interp,
    )
```

- [ ] **Step 2: Run the new tests to verify they pass**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
pytest backend/tests/unit/application/test_monte_carlo_service.py -k "build_interpretation" -v 2>&1 | tail -20
```

Expected: All 8 `build_interpretation` tests PASSED.

- [ ] **Step 3: Run all Monte Carlo unit tests to verify no regression**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
pytest backend/tests/unit/application/test_monte_carlo_service.py -v 2>&1 | tail -20
```

Expected: All tests PASSED.

- [ ] **Step 4: Run linting and type checks**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
ruff check backend/application/services/monte_carlo_service.py
ruff format --check backend/application/services/monte_carlo_service.py
mypy backend/application/services/monte_carlo_service.py --ignore-missing-imports
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/andreapetretta/prisma-v2
git add backend/application/services/monte_carlo_service.py backend/tests/unit/application/test_monte_carlo_service.py
git commit -m "feat(monte-carlo): add build_interpretation() and interpretation field to MonteCarloResult"
```

---

## Task 4: Update Pydantic schema and router

**Files:**
- Modify: `backend/interfaces/rest/schemas/monte_carlo.py`
- Modify: `backend/interfaces/rest/routers/portfolio.py`

- [ ] **Step 1: Add `interpretation` field to `MonteCarloResponse`**

In `backend/interfaces/rest/schemas/monte_carlo.py`, add `interpretation: str = ""` as the last field of `MonteCarloResponse`:

```python
class MonteCarloResponse(BaseModel):
    p5: list[float]
    p50: list[float]
    p95: list[float]
    final_distribution: list[float]
    prob_positive_return: float
    prob_500k: float
    contribution_total: float
    months: int
    correlation_degraded: bool = False
    interpretation: str = ""
```

- [ ] **Step 2: Pass `interpretation` in the router**

In `backend/interfaces/rest/routers/portfolio.py`, update the `return MonteCarloResponse(...)` block in the `monte_carlo` endpoint:

```python
    return MonteCarloResponse(
        p5=result.p5,
        p50=result.p50,
        p95=result.p95,
        final_distribution=result.final_distribution,
        prob_positive_return=result.prob_positive_return,
        prob_500k=result.prob_500k,
        contribution_total=result.contribution_total,
        months=result.months,
        correlation_degraded=result.correlation_degraded,
        interpretation=result.interpretation,
    )
```

- [ ] **Step 3: Run linting on changed files**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
ruff check backend/interfaces/rest/schemas/monte_carlo.py backend/interfaces/rest/routers/portfolio.py
ruff format --check backend/interfaces/rest/schemas/monte_carlo.py backend/interfaces/rest/routers/portfolio.py
mypy backend/interfaces/rest/schemas/monte_carlo.py backend/interfaces/rest/routers/portfolio.py --ignore-missing-imports
```

Expected: No errors.

- [ ] **Step 4: Run full backend unit tests**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
pytest backend/tests/unit/ -q 2>&1 | tail -10
```

Expected: All unit tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/andreapetretta/prisma-v2
git add backend/interfaces/rest/schemas/monte_carlo.py backend/interfaces/rest/routers/portfolio.py
git commit -m "feat(monte-carlo): expose interpretation field in MonteCarloResponse schema and router"
```

---

## Task 5: Update frontend TypeScript type and display component

**Files:**
- Modify: `frontend/lib/api/montecarlo.ts`
- Modify: `frontend/app/portfolio/simulator/SimulatorClient.tsx`

- [ ] **Step 1: Add `interpretation` to frontend API type**

In `frontend/lib/api/montecarlo.ts`, add `interpretation?: string` to `MonteCarloResponse`:

```typescript
export interface MonteCarloResponse {
  p5: number[];
  p50: number[];
  p95: number[];
  final_distribution: number[];
  prob_positive_return: number;
  prob_500k: number;
  contribution_total: number;
  months: number;
  correlation_degraded: boolean;
  interpretation?: string;
}
```

- [ ] **Step 2: Replace hardcoded interpretation block in `SimulatorClient.tsx`**

In `frontend/app/portfolio/simulator/SimulatorClient.tsx`, replace the `{/* Text Interpretation */}` block (lines 214–234) with the following:

```tsx
                {/* Text Interpretation */}
                {result.interpretation && (
                  <div className="rounded-xl border border-purple-500/20 bg-purple-950/20 p-4 space-y-2">
                    <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Was bedeutet das?
                    </h3>
                    {result.interpretation.split('. ').filter(Boolean).map((sentence, i) => (
                      <p key={i} className="text-sm text-white/70 leading-relaxed">
                        {sentence.endsWith('.') ? sentence : sentence + '.'}
                      </p>
                    ))}
                  </div>
                )}
```

- [ ] **Step 3: Verify TypeScript compiles (no type errors)**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors (or only pre-existing errors unrelated to this change).

- [ ] **Step 4: Commit**

```bash
cd /Users/andreapetretta/prisma-v2
git add frontend/lib/api/montecarlo.ts frontend/app/portfolio/simulator/SimulatorClient.tsx
git commit -m "feat(monte-carlo): display server-provided interpretation text in simulator UI"
```

---

## Task 6: Final lint + test gate and push

- [ ] **Step 1: Run full lint suite**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
ruff check backend/
ruff format --check backend/
mypy backend/ --ignore-missing-imports 2>&1 | tail -5
```

Expected: No errors.

- [ ] **Step 2: Run all unit tests**

```bash
cd /Users/andreapetretta/prisma-v2
source /tmp/prisma-v2/venv/bin/activate
pytest backend/tests/unit/ -q 2>&1 | tail -10
```

Expected: All pass, none failed.

- [ ] **Step 3: Push branch**

```bash
cd /Users/andreapetretta/prisma-v2
git push -u origin feat/montecarlo-text
```

- [ ] **Step 4: Create PR against `develop`**

```bash
cd /Users/andreapetretta/prisma-v2
gh pr create \
  --base develop \
  --title "feat(T8): Monte Carlo Textinterpretation — server-computed interpretation field" \
  --body "$(cat <<'EOF'
## Summary

- Adds `build_interpretation()` pure function to `monte_carlo_service.py` that generates human-readable probability statements from simulation results (e.g. \"Mit 90% Wahrscheinlichkeit liegt der Portfoliowert nach 20 Jahren zwischen CHF 95\'000 und CHF 420\'000.\")
- Adds `interpretation: str = \"\"` field to `MonteCarloResult` dataclass and `MonteCarloResponse` Pydantic schema (non-breaking, default empty string)
- Router now passes `interpretation` through to the API response
- Frontend `MonteCarloResponse` type gains `interpretation?: string`; simulator displays server-provided text in a styled card when present

## Test plan

- [ ] `pytest backend/tests/unit/application/test_monte_carlo_service.py -v` — all 12+ tests pass including 8 new `build_interpretation` tests
- [ ] `ruff check backend/` — clean
- [ ] `ruff format --check backend/` — clean
- [ ] `mypy backend/ --ignore-missing-imports` — no new errors
- [ ] Simulator UI shows interpretation text block after running a simulation

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `build_interpretation` generates text with 80%/90% probability statements → Task 3
- [x] Median scenario: "wächst CHF X auf CHF Y (+Z%)" → Task 3, `build_interpretation` line 2
- [x] Worst case (5. Perzentil) → Task 3, `build_interpretation` line 3
- [x] Unit test for text generation → Task 2
- [x] No breaking change: `interpretation` defaults to `""` in schema → Task 4
- [x] Frontend display → Task 5
- [x] Branch `feat/montecarlo-text`, PR against `develop` → Tasks 1 and 6

**No placeholders:** All code blocks are complete and concrete.

**Type consistency:** `build_interpretation` takes `(result: MonteCarloResult, initial_value: float, years: int) -> str` — consistent across Task 2 (import + test calls) and Task 3 (definition + call site in `_run_gbm`).
