# Spec: RAG-Pipeline Slice 1 — Foundation (pgvector + Persistence)

**Status:** Draft v1.0 — 2026-05-11
**Issue:** #18 (Slice 1 von ~3)
**Rolle:** B — AI Engineer (Sheyla)
**Parent-ADR:** `docs/adr/0004-multi-agent-framework-and-ops.md` §3 + §4
**Parent-Master-Spec:** `docs/specs/2026-04-28-multi-agent-research.md` (RAG-Vorbedingung fuer Layer-2-Deep-Dive)

---

## 1. Zweck & Slice-Position

Slice 1 etabliert die **RAG-Persistence-Schicht** end-to-end: pgvector-Extension,
Migration, Domain-Entities, Repository (Port + Adapter), Unit + Integration-Tests.

**Was Slice 1 NICHT macht:**
- KEIN Ingestion-Script (SEC-EDGAR-Download, PDF-Parsing, Chunking) → Slice 2
- KEIN Retrieval-Service / REST-Endpoint → Slice 3
- KEINE Voyage-Embedding-Calls in dieser Slice (`LLMClient.embed` ist bereits da, wird in Slice 2 erst genutzt)
- KEINE realen $0.24 Voyage-Kosten

**Demo-Wert nach Slice 1:**
- pgvector-Extension auf Render aktiv (verifiziert)
- Schema fuer Documents + Chunks + 2048-dim Embeddings vorhanden
- Repository-Roundtrip getestet
- Foundation fuer alle weiteren RAG-Arbeiten gelegt

**Slicing-Rationale:** Spiegelt MCP-Server-Slice-1-Playbook — thinnest end-to-end,
keine externen APIs in Slice 1. Risk-frei deploybar; sobald pgvector auf Render
laeuft, ist die teuerste Unbekannte (Extension-Verfuegbarkeit) eliminiert.

## 2. Bewusste Abweichungen vom Issue #18

| Issue #18 sagt | Slice-Verhalten | Begruendung |
|---|---|---|
| pgvector-Extension aktivieren | ✅ in Slice 1 | Kernziel der Foundation |
| Ingestion-Script `scripts/ingest_filings.py` | ⏭ Slice 2 | Externe API (SEC-EDGAR) + PDF-Parsing — eigene Risiko-Domaene |
| Retrieval-Service Top-K-Nearest | ⏭ Slice 3 | braucht Query-Embedding via Voyage — separates Auth + Cost-Risk |
| REST-Endpoint `POST /api/v1/rag/retrieve` | ⏭ Slice 3 | depends auf Retrieval-Service |
| 4000+ Chunks in DB | ⏭ Slice 2 | Acceptance-Kriterium von Slice 2 |
| README-Sektion Ingest-Trigger | ⏭ Slice 2 | depends auf Ingestion-Script |

## 3. Architektur

```
backend/alembic/versions/
└── 0008_enable_pgvector_and_create_embeddings.py     (NEU)
    - CREATE EXTENSION IF NOT EXISTS vector
    - documents-Tabelle
    - embedding_chunks-Tabelle mit vector(2048)
    - Index auf embedding_chunks.embedding (HNSW mit halfvec-Cast, weil pgvector den `vector`-Typ auf 2000 dim fuer Indexierung limitiert, wir aber 2048 dim brauchen)

backend/domain/entities/
├── document.py                                       (NEU)
│   └── Document (id, ticker, doc_type, filing_date, url, raw_text_hash, ingested_at)
└── embedding_chunk.py                                (NEU)
    └── EmbeddingChunk (id, document_id, chunk_idx, content, embedding, metadata)

backend/domain/repositories/
└── embedding_repository.py                           (NEU — Port)
    └── EmbeddingRepository (Abstract): save_document, save_chunks, get_document_by_url, count_chunks, list_documents

backend/infrastructure/persistence/
├── models/embedding_models.py                        (NEU — SQLAlchemy-ORM)
│   ├── DocumentRow
│   └── EmbeddingChunkRow (mit pgvector-Type)
└── repositories/embedding_repository.py              (NEU — SQLA-Adapter)
    └── SQLAEmbeddingRepository

backend/tests/unit/domain/entities/
├── test_document.py                                  (NEU)
└── test_embedding_chunk.py                           (NEU)

backend/tests/integration/persistence/
└── test_embedding_repository.py                      (NEU)
    - test_save_and_get_document
    - test_save_chunks_batch
    - test_unique_constraint_on_document_url
    - test_count_chunks_per_document
    - test_list_documents

pyproject.toml                                        (MODIFIZIERT)
└── + "pgvector>=0.3"   (SQLAlchemy-Type-Support fuer vector-Spalten)
```

