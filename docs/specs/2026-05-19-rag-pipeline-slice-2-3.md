# Spec: RAG-Pipeline Slice 2+3 — Ingestion + Retrieval-Endpoint

**Status:** Draft v1.0 — 2026-05-19
**Issue:** #18 (Slice 2 + Slice 3)
**Rolle:** B — AI Engineer (Andrea)
**Parent-ADR:** `docs/adr/0004-multi-agent-framework-and-ops.md` §3 + §4 + §7
**Parent-Spec:** `docs/specs/2026-05-11-rag-pipeline-slice-1-foundation.md`
**Vorgänger-Slice:** PR #96 — pgvector-Foundation (Migration, Entities, Repository-Port + Adapter, Tests)

---

## 1. Zweck & Slice-Position

Slice 1 (PR #96) hat die Persistence-Schicht etabliert: pgvector-Extension, `documents`- und `embedding_chunks`-Tabellen, `EmbeddingRepository`-Port und `SQLAEmbeddingRepository`-Adapter.

Slice 2 + 3 schliessen Issue #18 vollständig ab:

- **Slice 2** — SEC-EDGAR-Ingestion: 5 Ticker × (1× 10-K + 1× 10-Q) via EDGAR-API downloaden, als Text extrahieren, in ~800-Token-Chunks aufteilen, Voyage-Embeddings generieren, in pgvector upserten (`scripts/ingest_filings.py`).
- **Slice 3** — Retrieval-Service: `find_nearest(query_embedding, k, ticker?)` im Repository-Port + SQLA-Adapter, `RetrievalService` im Application-Layer, `POST /api/v1/rag/retrieve` REST-Endpoint.

**Demo-Wert nach Slice 2+3:**
- RAG-Corpus mit ~4 000 SEC-Filing-Chunks in der Produktions-DB
- Semantische Suche via `POST /api/v1/rag/retrieve?query=...&k=5&ticker=AAPL`
- Vollständige Cost-Tracking-Integration für Voyage-Embedding-Calls

---

## 2. Bewusste Abweichungen von Slice 1 / ADR-0004

| ADR/Spec sagt | Slice-2+3-Verhalten | Begründung |
|---|---|---|
| Ingestion als CLI-Command | Einmaliges Script via `python scripts/ingest_filings.py` | Kein Cronjob nötig — Corpus ändert sich selten; Re-Ingestion ist idempotent |
| Voyage `voyage-3-large` | ✅ verwendet | ADR-0004 §4 |
| ~800 Token / Chunk, 100 Token Overlap | 3 200 Chars / 400 Chars (~4 chars/token) | Gute Balance Text-Kontext vs. Chunk-Anzahl |
| ~4 000 Chunks total | 5 Ticker × 2 Filings × ~400 Chunks = ~4 000 | Schätzung, tatsächliche Anzahl variiert je nach Filing-Länge |
| HNSW-Index via halfvec-Cast | ✅ beide Seiten der `<=>` Operation auf `halfvec(2048)` gecastet | pgvector limitiert `vector`-Typ-Index auf 2 000 dim; HNSW braucht halfvec für 2 048 dim |

---

## 3. Architektur

### Dateistruktur

```
scripts/
└── ingest_filings.py                               NEU — Einmaliges Ingestion-Script

backend/domain/repositories/
└── embedding_repository.py                         ERWEITERT — find_nearest() + RetrievalResult

backend/infrastructure/persistence/repositories/
└── embedding_repository.py                         ERWEITERT — find_nearest() Adapter (Raw-SQL)

backend/application/services/
└── retrieval_service.py                            NEU — RetrievalService

backend/interfaces/rest/
├── routers/rag.py                                  NEU — POST /api/v1/rag/retrieve
├── schemas/rag.py                                  NEU — RetrieveRequest / ChunkResponse / RetrieveResponse
├── app.py                                          ERWEITERT — rag-Router registrieren
└── dependencies.py                                 ERWEITERT — get_embedding_repository / get_voyage_client / get_retrieval_service

backend/config.py                                   ERWEITERT — voyage_api_key

backend/tests/unit/application/
└── test_retrieval_service.py                       NEU — 6 Unit-Tests

backend/tests/integration/
└── test_rag_endpoint.py                            NEU — 9 Integrationstests

README.md                                           ERWEITERT — RAG-Ingestion-Sektion
docs/AI-USAGE.md                                    ERWEITERT — Eintrag PR #136
```

### Komponenten-Verantwortung

| Komponente | Verantwortung | Tests |
|---|---|---|
| `ingest_filings.py` | EDGAR-API → Download → Text-Extraktion → Chunking → Voyage-Embedding → pgvector-UPSERT. Idempotent via URL-Check. | — (einmaliges Script) |
| `RetrievalResult` (Domain) | Frozen Dataclass: `chunk_id`, `document_id`, `chunk_idx`, `content`, `similarity`, `ticker`, `doc_type`, `metadata` | — |
| `EmbeddingRepository.find_nearest()` (Port) | Abstract: Cosine-Similarity-Suche, optional Ticker-Filter, sortiert nach Similarity DESC | Integration (existierendes Test-Setup) |
| `SQLAEmbeddingRepository.find_nearest()` (Adapter) | Raw-SQL mit `halfvec(2048)`-Cast für HNSW-Index-Nutzung | Integration |
| `RetrievalService` | Bettet Query via `LLMClient.embed()` ein, ruft `find_nearest()` auf, capped auf `MAX_K=20` | Unit (6 Tests) |
| `POST /api/v1/rag/retrieve` | Pydantic-Validierung (`k` 1–20, `query` 1–2000 Chars), delegiert an `RetrievalService` | Integration (9 Tests) |

---

## 4. Ingestion-Script (`scripts/ingest_filings.py`)

### SEC-EDGAR-API-Flow

```
1. GET https://data.sec.gov/submissions/CIK{cik}.json
   → Liste aller Filings mit form, filingDate, accessionNumber

2. Neueste 10-K + 10-Q pro Ticker herausfiltern (count=2)

3. GET https://data.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession}-index.json
   → Haupt-Text-Dokument-URL (HTM/HTML bevorzugt, TXT als Fallback)

4. GET {filing_url} → HTML/Text-Content

5. HTML → Plaintext (stdlib html.parser, kein beautifulsoup)
   → _extract_text_from_html()

6. Text → Chunks (_chunk_text, 3200 Chars / 400 Chars Overlap, min 50 Chars)

7. Chunks → Voyage-Embeddings in Batches von 8 (voyage-3-large)

8. UPSERT: Document + EmbeddingChunks via SQLAEmbeddingRepository
```

### Idempotenz

- `repo.get_document_by_url(filing_url)` vor Download — falls existiert: skip
- `save_chunks` nutzt `ON CONFLICT DO UPDATE` (UPSERT per `(document_id, chunk_idx)`)
- `save_document` wirft `DuplicateUrl` bei Race — logged + skipped

### CIK-Map (hardcoded)

```python
_CIK_MAP = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "NVDA": "0001045810",
    "JPM":  "0000019617",
}
```

---

## 5. Repository-Port-Erweiterung

### `RetrievalResult` (Domain Dataclass)

```python
@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: UUID
    document_id: UUID
    chunk_idx: int
    content: str
    similarity: float       # Cosine-Similarity, 1=identisch, 0=unverwandt
    ticker: str
    doc_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

### `EmbeddingRepository.find_nearest()` (Abstract)

```python
@abstractmethod
async def find_nearest(
    self,
    query_embedding: list[float],
    k: int,
    ticker: str | None = None,
) -> list[RetrievalResult]:
    """Cosine-Similarity-Suche via HNSW-Index.
    Sortiert absteigend nach Similarity (höchste zuerst)."""
```

### `SQLAEmbeddingRepository.find_nearest()` (Adapter, Raw-SQL)

Die HNSW-Index-Nutzung erfordert **beiden** Seiten des `<=>` Operators als `halfvec(2048)`:

```sql
SELECT ec.id AS chunk_id, ec.document_id, ec.chunk_idx, ec.content, ec.metadata,
       d.ticker, d.doc_type,
       1 - ((ec.embedding::halfvec(2048)) <=> (:query::vector(2048)::halfvec(2048))) AS similarity
FROM embedding_chunks ec
JOIN documents d ON d.id = ec.document_id
WHERE 1=1 {ticker_filter}
ORDER BY (ec.embedding::halfvec(2048)) <=> (:query::vector(2048)::halfvec(2048))
LIMIT :k
```

---

## 6. Application-Layer: `RetrievalService`

```python
class RetrievalService:
    def __init__(self, embedding_repo: EmbeddingRepository, llm_client: LLMClient) -> None: ...

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        ticker: str | None = None,
    ) -> list[RetrievalResult]:
        k = min(k, _MAX_K)   # max 20
        embeddings = await self._llm.embed(
            texts=[query], model="voyage-3-large", feature="rag_retrieval"
        )
        return await self._repo.find_nearest(
            query_embedding=embeddings[0], k=k, ticker=ticker
        )
