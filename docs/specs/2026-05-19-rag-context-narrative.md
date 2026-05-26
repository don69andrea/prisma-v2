# Spec: RAG-Kontext in NarrativeService — SEC-Filing-Chunks in Memo-Prompts

**Status:** Draft v1.0 — 2026-05-19
**Issue:** #138
**Rolle:** B — AI Engineer (Andrea)
**Parent-ADR:** `docs/adr/0004-multi-agent-framework-and-ops.md` §3 (RAG als Retrieval-Layer)
**Parent-Spec:** `docs/specs/2026-05-11-rag-pipeline-slice-1-foundation.md` (pgvector-Foundation)
**Vorgänger-Slice:** PR #136 — `RetrievalService` + `POST /api/v1/rag/retrieve` (feat/rag-retrieval-18)

---

## 1. Zweck

Der `NarrativeService` generiert Research-Memos heute ausschliesslich aus Quant-Daten (Ranking-Scores, Modell-Ränge). Mit diesem Slice werden **SEC-Filing-Auszüge** (10-K / 10-Q) aus dem pgvector-Corpus als faktueller Kontext in den User-Prompt eingebettet — bevor der LLM-Call stattfindet.

**Erwarteter Nutzen:** Memos können konkrete Zahlen / Aussagen aus echten Filings referenzieren statt generischer Qualitäts-Statements formulieren. Der Quant-Kontext bleibt primär; der RAG-Kontext ist additiv.

**Dieses Slice setzt voraus:** PR #136 ist gemerged und `VOYAGE_API_KEY` ist in Production gesetzt (sonst kein RAG-Kontext, kein Feature-Ausfall).

---

## 2. Scope

### In Scope

- `NarrativeService.__init__`: optionaler Parameter `retrieval_service: RetrievalService | None = None`
- `_generate_memo_isolated`: neuer Step 3a — 5 Chunks per Ticker via `RetrievalService.retrieve(ticker=..., k=5)` abrufen
- Graceful Degradation: bei Exception im Retrieval → Warning-Log, `rag_context=""`, Memo wird trotzdem generiert
- `narrative_user.{en,de}.md.j2`: optionaler `{% if rag_context %}` Block (Jinja2-Guard)
- `dependencies.get_narrative_service`: `RetrievalService` per `Depends(get_retrieval_service)` injiziert
- 3 neue Unit-Tests (Chunks im Prompt, ohne RAG backward-compat, RAG-Fehler blockiert nicht)

### Out of Scope (Folge-PRs)

- Caching des RAG-Kontexts pro Ticker (heute: ein neuer Voyage-Call pro Memo)
- Konfigurierbare Chunk-Anzahl via Settings
- RAG-Kontext im Batch-Pfad separat testen (deckt der Batch-Test implizit ab)
- Integrationstest mit echter pgvector-DB (Unit-Tests mit Mocks ausreichend für diesen Slice)

---

## 3. Architektur

### Dateistruktur

```
backend/application/services/
└── narrative_service.py                            MODIFY — __init__ + _generate_memo_isolated

backend/infrastructure/llm/prompts/
├── narrative_user.en.md.j2                         MODIFY — {% if rag_context %} Block
└── narrative_user.de.md.j2                         MODIFY — {% if rag_context %} Block

backend/interfaces/rest/
└── dependencies.py                                 MODIFY — get_narrative_service + Depends(get_retrieval_service)

backend/tests/unit/application/
└── test_narrative_service.py                       MODIFY — 3 neue RAG-Tests

docs/specs/
├── 2026-05-19-rag-context-narrative.md             NEU (dieses Dokument)
└── 2026-05-19-rag-context-narrative-plan.md        NEU (Implementierungsplan)
```

### Komponenten-Verantwortung

| Komponente | Verantwortung | Tests |
|---|---|---|
| `NarrativeService` (erweitert) | RAG-Kontext abrufen, in Prompt einbetten, Fehler abfangen | Unit |
| `RetrievalService` (unverändert) | Voyage-Embedding + pgvector-Suche | bereits getestet in PR #136 |
| Jinja2-Templates (erweitert) | `{% if rag_context %}` Block — leer wenn kein RAG konfiguriert | implizit via Prompt-Render-Test |
| `get_narrative_service` (erweitert) | `RetrievalService` per DI injizieren | — |

---

## 4. Data Flow (erweitert)

```
POST /api/v1/memos/generate { stock_id, model_run_id }
  │
  ▼
NarrativeService._generate_memo_isolated(...)
  │
  ├─ 1. Cache-Check
  ├─ 2. Stock + RankingRun laden
  │
  ├─ 3a. RAG-Kontext (NEU)
  │       if self._retrieval is not None:
  │         chunks = await self._retrieval.retrieve(
  │             query=f"{ticker} revenue earnings outlook risk factors",
  │             k=5,
  │             ticker=ticker,
  │         )
  │         rag_context = "\n\n---\n\n".join(c.content for c in chunks)
  │       else:
  │         rag_context = ""
  │       (Exception → warning log, rag_context = "")
  │
  ├─ 3b. Prompts rendern  [bisher Schritt 3]
  │       user_prompt = prompt_loader.render(
  │         "narrative_user.{lang}.md.j2",
  │         { ..., "rag_context": rag_context }   ← NEU
  │       )
  │
  ├─ 4. LLM-Call (unverändert)
  ├─ 5. Schema-Validierung (unverändert)
  └─ 6. Persistieren (unverändert)
```