```
Slice 1 ist rein backend/persistence:

Application-Service → EmbeddingRepository (Port)
                              ↓
                      SQLAEmbeddingRepository (Adapter)
                              ↓
                      PostgreSQL + pgvector
```

Slice 2 wird `IngestionService` in `backend/application/services/` adden, der den
Port nutzt. Slice 3 added `RetrievalService` + REST.

## 4. Datenmodell

### 4.1 `documents`-Tabelle

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | UUID | PK |
| `ticker` | varchar(10) | NOT NULL, index |
| `doc_type` | varchar(8) | NOT NULL — `10-K` oder `10-Q` (Slice 1 ist generisch) |
| `filing_date` | date | NOT NULL |
| `url` | text | NOT NULL, UNIQUE |
| `raw_text_hash` | varchar(64) | NULLABLE — SHA-256 des extrahierten Texts (kommt mit Slice 2) |
| `ingested_at` | timestamp WITH TIME ZONE | NOT NULL, default NOW() |

### 4.2 `embedding_chunks`-Tabelle

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | UUID | PK |
| `document_id` | UUID | FK → documents.id ON DELETE CASCADE |
| `chunk_idx` | integer | NOT NULL — fortlaufender Index in Doc |
| `content` | text | NOT NULL — der Chunk-Text |
| `embedding` | vector(2048) | NOT NULL — Voyage-3-large-Dimension |
| `metadata` | jsonb | NULLABLE — z.B. `{"section": "Risk Factors", "page": 12}` |

**Indizes:**
- `(document_id, chunk_idx)` UNIQUE — keine Duplikate
- HNSW-Index auf `(embedding::halfvec(2048))` mit `halfvec_cosine_ops` (cosine-Distanz, ADR-0004 implizit)
  - Halfvec-Cast noetig, weil pgvector-Index-Limit fuer `vector` 2000 dim ist; `halfvec` erlaubt bis 4000 dim. Application-Column bleibt `vector(2048)` (volle Praezision), Index nutzt 16-bit-Floats. Recall-Verlust durch Half-Precision-Quantisierung ist marginal (~0.1% laut pgvector-Benchmarks) und industry-standard fuer Embeddings >1024 dim.
  - HNSW-Parameter: `m=16`, `ef_construction=64` (pgvector-Defaults, passen fuer 4000-100k Chunks ohne Tuning).

### 4.3 Domain-Entities

```python
# backend/domain/entities/document.py
@dataclass(frozen=True)
class Document:
    id: UUID
    ticker: str           # 'AAPL', 'MSFT', etc.
    doc_type: str         # '10-K' | '10-Q'
    filing_date: date
    url: str              # SEC-EDGAR-URL — eindeutig
    raw_text_hash: str | None  # in Slice 1 immer None; Slice 2 fuellt
    ingested_at: datetime # UTC-aware
```

```python
# backend/domain/entities/embedding_chunk.py
@dataclass(frozen=True)
class EmbeddingChunk:
    id: UUID
    document_id: UUID
    chunk_idx: int
    content: str
    embedding: list[float]   # 2048-dim — pgvector-native
    metadata: dict[str, Any] # default {}, JSON-serializable
```

**Type-Hinweis:** `embedding` als `list[float]` — pgvector-Library-Native,
keine Adapter-Conversion noetig. Entity bleibt `frozen=True` (verhindert
Attribute-Rebinding), die Mutability der Liste selbst ist akzeptiert —
Entities werden in unserem Code nicht als Dict-Keys verwendet, also keine
Hashable-Anforderung.

## 5. Repository-Port

```python
# backend/domain/repositories/embedding_repository.py
from abc import ABC, abstractmethod
from uuid import UUID

class EmbeddingRepository(ABC):
    @abstractmethod
    async def save_document(self, doc: Document) -> None:
        """Persistiert ein Document. Wirft DuplicateUrl wenn URL existiert."""

    @abstractmethod
    async def save_chunks(self, chunks: list[EmbeddingChunk]) -> None:
        """Batch-UPSERT von Chunks. Re-Run mit gleichem (document_id, chunk_idx)
        ueberschreibt content + embedding + metadata, wirft keinen Error."""

    @abstractmethod
    async def get_document_by_url(self, url: str) -> Document | None:
        ...

    @abstractmethod
    async def count_chunks(self, document_id: UUID) -> int:
        ...

    @abstractmethod
    async def list_documents(self, *, ticker: str | None = None) -> list[Document]:
        """Optional gefiltert nach Ticker. Sort: ingested_at DESC."""
```