```

**`feature="rag_retrieval"`** ist required — `LLMClient.embed()` hat keinen Default. Vergessen → `TypeError` zur Laufzeit (A8-Anti-Pattern aus AI-USAGE.md).

---

## 7. REST-Endpoint

### Request

```
POST /api/v1/rag/retrieve
Content-Type: application/json

{
  "query": "Apple revenue growth 2024",   // 1–2000 Zeichen
  "k": 5,                                  // 1–20, default 5
  "ticker": "AAPL"                         // optional
}
```

### Response

```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "chunk_idx": 0,
      "content": "Apple reported net sales of $391.0 billion...",
      "similarity": 0.924,
      "ticker": "AAPL",
      "doc_type": "10-K"
    }
  ],
  "total": 1
}
```

### DI-Kette

```
get_embedding_repository()   → SQLAEmbeddingRepository(session_factory)
get_voyage_client()          → voyageai.Client(api_key) | None
get_retrieval_service()      → RetrievalService(embedding_repo, LLMClient(voyage=voyage))
```

`voyage_api_key` in `Settings` (Pydantic-Settings, aus `VOYAGE_API_KEY` ENV). Wenn leer → `get_voyage_client()` gibt `None` → Voyage-Call wirft `RuntimeError` → 500 (kein graceful fallback im Endpoint selbst, da RAG ohne Voyage nicht sinnvoll ist).

---

## 8. Settings-Erweiterung

```python
class Settings(BaseSettings):
    voyage_api_key: str = ""   # NEU — aus VOYAGE_API_KEY ENV
