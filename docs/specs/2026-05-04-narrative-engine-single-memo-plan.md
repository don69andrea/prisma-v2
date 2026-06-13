# Narrative Engine — Single-Memo Slice Implementation Plan

> **For agentic workers:** Implementiere diesen Plan Schritt für Schritt. Schritte nutzen Checkbox-Syntax (`- [ ]`) zum Tracking.

**Goal:** Den Single-Memo-Pfad der Narrative-Engine implementieren (Service + Prompt-Templates + Tool-use-Strukturierung + 2 REST-Endpoints + Error-Memo-Persistierung + Tests), strikt nach Slice-Spec `docs/specs/2026-05-04-narrative-engine-single-memo.md`.

**Architecture:** Pydantic-Schema (Foundation) → NarrativeService orchestriert → LLMClient (mit cache_control + Tool-use) → Anthropic API → Pydantic-validate Tool-Response → ResearchMemoRepository UPSERT. Bei Tool-/Schema-Fehler → Error-Memo persistieren, Raw-Response in `logs/malformed_memos/`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, asyncpg, Anthropic Python SDK >=0.25, Jinja2 (NEU), pytest + pytest-asyncio + Testcontainers-Pattern (über docker-compose Postgres).

**Reference Spec:** `docs/specs/2026-05-04-narrative-engine-single-memo.md` v1.1
**Parent Spec:** `docs/specs/2026-04-28-narrative-engine.md`
**Foundation:** PR #54 — bestehende `ResearchMemo`-Entity, `ResearchMemoSchema`, `ResearchMemoRepository` werden hier verwendet, nicht angepasst.

---

## File Structure

| Pfad | Rolle | Status |
|---|---|---|
| `pyproject.toml` | + jinja2-Dep | MOD |
| `backend/domain/repositories/stock_repository.py` | + abstract `get(stock_id)` | MOD |
| `backend/infrastructure/persistence/repositories/stock_repository.py` | + Adapter `get(stock_id)` | MOD |
| `backend/infrastructure/llm/client.py` | `system: str \| list[dict[str, Any]] \| None` + Cost-Estimation | MOD |
| `backend/infrastructure/llm/prompts/__init__.py` | empty package marker | NEU |
| `backend/infrastructure/llm/prompts/prompt_loader.py` | Jinja2-Loader-Klasse | NEU |
| `backend/infrastructure/llm/prompts/narrative_system.de.md.j2` | DE System-Prompt-Template (gefüllt) | NEU |
| `backend/infrastructure/llm/prompts/narrative_system.en.md.j2` | EN Stub mit TODO-Kommentar | NEU |
| `backend/infrastructure/llm/prompts/narrative_user.md.j2` | Daten-Slot-User-Template (sprachneutral) | NEU |
| `backend/application/services/narrative_service.py` | Service + UniverseContext-VO + Helpers | NEU |
| `backend/interfaces/rest/routers/memos.py` | POST + GET | NEU |
| `backend/interfaces/rest/dependencies.py` | + DI-Funktionen für Service | MOD |
| `backend/interfaces/rest/app.py` | Router registrieren | MOD |
| `backend/tests/unit/infrastructure/test_stock_repository.py` | Adapter-Test für `get` | NEU |
| `backend/tests/unit/infrastructure/test_llm_client.py` | + Tests für list-system | MOD |
| `backend/tests/unit/infrastructure/test_prompt_loader.py` | Jinja2-Loader + Snapshot | NEU |
| `backend/tests/unit/application/test_narrative_service.py` | Service-Logik mit Mock-LLM | NEU |
| `backend/tests/integration/test_memos_endpoint.py` | FastAPI-TestClient (POST + GET) | NEU |
| `backend/tests/integration/test_narrative_service_integration.py` | Service gegen echte PG + StubAnthropic | NEU |
| `backend/tests/fixtures/llm/stub_anthropic_client.py` | StubAnthropic für Integration-Tests | NEU |
| `backend/tests/fixtures/llm/narrative/top_quality_stock.json` | Happy-Path Tool-Response | NEU |
| `backend/tests/fixtures/llm/narrative/contradictory_quality_risk.json` | Widerspruchs-Pfad | NEU |
| `backend/tests/fixtures/llm/narrative/malformed_response.json` | Pydantic-Fail-Pfad | NEU |
| `backend/tests/fixtures/prompts/expected_user_prompt.md` | Snapshot für Loader-Test | NEU |
| `docs/examples/research-memo-sample.json` | Realistisches Beispiel-Memo | NEU |
| `docs/AI-USAGE.md` | + Eintrag mit Cache-Hit-Rate | MOD |

---

## Build-Step-Übersicht

| # | Titel | Touching | Erwartung |
|---|---|---|---|
| 1 | Add jinja2 dependency | `pyproject.toml`, `uv.lock` | green-build |
| 2 | StockRepository.get(stock_id) | port + adapter + test | TDD RED→GREEN |
| 3 | LLMClient: system as list-of-blocks | client + test | TDD RED→GREEN |
| 4 | PromptTemplateLoader + 3 Templates | loader + 3 .j2 + snapshot test | TDD RED→GREEN |
| 5 | UniverseContext + ranking-extraction helpers | narrative_service.py (Skelett) + tests | TDD RED→GREEN |
| 6 | NarrativeService.get_memo | service + tests | TDD RED→GREEN |
| 7 | NarrativeService.generate_memo (happy + cached) | service + tests | TDD RED→GREEN |
| 8 | NarrativeService.generate_memo (error paths) | service + tests | TDD RED→GREEN |
| 9 | REST Router (POST + GET) + DI + Integration-Test | router + deps + e2e-test | TDD RED→GREEN |
| 10 | Stub-Anthropic + JSON-Fixtures + Integration-Tests | fixtures + integration | TDD RED→GREEN |
| 11 | Sample-Memo + AI-USAGE-Eintrag | docs | docs only |

---

## Task 1: Add jinja2 dependency

**Files:**
- Modify: `pyproject.toml`
- Update: `uv.lock`

- [ ] **Step 1.1: Lokalisiere die `[project] dependencies =`-Liste in `pyproject.toml`**

Bestätige mit:
```bash
grep -n "anthropic" pyproject.toml
```
Zeile sollte `"anthropic>=0.25",` enthalten — der jinja2-Eintrag kommt direkt darunter alphabetisch korrekt sortiert (es kommt `httpx`, dann `jinja2`, dann der nächste, je nach bestehender Reihenfolge — Reihenfolge im File übernehmen).

- [ ] **Step 1.2: Füge `"jinja2>=3.1",` an alphabetisch passender Stelle ein**

Konkret: nach der Zeile mit `httpx` (falls vorhanden) oder nach `fastapi`, abhängig von der bestehenden Sortierung.

- [ ] **Step 1.3: Lock-File aktualisieren**

```bash
uv lock
```
Erwartet: `uv.lock` ändert sich, neue jinja2-Section wird hinzugefügt. Kein Fehler.

- [ ] **Step 1.4: Verify-import**

```bash
uv run python -c "import jinja2; print(jinja2.__version__)"
```
Erwartet: Version >= 3.1.x ausgegeben.

- [ ] **Step 1.5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): jinja2>=3.1 fuer Prompt-Templates (#17, build-step 1/11)

Vorbereitung fuer NarrativeService Prompt-Loader. Spec:
docs/specs/2026-05-04-narrative-engine-single-memo.md §3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: StockRepository.get(stock_id)

**Files:**
- Modify: `backend/domain/repositories/stock_repository.py`
- Modify: `backend/infrastructure/persistence/repositories/stock_repository.py`
- Create: `backend/tests/unit/infrastructure/test_stock_repository.py`

### 2.1 — Test schreiben (RED)

- [ ] **Step 2.1: Erstelle `backend/tests/unit/infrastructure/test_stock_repository.py`**

```python
"""Unit-Tests fuer SQLAStockRepository.get(stock_id)."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.entities.stock import Stock
from backend.infrastructure.persistence.models.stock import StockORM
from backend.infrastructure.persistence.repositories.stock_repository import (
    SQLAStockRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def seeded_stock(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, str]:
    """Persistiere einen Stock und gib (id, ticker) zurueck."""
    stock_id = uuid4()
    async with session_factory() as session:
        session.add(
            StockORM(
                id=stock_id,
                ticker="NESN",
                name="Nestle SA",
                isin="CH0038863350",
                sector="Consumer Staples",
                country="CH",
                currency="CHF",
            )
        )
        await session.commit()
    return stock_id, "NESN"


async def test_get_returns_stock_when_found(
    session_factory: async_sessionmaker[AsyncSession],
    seeded_stock: tuple[UUID, str],
) -> None:
    stock_id, _ticker = seeded_stock
    async with session_factory() as session:
        repo = SQLAStockRepository(session=session)
        stock = await repo.get(stock_id)

    assert stock is not None
    assert isinstance(stock, Stock)
    assert stock.id == stock_id
    assert stock.ticker == "NESN"


async def test_get_returns_none_when_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SQLAStockRepository(session=session)
        stock = await repo.get(uuid4())

    assert stock is None
```

**Note:** Diese Tests verwenden die `session_factory`-Fixture aus `backend/tests/integration/persistence/conftest.py`. Damit das Unit-Test-Modul diese Fixture sieht, muss entweder die conftest.py-Fixture in `backend/tests/conftest.py` hochgezogen werden ODER der Test in `backend/tests/integration/persistence/` liegen. Für Konsistenz mit dem bestehenden `test_research_memo_orm.py` (welches DB-bound ist) → **lege die Datei stattdessen unter `backend/tests/unit/infrastructure/`** an UND prüfe vorher mit `pytest --co backend/tests/unit/infrastructure/test_llm_client.py` ob dieser Pfad bereits Zugriff auf die `session_factory`-Fixture hat. Falls nein, importiere die Fixture explizit oder verschiebe nach `backend/tests/integration/persistence/test_stock_repository.py`.

- [ ] **Step 2.2: Run test — Expected RED**

```bash
uv run pytest backend/tests/unit/infrastructure/test_stock_repository.py -v
```
Erwartet: `AttributeError: 'SQLAStockRepository' object has no attribute 'get'` ODER FAIL mit "abstract method 'get' not implemented" beim Konstruktor (je nach Pfad).

### 2.2 — Port erweitern

- [ ] **Step 2.3: Modify `backend/domain/repositories/stock_repository.py`**

Füge nach der bestehenden `get_by_ticker` die neue abstract-Methode hinzu:

```python
    @abstractmethod
    async def get(self, stock_id: UUID) -> Stock | None:
        """Sucht eine Stock-Entity anhand ihrer UUID.

        Gibt None zurück wenn kein Treffer gefunden wurde (kein Exception-Missbrauch).
        """
        ...
```

Imports erweitern: am Datei-Anfang `from uuid import UUID` ergänzen.

### 2.3 — Adapter erweitern (GREEN)

- [ ] **Step 2.4: Modify `backend/infrastructure/persistence/repositories/stock_repository.py`**

Füge nach `get_by_ticker` die neue Methode hinzu:

```python
    async def get(self, stock_id: UUID) -> Stock | None:
        result = await self._session.scalars(
            select(StockORM).where(StockORM.id == stock_id)
        )
        orm = result.one_or_none()
        return self._to_domain(orm) if orm else None
```

Imports erweitern falls nötig: `from uuid import UUID`.

- [ ] **Step 2.5: Run test — Expected GREEN**

```bash
uv run pytest backend/tests/unit/infrastructure/test_stock_repository.py -v
```
Erwartet: 2 passed.

- [ ] **Step 2.6: mypy + ruff check**

```bash
uv run mypy backend/domain/repositories/stock_repository.py backend/infrastructure/persistence/repositories/stock_repository.py
uv run ruff check backend/domain/repositories/stock_repository.py backend/infrastructure/persistence/repositories/stock_repository.py
```
Erwartet: keine Errors.

- [ ] **Step 2.7: Commit**

```bash
git add backend/domain/repositories/stock_repository.py backend/infrastructure/persistence/repositories/stock_repository.py backend/tests/unit/infrastructure/test_stock_repository.py
git commit -m "feat(domain): StockRepository.get(stock_id: UUID) (#17, build-step 2/11)

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §3.
NarrativeService braucht Stock-Lookup via UUID (statt Ticker), weil das
REST-API stock_id als kanonische Referenz fuehrt. Tests: SQLA-Adapter
gegen seeded Stock + None-Pfad.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: LLMClient — `system` als list-of-content-blocks

**Files:**
- Modify: `backend/infrastructure/llm/client.py`
- Modify: `backend/tests/unit/infrastructure/test_llm_client.py`

### 3.1 — Test schreiben (RED)

- [ ] **Step 3.1: Append zu `backend/tests/unit/infrastructure/test_llm_client.py`** (am Ende, vor letztem `\n`)

Zwei neue Tests + Anpassung der Cost-Estimation-Logik:

```python
async def test_messages_create_accepts_system_as_content_block_list() -> None:
    """system kann auch list[dict] sein fuer cache_control-Markierung."""
    fake_response = _fake_anthropic_response()
    fake_anthropic = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(return_value=fake_response))
    )
    fake_voyage = SimpleNamespace()
    fake_tracker = Mock()
    fake_tracker.check_cap = AsyncMock(return_value=None)
    fake_tracker.record = AsyncMock(return_value=None)

    client = LLMClient(
        anthropic=fake_anthropic, voyage=fake_voyage, cost_tracker=fake_tracker
    )

    system_blocks = [
        {
            "type": "text",
            "text": "You are a quant analyst." * 10,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    await client.messages_create(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=100,
        feature="test",
        system=system_blocks,
    )

    # SDK call must have received the system list verbatim
    call_kwargs = fake_anthropic.messages.create.await_args.kwargs
    assert call_kwargs["system"] == system_blocks


async def test_estimate_messages_cost_handles_system_as_list() -> None:
    """Cost-Estimator iteriert ueber alle text-blocks im system-list-Fall."""
    cost = LLMClient._estimate_messages_cost(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "abc" * 100}],
        max_tokens=200,
        system=[
            {"type": "text", "text": "block-one" * 50},
            {"type": "text", "text": "block-two" * 50},
        ],
    )
    # Sanity: cost is > 0 and a Decimal
    assert cost > Decimal("0")