### Prompt-Template-Erweiterung

**narrative_user.en.md.j2** (analog DE):

```jinja2
{% if rag_context %}
SEC FILING EXCERPTS (10-K / 10-Q — use as factual grounding, do not copy verbatim)
{{ rag_context }}

{% endif %}
Produce the structured JSON memo via the `submit_memo` tool per system instructions.
```

Der Guard `{% if rag_context %}` stellt sicher, dass ohne `VOYAGE_API_KEY` oder bei leerem Corpus exakt der bisherige Prompt entsteht — keine Regressions-Gefahr.

---

## 5. Interface-Änderungen

### `NarrativeService.__init__` (MODIFY)

```python
class NarrativeService:
    def __init__(
        self,
        *,
        # ... bestehende Parameter ...
        retrieval_service: RetrievalService | None = None,  # NEU — optional, default None
        model: str = "claude-sonnet-4-6",
        # ...
    ) -> None:
        self._retrieval = retrieval_service
```

**Backward-Kompatibilität:** `retrieval_service=None` (default) → `rag_context=""` → Jinja-Guard deaktiviert Block → identischer Prompt wie heute. Keine bestehenden Tests brechen.

### `get_narrative_service` (MODIFY)

```python
async def get_narrative_service(
    ...
    retrieval: RetrievalService = Depends(get_retrieval_service),  # NEU
    ...
) -> NarrativeService:
    return NarrativeService(
        ...
        retrieval_service=retrieval,  # NEU
    )
```

`get_retrieval_service` gibt bereits `None` zurück wenn `VOYAGE_API_KEY` nicht gesetzt — kein zusätzlicher Guard nötig.

---

## 6. Fehlerbehandlung

| Szenario | Verhalten |
|---|---|
| `VOYAGE_API_KEY` nicht gesetzt | `get_voyage_client()` → `None`, `RetrievalService` wirft `RuntimeError` beim `embed()`-Call → Exception-Handler in 3a → `rag_context=""` → Memo ohne RAG |
| Voyage-API down | `RuntimeError` → Warning-Log → `rag_context=""` → Memo ohne RAG |
| pgvector-Query schlägt fehl | Exception → Warning-Log → `rag_context=""` → Memo ohne RAG |
| Corpus leer (0 Chunks für Ticker) | `retrieve()` → `[]` → `rag_context=""` → `{% if rag_context %}` deaktiviert → normaler Prompt |
| RAG liefert Chunks | Chunks als Text eingebettet, LLM sieht factual grounding |

---

## 7. Kosten

Zusätzliche Voyage-Kosten pro Memo: 1 Embedding-Call für die Query-Text.
Bei `voyage-3-large` und ~50 Zeichen Query: < $0.001 pro Memo.

Kein Voyage-Call wenn:
- `VOYAGE_API_KEY` nicht gesetzt
- `RetrievalService` wirft Exception
- Corpus leer

---

## 8. Definition of Done

- [ ] `NarrativeService` akzeptiert optionalen `retrieval_service`
- [ ] `_generate_memo_isolated` ruft Chunks ab und bettet sie in den Prompt ein
- [ ] Graceful Degradation: Exception im Retrieval → Memo trotzdem generiert
- [ ] `{% if rag_context %}` Guard in beiden Templates (EN + DE)
- [ ] `get_narrative_service` injiziert `RetrievalService`
- [ ] 3 Unit-Tests: Chunks im Prompt, backward-compat ohne RAG, RAG-Fehler blockiert nicht
- [ ] Spec + Plan in `docs/specs/`
- [ ] CI grün (Ruff + Mypy + Unit + Integration)
- [ ] AI-USAGE.md-Eintrag

---

## 9. Offene Fragen / Risiken

| # | Frage | Entscheidung |
|---|---|---|
| R1 | Token-Overhead: 5 Chunks à ~800 Tokens = ~4000 zusätzliche Input-Tokens pro Memo. Kosten steigen ca. $0.012 pro Memo (claude-sonnet-4-6). | Akzeptiert — klein gegen Memo-Qualitätsgewinn |
| R2 | Reihenfolge der Chunks: `find_nearest` sortiert nach Cosine-Similarity DESC. Keine weitere Filterung. | Akzeptiert — einfachste sinnvolle Sortierung |
| R3 | Query-Text ist generisch (`"{ticker} revenue earnings outlook risk factors"`). Besser wäre ein spezifischer Query pro Memo-Typ. | Follow-up-Issue wenn Bedarf erkannt wird |