```

Kein Production-Validator (anders als `api_key`) — RAG ist optional, Backend bootet auch ohne Voyage.

---

## 9. Kosten (ADR-0004 §7)

| Schritt | Modell | Schätzung |
|---|---|---|
| Ingestion (einmalig) | voyage-3-large | ~$0.24 für ~4 000 Chunks |
| Retrieval pro Query | voyage-3-large | < $0.001 (1 Query-Embedding) |

---

## 10. Definition of Done (Issue #18 vollständig)

- [x] `scripts/ingest_filings.py` lauffähig, idempotent
- [x] `find_nearest()` im Repository-Port + SQLA-Adapter implementiert
- [x] `RetrievalService` mit `feature="rag_retrieval"` im embed()-Call
- [x] `POST /api/v1/rag/retrieve` mit Pydantic-Validierung (`k` 1–20)
- [x] DI-Kette: `get_embedding_repository`, `get_voyage_client`, `get_retrieval_service`
- [x] `voyage_api_key` in `Settings`
- [x] 6 Unit-Tests für `RetrievalService`
- [x] 9 Integrationstests für den RAG-Endpoint
- [x] README-Sektion: RAG-Ingestion auf Render Shell-Tab triggern
- [x] CI grün (Ruff + Mypy + Unit + Integration)
- [ ] Ingestion einmalig auf Render ausgeführt (4 000+ Chunks in DB) — Post-Merge-Schritt

---

## 11. Risiken & Mitigation

| # | Risiko | Mitigation |
|---|---|---|
| R1 | EDGAR-Rate-Limit (10 req/s) | `asyncio.sleep(0.5)` nach jedem Filing-Download |
| R2 | HNSW-Index ohne halfvec-Cast nicht genutzt | Raw-SQL mit explizitem `halfvec(2048)`-Cast auf beiden Seiten |
| R3 | `voyageai.Client` nicht im `__all__` von voyageai | `# type: ignore[attr-defined]` in dependencies.py (mypy A8) |
| R4 | Ingestion hängt bei grossem Filing | `httpx.AsyncClient(timeout=60.0)` — 1-Min-Timeout pro Request |