**Out-of-Scope fuer Slice 1:** `find_nearest(query_embedding, k)` — das ist
Slice-3-Material (Retrieval-Service). Port-Erweiterung in Slice 3.

## 6. Migration

`backend/alembic/versions/0008_enable_pgvector_and_create_embeddings.py`:

```python
"""enable pgvector and create embedding tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("doc_type", sa.String(8), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("raw_text_hash", sa.String(64), nullable=True),
        sa.Column("ingested_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_ticker", "documents", ["ticker"])

    op.create_table(
        "embedding_chunks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_idx", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(2048), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("document_id", "chunk_idx", name="uq_doc_chunk_idx"),
    )
    # HNSW-Index mit halfvec-Cast fuer Cosine-Similarity. pgvector limitiert
    # `vector` auf 2000 dim fuer Indexierung; wir nutzen 2048 (voyage-3-large
    # per ADR-0004). `halfvec` erlaubt bis 4000 dim — Application-Column bleibt
    # vector(2048), Index nutzt 16-bit-Floats. m=16/ef_construction=64 sind
    # pgvector-Defaults und passen fuer ~4000-100k Chunks ohne Tuning.
    op.execute(
        "CREATE INDEX ix_embedding_chunks_embedding "
        "ON embedding_chunks USING hnsw "
        "((embedding::halfvec(2048)) halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embedding_chunks_embedding")
    op.drop_table("embedding_chunks")
    op.drop_index("ix_documents_ticker", table_name="documents")
    op.drop_table("documents")
    # Extension bleibt — andere Tabellen koennten sie nutzen (zukuenftig)
```

**Render-Hinweis:** `CREATE EXTENSION IF NOT EXISTS vector` setzt voraus, dass
pgvector auf der Instance verfuegbar ist. Render-Postgres supports pgvector ab
DB-Creation-Date 2026-02-05+. Falls die Migration auf Render mit Permission-Error
abbricht: Support-Ticket an support@render.com.

## 7. Tests

### 7.1 Unit (Domain-Entities)
- `test_document.py`: Konstruktion + frozen-Verhalten + UTC-aware datetime-Validation
- `test_embedding_chunk.py`: 2048-dim-Constraint, tuple-vs-list-Verhalten, metadata-default

### 7.2 Integration (Repository)
- `test_save_and_get_document`: Roundtrip
- `test_save_chunks_batch`: 100 Chunks in einem Call, ueberprueft count_chunks
- `test_unique_url_constraint`: zweiter save_document mit gleicher URL wirft DuplicateUrl
- `test_upsert_on_duplicate_chunk_idx`: zweiter save_chunks mit gleichem (document_id, chunk_idx) ueberschreibt, wirft KEINEN Error
- `test_cascade_delete_document_deletes_chunks`: ON DELETE CASCADE
- `test_list_documents_filtered_by_ticker`
- `test_list_documents_sorted_by_ingested_at_desc`

**Test-Strategie:** Integration-Tests laufen gegen echtes Postgres (docker-compose
oder CI-Service). Keine InMemory-Variante fuer pgvector — Extension-Verhalten
muss real verifiziert werden.

## 8. Acceptance Criteria

- [ ] `pgvector>=0.3` in pyproject.toml
- [ ] Migration `0008_enable_pgvector_and_create_embeddings.py` laeuft up und down ohne Errors
- [ ] `documents`- und `embedding_chunks`-Tabellen existieren mit korrekten Constraints
- [ ] HNSW-Index mit halfvec-Cast ist angelegt und nutzbar (manueller Check via psql `\d embedding_chunks`)
- [ ] `Document`- und `EmbeddingChunk`-Domain-Entities frozen + typed
- [ ] `EmbeddingRepository`-Port + `SQLAEmbeddingRepository`-Adapter implementiert
- [ ] Unit-Tests fuer Entities gruen
- [ ] Integration-Tests fuer Repository gruen (alle 6+ Cases aus §7.2)
- [ ] mypy strict + ruff clean
- [ ] Migration auf Render verifiziert (oder Permission-Issue dokumentiert + Support-Ticket gestellt)
- [ ] `docs/AI-USAGE.md`-Eintrag