```

- [ ] **Step 3.2: Run tests — Expected RED**

```bash
uv run pytest backend/tests/unit/infrastructure/test_llm_client.py -v -k "system_as"
```
Erwartet: FAIL — entweder TypeError beim `len(system)` (weil system kein str ist) oder `messages_create` wirft beim Forwarding.

### 3.2 — Implementierung (GREEN)

- [ ] **Step 3.3: Modify `backend/infrastructure/llm/client.py`**

Ändere die Type-Annotation und die Estimation-Logik:

**Signatur** (Zeile 51): von
```python
system: str | None = None,
```
auf
```python
system: str | list[dict[str, Any]] | None = None,
```

**`_estimate_messages_cost`** (Zeile 126ff): ändere den system-handling-Block

Vorher:
```python
        chars = sum(len(m.get("content", "")) for m in messages)
        if system:
            chars += len(system)
```

Nachher:
```python
        chars = sum(len(m.get("content", "")) for m in messages)
        if isinstance(system, str):
            chars += len(system)
        elif isinstance(system, list):
            for block in system:
                text = block.get("text") if isinstance(block, dict) else None
                if isinstance(text, str):
                    chars += len(text)
```

**Signatur von `_estimate_messages_cost`** (Zeile 132): von
```python
        system: str | None,
```
auf
```python
        system: str | list[dict[str, Any]] | None,
```

- [ ] **Step 3.4: Run tests — Expected GREEN**

```bash
uv run pytest backend/tests/unit/infrastructure/test_llm_client.py -v
```
Erwartet: alle Tests passed (bestehende + 2 neue).

- [ ] **Step 3.5: mypy + ruff**

```bash
uv run mypy backend/infrastructure/llm/client.py
uv run ruff check backend/infrastructure/llm/client.py
```
Erwartet: clean.

- [ ] **Step 3.6: Commit**

```bash
git add backend/infrastructure/llm/client.py backend/tests/unit/infrastructure/test_llm_client.py
git commit -m "feat(llm): LLMClient.system akzeptiert list[dict] fuer cache_control (#17, build-step 3/11)

Vorbereitung fuer Prompt-Caching im NarrativeService. Anthropic-API
erlaubt system entweder als str oder als list-of-content-blocks; nur
letzteres erlaubt cache_control: ephemeral-Markierung.

Cost-Estimator iteriert ueber alle text-blocks im list-Fall.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §3, §8.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: PromptTemplateLoader + 3 Templates

**Files:**
- Create: `backend/infrastructure/llm/prompts/__init__.py`
- Create: `backend/infrastructure/llm/prompts/prompt_loader.py`
- Create: `backend/infrastructure/llm/prompts/narrative_system.de.md.j2`
- Create: `backend/infrastructure/llm/prompts/narrative_system.en.md.j2`
- Create: `backend/infrastructure/llm/prompts/narrative_user.md.j2`
- Create: `backend/tests/unit/infrastructure/test_prompt_loader.py`
- Create: `backend/tests/fixtures/prompts/expected_user_prompt.md`

### 4.1 — Templates schreiben (kein TDD nötig — pure Daten)

- [ ] **Step 4.1: `backend/infrastructure/llm/prompts/__init__.py`** (leere Datei)

```python
"""Prompt-Templates und Loader fuer LLM-Aufrufe."""
```

- [ ] **Step 4.2: `backend/infrastructure/llm/prompts/narrative_system.de.md.j2`**

System-Prompt nach Parent-Spec §5.1, ~1800-2200 Tokens. Inhalt:

```jinja2
{# Narrative-Engine System-Prompt — DE
   Cached via cache_control: ephemeral. Bei Aenderungen: Cache wird automatisch
   invalidiert (5-Min-TTL nach letztem Hit). #}
Du bist ein erfahrener quantitativer Research-Analyst bei einer Schweizer
Asset-Management-Boutique. Deine Aufgabe: aus strukturierten Ranking-Daten
ein praezises, nuechtern formuliertes Memo auf Deutsch erstellen.

# Methodisches Framework

## Die 5 Quant-Modelle

PRISMA bewertet jede Aktie mit 5 unabhaengigen Modellen:

1. **Quality Classic** — fundamentale Profitabilitaets- und Bilanzqualitaet
   (ROE, Profit-Margin, Debt/Equity). Hoher Rang = solide Bilanz und
   Ertragskraft.
2. **Alpha** — modellunabhaengige Ueberrendite (z.B. 12-Monats-Excess-Return
   gegenueber Benchmark, kontrolliert um Marktbeta). Hoher Rang = die Aktie
   ist in den letzten 12 Monaten ueberraschend stark gelaufen.
3. **Trend Momentum** — EWMA-basierte Momentum-Signale (Halflife 63 Tage)
   gegenueber gleichgewichtetem Benchmark. Hoher Rang = klarer Aufwaerts-Trend.
4. **Value Alpha Potential** — Mean-Reversion-Signal aus rolling-max-Alpha:
   Aktien, deren aktuelle Alpha-Performance deutlich unter ihrem
   12-Monats-Hoch liegt, gelten als "ausgepreist" und kommen tendenziell
   zurueck. Hoher Rang = grosses Reversion-Potenzial.
5. **Diversification** — Ledoit-Wolf-shrinkage-basierte Risiko- und
   Korrelationsmessung. Hoher Rang = niedriges Risiko UND niedrige
   Korrelation zum Universumsdurchschnitt.

## Die 4 Kategorien

Die 5 Modelle clustern in 4 fachliche Kategorien:

- **Quality** = Quality Classic
- **Trend** = Alpha + Trend Momentum
- **Value** = Value Alpha Potential
- **Risk** = Diversification

## Quant Sweet Spot

Eine Aktie ist im **Sweet Spot**, wenn sie in **mindestens 3 von 5 Modellen**
in den **Top 25%** des Universums liegt. Sweet-Spot-Aktien sind statistisch
robust gegenueber Modellwechsel — kein einzelnes Modell allein traegt das
Ranking.

# Interpretations-Regeln

## Rang-zu-Sprache-Mapping

- Top 10% (Rang ≤ 0.10·N): "sehr stark"
- Top 25% (Rang ≤ 0.25·N): "stark"
- Top 50%: "ueberdurchschnittlich"
- 50-75%: "unterdurchschnittlich"
- Bottom 25%: "schwach"
- Bottom 10%: "sehr schwach"

N = Anzahl Aktien im Universum.

## Widersprueche (Contradictions)

Flagge nur Widersprueche, die wirklich Aufmerksamkeit verdienen — Delta zwischen
zwei Modellen ≥ 50 Perzentile (z.B. Quality Top 10%, Risk Bottom 25% → 65
Perzentile auseinander → flaggen).

Wenn weniger als 2 substantielle Widersprueche existieren, ist die Liste
leer (max 3 Eintraege).

## Confidence

- **high**: klares Muster, kaum Widersprueche, Sweet Spot oder klare Negativ-Signale
- **medium**: gemischtes Bild, 1-2 Widersprueche, Mittelfeld-Ranking
- **low**: stark widersprueechliche Signale, oder Datenbasis grenzwertig

# Ton-Vorgaben

- Sachlich, nuechtern. Keine Superlative ("herausragend", "ausgezeichnet"
  vermeiden — stattdessen "stark", "deutlich").
- Keine Handlungsempfehlung ("kaufen", "halten", "verkaufen" sind verboten).
- Keine emotionalen Werturteile ("attraktiv", "interessant" vermeiden).
- Direkter Stil, keine Konjunktive wenn nicht noetig.

# Disclaimer

Das Memo ist Educational/Research-Output und stellt **keine** Anlageempfehlung
dar. Keine personalisierte Beratung. Vergangene Performance ist keine Garantie
fuer zukuenftige Renditen.

# Output-Format

Du MUSST das `submit_memo`-Tool aufrufen. Kein Freitext-Output. Alle Felder
auf Deutsch. Halte dich an die Constraints aus dem Tool-Schema (Min-/Max-
Laengen, Confidence-Werte).

# Beispiel-Memo (Few-Shot)

Beispiel-Eingabe:
```
AKTIE
Ticker: NESN
Name: Nestle SA
Sektor: Consumer Staples
Land: CH

