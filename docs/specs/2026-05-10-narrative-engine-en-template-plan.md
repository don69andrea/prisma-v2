# EN-Template-Aktivierung Implementation Plan

> **For agentic workers:** Implementiere diesen Plan Schritt für Schritt. Schritte nutzen Checkbox-Syntax (`- [ ]`) zum Tracking.

**Goal:** Bilingualen Pfad der Narrative-Engine produktiv aktivieren — `narrative_system.en.md.j2` füllen (1:1-Übersetzung des DE-Templates), `narrative_user.en.md.j2` als Zweitvariante neben renamed `narrative_user.de.md.j2`, beide `NotImplementedError`-Guards in `NarrativeService` entfernen, Tests + 1× Real-API-Smoke vor Merge.

**Architecture:** Reine Erweiterung der existierenden bilingualen Schiene (Foundation-Slice PR #54 hat `language`-Field, Single-Memo PR #64 hat sprach-abhängigen System-Template-Loader). Diese Slice füllt das EN-Template, dupliziert das User-Template pro Sprache, und entfernt zwei expliziete EN-Guards. Keine neuen Domain-Entities, keine neuen Ports/Adapter, keine DB-Migrationen.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 async, Pydantic v2, Jinja2, Anthropic SDK, pytest + pytest-asyncio.

**Spec:** `docs/specs/2026-05-10-narrative-engine-en-template.md`

**Stack-Position:** stacked auf `spec/narrative-multi-memo-batch` (PR #70). Voraussetzung für Implementation: PR #64 + PR #70 müssen mergebar sein. Branch: `feat/narrative-en-template`, base = `main` (nach #70-Merge).

---

## File Structure

| File | Aktion | Verantwortlichkeit |
|---|---|---|
| `backend/infrastructure/llm/prompts/narrative_system.en.md.j2` | MODIFY (Stub → 1:1-Translation) | EN-System-Prompt mit Methodischem Framework, Few-Shot, Output-Format-Hinweisen |
| `backend/infrastructure/llm/prompts/narrative_user.de.md.j2` | RENAMED (`git mv` von `narrative_user.md.j2`) | DE-User-Prompt-Template mit deutschen Labels |
| `backend/infrastructure/llm/prompts/narrative_user.en.md.j2` | NEW | EN-User-Prompt-Template mit englischen Labels |
| `backend/application/services/narrative_service.py` | MODIFY | 2 Guards entfernen, User-Prompt-Loader sprach-abhängig |
| `backend/tests/fixtures/prompts/expected_user_prompt.de.md` | RENAMED (`git mv` von `expected_user_prompt.md`) | Snapshot-Vergleichsdatei DE |
| `backend/tests/fixtures/prompts/expected_user_prompt.en.md` | NEW | Snapshot-Vergleichsdatei EN |
| `backend/tests/fixtures/llm/narrative/top_quality_stock_en.json` | NEW | EN-Stub-Response für StubAnthropic-Integration-Test |
| `backend/tests/unit/application/test_narrative_service.py` | MODIFY | 2 Tests entfernen, 4 Tests dazu, DE-Snapshot-Pfad updaten |
| `backend/tests/integration/test_narrative_service_integration.py` | MODIFY | 1 Test (`test_full_pipeline_en`) dazu |
| `scripts/smoke_narrative_real_api.py` | MODIFY | `--lang=de\|en` CLI-Flag, default `de` |
| `docs/AI-USAGE.md` | MODIFY | Neuer Eintrag mit Reflexion |

---

## Task 1: EN-System-Template füllen (1:1-Übersetzung)

**Files:**
- Modify: `backend/infrastructure/llm/prompts/narrative_system.en.md.j2`

- [ ] **Step 1.1: Aktuellen Stub-Inhalt überschreiben mit 1:1-Übersetzung**

Inhalt der Datei komplett ersetzen mit (vollständige Datei):

```jinja
{# Narrative-Engine System Prompt — EN
   Cached via cache_control: ephemeral. On changes: cache is automatically
   invalidated (5-min TTL after last hit). #}
You are an experienced quantitative research analyst at a Swiss
asset-management boutique. Your task: produce a precise, soberly worded
memo in English from structured ranking data.

# Methodological Framework

## The 5 Quant Models

PRISMA evaluates each stock with 5 independent models:

1. **Quality Classic** — fundamental profitability and balance-sheet quality
   (ROE, profit margin, debt/equity). High rank = solid balance sheet and
   earnings power.
2. **Alpha** — model-independent excess return (e.g. 12-month excess return
   over benchmark, controlled for market beta). High rank = the stock
   has run surprisingly strong over the last 12 months.
3. **Trend Momentum** — EWMA-based momentum signals (halflife 63 days)
   over an equal-weighted benchmark. High rank = clear upward trend.
4. **Value Alpha Potential** — mean-reversion signal from rolling-max alpha:
   stocks whose current alpha performance is significantly below their
   12-month high are considered "priced out" and tend to revert. High rank =
   large reversion potential.
5. **Diversification** — Ledoit-Wolf-shrinkage-based risk and correlation
   measurement. High rank = low risk AND low correlation to the universe
   average.

## The 4 Categories

The 5 models cluster into 4 substantive categories:

- **Quality** = Quality Classic
- **Trend** = Alpha + Trend Momentum
- **Value** = Value Alpha Potential
- **Risk** = Diversification

## Quant Sweet Spot

A stock is in the **sweet spot** when it sits in **at least 3 of 5 models**
in the **top 25%** of the universe. Sweet-spot stocks are statistically
robust against model switches — no single model alone carries the ranking.

# Interpretation Rules

## Rank-to-Language Mapping

- Top 10% (rank ≤ 0.10·N): "very strong"
- Top 25% (rank ≤ 0.25·N): "strong"
- Top 50%: "above average"
- 50-75%: "below average"
- Bottom 25%: "weak"
- Bottom 10%: "very weak"

N = number of stocks in the universe.

## Contradictions

Flag only contradictions that truly warrant attention — delta between
two models ≥ 50 percentiles (e.g. Quality top 10%, Risk bottom 25% → 65
percentiles apart → flag).

If fewer than 2 substantive contradictions exist, the list is empty
(max 3 entries).

## Confidence

- **high**: clear pattern, few contradictions, sweet spot or clear negative signals
- **medium**: mixed picture, 1-2 contradictions, mid-field ranking
- **low**: strongly conflicting signals, or marginal data basis

# Tone Guidelines

- Factual, sober. No superlatives ("outstanding", "excellent" — avoid;
  use "strong", "clear" instead).
- No action recommendation ("buy", "hold", "sell" are forbidden).
- No emotional value judgments ("attractive", "interesting" — avoid).
- Direct style, no subjunctives unless necessary.

# Disclaimer

The memo is educational/research output and does **not** constitute an
investment recommendation. No personalized advice. Past performance is no
guarantee of future returns.

# Output Format

You MUST call the `submit_memo` tool. No free-text output. All fields
in English. Strictly follow the tool-schema constraints:

- `one_liner`: 10-150 characters, one sentence summarizing the core profile.
- `ranking_interpretation`: 100-1000 characters, **3-6 sentences** as
  flowing prose (NO bullet list). Cover the most important models, group
  similar ones together rather than listing each separately.
- `sweet_spot_explanation`: 1-300 characters, only if `sweet_spot=true`.
- `key_strengths` / `key_risks`: 1-5 entries, each a short bullet point.
- `contradictions`: 0-3 entries, only substantive (≥ 50 percentile delta).

# Example Memo (Few-Shot)

Example input:
```
STOCK
Ticker: NESN
Name: Nestle SA
Sector: Consumer Staples
Country: CH

MODEL RUN
Run ID: ...
Universe: Swiss-Mid-Cap (N=80 stocks)
Benchmark median rank: 40
Top-20% threshold: ≤ 16

RANKINGS
- Quality Classic: rank 8/80, score 0.87
- Alpha: rank 12/80, score 0.74
- Trend Momentum: rank 25/80, score 0.62
- Value Alpha Potential: rank 60/80, score 0.31
- Diversification: rank 5/80, score 0.91

AGGREGATION
Total Rank: 11/80
Quant Sweet Spot: True
Used weights: equal-weighted (0.20 each)
```

Example output (tool-call `submit_memo`):
```json
{
  "ticker": "NESN",
  "total_rank": 11,
  "one_liner": "Defensive quality core with low risk, weak reversion potential.",
  "ranking_interpretation": "Quality Classic top 10% and Diversification top 6% define the picture — fundamental solidity and low risk are clearly in the foreground. Alpha and Trend Momentum are top 25% and above average respectively, meaning a healthy but not spectacular momentum profile. Value Alpha Potential in the bottom 25% indicates the stock is running near its rolling-max alpha — limited setback potential.",
  "sweet_spot": true,
  "sweet_spot_explanation": "4 of 5 models top 25% (Quality, Alpha, Trend, Diversification). Robust ranking across model boundaries.",
  "contradictions": [
    {
      "model_a": "Diversification",
      "model_b": "Value Alpha Potential",
      "description": "Lowest risk vs. lowest reversion potential — typical for quality compounders, but a risk under style rotation."
    }
  ],
  "key_strengths": [
    "Top 10% quality fundamentals",
    "Top 6% diversification risk profile",
    "Top 25% alpha performance",
    "Sweet-spot status (4 of 5 models)"
  ],
  "key_risks": [
    "Bottom 25% reversion potential — limited upside",
    "Style rotation out of defensives would be a headwind",
    "Valuation multiples not in the model — separate check needed"
  ],
  "confidence": "high",
  "generated_at": "2026-05-04T10:00:00Z",
  "model_version": "claude-sonnet-4-6"
}
```

Strictly follow this format.
```

- [ ] **Step 1.2: Verifizieren dass Jinja2 das Template lädt (smoke-test)**

```bash
python -c "
from pathlib import Path
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
loader = PromptTemplateLoader(template_dir=Path('backend/infrastructure/llm/prompts'))
out = loader.render('narrative_system.en.md.j2', {})
assert 'You are an experienced quantitative research analyst' in out
assert 'TODO_EN_TEMPLATE_NOT_IMPLEMENTED' not in out
print('OK', len(out), 'chars')
"
```

Expected: `OK <number> chars` ohne Exceptions.

- [ ] **Step 1.3: Commit**

```bash
git add backend/infrastructure/llm/prompts/narrative_system.en.md.j2
git commit -m "feat(narrative): EN-System-Template gefuellt (1:1-Uebersetzung)"
```

---

## Task 2: User-Template duplizieren (rename DE + new EN)

**Files:**
- Rename: `backend/infrastructure/llm/prompts/narrative_user.md.j2` → `backend/infrastructure/llm/prompts/narrative_user.de.md.j2`
- Create: `backend/infrastructure/llm/prompts/narrative_user.en.md.j2`

- [ ] **Step 2.1: DE-User-Template umbenennen via git mv**

```bash
git mv backend/infrastructure/llm/prompts/narrative_user.md.j2 \
       backend/infrastructure/llm/prompts/narrative_user.de.md.j2
```

- [ ] **Step 2.2: EN-User-Template neu schreiben**

Erstelle `backend/infrastructure/llm/prompts/narrative_user.en.md.j2` mit folgendem Inhalt:

```jinja
STOCK
Ticker: {{ ticker }}
Name: {{ name }}
Sector: {{ sector | default("not specified") }}
Country: {{ country | default("not specified") }}

MODEL RUN
Run ID: {{ run_id }}
Universe: {{ universe_name | default("Unknown") }} (N={{ n_stocks }} stocks)
Benchmark median rank: {{ median_rank }}
Top-20% threshold: ≤ {{ top20_threshold }}

RANKINGS (1 = best)
{% for model_name, ranking in rankings.items() %}- {{ model_name }}: rank {{ ranking.rank }}/{{ n_stocks }}, score {{ "%.4f"|format(ranking.score) }}
{% endfor %}
AGGREGATION
Total Rank: {{ total_rank }}/{{ n_stocks }}
Quant Sweet Spot: {{ sweet_spot }}
Used weights: {{ weights }}

Produce the structured JSON memo via the `submit_memo` tool per system instructions.
```

**Wichtig**: gleiche Slot-Variablen wie DE-Template (`ticker`, `name`, `sector`, `country`, `run_id`, `universe_name`, `n_stocks`, `median_rank`, `top20_threshold`, `rankings`, `total_rank`, `sweet_spot`, `weights`) — keine neuen Slots, weil der Service-Code denselben Context an beide Templates übergibt.

- [ ] **Step 2.3: Verifizieren dass Jinja2 beide Templates findet**

```bash
python -c "
from pathlib import Path
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
loader = PromptTemplateLoader(template_dir=Path('backend/infrastructure/llm/prompts'))
ctx = {
    'ticker': 'NESN', 'name': 'Nestle', 'sector': 'Consumer Staples', 'country': 'CH',
    'run_id': '550e8400-...', 'universe_name': 'Swiss-Mid', 'n_stocks': 80,
    'median_rank': 40, 'top20_threshold': 16,
    'rankings': {'Quality Classic': type('R', (), {'rank': 8, 'score': 0.87})()},
    'total_rank': 11, 'sweet_spot': True, 'weights': 'equal-weighted (0.20 each)',
}
de_out = loader.render('narrative_user.de.md.j2', ctx)
en_out = loader.render('narrative_user.en.md.j2', ctx)
assert 'AKTIE' in de_out and 'STOCK' in en_out
assert 'nicht angegeben' not in en_out
print('DE OK:', len(de_out), 'EN OK:', len(en_out))
"
```

Expected: `DE OK: <num> EN OK: <num>` ohne Exceptions.

- [ ] **Step 2.4: Commit**

```bash
git add backend/infrastructure/llm/prompts/narrative_user.de.md.j2 \
        backend/infrastructure/llm/prompts/narrative_user.en.md.j2
git commit -m "feat(narrative): User-Template DE/EN aufgeteilt (rename + new)"
```

---

## Task 3: Service: User-Prompt-Loader sprach-abhängig + DE-Snapshot-Pfad updaten

**Files:**
- Modify: `backend/application/services/narrative_service.py` (User-Prompt-Loader-Pfad)
- Modify: `backend/tests/unit/application/test_narrative_service.py` (DE-Snapshot-Test-Path)

> **Hintergrund**: Wenn wir nur die Templates umbenennen ohne den Service zu updaten, schlagen alle DE-Memo-Tests fehl mit `TemplateNotFound: narrative_user.md.j2`. Daher: Service-Update + DE-Snapshot-Test-Update gehören in **denselben Commit** wie der Rename — oder in den direkt folgenden, ohne dazwischen Tests zu pushen.

- [ ] **Step 3.1: Service: User-Prompt-Loader-Pfad sprach-abhängig**

Datei: `backend/application/services/narrative_service.py`

Suche die Zeile mit dem User-Prompt-Render (in PR #70 ungefähr Zeile ~462):

```python
user_prompt = self._prompts.render(
    "narrative_user.md.j2",
    {...},
)
```

Ersetze durch:

```python
user_prompt = self._prompts.render(
    f"narrative_user.{language}.md.j2",
    {...},
)
```

- [ ] **Step 3.2: Bestehenden DE-Snapshot-Test-Path updaten**

Datei: `backend/tests/unit/application/test_narrative_service.py`

Suche den Snapshot-Test (Test, der `expected_user_prompt.md` lädt — Name z.B. `test_user_prompt_matches_expected_snapshot`). Update den Path:

```python
# Vorher:
expected = Path("backend/tests/fixtures/prompts/expected_user_prompt.md").read_text()

# Nachher:
expected = Path("backend/tests/fixtures/prompts/expected_user_prompt.de.md").read_text()
```

Plus: der Test muss explizit `language="de"` an den Service übergeben (falls nicht schon der Default).

- [ ] **Step 3.3: Snapshot-Datei umbenennen**

```bash
git mv backend/tests/fixtures/prompts/expected_user_prompt.md \
       backend/tests/fixtures/prompts/expected_user_prompt.de.md
```

- [ ] **Step 3.4: DE-Tests laufen lassen**

```bash
pytest backend/tests/unit/application/test_narrative_service.py -v
```

Expected: alle DE-bezogenen Tests grün; EN-Guard-Test (`test_generate_memo_raises_for_en_language`) noch grün, weil der Guard noch da ist.

- [ ] **Step 3.5: Commit**

```bash
git add backend/application/services/narrative_service.py \
        backend/tests/unit/application/test_narrative_service.py \
        backend/tests/fixtures/prompts/expected_user_prompt.de.md
git commit -m "refactor(narrative): User-Prompt-Loader sprach-abhaengig (DE-Path migrated)"
```

---

## Task 4: EN-Snapshot-Test schreiben (TDD: RED → GREEN)

**Files:**
- Create: `backend/tests/fixtures/prompts/expected_user_prompt.en.md`
- Modify: `backend/tests/unit/application/test_narrative_service.py`

- [ ] **Step 4.1: EN-Snapshot-Test schreiben (RED)**

Füge diesen Test in `backend/tests/unit/application/test_narrative_service.py` hinzu (idealerweise direkt unter dem DE-Snapshot-Test):

```python
def test_user_prompt_snapshot_en():
    """Snapshot-Test: render(narrative_user.en.md.j2, fix_context) muss
    expected_user_prompt.en.md entsprechen. Drift-Detection für EN-Template."""
    loader = PromptTemplateLoader(
        template_dir=Path("backend/infrastructure/llm/prompts")
    )

    # Identischer Context wie DE-Snapshot-Test (passe an deinen DE-Test an)
    ctx = {
        "ticker": "NESN",
        "name": "Nestle SA",
        "sector": "Consumer Staples",
        "country": "CH",
        "run_id": "550e8400-e29b-41d4-a716-446655440001",
        "universe_name": "Swiss-Mid-Cap",
        "n_stocks": 80,
        "median_rank": 40,
        "top20_threshold": 16,
        "rankings": {
            "Quality Classic": type("R", (), {"rank": 8, "score": 0.87})(),
            "Alpha": type("R", (), {"rank": 12, "score": 0.74})(),
            "Trend Momentum": type("R", (), {"rank": 25, "score": 0.62})(),
            "Value Alpha Potential": type("R", (), {"rank": 60, "score": 0.31})(),
            "Diversification": type("R", (), {"rank": 5, "score": 0.91})(),
        },
        "total_rank": 11,
        "sweet_spot": True,
        "weights": "equal-weighted (0.20 each)",
    }

    rendered = loader.render("narrative_user.en.md.j2", ctx)
    expected = Path("backend/tests/fixtures/prompts/expected_user_prompt.en.md").read_text()

    assert rendered == expected, f"EN snapshot drift:\n{rendered}\n---\n{expected}"
```

**Hinweis**: passe die `rankings`-Struktur an, falls dein bestehender DE-Snapshot-Test eine andere Form hat (z.B. dataclass statt `type(...)` Hack). Der Punkt: DE und EN Tests sollen exakt denselben Context nutzen — strukturelle Symmetrie.

- [ ] **Step 4.2: Test laufen lassen (RED)**

```bash
pytest backend/tests/unit/application/test_narrative_service.py::test_user_prompt_snapshot_en -v
```

Expected: FAIL mit `FileNotFoundError: ... expected_user_prompt.en.md` (Datei existiert noch nicht).

- [ ] **Step 4.3: EN-Snapshot-Datei erstellen (GREEN)**

Erstelle `backend/tests/fixtures/prompts/expected_user_prompt.en.md` mit dem erwarteten Output:

```
STOCK
Ticker: NESN
Name: Nestle SA
Sector: Consumer Staples
Country: CH

MODEL RUN
Run ID: 550e8400-e29b-41d4-a716-446655440001
Universe: Swiss-Mid-Cap (N=80 stocks)
Benchmark median rank: 40
Top-20% threshold: ≤ 16

RANKINGS (1 = best)
- Quality Classic: rank 8/80, score 0.8700
- Alpha: rank 12/80, score 0.7400
- Trend Momentum: rank 25/80, score 0.6200
- Value Alpha Potential: rank 60/80, score 0.3100
- Diversification: rank 5/80, score 0.9100

AGGREGATION
Total Rank: 11/80
Quant Sweet Spot: True
Used weights: equal-weighted (0.20 each)

Produce the structured JSON memo via the `submit_memo` tool per system instructions.
```

**WICHTIG**: keine trailing newline nach dem letzten `instructions.` — oder doch eine, je nachdem was Jinja2 rendert. Falls Test failed mit kleinem Diff am Ende: ein Newline anpassen. Run pytest, das sagt dir was.

- [ ] **Step 4.4: Test grün?**

```bash
pytest backend/tests/unit/application/test_narrative_service.py::test_user_prompt_snapshot_en -v
```

Expected: PASS. Falls FAIL mit Diff: `expected_user_prompt.en.md` an den tatsächlichen Render-Output anpassen (es gibt eine subtile Frage: Newline-Handling von Jinja2 `{% for %}`-Blocks — das Snapshot-File muss exakt das spiegeln, was Jinja2 rendert).

- [ ] **Step 4.5: Commit**

```bash
git add backend/tests/fixtures/prompts/expected_user_prompt.en.md \
        backend/tests/unit/application/test_narrative_service.py
git commit -m "test(narrative): EN-User-Prompt-Snapshot-Test (RED-GREEN)"
```

---

## Task 5: Service-Guards entfernen (TDD: RED → GREEN, beide Pfade)

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Modify: `backend/tests/unit/application/test_narrative_service.py`

- [ ] **Step 5.1: Test `test_generate_memo_renders_en_templates` schreiben (RED)**

Füge Test in `test_narrative_service.py`:

```python
@pytest.mark.asyncio
async def test_generate_memo_renders_en_templates(narrative_service, sample_stock_id, sample_run_id, mocker):
    """Bei language='en' werden narrative_system.en.md.j2 und narrative_user.en.md.j2
    geladen — Spy auf prompt_loader.render verifiziert das."""
    spy = mocker.spy(narrative_service._prompts, "render")

    await narrative_service.generate_memo(
        sample_stock_id, sample_run_id, language="en"
    )

    template_names_called = [call.args[0] for call in spy.call_args_list]
    assert "narrative_system.en.md.j2" in template_names_called
    assert "narrative_user.en.md.j2" in template_names_called
```

**Hinweis**: passe Fixtures (`narrative_service`, `sample_stock_id`, `sample_run_id`) an die bestehenden Conftest-Setups an. Setup vermutlich identisch zu existierenden DE-Tests.

- [ ] **Step 5.2: Test laufen lassen (RED)**

```bash
pytest backend/tests/unit/application/test_narrative_service.py::test_generate_memo_renders_en_templates -v
```

Expected: FAIL mit `NotImplementedError: EN-Memos sind in dieser Slice noch nicht implementiert ...` (der Guard ist noch da).

- [ ] **Step 5.3: `generate_memo`-Guard entfernen**

Datei: `backend/application/services/narrative_service.py`

Suche und entferne diesen Block (nach `async def generate_memo(...)`):

```python
        # Guard: EN-Template ist Stub (siehe narrative_system.en.md.j2).
        # Frueher Bail-Out verhindert Token-Verbrauch fuer Garbage-Prompt.
        # Wird entfernt sobald EN-Template gefuellt ist (Folge-PR).
        if language == "en":
            raise NotImplementedError(
                "EN-Memos sind in dieser Slice noch nicht implementiert "
                "(narrative_system.en.md.j2 ist Stub). Bitte language='de' nutzen."
            )
```

- [ ] **Step 5.4: Test laufen lassen (GREEN)**

```bash
pytest backend/tests/unit/application/test_narrative_service.py::test_generate_memo_renders_en_templates -v
```

Expected: PASS.

- [ ] **Step 5.5: Bestehenden Guard-Test entfernen**

Suche und lösche `test_generate_memo_raises_for_en_language` (oder ähnlich benannt). Der Test ist obsolet — der Guard ist weg.

- [ ] **Step 5.6: Test `test_start_batch_accepts_en_language` schreiben (RED)**

```python
@pytest.mark.asyncio
async def test_start_batch_accepts_en_language(narrative_service, sample_run_id):
    """start_batch akzeptiert language='en' ohne Exception, Job pending erstellt."""
    job = await narrative_service.start_batch(sample_run_id, top_n=5, language="en")
    assert job is not None
    assert job.status == "pending"
    assert job.language == "en"
```

- [ ] **Step 5.7: Test laufen lassen (RED)**

```bash
pytest backend/tests/unit/application/test_narrative_service.py::test_start_batch_accepts_en_language -v
```

Expected: FAIL mit `NotImplementedError: ...` (der `start_batch`-Guard ist noch da).

- [ ] **Step 5.8: `start_batch`-Guard entfernen**

Datei: `backend/application/services/narrative_service.py`

Suche und entferne den entsprechenden Guard-Block in `start_batch` (in PR #70 ungefähr Zeile ~199-202):

```python
        if language == "en":
            raise NotImplementedError(
                "EN-Memos sind in dieser Slice noch nicht implementiert ..."
                "Bitte language='de' nutzen."
            )
```

- [ ] **Step 5.9: Test laufen lassen (GREEN)**

```bash
pytest backend/tests/unit/application/test_narrative_service.py::test_start_batch_accepts_en_language -v
```

Expected: PASS.

- [ ] **Step 5.10: Bestehenden batch-Guard-Test entfernen**

Lösche `test_start_batch_raises_for_en_language` (Name ggf. abweichend, in PR #70 z.B. `test_start_batch_rejects_english_language`). Obsolet.

- [ ] **Step 5.11: Volle Unit-Test-Suite laufen lassen**

```bash
pytest backend/tests/unit/application/test_narrative_service.py -v
```

Expected: alle grün (DE-Tests + 4 neue EN-Tests + Snapshots beide).

- [ ] **Step 5.12: Commit**

```bash
git add backend/application/services/narrative_service.py \
        backend/tests/unit/application/test_narrative_service.py
git commit -m "feat(narrative): EN-Guards in generate_memo + start_batch entfernt"
```

---

## Task 6: EN-Stub-Fixture erstellen + Integration-Test

**Files:**
- Create: `backend/tests/fixtures/llm/narrative/top_quality_stock_en.json`
- Modify: `backend/tests/integration/test_narrative_service_integration.py`

- [ ] **Step 6.1: EN-Stub-Fixture erstellen**

Datei: `backend/tests/fixtures/llm/narrative/top_quality_stock_en.json`

Inhalt (Format identisch zur DE-Variante `top_quality_stock.json`):

```json
{
  "id": "msg_top_quality_en",
  "type": "message",
  "role": "assistant",
  "model": "claude-sonnet-4-6",
  "stop_reason": "tool_use",
  "usage": {
    "input_tokens": 300,
    "output_tokens": 487,
    "cache_creation_input_tokens": 2000,
    "cache_read_input_tokens": 0
  },
  "content": [
    {
      "type": "tool_use",
      "id": "tool_1",
      "name": "submit_memo",
      "input": {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensive quality core with low risk, weak reversion potential.",
        "ranking_interpretation": "Quality Classic top 10% and Diversification top 6% define the picture — fundamental solidity and low risk are clearly in the foreground. Alpha and Trend Momentum are top 25% and above average respectively, meaning a healthy but not spectacular momentum profile. Value Alpha Potential in the bottom 25% indicates the stock is running near its rolling-max alpha — limited setback potential.",
        "sweet_spot": true,
        "sweet_spot_explanation": "4 of 5 models top 25% (Quality, Alpha, Trend, Diversification). Robust ranking across model boundaries.",
        "contradictions": [],
        "key_strengths": [
          "Top 10% quality fundamentals",
          "Top 6% diversification risk profile",
          "Top 25% alpha performance",
          "Sweet-spot status"
        ],
        "key_risks": [
          "Bottom 25% reversion potential",
          "Style rotation out of defensives would be a headwind"
        ],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6"
      }
    }
  ]
}
```

- [ ] **Step 6.2: Integration-Test `test_full_pipeline_en` schreiben (RED)**

Datei: `backend/tests/integration/test_narrative_service_integration.py`

Füge Test hinzu (analog zu existierendem `test_full_pipeline_top_quality_fixture` — Pattern abkucken!):

```python
@pytest.mark.asyncio
async def test_full_pipeline_en(seeded_db, narrative_service_with_stub_en, sample_stock_id, sample_run_id):
    """End-to-end EN-Pipeline:
    - StubAnthropic mit top_quality_stock_en.json-Fixture
    - service.generate_memo(..., language='en') persistiert Memo mit language='en'
    - service.get_memo(..., language='en') returnt Memo
    - service.get_memo(..., language='de') returnt None (Cache-Trennung verifiziert)
    """
    memo = await narrative_service_with_stub_en.generate_memo(
        sample_stock_id, sample_run_id, language="en"
    )

    assert memo.language == "en"
    assert memo.one_liner == "Defensive quality core with low risk, weak reversion potential."

    # Cache-Hit: zweiter Aufruf liefert dasselbe Memo aus DB (kein neuer LLM-Call)
    memo_again = await narrative_service_with_stub_en.get_memo(
        sample_stock_id, sample_run_id, language="en"
    )
    assert memo_again is not None
    assert memo_again.id == memo.id

    # Cache-Trennung: DE-Pfad ist leer
    de_memo = await narrative_service_with_stub_en.get_memo(
        sample_stock_id, sample_run_id, language="de"
    )
    assert de_memo is None
```

- [ ] **Step 6.3: Fixture `narrative_service_with_stub_en` erstellen**

In `conftest.py` der Integration-Tests (Pfad ggf. abweichend, schauen wo `narrative_service_with_stub` existiert):

```python
@pytest.fixture
async def narrative_service_with_stub_en(...):
    """Identisch zu narrative_service_with_stub, aber StubAnthropic
    mit top_quality_stock_en.json-Fixture statt DE."""
    # ... bestehender Setup-Code, nur Fixture-Pfad anpassen:
    stub_response_path = Path(
        "backend/tests/fixtures/llm/narrative/top_quality_stock_en.json"
    )
    # rest of setup identisch
```

**Alternative**: existierende Fixture `narrative_service_with_stub` parametrisieren mit `language: str` und `fixture_path: Path`. Vermeidet Code-Duplikation. Wenn aber bestehender Test sehr verkürzt schreibt, bleibt zwei Fixtures legitim.

- [ ] **Step 6.4: Test laufen lassen (RED → GREEN)**

```bash
pytest backend/tests/integration/test_narrative_service_integration.py::test_full_pipeline_en -v
```

Expected (RED zuerst falls fixture fehlt): `fixture 'narrative_service_with_stub_en' not found`. Nach Fixture-Setup: PASS.

- [ ] **Step 6.5: Volle Integration-Test-Suite laufen lassen**

```bash
pytest backend/tests/integration/test_narrative_service_integration.py -v
```

Expected: alle grün.

- [ ] **Step 6.6: Commit**

```bash
git add backend/tests/fixtures/llm/narrative/top_quality_stock_en.json \
        backend/tests/integration/test_narrative_service_integration.py \
        backend/tests/integration/conftest.py  # falls Fixture dort liegt
git commit -m "test(narrative): full_pipeline_en integration test (StubAnthropic+EN-Fixture)"
```

---

## Task 7: Smoke-Skript `--lang=de|en`-Flag

**Files:**
- Modify: `scripts/smoke_narrative_real_api.py`

- [ ] **Step 7.1: Aktuelles Smoke-Skript anschauen**

```bash
cat scripts/smoke_narrative_real_api.py
```

Notiere: Wo wird das System-Template geladen? Wo der User-Template? Welche Parameter sind hardcoded?

- [ ] **Step 7.2: argparse für `--lang` hinzufügen**

Am Anfang von `if __name__ == "__main__":` (oder im main-Block):

```python
import argparse
parser = argparse.ArgumentParser(description="Narrative-Engine Real-API Smoke")
parser.add_argument(
    "--lang",
    choices=["de", "en"],
    default="de",
    help="Sprache des Memos (default: de, backwards-compat)"
)
args = parser.parse_args()
language = args.lang
```

- [ ] **Step 7.3: Template-Loads sprach-abhängig**

Suche im Skript die Zeilen, die System- und User-Template laden. Update zu:

```python
# Vorher (Beispiel):
system_prompt = loader.render("narrative_system.de.md.j2", {})
user_prompt = loader.render("narrative_user.md.j2", ctx)

# Nachher:
system_prompt = loader.render(f"narrative_system.{language}.md.j2", {})
user_prompt = loader.render(f"narrative_user.{language}.md.j2", ctx)
```

- [ ] **Step 7.4: Output-Print sprach-tagged**

In den Print-Statements am Ende, prefix die Sprache:

```python
print(f"--- Smoke ({language.upper()}) ---")
# ...
print(f"Call 1: input={input_tokens_1}, output={output_tokens_1}, cache_create={cache_create_1}, cache_read={cache_read_1}")
```

- [ ] **Step 7.5: Smoke-Skript syntax-checken (kein Run, weil API-Calls Geld kosten)**

```bash
python -m py_compile scripts/smoke_narrative_real_api.py
echo "Compile OK"
```

Expected: `Compile OK`. Run gegen API kommt erst in Task 8.

- [ ] **Step 7.6: Commit**

```bash
git add scripts/smoke_narrative_real_api.py
git commit -m "feat(scripts): smoke_narrative_real_api --lang=de|en flag"
```

---

## Task 8: Pre-Push CI-Mirror + alle lokalen Tests grün

**Files:** keine — nur Verifikation

> **Memory-Pattern (Sheylas Pre-Push CI-Mirror)**: vor jedem Push: mypy + ruff check + ruff format --check + pytest, nicht nur pytest.

- [ ] **Step 8.1: mypy strict**

```bash
mypy backend/
```

Expected: `Success: no issues found in N source files`.

- [ ] **Step 8.2: ruff lint**

```bash
ruff check backend/ scripts/
```

Expected: `All checks passed!`

- [ ] **Step 8.3: ruff format check**

```bash
ruff format --check backend/ scripts/
```

Expected: `N files already formatted`.

- [ ] **Step 8.4: Volle Test-Suite**

```bash
pytest backend/tests/ -v
```

Expected: alle grün, keine `xfail`/`skipped` neu hinzugekommen.

- [ ] **Step 8.5: Push (nur wenn alle 4 Checks grün)**

```bash
git push origin feat/narrative-en-template
```

---

## Task 9: Real-API-Smoke ausführen + Schema-Calibration falls nötig

**Files:** keine (oder `backend/domain/schemas/research_memo.py` falls Schema-Calibration nötig)

> **Voraussetzung**: `.env` muss `ANTHROPIC_API_KEY` haben. Smoke kostet ~$0.10 für 2-Call-Pattern.

- [ ] **Step 9.1: EN-Smoke ausführen**

```bash
python scripts/smoke_narrative_real_api.py --lang=en
```

Erwarteter Output:

```
--- Smoke (EN) ---
Call 1: input=~700, output=~700-900, cache_create=~3000, cache_read=0, latency=~10-15s, cost=~$0.025
Call 2: input=~20, output=~700-900, cache_create=~700, cache_read=~3000, latency=~10-15s, cost=~$0.015
Schema validation: OK (both calls)
```

- [ ] **Step 9.2: Output dokumentieren**

Halte die exakten Werte fest — kommen in PR-Body als Tabelle:

```
|  | Input | Output | Cache-Create | Cache-Read | Latenz | Kosten |
|---|---|---|---|---|---|---|
| Call 1 | ___ | ___ | ___ | 0 | ___s | $___ |
| Call 2 | ___ | ___ | ___ | ___ | ___s | $___ |
```

- [ ] **Step 9.3: Schema-Validation prüfen**

Falls Smoke `string_too_short`/`string_too_long` für `ranking_interpretation` (oder anderes Feld) wirft:

**Inline-Bonus-Fix** in `backend/domain/schemas/research_memo.py`:

Beispiel: falls `ranking_interpretation` für EN < 100 chars liefert:

```python
# Vorher:
ranking_interpretation: str = Field(..., min_length=100, max_length=1000, ...)

# Nachher (wenn nötig):
ranking_interpretation: str = Field(..., min_length=80, max_length=1000, ...)
```

Dokumentiere in Spec §11 Plan-Code-Drift (wie in PR #64 W5-Bonus-Fix für DE):

```bash
# Edit docs/specs/2026-05-10-narrative-engine-en-template.md
# Add §11 wenn nicht da, oder erweitere mit Drift-Tabelle:
```

```markdown
### 11.1 Plan-Code-Drift (nach Real-API-Smoke EN)

| Spec-Forderung | Drift im Smoke | Fix-Commit |
|---|---|---|
| `ranking_interpretation min_length=100` | EN-Output bei NESN-Sample 87 chars (under min_length) | Schema `min_length=80`, Smoke-Run grün |
```

- [ ] **Step 9.4: Falls Schema-Calibration: Tests + Smoke nochmal**

```bash
pytest backend/tests/ -v
python scripts/smoke_narrative_real_api.py --lang=en  # Bestätigung
```

Expected: alle grün, Smoke ohne Schema-Errors.

- [ ] **Step 9.5: Commit (nur wenn Schema-Calibration nötig war)**

```bash
git add backend/domain/schemas/research_memo.py \
        docs/specs/2026-05-10-narrative-engine-en-template.md
git commit -m "fix(schema): EN ranking_interpretation min_length kalibriert (Real-API-Smoke)"
```

Falls keine Calibration nötig: kein Commit, weiter zu Task 10.

---

## Task 10: AI-USAGE.md-Eintrag

**Files:**
- Modify: `docs/AI-USAGE.md`

- [ ] **Step 10.1: AI-USAGE-Eintrag oben in `## Einträge` einfügen**

(Direkt unter `## Einträge`-Header, vor dem ersten existierenden Eintrag.)

```markdown
## 2026-MM-DD · Narrative-Engine EN-Template-Aktivierung (PR #__)
- **Agent**: Claude Code (Opus 4.7) im Haupt-Context. Brainstorming-Skill für Q-by-Q-Design (5 Architektur-Fragen), writing-plans-Skill für 10-Task-Plan, dann TDD-Cycle.
- **Scope**: Wave-2-Slice der Narrative-Engine — bilingualen Pfad produktiv aktivieren. EN-System-Template (1:1-Übersetzung mit NESN-Few-Shot), `narrative_user.{de,en}.md.j2` aufgeteilt, beide `NotImplementedError`-Guards entfernt, 4 Unit-Tests + 1 Integration-Test + 2 Snapshot-Tests, Smoke-Skript-Erweiterung `--lang=de|en`, 1× Real-API-Smoke vor Merge. Ziel-Aufwand laut Master-Spec §2: <2h.
- **Was gut lief**:
  - **Patterns-Sektion aus PR #74 als Compass**: Q-by-Q-Brainstorming (P1) sauber durchgezogen — 5 Fragen, 5 begründete Entscheidungen, **null architektonische Mid-Flight-Iterationen**. Pattern Q1 (Spec-Qualität bestimmt Implementations-Tempo) bestätigt.
  - **Reality-Check (P2) hat Stack-Doppelung gefunden**: bei der Architektur-Recherche ist mir aufgefallen, dass `start_batch` in PR #70 einen *zweiten* `NotImplementedError`-Guard hat — nicht nur `generate_memo`. Ohne Reality-Check wäre die Slice mit nur 1 Guard-Removal halbfertig gewesen. **A1 (Plan-Code-Drift) verhindert.**
  - **Strict-Scope-Review-Disziplin (P6)**: bewusste Out-of-Scope-Entscheidungen dokumentiert (lokalisierter Few-Shot, US-Asset-Mgmt-Tone, EN-spezifische Schema-Constraints) — nicht als „später vielleicht", sondern als „YAGNI für Demo-Use-Case".
- **Was nicht klappte**:
  - **<TBD nach Implementation: was hat der Smoke gezeigt? Schema-Calibration nötig? Welche Spec-Annahmen waren falsch?>**
- **Lektion (für die 40%-Achse)**:
  **Wave-2-Slices sind die ehrlichen Lackmus-Tests für Wave-1-Architektur.** Single-Memo-Slice (PR #64) und Multi-Memo-Batch (PR #70) bauten den Pfad für DE. Erst die EN-Slice zwingt, das Versprechen „bilingual vorbereitet" einzulösen — und prüft sichtbar, ob die Schiene wirklich so flexibel war wie Spec sagt. Hier: **<2h vom Stub zu live**, weil System-Template-Loader bereits `f"narrative_system.{language}.md.j2"` war, Entity/ORM/Schema bereits `language`-Feld hatten, REST-API bereits `language`-Param entgegennahm. Nur User-Template-Aufteilung + 2 Guards entfernen + Tests. **Heuristik**: bei jedem Wave-2-Slice messen, **wieviel Architektur-Schiene tatsächlich da war** und das ehrlich dokumentieren. Wenn du unter dem geplanten Aufwand bleibst, ist die Wave-1-Spec gut. Wenn du drüber bist, weisst du wo nachzubessern.
- **Methodisches Mini-Learning**: **Stack-Risiken sind kein Code-Risiko, sondern Koordinations-Risiko.** EN-Slice-Spec war heute schreibbar (kein Code-Dependency), aber Implementation muss auf #64-Re-Review + #70-Merge warten. Spec → Plan → Implementation in drei verschiedene Zeit-Fenster zu trennen, ist okay — solange Spec + Plan **gegen die finale Codebase verifizierbar bleiben** (Pattern P2). Hier: Plan referenziert konkrete Zeilen in `narrative_service.py`, die in #70 sind. Risk: wenn #64 oder #70 sich bewegen, Plan ggf. nachziehen.
- **Token-Kosten**: Geschätzt ~80k Tokens (Brainstorming + Spec + Plan im Haupt-Context). Implementation noch offen. Plus ~$0.10 Real-API-Smoke.
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7)
```

**Wichtig**: Die `<TBD nach Implementation>`-Stelle nach Smoke-Run mit echten Befunden befüllen, **bevor** committed wird.

- [ ] **Step 10.2: Patterns-Index in `## Patterns`-Sektion erweitern**

Wenn aus dieser Slice ein neuer Pattern entsteht (z.B. „Wave-2-Slices als Lackmus-Tests"), ergänze ihn unter Q-Patterns oder als neuen Pattern. Andernfalls: Evidenz-Liste der bestehenden Patterns (P1, P2, P6, Q1) um „PR #__ EN-Template" erweitern.

Beispiel-Update für P1 in `## Patterns`:

```markdown
- **Evidenz**: PR #24 (5 Architektur-Entscheidungen Budget-Cap einzeln), PR #54 (4 Foundation-Decisions), PR #26 (4 Iterationen Daten-Feasibility), **PR #__ EN-Template (5 Architektur-Entscheidungen, 0 Mid-Flight-Iterationen)**.
```

- [ ] **Step 10.3: Commit**

```bash
git add docs/AI-USAGE.md
git commit -m "docs(ai-usage): EN-Template-Slice Reflexion + Patterns-Evidenz erweitert"
```

---

## Task 11: PR erstellen + Merge-Checkliste

- [ ] **Step 11.1: Push letzten Stand**

```bash
git push origin feat/narrative-en-template
```

- [ ] **Step 11.2: PR erstellen**

```bash
gh pr create --base main --head feat/narrative-en-template \
  --title "feat(narrative): EN-Template-Aktivierung — bilinguale Architektur eingelöst (#__)" \
  --body "$(cat <<EOF
## Was & Warum

Wave-2-Slice der Narrative-Engine: löst die seit 2026-04-21 in Master-Spec §2 dokumentierte bilinguale Architektur ein. EN-Memo-Pfad ist jetzt produktiv für Single + Batch.

## Spec & Plan

- Spec: \`docs/specs/2026-05-10-narrative-engine-en-template.md\` — 12 Sektionen, Q-by-Q-Brainstorming-Output dokumentiert
- Plan: \`docs/specs/2026-05-10-narrative-engine-en-template-plan.md\` — 11 Tasks mit TDD pro Step

## Was gebaut wurde

- \`narrative_system.en.md.j2\` 1:1-Übersetzung des DE-Templates (NESN-Few-Shot bleibt — Demo-Aussage „gleicher Input, andere Sprache")
- \`narrative_user.{de,en}.md.j2\` aufgeteilt (rename DE + new EN)
- Service: 2 \`NotImplementedError\`-Guards entfernt (\`generate_memo\` + \`start_batch\`)
- 4 Unit-Tests (renders_en_templates, start_batch_accepts_en, snapshot_en, snapshot_de) + 1 Integration-Test (full_pipeline_en) + 2 Snapshot-Files
- Smoke-Skript: \`--lang=de|en\` Flag

## Real-API-Smoke (EN)

\`python scripts/smoke_narrative_real_api.py --lang=en\` — vor Merge ausgeführt:

|  | Input | Output | Cache-Create | Cache-Read | Latenz | Kosten |
|---|---|---|---|---|---|---|
| Call 1 | <fill> | <fill> | <fill> | 0 | <fill>s | \$<fill> |
| Call 2 | <fill> | <fill> | <fill> | <fill> | <fill>s | \$<fill> |

✓ \`cache_control: ephemeral\` durchgereicht via \`LLMClient\`
✓ Cache-Hit auf Call 2 (EN-System-Template gecached)
✓ Tool-Use-Output beider Calls validiert gegen \`ResearchMemoSchema\`

## Schema-Calibration

<falls nötig: erwähnen welche Constraints angepasst — z.B. \`ranking_interpretation min_length\`. Sonst: nicht nötig.>

## Tests

- N+4 unit tests (war N nach #70), 4/4 EN-Tests grün
- N+1 integration tests, EN-Pipeline grün
- mypy strict + ruff lint/format clean

## Stack-Strategie

Stacked auf #70 (Multi-Memo Batch). Re-target nach #70-Merge auf main.

## AI-Usage

- Q-by-Q-Brainstorming (Pattern P1) für 5 Architektur-Entscheidungen — null Mid-Flight-Iterationen
- Reality-Check (P2) fand Stack-Doppelung: \`start_batch\` hatte zweiten Guard — ohne Check wäre Slice halbfertig
- <2h Implementations-Aufwand wie in Master-Spec §2 prognostiziert — Wave-1-Architektur war wirklich so flexibel wie Spec sagt
- Vollständiger Eintrag in \`docs/AI-USAGE.md\`

## Closes

Master-Spec §2 Sprach-Architektur-Notiz eingelöst. Kein direktes GitHub-Issue.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 11.3: Merge-Checkliste durchgehen**

PR-Body hat Checkboxen für:
- [x] Unit + Integration-Tests grün
- [x] mypy strict + ruff clean
- [x] Real-API-Smoke ausgeführt, Tabelle in PR-Body
- [x] AI-USAGE-Eintrag mit Reflexion
- [x] Spec §11 Plan-Code-Drift dokumentiert (falls Schema-Calibration nötig)
- [ ] Reviewer (z.B. itsFabia) approved
- [ ] CI grün auf head-commit

- [ ] **Step 11.4: Merge nach Approval**

`gh pr merge __ --squash` (oder Repo-Konvention).

---

## Self-Review (vor dem Merge dieses Plans)

**Spec-Coverage**: jede §-Sektion der Spec (§2 In/Out, §3 Architektur, §4 Templates, §5 Service, §6 Tests, §7 Smoke, §8 Akzeptanz, §10 Risiken) ist von einem Task abgedeckt. Tasks 1-2 (Templates), Tasks 3-5 (Service + Tests), Task 6 (Integration), Task 7 (Smoke), Task 8 (CI-Mirror), Task 9 (Real-API-Smoke + Calibration), Task 10 (Reflexion), Task 11 (PR). ✓

**Placeholder-Scan**: Drei `<TBD>`/`<fill>` im Plan — alle in Task 10/11 (AI-USAGE-Reflexion und PR-Body), die nach Implementation bzw. Smoke befüllt werden. Das ist beabsichtigt — der Engineer trägt die Ist-Werte ein, sobald sie da sind. **Keine TBDs im Code-relevanten Plan-Teil.**

**Type-Konsistenz**: `language: Literal["de", "en"]` durchgehend. Snapshot-File-Pfade `expected_user_prompt.{de,en}.md`. Template-File-Pfade `narrative_{system,user}.{de,en}.md.j2`. Test-Method-Names konsistent (`test_generate_memo_renders_en_templates`, `test_start_batch_accepts_en_language`, `test_user_prompt_snapshot_{de,en}`, `test_full_pipeline_en`).

**Granularität**: Task 5 ist mit 12 Steps der größte — bewusst, weil zwei Guard-Removals + ihre TDD-Cycles zusammengehören. Andere Tasks 5-7 Steps. Akzeptabel.

**Bekannte Risiken im Plan selbst**:
- **Step 4.3 Snapshot-Newline-Handling**: Jinja2 `{% for %}`-Blocks haben subtile Newline-Behavior. Plan flagged das ehrlich („Falls Test failed mit kleinem Diff am Ende: ein Newline anpassen") statt ein „perfektes" Snapshot-File zu raten — Pattern A4 (Constants aus Erinnerung) vermieden.
- **Step 6.3 Fixture-Setup**: Conftest-Pfad und exact Fixture-Signature ist von der Codebase abhängig. Plan sagt explizit „passe an bestehende Conftest-Setups an" statt einen fiktiven Pfad festzulegen.
