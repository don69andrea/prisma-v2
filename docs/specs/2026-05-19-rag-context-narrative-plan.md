# Implementation Plan: RAG-Kontext in NarrativeService (#138)

> **Für Agentic Workers:** Checkboxen zum Tracking. Jeden Step nach Completion abhaken.
> **Base-Branch:** `feat/rag-retrieval-18` (enthält `RetrievalService` aus PR #136)
> **Ziel-Branch:** `feat/rag-context-narrative-138`

**Abhängigkeiten:**
- PR #136 muss gemerged sein, bevor dieser Branch auf `main` rebased wird
- `RetrievalService` (`backend/application/services/retrieval_service.py`) muss existieren

**Reality-Check (vor Implementierung):**
- `NarrativeService.__init__` hat `**` — keyword-only, alle Parameter müssen benannt sein
- `_generate_memo_isolated` ist private und kennt `self._retrieval` direkt (kein param nötig)
- Bestehende `_make_service(**overrides)` im Test-File wird durch `retrieval_service=None` Default nicht gebrochen

---

## File Structure

| Datei | Typ | Verantwortung |
|---|---|---|
| `backend/application/services/narrative_service.py` | MODIFY | Import + `__init__` + Step 3a |
| `backend/infrastructure/llm/prompts/narrative_user.en.md.j2` | MODIFY | `{% if rag_context %}` Block |
| `backend/infrastructure/llm/prompts/narrative_user.de.md.j2` | MODIFY | `{% if rag_context %}` Block |
| `backend/interfaces/rest/dependencies.py` | MODIFY | `get_narrative_service` + Depends |
| `backend/tests/unit/application/test_narrative_service.py` | MODIFY | 3 neue RAG-Tests |
| `docs/specs/2026-05-19-rag-context-narrative.md` | CREATE | Design-Spec (dieses Repo) |
| `docs/specs/2026-05-19-rag-context-narrative-plan.md` | CREATE | dieser Plan |

---

## Task 1: NarrativeService erweitern

**Files:** `backend/application/services/narrative_service.py`

- [ ] **Step 1.1: Import RetrievalService**

```python
# Nach dem bestehenden CostTracker-Import:
from backend.application.services.cost_tracker import CostTracker
from backend.application.services.retrieval_service import RetrievalService
```

- [ ] **Step 1.2: `retrieval_service`-Parameter in `__init__`**

Direkt vor `model: str = "claude-sonnet-4-6"` einfügen (keyword-only via `*`):

```python
retrieval_service: RetrievalService | None = None,
model: str = "claude-sonnet-4-6",
```

Und im Body direkt nach dem Docstring (vor `self._memo_repo`):

```python
self._retrieval = retrieval_service
```

- [ ] **Step 1.3: Step 3a in `_generate_memo_isolated`**

Zwischen `universe_context = _build_universe_context(results)` und dem bestehenden Kommentar `# 3. Prompts rendern` einfügen:

```python
# 3a. RAG-Kontext abrufen (optional — graceful degradation wenn nicht konfiguriert)
rag_context = ""
if self._retrieval is not None:
    try:
        chunks = await self._retrieval.retrieve(
            query=f"{stock.ticker} revenue earnings outlook risk factors",
            k=5,
            ticker=stock.ticker,
        )
        rag_context = "\n\n---\n\n".join(c.content for c in chunks)
    except Exception:
        self._logger.warning(
            "RAG retrieval fuer %s fehlgeschlagen — Memo ohne SEC-Kontext",
            stock.ticker,
            exc_info=True,
        )
```

Den bestehenden Kommentar `# 3. Prompts rendern` zu `# 3b. Prompts rendern` umbenennen.

- [ ] **Step 1.4: `rag_context` in den Template-Kontext**

Im `prompt_loader.render(f"narrative_user.{language}.md.j2", {...})` Call die neue Variable ergänzen:

```python
"weights": "equal-weighted (0.20 each)",
"rag_context": rag_context,   # NEU
```

- [ ] **Step 1.5: Ruff + Syntax prüfen**

```bash
ruff check backend/application/services/narrative_service.py
ruff format --check backend/application/services/narrative_service.py
python -c "import ast; ast.parse(open('backend/application/services/narrative_service.py').read()); print('OK')"
```

---

## Task 2: Prompt-Templates erweitern

**Files:** `backend/infrastructure/llm/prompts/narrative_user.en.md.j2`, `narrative_user.de.md.j2`

- [ ] **Step 2.1: EN-Template**

Vor der letzten Zeile `Produce the structured JSON memo...` einfügen:

```jinja2
{% if rag_context %}
SEC FILING EXCERPTS (10-K / 10-Q — use as factual grounding, do not copy verbatim)
{{ rag_context }}

{% endif %}
```

- [ ] **Step 2.2: DE-Template**

Analog:

```jinja2
{% if rag_context %}
SEC-FILING-AUSZUEGE (10-K / 10-Q — als faktische Grundlage verwenden, nicht wortwoertlich kopieren)
{{ rag_context }}

{% endif %}
```

---

## Task 3: DI-Kette verdrahten

**Files:** `backend/interfaces/rest/dependencies.py`

- [ ] **Step 3.1: `retrieval` als Depends in `get_narrative_service`**

In der Funktionssignatur nach `cost_tracker`:

```python
retrieval: RetrievalService = Depends(get_retrieval_service),
```

Im `NarrativeService(...)`-Konstruktor-Aufruf:

```python
retrieval_service=retrieval,
```

`RetrievalService` ist bereits auf Zeile 17 importiert — kein neuer Import nötig.

- [ ] **Step 3.2: Ruff prüfen**

```bash
ruff check backend/interfaces/rest/dependencies.py
```

---

## Task 4: Unit-Tests

**Files:** `backend/tests/unit/application/test_narrative_service.py`

Drei neue Tests am Ende der Datei anhängen:

- [ ] **Step 4.1: `test_rag_chunks_appear_in_rendered_prompt`**

Setup: Mock-`retrieval_service` gibt 1 Chunk zurück. Capturing-`render`-Funktion speichert den Template-Kontext in `captured_ctx`.

Assertions:
- `retrieval_mock.retrieve.assert_awaited_once()`
- `call_kwargs["ticker"] == stock.ticker`
- `call_kwargs["k"] == 5`
- `chunk_content in captured_ctx["rag_context"]`

- [ ] **Step 4.2: `test_generate_memo_without_retrieval_service_works`**

Setup: `retrieval_service=None` in `_make_service`.

Assertions:
- `result is persisted` (Memo generiert)
- `captured_ctx.get("rag_context") == ""`

- [ ] **Step 4.3: `test_rag_failure_does_not_block_memo_generation`**

Setup: `retrieval_service` mit `retrieve = AsyncMock(side_effect=RuntimeError("Voyage API down"))`.

Assertions:
- `result is persisted` (trotz Exception)
- `llm.messages_create.assert_awaited_once()` (LLM wurde aufgerufen)

- [ ] **Step 4.4: Ruff prüfen**

```bash
ruff check backend/tests/unit/application/test_narrative_service.py
```

---

## Task 5: Spec + Plan committen

**Files:** `docs/specs/2026-05-19-rag-context-narrative.md`, `docs/specs/2026-05-19-rag-context-narrative-plan.md`

- [ ] **Step 5.1: Beide Spec-Dateien erstellen** (dieses Dokument)

- [ ] **Step 5.2: Commit**

```bash
git add \
  backend/application/services/narrative_service.py \
  backend/infrastructure/llm/prompts/narrative_user.en.md.j2 \
  backend/infrastructure/llm/prompts/narrative_user.de.md.j2 \
  backend/interfaces/rest/dependencies.py \
  backend/tests/unit/application/test_narrative_service.py \
  docs/specs/2026-05-19-rag-context-narrative.md \
  docs/specs/2026-05-19-rag-context-narrative-plan.md

git commit -m "feat(ai): RAG-Kontext in NarrativeService integrieren (#138)"
git push -u origin feat/rag-context-narrative-138
```

---

## Task 6: PR erstellen

- [ ] **Step 6.1: PR gegen `feat/rag-retrieval-18` öffnen**

Base: `feat/rag-retrieval-18` (nicht `main` — wegen `RetrievalService`-Dependency).

Nach Merge von PR #136 auf `main`: `git rebase origin/main` und PR-Base auf `main` ändern.

- [ ] **Step 6.2: CI abwarten**

Erwartetes Ergebnis:
- Ruff check ✅
- Mypy ✅
- Backend Unit Tests ✅ (inkl. 3 neue RAG-Tests)
- Backend Integration Tests ✅ (unverändert)

---

## Task 7: AI-USAGE.md aktualisieren

- [ ] **Step 7.1: Eintrag für PR #139 einfügen**

Format:

```markdown
## 2026-05-19 · RAG-Kontext in NarrativeService (#138, PR #139)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: ...
- **Was gut lief**: ...
- **Was nicht klappte**: Spec vergessen → PR-Freigabe blockiert. Lesson: Spec-First ist nicht optional.
- **Lektion**: ...
- **Autor**: Andrea Petretta (mit Claude Code)
```