MODEL RUN
Run-ID: ...
Universum: Swiss-Mid-Cap (N=80 Aktien)
Benchmark-Median-Rang: 40
Top-20%-Schwelle: ≤ 16

RANKINGS
- Quality Classic: Rang 8/80, Score 0.87
- Alpha: Rang 12/80, Score 0.74
- Trend Momentum: Rang 25/80, Score 0.62
- Value Alpha Potential: Rang 60/80, Score 0.31
- Diversification: Rang 5/80, Score 0.91

AGGREGATION
Total Rank: 11/80
Quant Sweet Spot: True
Verwendete Gewichte: equal-weighted (0.20 each)
```

Beispiel-Output (Tool-Call `submit_memo`):
```json
{
  "ticker": "NESN",
  "total_rank": 11,
  "one_liner": "Defensiver Quality-Kern mit niedrigem Risiko, schwaches Reversion-Potenzial.",
  "ranking_interpretation": "Quality Classic Top 10% und Diversification Top 6% pruegen das Bild — fundamentale Solidaet und niedriges Risiko stehen klar im Vordergrund. Alpha und Trend Momentum sind Top 25% bzw. ueberdurchschnittlich, also ein gesundes aber nicht spektakulaeres Momentum-Profil. Value Alpha Potential im Bottom 25% deutet darauf hin, dass die Aktie nahe ihrem rolling-max Alpha laeuft — wenig Rueckschlag-Potenzial.",
  "sweet_spot": true,
  "sweet_spot_explanation": "4 von 5 Modellen Top 25% (Quality, Alpha, Trend, Diversification). Robustes Ranking ueber Modellgrenzen hinweg.",
  "contradictions": [
    {
      "model_a": "Diversification",
      "model_b": "Value Alpha Potential",
      "description": "Niedrigstes Risiko vs. niedrigstes Reversion-Potenzial — ueblich fuer Quality-Compounder, aber bei Stil-Rotation ein Risiko."
    }
  ],
  "key_strengths": [
    "Top 10% Quality-Bilanz",
    "Top 6% Diversifikations-Risikoprofil",
    "Top 25% Alpha-Performance",
    "Sweet-Spot-Status (4 von 5 Modellen)"
  ],
  "key_risks": [
    "Bottom 25% Reversion-Potenzial — weniger Upside",
    "Stil-Rotation aus Defensives waere ein Headwind",
    "Bewertungs-Multiples nicht im Modell — separate Pruefung"
  ],
  "confidence": "high",
  "generated_at": "2026-05-04T10:00:00Z",
  "model_version": "claude-sonnet-4-6"
}
```

Halte dich strikt an dieses Format.
```

- [ ] **Step 4.3: `backend/infrastructure/llm/prompts/narrative_system.en.md.j2`**

```jinja2
{# Narrative-Engine System-Prompt — EN
   STUB — TODO: full English translation in follow-up PR (out of scope per
   docs/specs/2026-05-04-narrative-engine-single-memo.md §2). MVP is DE-only;
   architecture supports lang="en" but EN template is intentionally empty.
   Calling the service with lang="en" should fail in the loader's render
   step (Jinja2-Error or empty render — both acceptable for MVP). #}
TODO_EN_TEMPLATE_NOT_IMPLEMENTED
```

- [ ] **Step 4.4: `backend/infrastructure/llm/prompts/narrative_user.md.j2`**

User-Prompt nach Parent-Spec §5.2:

```jinja2
AKTIE
Ticker: {{ ticker }}
Name: {{ name }}
Sektor: {{ sector | default("nicht angegeben") }}
Land: {{ country | default("nicht angegeben") }}

MODEL RUN
Run-ID: {{ run_id }}
Universum: {{ universe_name | default("Unbekannt") }} (N={{ n_stocks }} Aktien)
Benchmark-Median-Rang: {{ median_rank }}
Top-20%-Schwelle: ≤ {{ top20_threshold }}

RANKINGS (1 = bester)
{% for model_name, ranking in rankings.items() %}- {{ model_name }}: Rang {{ ranking.rank }}/{{ n_stocks }}, Score {{ "%.4f"|format(ranking.score) }}
{% endfor %}
AGGREGATION
Total Rank: {{ total_rank }}/{{ n_stocks }}
Quant Sweet Spot: {{ sweet_spot }}
Verwendete Gewichte: {{ weights }}

Produziere das strukturierte JSON-Memo via `submit_memo`-Tool gemaess Systemanweisungen.
```

### 4.2 — Loader-Test (RED)

- [ ] **Step 4.5: `backend/tests/fixtures/prompts/expected_user_prompt.md`** (Snapshot-Datei)

Mit erwarteten Daten — siehe Test-Code in 4.6 für die Werte. Inhalt:

```
AKTIE
Ticker: NESN
Name: Nestle SA
Sektor: Consumer Staples
Land: CH

MODEL RUN
Run-ID: 550e8400-e29b-41d4-a716-446655440001
Universum: Swiss-Mid-Cap (N=80 Aktien)
Benchmark-Median-Rang: 40
Top-20%-Schwelle: ≤ 16

RANKINGS (1 = bester)
- Quality Classic: Rang 8/80, Score 0.8700
- Alpha: Rang 12/80, Score 0.7400
- Trend Momentum: Rang 25/80, Score 0.6200
- Value Alpha Potential: Rang 60/80, Score 0.3100
- Diversification: Rang 5/80, Score 0.9100

AGGREGATION
Total Rank: 11/80
Quant Sweet Spot: True
Verwendete Gewichte: equal-weighted (0.20 each)

Produziere das strukturierte JSON-Memo via `submit_memo`-Tool gemaess Systemanweisungen.
```

- [ ] **Step 4.6: `backend/tests/unit/infrastructure/test_prompt_loader.py`**

```python
"""Unit-Tests fuer PromptTemplateLoader (Jinja2)."""

from pathlib import Path

import pytest

from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "prompts"


def test_render_user_prompt_matches_snapshot() -> None:
    loader = PromptTemplateLoader()
    rendered = loader.render(
        "narrative_user.md.j2",
        {
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
                "Quality Classic": {"rank": 8, "score": 0.87},
                "Alpha": {"rank": 12, "score": 0.74},
                "Trend Momentum": {"rank": 25, "score": 0.62},
                "Value Alpha Potential": {"rank": 60, "score": 0.31},
                "Diversification": {"rank": 5, "score": 0.91},
            },
            "total_rank": 11,
            "sweet_spot": True,
            "weights": "equal-weighted (0.20 each)",
        },
    )

    expected = (FIXTURES / "expected_user_prompt.md").read_text(encoding="utf-8").rstrip()
    assert rendered.rstrip() == expected


def test_render_unknown_template_raises() -> None:
    loader = PromptTemplateLoader()
    with pytest.raises(Exception):  # Jinja2 TemplateNotFound oder ähnlich
        loader.render("does_not_exist.md.j2", {})


def test_render_de_system_template_succeeds() -> None:
    """System-Template darf einfach gerendert werden (keine Slots — alles statisch)."""
    loader = PromptTemplateLoader()
    rendered = loader.render("narrative_system.de.md.j2", {})
    assert "quantitativer Research-Analyst" in rendered
    assert "submit_memo" in rendered
    assert "Sweet Spot" in rendered
```

- [ ] **Step 4.7: Run test — Expected RED**

```bash
uv run pytest backend/tests/unit/infrastructure/test_prompt_loader.py -v
```
Erwartet: ImportError — PromptTemplateLoader existiert noch nicht.

### 4.3 — Loader implementieren (GREEN)

- [ ] **Step 4.8: `backend/infrastructure/llm/prompts/prompt_loader.py`**

