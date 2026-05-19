# Plan: RAG-Pipeline Slice 2+3 — Implementierungsplan

**Datum:** 2026-05-19
**Branch:** `feat/rag-retrieval-18`
**Spec:** `docs/specs/2026-05-19-rag-pipeline-slice-2-3.md`
**Issue:** #18

---

## Implementierungsschritte

- [x] **Task 1 — Domain: `RetrievalResult` Dataclass**
  - `backend/domain/repositories/embedding_repository.py` erweitern
  - `RetrievalResult` frozen Dataclass hinzufügen: `chunk_id`, `document_id`, `chunk_idx`, `content`, `similarity`, `ticker`, `doc_type`, `metadata`
  - `find_nearest()` Abstract-Method im `EmbeddingRepository`-Port hinzufügen

- [x] **Task 2 — Adapter: `SQLAEmbeddingRepository.find_nearest()`**
  - `backend/infrastructure/persistence/repositories/embedding_repository.py` erweitern
  - Raw-SQL mit `halfvec(2048)`-Cast auf beiden Seiten des `<=>` Operators
  - Optionaler Ticker-Filter via `WHERE`-Klausel
  - `params: dict[str, object]` für Mypy-Kompatibilität

- [x] **Task 3 — Application: `RetrievalService`**
  - `backend/application/services/retrieval_service.py` neu anlegen
  - `retrieve(query, k, ticker?)` — embed via `LLMClient.embed(texts=[query], model="voyage-3-large", feature="rag_retrieval")`
  - `k = min(k, _MAX_K)` — cap auf 20
  - `_MAX_K = 20` als Modul-Konstante (für Tests importierbar)

- [x] **Task 4 — REST: Schemas + Router**
  - `backend/interfaces/rest/schemas/rag.py` anlegen: `RetrieveRequest`, `ChunkResponse`, `RetrieveResponse`
  - `backend/interfaces/rest/routers/rag.py` anlegen: `POST /api/v1/rag/retrieve`
  - Pydantic-Validierung: `query` 1–2000 Chars, `k` 1–20 (default 5), `ticker` optional
  - `backend/interfaces/rest/app.py` erweitern: rag-Router registrieren

- [x] **Task 5 — DI-Kette + Settings**
  - `backend/config.py`: `voyage_api_key: str = ""` in `Settings`
  - `backend/interfaces/rest/dependencies.py`:
    - `get_embedding_repository()` — `SQLAEmbeddingRepository(session_factory=...)`
    - `get_voyage_client()` — `voyageai.Client(api_key)` oder `None`
    - `get_retrieval_service()` — `RetrievalService(embedding_repo, LLMClient(voyage=voyage, ...))`
  - `# type: ignore[attr-defined]` für `voyageai.Client` (nicht in `__all__`)

- [x] **Task 6 — Unit-Tests: `RetrievalService` (6 Tests)**
  - `backend/tests/unit/application/test_retrieval_service.py` anlegen
  - `pytestmark = pytest.mark.unit`
  - Tests: `test_calls_embed_with_query_text`, `test_calls_find_nearest_with_embedding`, `test_passes_ticker_filter`, `test_clamps_k_to_max`, `test_returns_results_from_repo`, `test_default_k_is_five`
  - Imports alphabetisch sortiert (Ruff I001): `_MAX_K` vor `RetrievalService`

- [x] **Task 7 — Integrationstests: RAG-Endpoint (9 Tests)**
  - `backend/tests/integration/test_rag_endpoint.py` anlegen
  - Tests: 200-Response, Response-Shape, Felder vorhanden, total-Invariante, k-Passthrough, Ticker-Passthrough, leere Query 422, k>20 422, k=0 422
  - `app.dependency_overrides[get_retrieval_service]` für Test-Isolation

- [x] **Task 8 — Ingestion-Script**
  - `scripts/ingest_filings.py` anlegen
  - EDGAR-API-Flow: Submissions → Filing-Index → HTML-Download → Text-Extraktion → Chunking → Voyage-Embeddings → pgvector-UPSERT
  - Idempotenz via `get_document_by_url()` + `ON CONFLICT DO UPDATE`
  - CIK-Map: AAPL, MSFT, GOOGL, NVDA, JPM
  - 3 200 Chars / 400 Chars Overlap, Batches à 8 für Voyage-Calls
  - `asyncio.sleep(0.5)` nach jedem Filing (EDGAR Rate-Limit)
  - `httpx.AsyncClient(timeout=60.0)` — 1-Min-Timeout

- [x] **Task 9 — CI + Linting**
  - Ruff: Import-Sortierung prüfen (I001)
  - Mypy: `dict[str, object]` für SQL-Params, `type: ignore[attr-defined]` für Voyage
  - Alle bestehenden Tests müssen grün bleiben

- [ ] **Task 10 — Post-Merge (Render)**
  - `VOYAGE_API_KEY` in Render ENV gesetzt prüfen
  - Ingestion via Render Shell-Tab: `python scripts/ingest_filings.py`
  - Erwartetes Ergebnis: ~4 000 Chunks in DB