## 9. Risiken & Mitigation

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| pgvector auf Render nicht aktiviert (DB pre-2026-02-05) | niedrig (PRISMA gestartet FS 2026) | Migration faellt mit klarer Error-Msg, Support-Ticket-Pfad dokumentiert |
| `pgvector.sqlalchemy.Vector`-Type bricht mit current SQLA 2.0 | niedrig | pgvector-Lib ist SQLA-2.0-kompatibel seit 0.2; pyproject pinnt >=0.3 |
| `embedding`-Type-Mapping zwischen Domain (list[float]) und pgvector | niedrig | pgvector-Lib reicht list[float] direkt durch — kein Conversion-Code |
| HNSW-Index braucht keine Trainings-Daten (im Gegensatz zu IVFFlat), aber bei leerer Tabelle in Slice 1 ohnehin irrelevant | niedrig | Index ist erstellt aber leer — wird in Slice 2 nach Ingestion automatisch verwendet. Cosine-Suche faellt waehrenddessen auf seq-scan zurueck (OK fuer leeren Corpus). |
| Test-DB hat kein pgvector | mittel | docker-compose fuer Tests muss `pgvector/pgvector:pg16` Image nutzen, nicht plain postgres |

## 10. Q-by-Q-Decisions (Audit-Trail)

| # | Frage | Entscheidung | Datum |
|---|---|---|---|
| 1 | Slice-Groesse? | Option A: Foundation only (Schema + Repository, kein Ingestion/Retrieval) | 2026-05-11 |
| 2 | pgvector-Verfuegbarkeit auf Render verifiziert? | ✅ ja, via Render-Docs — DBs nach 2026-02-05 automatisch | 2026-05-11 |
| 3 | Index in Slice 1 oder erst nach Ingestion? | In Slice 1 anlegen — leerer Index ist OK, spaete Index-Creation oft langsamer. Index-Typ HNSW mit halfvec-Cast (siehe §4.2), nicht IVFFlat wie urspruenglich geplant — 2048-dim sprengt das `vector`-Index-Limit von 2000 dim. | 2026-05-11 |
| 4 | Embedding-Dimension fest auf 2048 oder configurable? | Fest 2048 (ADR-0004 §4 — voyage-3-large) — config-Pfad ist Stretch | 2026-05-11 |
| 5 | InMemory-Repository fuer Tests? | Nein — pgvector-Verhalten muss real verifiziert werden, nutzen wir wo Tests bereits real PG nutzen (siehe `test_research_memo_repository.py`-Pattern) | 2026-05-11 |

## 11. Folge-Slices (nicht Teil von Slice 1)

- **Slice 2 — Ingestion:** SEC-EDGAR-Download, PDF-Parsing, Chunking, Voyage-Embedding-Calls, Batch-Upsert. Real ~$0.24 Kosten. Acceptance: 4000+ Chunks fuer 5 Ticker.

  **Cost-Herleitung:** 4000 Chunks × ~333 tokens/Chunk × $0.18 / 1 Mio. Tokens = $0.24.
  - 333 tokens/Chunk entspricht ~1000 Zeichen bei der konservativen 3-chars/token-Schaetzung aus `backend/infrastructure/llm/client.py` (Konstante `_CHARS_PER_TOKEN_ESTIMATE`).
  - $0.18/Mtok ist `voyage-3-large` `embed_per_mtok` aus `backend/infrastructure/llm/pricing.py` (per ADR-0004 §4).
  - Realer Chunk-Token-Count via Voyage-Tokenizer kann ±50% schwanken — Realistische Range: **$0.12-$0.36** fuer einen vollen Slice-2-Ingestion-Run. Bei Pre-Production-Smoke ist das von Budget-Cap $20 weit weg.
- **Slice 3 — Retrieval:** `EmbeddingRepository.find_nearest(query_embedding, k)`, `RetrievalService`, REST-Endpoint `POST /api/v1/rag/retrieve`. Auth via existing `require_api_key`.
- **Slice 4 (optional) — Hardening:** Caching der Query-Embeddings, Metric-Logging, README-Doku.

## 12. Aenderungshistorie

| Version | Datum | Autor | Aenderung |
|---|---|---|---|
| Draft v1.0 | 2026-05-11 | Claude Code fuer Sheyla | Foundation-Slice nach Q-by-Q-Brainstorming + pgvector-Render-Verify |