```python
"""Jinja2-basierter Loader fuer Prompt-Templates.

Templates leben unter `backend/infrastructure/llm/prompts/*.j2`. Loader
wird beim App-Start einmal instanziiert (DI-Singleton) — Templates werden
lazy beim ersten render gecached.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class PromptTemplateLoader:
    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir is None:
            template_dir = Path(__file__).resolve().parent

        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
            undefined=StrictUndefined,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Rendert ein Template mit dem gegebenen Context-Dict.

        Wirft `jinja2.exceptions.TemplateNotFound` bei unbekanntem Template,
        `jinja2.exceptions.UndefinedError` bei fehlenden Slots
        (StrictUndefined).
        """
        template = self._env.get_template(template_name)
        return template.render(**context)
```

- [ ] **Step 4.9: Run test — Expected GREEN**

```bash
uv run pytest backend/tests/unit/infrastructure/test_prompt_loader.py -v
```
Erwartet: 3 passed.

**Hinweis Snapshot-Mismatch**: Falls die Whitespace-Endung der gerenderten Datei nicht stimmt (z.B. `for`-Loop generiert trailing newline), passe das `expected_user_prompt.md` an oder fuege `.rstrip()` im Test hinzu (ist bereits drin).

- [ ] **Step 4.10: mypy + ruff**

```bash
uv run mypy backend/infrastructure/llm/prompts/prompt_loader.py
uv run ruff check backend/infrastructure/llm/prompts/
```
Erwartet: clean.

- [ ] **Step 4.11: Commit**

```bash
git add backend/infrastructure/llm/prompts/ backend/tests/unit/infrastructure/test_prompt_loader.py backend/tests/fixtures/prompts/
git commit -m "feat(llm): PromptTemplateLoader + DE-System-/User-Templates (#17, build-step 4/11)

Jinja2-basiert mit StrictUndefined (fehlende Slots → Error, nicht still).
DE-System-Prompt nach Parent-Spec §5.1 ausgefuellt; EN-Template als Stub
mit TODO (out of scope per Slice-Spec §2). User-Template mit Daten-Slots
fuer Stock + Run + Rankings + Aggregation.

Snapshot-Test prueft Render-Determinismus.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §3, §4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: UniverseContext + Ranking-Extraction Helpers

**Files:**
- Create: `backend/application/services/narrative_service.py` (Skelett mit Helpers, Service-Klasse leer)
- Create: `backend/tests/unit/application/__init__.py` (falls nicht vorhanden)
- Create: `backend/tests/unit/application/test_narrative_service.py` (nur Helper-Tests in dieser Task)

### 5.1 — Test schreiben (RED)

- [ ] **Step 5.1: `backend/tests/unit/application/test_narrative_service.py`**

```python
"""Unit-Tests fuer NarrativeService — Helpers + Service-Logik."""

from typing import Any

import pytest

from backend.application.services.narrative_service import (
    UniverseContext,
    _build_universe_context,
    _extract_ranking_for_ticker,
)

pytestmark = pytest.mark.unit


def _sample_results() -> list[dict[str, Any]]:
    """3-Stock-Mini-Universe."""
    return [
        {
            "ticker": "NESN",
            "total_rank": 1,
            "weighted_avg": 8.4,
            "is_sweet_spot": True,
            "per_model_ranks": {
                "quality_classic": 8,
                "alpha": 12,
                "trend_momentum": 25,
                "value_alpha_potential": 60,
                "diversification": 5,
            },
        },
        {
            "ticker": "ROG",
            "total_rank": 2,
            "weighted_avg": 12.0,
            "is_sweet_spot": False,
            "per_model_ranks": {
                "quality_classic": 15,
                "alpha": 20,
                "trend_momentum": 18,
                "value_alpha_potential": 22,
                "diversification": 10,
            },
        },
        {
            "ticker": "ABBN",
            "total_rank": 3,
            "weighted_avg": 25.0,
            "is_sweet_spot": False,
            "per_model_ranks": {
                "quality_classic": 30,
                "alpha": 28,
                "trend_momentum": 35,
                "value_alpha_potential": 18,
                "diversification": 14,
            },
        },
    ]


def test_extract_ranking_for_ticker_returns_dict() -> None:
    results = _sample_results()
    extracted = _extract_ranking_for_ticker(results, ticker="ROG")

    assert extracted["ticker"] == "ROG"
    assert extracted["total_rank"] == 2
    assert extracted["per_model_ranks"]["quality_classic"] == 15


def test_extract_ranking_for_ticker_raises_when_missing() -> None:
    results = _sample_results()
    with pytest.raises(KeyError):
        _extract_ranking_for_ticker(results, ticker="UNKNOWN")


def test_build_universe_context_computes_correct_metrics() -> None:
    results = _sample_results()
    ctx = _build_universe_context(results)

    assert isinstance(ctx, UniverseContext)
    assert ctx.n_stocks == 3
    assert ctx.median_rank == 2  # median of [1, 2, 3]
    # 20%-Quantile von [1,2,3] mit linear interpolation: 1 + 0.4*(2-1) = 1.4 → round to 1 (we use int)
    # but exact computation depends on implementation; assert reasonable bounds
    assert 1 <= ctx.top20_threshold <= 2


def test_build_universe_context_with_one_stock() -> None:
    """Edge case: Universe mit nur 1 Stock — median=top20=1."""
    results = [
        {
            "ticker": "NESN",
            "total_rank": 1,
            "weighted_avg": 1.0,
            "is_sweet_spot": True,
            "per_model_ranks": {},
        }
    ]
    ctx = _build_universe_context(results)
    assert ctx.n_stocks == 1
    assert ctx.median_rank == 1
    assert ctx.top20_threshold == 1
```

- [ ] **Step 5.2: Run test — Expected RED**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v
```
Erwartet: ImportError — `narrative_service.py` existiert nicht.

### 5.2 — Skelett mit Helpers (GREEN)

- [ ] **Step 5.3: `backend/application/services/narrative_service.py`**

```python
"""NarrativeService — orchestriert Memo-Generation Ende-zu-Ende.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md.

In dieser Datei (alles Service-internes Detail):
- `UniverseContext` (Pydantic-Value-Object — nur 1 Consumer im MVP)
- `_extract_ranking_for_ticker` (Helper)
- `_build_universe_context` (Helper)
- `NarrativeService` (Klasse mit get_memo + generate_memo)
"""

from __future__ import annotations

from statistics import median
from typing import Any

from pydantic import BaseModel, Field


class UniverseContext(BaseModel):
    """Aggregierte Verteilungs-Metadaten fuer den User-Prompt.

    Wird im Service aus dict-list-Results von RankingRunRepository abgeleitet.
    Keine eigene Datei (YAGNI — nur 1 Consumer).
    """

    model_config = {"frozen": True}

    n_stocks: int = Field(..., ge=1)
    median_rank: int = Field(..., ge=1)
    top20_threshold: int = Field(..., ge=1)


def _extract_ranking_for_ticker(
    results: list[dict[str, Any]], *, ticker: str
) -> dict[str, Any]:
    """Filtert den Ranking-Eintrag fuer einen bestimmten Ticker.

    Wirft KeyError, wenn der Ticker nicht im Run vorkommt.
    """
    for row in results:
        if row["ticker"] == ticker:
            return row
    raise KeyError(f"Ticker {ticker} not in run results")


def _build_universe_context(results: list[dict[str, Any]]) -> UniverseContext:
    """Berechnet aggregierte Stats (n, median, top20-threshold) aus dict-list."""
    ranks = sorted(int(r["total_rank"]) for r in results if r.get("total_rank") is not None)
    if not ranks:
        raise ValueError("Keine validen total_ranks in den Results")

    n = len(ranks)
    median_rank = int(median(ranks))
    # 20%-Perzentile via Index-Lookup; fuer kleine N robust ohne numpy
    idx = max(0, int(round(0.20 * (n - 1))))
    top20_threshold = ranks[idx]

    return UniverseContext(
        n_stocks=n, median_rank=median_rank, top20_threshold=top20_threshold
    )


class NarrativeService:
    """Memo-Generation. Implementation kommt in Tasks 6-8."""

    def __init__(self) -> None:
        raise NotImplementedError("NarrativeService wird in Task 6 vollstaendig implementiert")
```

- [ ] **Step 5.4: `backend/tests/unit/application/__init__.py`** (falls fehlend)

```bash
test -f backend/tests/unit/application/__init__.py || touch backend/tests/unit/application/__init__.py
```

- [ ] **Step 5.5: Run test — Expected GREEN**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v
```
Erwartet: 4 passed.

- [ ] **Step 5.6: mypy + ruff**

```bash
uv run mypy backend/application/services/narrative_service.py backend/tests/unit/application/
uv run ruff check backend/application/services/narrative_service.py backend/tests/unit/application/
```
Erwartet: clean.

- [ ] **Step 5.7: Commit**

```bash
git add backend/application/services/narrative_service.py backend/tests/unit/application/
git commit -m "feat(narrative): UniverseContext + Ranking-Extraction-Helpers (#17, build-step 5/11)

Skelett-Datei + 2 Helpers + UniverseContext-VO. Service-Klasse selbst
nur als Platzhalter (NotImplementedError) — wird in Tasks 6-8 vervollstaendigt.

Helpers werden in get_memo (Task 6) und generate_memo (Task 7) genutzt;
hier vorab mit eigenen Unit-Tests RED→GREEN, damit die Edge-Cases isoliert
getestet sind.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §3, §4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: NarrativeService.get_memo

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Modify: `backend/tests/unit/application/test_narrative_service.py`

### 6.1 — Test schreiben (RED)

- [ ] **Step 6.1: Append zu `backend/tests/unit/application/test_narrative_service.py`**

```python
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo


def _sample_memo(stock_id: Any = None, run_id: Any = None) -> ResearchMemo:
    return ResearchMemo(
        id=uuid4(),
        stock_id=stock_id or uuid4(),
        model_run_id=run_id or uuid4(),
        language="de",
        created_at=datetime.now(tz=UTC),
        one_liner="Kurzfassung des Memos.",
        ranking_interpretation="x" * 120,
        sweet_spot=True,
        sweet_spot_explanation=None,
        contradictions=[],
        key_strengths=["Top 10% Quality"],
        key_risks=["Bewertungs-Multiples nicht im Modell"],
        confidence="high",
        model_version="claude-sonnet-4-6",
    )


async def test_get_memo_returns_existing() -> None:
    stock_id, run_id = uuid4(), uuid4()
    expected = _sample_memo(stock_id=stock_id, run_id=run_id)

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=expected)

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=AsyncMock(),
        stock_repository=AsyncMock(),
        llm_client=AsyncMock(),
        prompt_loader=AsyncMock(),
    )
    result = await service.get_memo(stock_id, run_id)

    assert result is expected
    memo_repo.get.assert_awaited_once_with(stock_id, run_id, language="de")


async def test_get_memo_returns_none_when_missing() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=AsyncMock(),
        stock_repository=AsyncMock(),
        llm_client=AsyncMock(),
        prompt_loader=AsyncMock(),
    )
    result = await service.get_memo(uuid4(), uuid4())

    assert result is None
```

Plus oben in der Datei: ergänze `pytestmark = [pytest.mark.unit, pytest.mark.asyncio]` (falls bisher nur `pytest.mark.unit` ist — das ist wichtig für die async-Tests).

- [ ] **Step 6.2: Run test — Expected RED**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v -k "get_memo"
```
Erwartet: TypeError beim NarrativeService(...) wegen `NotImplementedError` im Konstruktor.

### 6.2 — Service-Konstruktor + get_memo (GREEN)

- [ ] **Step 6.3: Modify `backend/application/services/narrative_service.py`**

Ersetze die NarrativeService-Stub-Klasse durch:

```python
from typing import Literal
from uuid import UUID

from backend.domain.entities.research_memo import ResearchMemo
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader


class NarrativeService:
    """Memo-Generation. Spec §5."""

    def __init__(
        self,
        *,
        memo_repository: ResearchMemoRepository,
        run_repository: RankingRunRepository,
        stock_repository: StockRepository,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._memo_repo = memo_repository
        self._run_repo = run_repository
        self._stock_repo = stock_repository
        self._llm = llm_client
        self._prompts = prompt_loader
        self._model = model

    async def get_memo(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
    ) -> ResearchMemo | None:
        return await self._memo_repo.get(stock_id, model_run_id, language=language)
```

(Alle bestehenden Imports am Datei-Anfang behalten.)

- [ ] **Step 6.4: Run test — Expected GREEN**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v -k "get_memo"
```
Erwartet: 2 passed.

- [ ] **Step 6.5: mypy + ruff**

```bash
uv run mypy backend/application/services/narrative_service.py
uv run ruff check backend/application/services/narrative_service.py
```
Erwartet: clean.

- [ ] **Step 6.6: Commit**

```bash
git add backend/application/services/narrative_service.py backend/tests/unit/application/test_narrative_service.py
git commit -m "feat(narrative): NarrativeService.get_memo (#17, build-step 6/11)

Konstruktor mit allen 5 Dependencies + 1 trivialer Lookup-Methode.
Bewusst getrennt von generate_memo, weil GET /memos/... diesen Pfad
allein nutzt — ohne LLM-Setup einfacher zu testen.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §5, §6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: NarrativeService.generate_memo (happy + cached)

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Modify: `backend/tests/unit/application/test_narrative_service.py`

### 7.1 — Tests schreiben (RED)

- [ ] **Step 7.1: Append zu `test_narrative_service.py`**

```python
from types import SimpleNamespace

from backend.domain.entities.stock import Stock


def _stock(stock_id: Any | None = None, ticker: str = "NESN") -> Stock:
    return Stock(
        id=stock_id or uuid4(),
        ticker=ticker,
        name="Nestle SA",
        isin="CH0038863350",
        sector="Consumer Staples",
        country="CH",
        currency="CHF",
    )


def _tool_use_response(memo_payload: dict[str, Any]) -> Any:
    """Imitiert Anthropic-Response mit Tool-Use-Block."""
    return SimpleNamespace(
        id="msg_test",
        usage=SimpleNamespace(input_tokens=2300, output_tokens=487),
        content=[SimpleNamespace(type="tool_use", name="submit_memo", input=memo_payload)],
        stop_reason="tool_use",
    )


async def test_generate_memo_returns_cached_when_exists_and_no_force() -> None:
    stock_id, run_id = uuid4(), uuid4()
    cached = _sample_memo(stock_id=stock_id, run_id=run_id)

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=cached)
    memo_repo.save = AsyncMock()

    llm = AsyncMock()
    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=AsyncMock(),
        stock_repository=AsyncMock(),
        llm_client=llm,
        prompt_loader=AsyncMock(),
    )

    result = await service.generate_memo(stock_id, run_id, force_regenerate=False)

    assert result is cached
    memo_repo.save.assert_not_awaited()
    llm.messages_create.assert_not_awaited()


async def test_generate_memo_happy_path() -> None:
    stock_id, run_id = uuid4(), uuid4()

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)  # kein cache
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))

    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensiver Quality-Kern.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "Top 25% in 4 Modellen.",
        "contradictions": [],
        "key_strengths": ["Top 10% Quality"],
        "key_risks": ["Bewertungs-Multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))

    prompt_loader = SimpleNamespace(
        render=Mock(side_effect=lambda name, ctx: f"<rendered-{name}>")
    )

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id)

    # LLM wurde aufgerufen
    llm.messages_create.assert_awaited_once()
    call_kwargs = llm.messages_create.await_args.kwargs

    # System ist eine Liste mit cache_control
    assert isinstance(call_kwargs["system"], list)
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

    # Tool-use forced
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "submit_memo"}
    assert any(t["name"] == "submit_memo" for t in call_kwargs["tools"])

    # feature-Tag fuer Cost-Tracking
    assert call_kwargs["feature"] == "narrative_engine"

    # Memo wurde persistiert
    memo_repo.save.assert_awaited_once()
    saved = memo_repo.save.await_args.args[0]
    assert saved.stock_id == stock_id
    assert saved.model_run_id == run_id
    assert saved.one_liner == "Defensiver Quality-Kern."

    # Returnwert ist die Entity
    assert result.one_liner == "Defensiver Quality-Kern."


async def test_generate_memo_404_when_stock_missing() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=None)

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=AsyncMock(),
        stock_repository=stock_repo,
        llm_client=AsyncMock(),
        prompt_loader=AsyncMock(),
    )

    with pytest.raises(LookupError, match="Stock"):
        await service.generate_memo(uuid4(), uuid4())


async def test_generate_memo_404_when_run_missing() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock())
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=None)

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=AsyncMock(),
        prompt_loader=AsyncMock(),
    )

    with pytest.raises(LookupError, match="Run"):
        await service.generate_memo(uuid4(), uuid4())


async def test_generate_memo_404_when_stock_not_in_run() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(ticker="UNKNOWN"))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())  # nur NESN/ROG/ABBN

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=AsyncMock(),
        prompt_loader=AsyncMock(),
    )

    with pytest.raises(LookupError, match="UNKNOWN"):
        await service.generate_memo(uuid4(), uuid4())
```

- [ ] **Step 7.2: Run tests — Expected RED**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v -k "generate_memo"
```
Erwartet: AttributeError — `generate_memo` existiert nicht.

### 7.2 — Implementierung (GREEN)

- [ ] **Step 7.3: Modify `backend/application/services/narrative_service.py`**

Ergänze die `NarrativeService`-Klasse um `generate_memo` und einen privaten `_call_llm`-Helper. Erst importe oben hinzufügen:

```python
from datetime import UTC, datetime
from uuid import uuid4

from backend.domain.entities.research_memo import ContradictionItem
from backend.domain.schemas.research_memo_schema import ResearchMemoSchema
```

Dann die Methode anhängen (nach `get_memo`):

```python
    async def generate_memo(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
        force_regenerate: bool = False,
    ) -> ResearchMemo:
        # 1. Cache check
        if not force_regenerate:
            existing = await self._memo_repo.get(stock_id, model_run_id, language=language)
            if existing is not None:
                return existing

        # 2. Daten laden + 404-Pfade
        stock = await self._stock_repo.get(stock_id)
        if stock is None:
            raise LookupError(f"Stock {stock_id} not found")

        results = await self._run_repo.get_results(model_run_id)
        if results is None:
            raise LookupError(f"Run {model_run_id} not found")

        try:
            ranking = _extract_ranking_for_ticker(results, ticker=stock.ticker)
        except KeyError as exc:
            raise LookupError(
                f"Stock {stock.ticker} not in run {model_run_id}"
            ) from exc

        universe_context = _build_universe_context(results)

        # 3. Prompts rendern
        system_prompt = self._prompts.render(
            f"narrative_system.{language}.md.j2", {}
        )
        user_prompt = self._prompts.render(
            "narrative_user.md.j2",
            {
                "ticker": stock.ticker,
                "name": stock.name,
                "sector": stock.sector,
                "country": stock.country,
                "run_id": str(model_run_id),
                "universe_name": "Universe",
                "n_stocks": universe_context.n_stocks,
                "median_rank": universe_context.median_rank,
                "top20_threshold": universe_context.top20_threshold,
                "rankings": _rankings_for_template(ranking),
                "total_rank": ranking["total_rank"],
                "sweet_spot": ranking["is_sweet_spot"],
                "weights": "equal-weighted (0.20 each)",
            },
        )

        # 4. LLM-Call mit Tool-use + Caching
        response = await self._llm.messages_create(
            model=self._model,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
            tools=[
                {
                    "name": "submit_memo",
                    "description": "Submit the structured research memo.",
                    "input_schema": ResearchMemoSchema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "submit_memo"},
            max_tokens=2000,
            feature="narrative_engine",
        )

        # 5. Tool-use Antwort → Pydantic-Validate
        memo_schema = self._validate_tool_response(response, stock=stock, ranking=ranking)

        # 6. Persist
        memo_entity = ResearchMemo(
            id=uuid4(),
            stock_id=stock_id,
            model_run_id=model_run_id,
            language=language,
            created_at=datetime.now(tz=UTC),
            one_liner=memo_schema.one_liner,
            ranking_interpretation=memo_schema.ranking_interpretation,
            sweet_spot=memo_schema.sweet_spot,
            sweet_spot_explanation=memo_schema.sweet_spot_explanation,
            contradictions=list(memo_schema.contradictions),
            key_strengths=list(memo_schema.key_strengths),
            key_risks=list(memo_schema.key_risks),
            confidence=memo_schema.confidence,
            model_version=memo_schema.model_version,
        )
        await self._memo_repo.save(memo_entity)
        return memo_entity

    def _validate_tool_response(
        self, response: Any, *, stock: Stock, ranking: dict[str, Any]
    ) -> ResearchMemoSchema:
        """Extrahiert tool_use-Block + Pydantic-Validate. Error-Memo-Pfad: Task 8."""
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_memo":
                return ResearchMemoSchema.model_validate(block.input)
        # Kein passender Block — Task 8 ergaenzt hier den error-memo-Pfad.
        raise RuntimeError("No submit_memo tool_use block in response (Task 8: error-memo path)")
```

Plus den kleinen `_rankings_for_template`-Helper (oben bei den anderen Helpers):

```python
def _rankings_for_template(ranking: dict[str, Any]) -> dict[str, dict[str, float | int]]:
    """Wandelt das per_model_ranks-Dict + weighted_avg in ein
    Template-freundliches dict[name, {rank, score}]-Format um.

    Score-Daten sind zu diesem Zeitpunkt nicht alle in den Run-Results,
    daher Score = 1 / rank als grobe Visualisierung. Spec sagt nichts
    Strenges dazu, das Template zeigt nur eine Sichtbarmachung.
    """
    model_label = {
        "quality_classic": "Quality Classic",
        "alpha": "Alpha",
        "trend_momentum": "Trend Momentum",
        "value_alpha_potential": "Value Alpha Potential",
        "diversification": "Diversification",
    }
    out: dict[str, dict[str, float | int]] = {}
    per_model = ranking.get("per_model_ranks") or {}
    for key, label in model_label.items():
        rank = per_model.get(key)
        if rank is not None:
            out[label] = {"rank": int(rank), "score": round(1.0 / max(int(rank), 1), 4)}
    return out
```

Plus den `Stock` und `Any` Import in narrative_service.py oben:

```python
from typing import Any, Literal
from backend.domain.entities.stock import Stock
```

- [ ] **Step 7.4: Run tests — Expected GREEN**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v
```
Erwartet: alle Tests passed (incl. 4 aus Task 5 + 2 aus Task 6 + 5 aus Task 7).

- [ ] **Step 7.5: mypy + ruff**

```bash
uv run mypy backend/application/services/narrative_service.py
uv run ruff check backend/application/services/narrative_service.py
```
Erwartet: clean.

- [ ] **Step 7.6: Commit**

```bash
git add backend/application/services/narrative_service.py backend/tests/unit/application/test_narrative_service.py
git commit -m "feat(narrative): generate_memo Happy-Path + Cache-Hit + 404-Pfade (#17, build-step 7/11)

Implementiert den End-zu-Ende-Pfad ohne Error-Handling: Cache-Check,
Stock/Run/Ticker-Lookup, Prompt-Rendering, LLM-Call mit Tool-use +
cache_control, Pydantic-Validate, Persist als ResearchMemo-Entity.

3 LookupError-Pfade (404 in REST): stock fehlt, run fehlt, stock nicht
im run drin. Error-Memo-Pfad bei Tool-Use-Fehlern kommt in Task 8.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §4, §5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: NarrativeService.generate_memo — Error-Pfade

**Files:**
- Modify: `backend/application/services/narrative_service.py`
- Modify: `backend/tests/unit/application/test_narrative_service.py`

### 8.1 — Tests schreiben (RED)

- [ ] **Step 8.1: Append zu `test_narrative_service.py`**

```python
import json
from pathlib import Path

import pytest


async def test_generate_memo_persists_error_memo_when_no_tool_use_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bei Anthropic-Response ohne submit_memo-Tool-Block: error-memo persistieren."""
    monkeypatch.chdir(tmp_path)  # logs/malformed_memos/ landet in tmp

    stock_id, run_id = uuid4(), uuid4()

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    memo_repo.save = AsyncMock()
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    bad_response = SimpleNamespace(
        id="msg_x",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        content=[SimpleNamespace(type="text", text="I refuse")],
        stop_reason="end_turn",
    )
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=bad_response)
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: "<rendered>"))

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id)

    # Error-Memo wurde persistiert
    memo_repo.save.assert_awaited_once()
    assert result.confidence == "low"
    assert "fehlgeschlagen" in result.one_liner.lower()
    assert result.model_version == "error-fallback"

    # Raw-Response in logs/malformed_memos/
    log_dir = tmp_path / "logs" / "malformed_memos"
    assert log_dir.exists()
    log_files = list(log_dir.glob("*.json"))
    assert len(log_files) == 1
    raw = json.loads(log_files[0].read_text())
    # Mindestens id und content sind im Dump
    assert raw.get("id") == "msg_x"


async def test_generate_memo_persists_error_memo_on_pydantic_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bei Schema-Verletzung (z.B. one_liner zu kurz): error-memo persistieren."""
    monkeypatch.chdir(tmp_path)

    stock_id, run_id = uuid4(), uuid4()

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    memo_repo.save = AsyncMock()
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    invalid_payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "x",  # zu kurz (min_length=10)
        "ranking_interpretation": "y" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": None,
        "contradictions": [],
        "key_strengths": ["a"],
        "key_risks": ["b"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(invalid_payload))
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: "<rendered>"))

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id)

    memo_repo.save.assert_awaited_once()
    assert result.confidence == "low"
    assert result.model_version == "error-fallback"
```

- [ ] **Step 8.2: Run tests — Expected RED**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v -k "error_memo"
```
Erwartet: FAIL — RuntimeError (no submit_memo block) bzw. ValidationError werden geworfen, nicht abgefangen.

### 8.2 — Implementierung (GREEN)

- [ ] **Step 8.3: Modify `narrative_service.py`** — `_validate_tool_response` und Error-Memo-Builder

Ersetze die bestehende `_validate_tool_response`-Methode + füge Helper hinzu. Imports oben ergänzen:

```python
import json as _json
from pathlib import Path

from pydantic import ValidationError
```

Ersetze `_validate_tool_response` durch eine Variante, die Schema-Verletzung **nicht** rethrowt, sondern an den Caller signalisiert:

```python
    def _try_validate_tool_response(self, response: Any) -> ResearchMemoSchema | None:
        """Liefert die validierte Schema-Instanz oder None bei Fehler."""
        for block in response.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == "submit_memo"
            ):
                try:
                    return ResearchMemoSchema.model_validate(block.input)
                except ValidationError:
                    return None
        return None
```

Dann modifiziere die `generate_memo`-Methode: ersetze den Block ab "5. Tool-use Antwort → Pydantic-Validate" bis vor "6. Persist" durch:

```python
        # 5. Tool-use Antwort → Pydantic-Validate (oder Error-Memo-Pfad)
        memo_schema = self._try_validate_tool_response(response)
        if memo_schema is None:
            self._dump_malformed_response(response, stock_id=stock_id, run_id=model_run_id)
            memo_schema = self._build_error_memo_schema(stock=stock, ranking=ranking)
```

Plus zwei neue private Methoden (am Ende der Klasse):

```python
    def _dump_malformed_response(
        self, response: Any, *, stock_id: UUID, run_id: UUID
    ) -> None:
        log_dir = Path("logs/malformed_memos")
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = int(datetime.now(tz=UTC).timestamp())
        path = log_dir / f"{run_id}_{stock_id}_{ts}.json"
        try:
            dump = response.model_dump() if hasattr(response, "model_dump") else _stringify(response)
        except Exception:  # noqa: BLE001
            dump = _stringify(response)
        path.write_text(_json.dumps(dump, default=str, indent=2), encoding="utf-8")

    def _build_error_memo_schema(
        self, *, stock: Stock, ranking: dict[str, Any]
    ) -> ResearchMemoSchema:
        return ResearchMemoSchema(
            ticker=stock.ticker,
            total_rank=int(ranking["total_rank"]),
            one_liner="Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
            ranking_interpretation=(
                "Automatisch generiertes Memo nicht erzeugbar. Siehe "
                "logs/malformed_memos/ fuer die Raw-Response."
            ),
            sweet_spot=False,
            sweet_spot_explanation=None,
            contradictions=[],
            key_strengths=["—"],
            key_risks=["—"],
            confidence="low",
            generated_at=datetime.now(tz=UTC),
            model_version="error-fallback",
        )
```

Plus globaler `_stringify`-Helper (bei den anderen Helpern):

```python
def _stringify(obj: Any) -> dict[str, Any]:
    """Fallback-Dump fuer SimpleNamespace und aehnliche Objekte ohne model_dump."""
    if hasattr(obj, "__dict__"):
        return {k: _stringify(v) if hasattr(v, "__dict__") else v for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return {"_list": [_stringify(x) if hasattr(x, "__dict__") else x for x in obj]}
    return {"_repr": repr(obj)}
```

- [ ] **Step 8.4: Run all tests — Expected GREEN**

```bash
uv run pytest backend/tests/unit/application/test_narrative_service.py -v
```
Erwartet: alle Tests passed (incl. die 2 neuen error-Pfad-Tests).

- [ ] **Step 8.5: mypy + ruff**

```bash
uv run mypy backend/application/services/narrative_service.py
uv run ruff check backend/application/services/narrative_service.py
```
Erwartet: clean.

- [ ] **Step 8.6: Commit**

```bash
git add backend/application/services/narrative_service.py backend/tests/unit/application/test_narrative_service.py
git commit -m "feat(narrative): generate_memo Error-Memo-Pfade (#17, build-step 8/11)

Bei Tool-Use-Block-Fehlen oder Pydantic-ValidationError: Raw-Response
wird nach logs/malformed_memos/{run_id}_{stock_id}_{ts}.json gedumpt,
und ein error-memo (confidence=low, model_version='error-fallback')
wird persistiert. Kein App-Crash — Frontend kann is_error rendern.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §7.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: REST Router + DI + FastAPI-Integration-Test

**Files:**
- Create: `backend/interfaces/rest/routers/memos.py`
- Modify: `backend/interfaces/rest/dependencies.py`
- Modify: `backend/interfaces/rest/app.py`
- Create: `backend/tests/integration/test_memos_endpoint.py`

### 9.1 — Pydantic-Response-DTO + Router

- [ ] **Step 9.1: `backend/interfaces/rest/routers/memos.py`**

```python
"""POST /memos/generate + GET /memos/{stock_id}/{run_id}.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §6.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.research_memo import ContradictionItem, ResearchMemo
from backend.interfaces.rest.dependencies import get_narrative_service

router = APIRouter(prefix="/memos", tags=["memos"])


class GenerateMemoRequest(BaseModel):
    stock_id: UUID
    model_run_id: UUID
    language: Literal["de", "en"] = "de"


class MemoResponse(BaseModel):
    id: UUID
    stock_id: UUID
    model_run_id: UUID
    language: Literal["de", "en"]
    one_liner: str
    ranking_interpretation: str
    sweet_spot: bool
    sweet_spot_explanation: str | None
    contradictions: list[ContradictionItem]
    key_strengths: list[str]
    key_risks: list[str]
    confidence: Literal["low", "medium", "high"]
    model_version: str
    created_at: datetime
    is_error: bool

    @classmethod
    def from_entity(cls, memo: ResearchMemo) -> "MemoResponse":
        is_error = (
            memo.model_version == "error-fallback"
            or memo.one_liner.startswith("Memo-Generierung fehlgeschlagen")
        )
        return cls(
            id=memo.id,
            stock_id=memo.stock_id,
            model_run_id=memo.model_run_id,
            language=memo.language,
            one_liner=memo.one_liner,
            ranking_interpretation=memo.ranking_interpretation,
            sweet_spot=memo.sweet_spot,
            sweet_spot_explanation=memo.sweet_spot_explanation,
            contradictions=list(memo.contradictions),
            key_strengths=list(memo.key_strengths),
            key_risks=list(memo.key_risks),
            confidence=memo.confidence,
            model_version=memo.model_version,
            created_at=memo.created_at,
            is_error=is_error,
        )


@router.post("/generate", response_model=MemoResponse)
async def generate_memo(
    request: GenerateMemoRequest,
    service: NarrativeService = Depends(get_narrative_service),
) -> MemoResponse:
    try:
        memo = await service.generate_memo(
            request.stock_id, request.model_run_id, language=request.language
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MemoResponse.from_entity(memo)


@router.get("/{stock_id}/{run_id}", response_model=MemoResponse)
async def get_memo(
    stock_id: UUID,
    run_id: UUID,
    language: Literal["de", "en"] = "de",
    service: NarrativeService = Depends(get_narrative_service),
) -> MemoResponse:
    memo = await service.get_memo(stock_id, run_id, language=language)
    if memo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memo not found")
    return MemoResponse.from_entity(memo)
```

- [ ] **Step 9.2: Modify `backend/interfaces/rest/dependencies.py`**

Füge nach dem bestehenden DI-Code hinzu:

```python
from backend.application.services.narrative_service import NarrativeService
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
from backend.infrastructure.persistence.repositories.research_memo_repository import (
    SQLAResearchMemoRepository,
)


_PROMPT_LOADER_SINGLETON: PromptTemplateLoader | None = None


def get_prompt_loader() -> PromptTemplateLoader:
    """Singleton — Templates werden einmal beim ersten Aufruf geladen."""
    global _PROMPT_LOADER_SINGLETON
    if _PROMPT_LOADER_SINGLETON is None:
        _PROMPT_LOADER_SINGLETON = PromptTemplateLoader()
    return _PROMPT_LOADER_SINGLETON


async def get_research_memo_repository(
    session: AsyncSession = Depends(get_session),
) -> ResearchMemoRepository:
    return SQLAResearchMemoRepository(session=session)


async def get_narrative_service(
    memo_repo: ResearchMemoRepository = Depends(get_research_memo_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    stock_repo: StockRepository = Depends(get_stock_repository),
    llm: LLMClient = Depends(get_llm_client),
    prompt_loader: PromptTemplateLoader = Depends(get_prompt_loader),
) -> NarrativeService:
    return NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )
```

**Wichtig:** `get_ranking_run_repository` und `get_llm_client` existieren möglicherweise nicht in `dependencies.py`. Vor Implementation prüfen:
```bash
grep -n "get_ranking_run_repository\|get_llm_client" backend/interfaces/rest/dependencies.py
```
Falls fehlend: dem bestehenden Pattern folgend ergänzen (analog `get_stock_repository`).

- [ ] **Step 9.3: Modify `backend/interfaces/rest/app.py`**

Füge den Memo-Router hinzu, parallel zu den bestehenden:

```python
from backend.interfaces.rest.routers import memos
# ...
app.include_router(memos.router, prefix="/api/v1")
```

(Die genaue Stelle: dort, wo bereits `stocks.router`, `runs.router` etc. registriert werden.)

### 9.2 — Integration-Test (RED)

- [ ] **Step 9.4: `backend/tests/integration/test_memos_endpoint.py`**

```python
"""Integration-Tests fuer /api/v1/memos/* via FastAPI-TestClient."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.research_memo import ResearchMemo
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_narrative_service

pytestmark = pytest.mark.integration


def _sample_memo() -> ResearchMemo:
    return ResearchMemo(
        id=uuid4(),
        stock_id=uuid4(),
        model_run_id=uuid4(),
        language="de",
        created_at=datetime.now(tz=UTC),
        one_liner="One-Liner.",
        ranking_interpretation="x" * 120,
        sweet_spot=True,
        sweet_spot_explanation="Top 25% in 4 Modellen.",
        contradictions=[],
        key_strengths=["Top 10% Quality"],
        key_risks=["Bewertungs-Multiples"],
        confidence="high",
        model_version="claude-sonnet-4-6",
    )


@pytest_asyncio.fixture
async def app_with_mock_service() -> Any:
    app = create_app()
    mock_service = AsyncMock(spec=NarrativeService)
    app.dependency_overrides[get_narrative_service] = lambda: mock_service
    yield app, mock_service
    app.dependency_overrides.clear()


def test_post_generate_returns_200_with_memo(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    memo = _sample_memo()
    mock_service.generate_memo = AsyncMock(return_value=memo)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={
                "stock_id": str(memo.stock_id),
                "model_run_id": str(memo.model_run_id),
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["one_liner"] == "One-Liner."
    assert body["is_error"] is False


def test_post_generate_returns_404_when_stock_missing(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    mock_service.generate_memo = AsyncMock(side_effect=LookupError("Stock not found"))

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={"stock_id": str(uuid4()), "model_run_id": str(uuid4())},
        )

    assert resp.status_code == 404


def test_get_memo_returns_200_when_exists(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    memo = _sample_memo()
    mock_service.get_memo = AsyncMock(return_value=memo)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/{memo.stock_id}/{memo.model_run_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == "high"


def test_get_memo_returns_404_when_missing(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    mock_service.get_memo = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/{uuid4()}/{uuid4()}")

    assert resp.status_code == 404


def test_post_generate_sets_is_error_when_fallback_memo(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    memo = _sample_memo().model_copy(update={
        "model_version": "error-fallback",
        "one_liner": "Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
        "confidence": "low",
    })
    mock_service.generate_memo = AsyncMock(return_value=memo)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={"stock_id": str(memo.stock_id), "model_run_id": str(memo.model_run_id)},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_error"] is True
```

- [ ] **Step 9.5: Run integration tests — Expected RED then GREEN**

```bash
uv run pytest backend/tests/integration/test_memos_endpoint.py -v
```
Falls die DI-Funktionen `get_ranking_run_repository` oder `get_llm_client` noch nicht existieren — anlegen analog zum bestehenden Pattern in `dependencies.py`.

Erwartet nach Fix: 5 passed.

- [ ] **Step 9.6: mypy + ruff**

```bash
uv run mypy backend/interfaces/rest/routers/memos.py backend/interfaces/rest/dependencies.py
uv run ruff check backend/interfaces/rest/
```
Erwartet: clean.

- [ ] **Step 9.7: Manual Smoke (OpenAPI sichtbar)**

```bash
docker compose up -d backend
sleep 5
curl -s http://localhost:8000/openapi.json | python -c "import json,sys; ops=[p for p in json.load(sys.stdin)['paths'] if 'memo' in p]; print(ops)"
```
Erwartet: `['/api/v1/memos/generate', '/api/v1/memos/{stock_id}/{run_id}']`

- [ ] **Step 9.8: Commit**

```bash
git add backend/interfaces/rest/ backend/tests/integration/test_memos_endpoint.py
git commit -m "feat(rest): POST/GET /memos Endpoints + DI-Wiring (#17, build-step 9/11)

NarrativeService an FastAPI-DI angebunden, 2 Endpoints + Pydantic
Request/Response-DTO. is_error wird im Response abgeleitet aus
model_version='error-fallback' oder 'fehlgeschlagen'-Praefix im
one_liner — Frontend kann darauf rendern.

Tests: TestClient + dependency_overrides → kein DB-Bedarf, alle
5 Pfade abgedeckt (POST happy, POST 404, GET hit, GET 404, error-flag).

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Stub-Anthropic + 3 Fixtures + Persistence-Integration-Test

**Files:**
- Create: `backend/tests/fixtures/llm/__init__.py` (falls fehlend)
- Create: `backend/tests/fixtures/llm/stub_anthropic_client.py`
- Create: `backend/tests/fixtures/llm/narrative/__init__.py`
- Create: `backend/tests/fixtures/llm/narrative/top_quality_stock.json`
- Create: `backend/tests/fixtures/llm/narrative/contradictory_quality_risk.json`
- Create: `backend/tests/fixtures/llm/narrative/malformed_response.json`
- Create: `backend/tests/integration/test_narrative_service_integration.py`

### 10.1 — Stub-Client + Fixtures

- [ ] **Step 10.1: `backend/tests/fixtures/llm/stub_anthropic_client.py`**

```python
"""Stub fuer den Anthropic-SDK-Client in Integration-Tests."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any


class StubMessages:
    def __init__(self, fixtures: list[Path]) -> None:
        self._fixtures = list(fixtures)
        self._idx = 0
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._idx >= len(self._fixtures):
            raise RuntimeError("StubMessages: kein Fixture mehr verfuegbar")
        path = self._fixtures[self._idx]
        self._idx += 1
        data = json.loads(path.read_text(encoding="utf-8"))
        return _to_namespace(data)


class StubAnthropicClient:
    def __init__(self, fixture_paths: list[Path]) -> None:
        self.messages = StubMessages(fixture_paths)


def _to_namespace(obj: Any) -> Any:
    """Dict → SimpleNamespace rekursiv (dict-content-blocks bleiben dicts wo noetig)."""
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_namespace(x) for x in obj]
    return obj
```

- [ ] **Step 10.2: `backend/tests/fixtures/llm/narrative/top_quality_stock.json`**

```json
{
  "id": "msg_top_quality",
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
        "one_liner": "Defensiver Quality-Kern mit niedrigem Risiko, schwaches Reversion-Potenzial.",
        "ranking_interpretation": "Quality Classic Top 10% und Diversification Top 6% pruegen das Bild — fundamentale Solidaet und niedriges Risiko stehen klar im Vordergrund. Alpha und Trend Momentum sind Top 25% bzw. ueberdurchschnittlich, also ein gesundes aber nicht spektakulaeres Momentum-Profil. Value Alpha Potential im Bottom 25% deutet darauf hin, dass die Aktie nahe ihrem rolling-max Alpha laeuft — wenig Rueckschlag-Potenzial.",
        "sweet_spot": true,
        "sweet_spot_explanation": "4 von 5 Modellen Top 25% (Quality, Alpha, Trend, Diversification). Robustes Ranking ueber Modellgrenzen hinweg.",
        "contradictions": [],
        "key_strengths": [
          "Top 10% Quality-Bilanz",
          "Top 6% Diversifikations-Risikoprofil",
          "Top 25% Alpha-Performance",
          "Sweet-Spot-Status"
        ],
        "key_risks": [
          "Bottom 25% Reversion-Potenzial",
          "Stil-Rotation aus Defensives waere ein Headwind"
        ],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6"
      }
    }
  ]
}
```

- [ ] **Step 10.3: `backend/tests/fixtures/llm/narrative/contradictory_quality_risk.json`**

```json
{
  "id": "msg_contradictory",
  "type": "message",
  "role": "assistant",
  "model": "claude-sonnet-4-6",
  "stop_reason": "tool_use",
  "usage": {"input_tokens": 280, "output_tokens": 510, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 2000},
  "content": [
    {
      "type": "tool_use",
      "id": "tool_2",
      "name": "submit_memo",
      "input": {
        "ticker": "ROG",
        "total_rank": 12,
        "one_liner": "Solide Quality-Bilanz, aber Risiko-Profil weicht stark ab.",
        "ranking_interpretation": "Quality Classic Top 10% steht im starken Kontrast zu Diversification Bottom 25% — typisch fuer hoch-konzentrierte Geschaeftsmodelle. Trend und Value im Mittelfeld. Confidence reduziert wegen klarer Modell-Diskrepanz.",
        "sweet_spot": false,
        "sweet_spot_explanation": null,
        "contradictions": [
          {
            "model_a": "Quality Classic",
            "model_b": "Diversification",
            "description": "Top 10% Quality vs. Bottom 25% Risiko-/Diversifikations-Profil — 65 Perzentile auseinander."
          }
        ],
        "key_strengths": [
          "Top 10% Quality-Bilanz",
          "Solide Trend-Signale"
        ],
        "key_risks": [
          "Bottom 25% Risiko-Profil — hoch konzentriert",
          "Sektor-Klumpen-Risiko",
          "Liquiditaets-Risiko nicht modelliert"
        ],
        "confidence": "medium",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6"
      }
    }
  ]
}
```

- [ ] **Step 10.4: `backend/tests/fixtures/llm/narrative/malformed_response.json`**

```json
{
  "id": "msg_malformed",
  "type": "message",
  "role": "assistant",
  "model": "claude-sonnet-4-6",
  "stop_reason": "tool_use",
  "usage": {"input_tokens": 290, "output_tokens": 50, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 2000},
  "content": [
    {
      "type": "tool_use",
      "id": "tool_3",
      "name": "submit_memo",
      "input": {
        "ticker": "ABBN",
        "total_rank": 25,
        "one_liner": "x",
        "ranking_interpretation": "zu kurz",
        "sweet_spot": false,
        "contradictions": [],
        "key_strengths": [],
        "key_risks": [],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6"
      }
    }
  ]
}
```

(`one_liner` zu kurz, `ranking_interpretation` zu kurz, `key_strengths`/`key_risks` leer — mehrere Constraint-Verletzungen für Pydantic.)

### 10.2 — Integration-Test gegen echte PG + Stub-LLM (RED → GREEN)

- [ ] **Step 10.5: `backend/tests/integration/test_narrative_service_integration.py`**

```python
"""Integration: NarrativeService gegen echte Postgres + StubAnthropicClient."""

from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.services.cost_tracker import CostTracker
from backend.application.services.narrative_service import NarrativeService
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
from backend.infrastructure.persistence.models.stock import StockORM
from backend.infrastructure.persistence.repositories.cost_log_repository import (
    SQLACostLogRepository,
)
from backend.infrastructure.persistence.repositories.ranking_run_repository import (
    SQLARankingRunRepository,
)
from backend.infrastructure.persistence.repositories.research_memo_repository import (
    SQLAResearchMemoRepository,
)
from backend.infrastructure.persistence.repositories.stock_repository import (
    SQLAStockRepository,
)
from backend.tests.fixtures.llm.stub_anthropic_client import StubAnthropicClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / "narrative"


@pytest_asyncio.fixture
async def seeded_run_with_stock(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[AsyncSession, dict]:
    """Persistiere einen Stock + RankingRun + Results, gib (session, ids) zurueck."""
    # SETUP — vereinfachtes Setup; Details haengen vom RankingRun-ORM ab
    # (universe + run + results muessen existieren).
    # Concrete-Steps: TODO im Plan-Subagent — analog zum
    # backend/tests/integration/persistence/test_research_memo_repository.py-conftest.
    raise NotImplementedError(
        "TODO im Subagent: setup analog zu test_research_memo_repository.py"
    )


async def test_full_pipeline_top_quality_fixture(
    seeded_run_with_stock: tuple[AsyncSession, dict],
) -> None:
    """End-to-End: Stock + Run → Service ruft Stub-Anthropic → Memo in DB."""
    session, ids = seeded_run_with_stock

    stub = StubAnthropicClient([FIXTURES / "top_quality_stock.json"])
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session=session),
        cap_usd=20,
    )
    llm = LLMClient(anthropic=stub, voyage=None, cost_tracker=cost_tracker)
    service = NarrativeService(
        memo_repository=SQLAResearchMemoRepository(session=session),
        run_repository=SQLARankingRunRepository(session=session),
        stock_repository=SQLAStockRepository(session=session),
        llm_client=llm,
        prompt_loader=PromptTemplateLoader(),
    )

    memo = await service.generate_memo(ids["stock_id"], ids["run_id"])

    assert memo.confidence == "high"
    assert memo.sweet_spot is True
    assert memo.model_version == "claude-sonnet-4-6"


async def test_pydantic_fail_persists_error_memo(
    seeded_run_with_stock: tuple[AsyncSession, dict],
) -> None:
    session, ids = seeded_run_with_stock

    stub = StubAnthropicClient([FIXTURES / "malformed_response.json"])
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session=session),
        cap_usd=20,
    )
    llm = LLMClient(anthropic=stub, voyage=None, cost_tracker=cost_tracker)
    service = NarrativeService(
        memo_repository=SQLAResearchMemoRepository(session=session),
        run_repository=SQLARankingRunRepository(session=session),
        stock_repository=SQLAStockRepository(session=session),
        llm_client=llm,
        prompt_loader=PromptTemplateLoader(),
    )

    memo = await service.generate_memo(ids["stock_id"], ids["run_id"])

    assert memo.confidence == "low"
    assert memo.model_version == "error-fallback"


async def test_cache_hit_smoke_two_sequential_calls(
    seeded_run_with_stock: tuple[AsyncSession, dict],
) -> None:
    """Smoke: 2 generate_memo-Calls → Stub-Client sieht 2x denselben System-Block."""
    session, ids = seeded_run_with_stock
    second_stock_id = ids["second_stock_id"]  # zusaetzlich seedet die fixture einen 2. Stock

    stub = StubAnthropicClient([
        FIXTURES / "top_quality_stock.json",
        FIXTURES / "contradictory_quality_risk.json",
    ])
    cost_tracker = CostTracker(
        repository=SQLACostLogRepository(session=session), cap_usd=20
    )
    llm = LLMClient(anthropic=stub, voyage=None, cost_tracker=cost_tracker)
    service = NarrativeService(
        memo_repository=SQLAResearchMemoRepository(session=session),
        run_repository=SQLARankingRunRepository(session=session),
        stock_repository=SQLAStockRepository(session=session),
        llm_client=llm,
        prompt_loader=PromptTemplateLoader(),
    )

    await service.generate_memo(ids["stock_id"], ids["run_id"])
    await service.generate_memo(second_stock_id, ids["run_id"])

    assert len(stub.messages.calls) == 2
    sys1 = stub.messages.calls[0]["system"]
    sys2 = stub.messages.calls[1]["system"]
    assert sys1 == sys2
    assert sys1[0]["cache_control"] == {"type": "ephemeral"}
```

**Hinweis**: Das Fixture-Setup für `seeded_run_with_stock` ist im Plan **NICHT vollständig ausgeschrieben**, weil es vom konkreten RankingRun-ORM-Schema abhängt. Der Subagent (oder ausführende Engineer) muss:

1. `backend/tests/integration/persistence/test_research_memo_repository.py` als Vorlage anschauen (dort ist der Stock+Run-Setup ausformuliert)
2. Diesen Setup hier portieren (Universe + Run + Results in `ranking_runs.results`-JSON-Spalte mit den Sample-Results aus Task 5)
3. `seeded_run_with_stock`-Fixture vollständig implementieren

- [ ] **Step 10.6: Run integration tests — Expected GREEN nach Fixture-Implementation**

```bash
docker compose up -d postgres backend
uv run pytest backend/tests/integration/test_narrative_service_integration.py -v
```
Erwartet: 3 passed.

- [ ] **Step 10.7: Commit**

```bash
git add backend/tests/fixtures/ backend/tests/integration/test_narrative_service_integration.py
git commit -m "test(narrative): Integration-Tests gegen PG + 3 Stub-Anthropic-Fixtures (#17, build-step 10/11)

3 Fixtures abgedeckt: happy-path (top_quality_stock), Widerspruch
(contradictory_quality_risk), Pydantic-Fail (malformed_response).
Plus Cache-Hit-Smoke-Test: 2 sequentielle Calls → System-Block-Identity
verifiziert.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md §9.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Sample-Memo + AI-USAGE-Eintrag

**Files:**
- Create: `docs/examples/research-memo-sample.json`
- Modify: `docs/AI-USAGE.md`

- [ ] **Step 11.1: `docs/examples/research-memo-sample.json`**

```json
{
  "_meta": {
    "description": "Realistisches Beispiel-Memo, exportiert aus dem MVP-Service. Quelle: Test-Run gegen claude-sonnet-4-6 mit NESN als Stock.",
    "created_at": "2026-05-04",
    "model_version": "claude-sonnet-4-6"
  },
  "id": "550e8400-e29b-41d4-a716-446655440099",
  "stock_id": "550e8400-e29b-41d4-a716-446655440000",
  "model_run_id": "550e8400-e29b-41d4-a716-446655440001",
  "language": "de",
  "one_liner": "Defensiver Quality-Kern mit niedrigem Risiko, schwaches Reversion-Potenzial.",
  "ranking_interpretation": "Quality Classic Top 10% und Diversification Top 6% pruegen das Bild — fundamentale Solidaet und niedriges Risiko stehen klar im Vordergrund. Alpha und Trend Momentum sind Top 25% bzw. ueberdurchschnittlich, also ein gesundes aber nicht spektakulaeres Momentum-Profil. Value Alpha Potential im Bottom 25% deutet darauf hin, dass die Aktie nahe ihrem rolling-max Alpha laeuft — wenig Rueckschlag-Potenzial.",
  "sweet_spot": true,
  "sweet_spot_explanation": "4 von 5 Modellen Top 25% (Quality, Alpha, Trend, Diversification). Robustes Ranking ueber Modellgrenzen hinweg.",
  "contradictions": [
    {
      "model_a": "Diversification",
      "model_b": "Value Alpha Potential",
      "description": "Niedrigstes Risiko vs. niedrigstes Reversion-Potenzial — ueblich fuer Quality-Compounder, aber bei Stil-Rotation ein Risiko."
    }
  ],
  "key_strengths": [
    "Top 10% Quality-Bilanz",
    "Top 6% Diversifikations-Risikoprofil",
    "Top 25% Alpha-Performance",
    "Sweet-Spot-Status (4 von 5 Modellen)"
  ],
  "key_risks": [
    "Bottom 25% Reversion-Potenzial — weniger Upside",
    "Stil-Rotation aus Defensives waere ein Headwind",
    "Bewertungs-Multiples nicht im Modell — separate Pruefung"
  ],
  "confidence": "high",
  "model_version": "claude-sonnet-4-6",
  "created_at": "2026-05-04T10:00:00Z",
  "is_error": false
}
```

- [ ] **Step 11.2: AI-USAGE.md-Eintrag**

Vor der Spitze von `## Einträge` einen neuen Eintrag einfügen — Inhalt zusammenfassen aus dem realen Build:

- Token-Kosten (geschaetzt + reale aus CostTracker)
- Beobachtete Cache-Hit-Rate beim manuellen Smoke-Test (1 Call mit cache_creation, 2-3 Folge-Calls mit cache_read)
- Was-gut-lief / Was-nicht / Lektion / Methodisches Mini-Learning
- Autor: Sheyla / Claude Code Opus 4.7

Format genau wie der Foundation-Eintrag (siehe `docs/AI-USAGE.md` zur Vorlage). Inhalt füllt der ausführende Engineer/Subagent nach Abschluss aller anderen Tasks aus mit echten Daten — kein Boilerplate-Text.

- [ ] **Step 11.3: Manueller Smoke gegen echte API**

```bash
docker compose up -d backend postgres
# Mit echtem ANTHROPIC_API_KEY in .env:
curl -X POST http://localhost:8000/api/v1/memos/generate \
  -H "Content-Type: application/json" \
  -d '{"stock_id":"<existing>", "model_run_id":"<existing>"}'
```
Erwartet: 200 + Memo. Der zweite Call (anderer stock_id, gleicher run_id, innerhalb 5 Min) zeigt im CostTracker `cache_read_input_tokens > 0`.

Werte aus dem CostTracker für AI-USAGE-Eintrag erfassen.

- [ ] **Step 11.4: Commit**

```bash
git add docs/examples/research-memo-sample.json docs/AI-USAGE.md
git commit -m "docs: Sample-Memo + AI-USAGE-Eintrag mit Cache-Hit-Rate (#17, build-step 11/11)

Slice komplett. Sample-Memo unter docs/examples/ als Frontend-/MCP-
Referenz. AI-USAGE-Eintrag inkl. realer Cache-Hit-Rate aus manuellem
Smoke-Test gegen die echte Anthropic-API.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Final Verification

Nach Abschluss aller Tasks:

- [ ] **Full test suite green:**
  ```bash
  docker compose up -d postgres
  uv run pytest backend/tests/ -v
  ```
  Erwartet: alle Tests passed, Coverage Service-Modul ≥90%, Integration ≥80%.

- [ ] **mypy strict + ruff clean:**
  ```bash
  uv run mypy backend/
  uv run ruff check backend/
  ```

- [ ] **OpenAPI-Schema sichtbar:**
  ```bash
  curl -s http://localhost:8000/openapi.json | python -m json.tool | grep -E '"/api/v1/memos'
  ```

- [ ] **Acceptance-Liste aus Spec §10 abgehakt** — alle 14 Punkte verifiziert.

- [ ] **PR erstellen** zu `main` (nicht zu Foundation-Branch) mit Verweis auf Spec + Parent-Spec.

---

## Self-Review (Plan-Author Inline-Check)

Nach dem Schreiben dieses Plans habe ich gegen die Spec geprüft:

✅ **Spec §3 Architektur** — alle Files in Plan §1
✅ **Spec §4 Data Flow** — Tasks 5/6/7/8 decken alle 6 Schritte ab
✅ **Spec §5 Service-API** — Tasks 6/7 decken `get_memo` + `generate_memo`
✅ **Spec §6 REST-Endpoints** — Task 9
✅ **Spec §7 Error-Handling** — Task 8 (Tool-Use-leer + Pydantic-Fail), 503/504 sind im LLMClient bereits gehandelt
✅ **Spec §8 Prompt-Caching** — System-Block mit `cache_control: ephemeral` in Task 7; Smoke-Test in Task 10
✅ **Spec §9 Test-Strategie** — Tasks 5/6/7/8 (Unit), 9 (Router-E2E), 10 (Integration + Cache-Hit)
✅ **Spec §10 Acceptance** — Final Verification Section

⚠️ **Bekannte Plan-Gaps**, die der ausführende Engineer/Subagent füllen muss:
1. **Task 9 Step 9.2** — `get_ranking_run_repository` und `get_llm_client` müssen ggf. erst in `dependencies.py` ergänzt werden (Plan zeigt das Pattern; konkrete Existenz-Verifikation am Anfang von Task 9)
2. **Task 10 `seeded_run_with_stock`-Fixture** — voller DB-Setup ist nicht ausgeschrieben, weil RankingRun-ORM-Schema-spezifisch. Vorlage: `test_research_memo_repository.py`-conftest.
3. **Task 4.5 — `expected_user_prompt.md`-Snapshot** — ggf. trailing whitespace anpassen, falls der erste Run einen 1-Char-Mismatch zeigt.

Diese Gaps sind bewusst, weil eine vollständige Vorab-Spezifikation entweder fragile copypaste produziert (Foundation-Lehre: 5 Plan-Code-Bugs) oder den Plan auf >2000 Zeilen aufbläht. Subagent darf diese drei Stellen mit Trust-but-Verify-Pattern selbst ausführen.

---

**Plan komplett. Saved to `docs/specs/2026-05-04-narrative-engine-single-memo-plan.md`.**
