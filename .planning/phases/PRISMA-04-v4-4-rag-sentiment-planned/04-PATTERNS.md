# Phase 4: V4-4 RAG Sentiment - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 14 new/modified files
**Analogs found:** 13 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/infrastructure/adapters/cryptopanic_adapter.py` | adapter | request-response | `backend/infrastructure/adapters/rss_news_adapter.py` | exact |
| `backend/domain/schemas/agent_schemas.py` | schema | transform | `backend/domain/schemas/agent_schemas.py` (same file) | self-extend |
| `backend/domain/entities/news_article.py` | entity | transform | self (additive constant change) | self-extend |
| `backend/domain/entities/news_retrieval_result.py` | entity | transform | `backend/domain/entities/news_retrieval_result.py` (same file) | self-extend |
| `backend/infrastructure/persistence/repositories/news_repository.py` | repository | CRUD | self (additive SQL change) | self-extend |
| `backend/application/agents/sentiment_analyst_agent.py` | agent | request-response | `backend/application/agents/sentiment_analyst_agent.py` (V4-3 stub) | self-replace-body |
| `backend/application/services/news_ingestion_service.py` | service | CRUD | self (add method) | self-extend |
| `backend/application/agents/signal_director.py` | orchestrator | request-response | self (targeted insertion) | self-extend |
| `backend/infrastructure/llm/prompts/sentiment_analyst.de.md.j2` | prompt | transform | self (V4-3 F&G prompt) | self-rewrite |
| `backend/config.py` | config | — | self (add field) | self-extend |
| `backend/alembic/versions/0042_widen_news_source_column.py` | migration | — | `backend/alembic/versions/0041_agent_audit_trail.py` | role-match |
| `backend/tests/unit/infrastructure/test_cryptopanic_adapter.py` | test | — | `backend/tests/unit/application/test_analyst_agents.py` | role-match |
| `backend/tests/unit/application/test_news_ingestion_cryptopanic.py` | test | — | `backend/tests/unit/application/test_analyst_agents.py` | role-match |
| `backend/tests/unit/application/test_sentiment_score_formula.py` | test | — | `backend/tests/unit/application/test_analyst_agents.py::TestSentimentAnalystAgent` | role-match |
| `backend/tests/integration/test_backtest_sentiment_comparison.py` | test | — | `backend/tests/integration/test_agent_mandatory_suite.py` | role-match |
| `scripts/compare_sentiment_backtest.py` | script | batch | `scripts/llm_smoke_judge.py` | partial |

---

## Pattern Assignments

### `backend/infrastructure/adapters/cryptopanic_adapter.py` (adapter, request-response)

**Analog:** `backend/infrastructure/adapters/rss_news_adapter.py`

**Imports pattern** (lines 1-16):
```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

_logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]  # Exponential Backoff in Sekunden
```

**Dataclass pattern** (analog lines 24-31):
```python
@dataclass(frozen=True)
class RawArticle:
    url: str
    title: str
    content: str
    published_at: datetime | None
    source: str
```
For CryptoPanicAdapter, the new dataclass is:
```python
@dataclass(frozen=True)
class RawCryptoPanicArticle:
    url: str
    title: str
    published_at: datetime | None
    votes_positive: int
    votes_negative: int
    currencies: list[str]  # e.g. ["BTC", "ETH"] from currencies[].code tags
```

**Core retry pattern** (analog lines 42-56):
```python
async def fetch_articles(self, source: str, feed_url: str) -> list[RawArticle]:
    import asyncio
    for attempt, backoff in enumerate(_RETRY_BACKOFF, start=1):
        try:
            xml_text = await self._fetch_raw(feed_url)
            return _parse_rss(xml_text, source)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt >= _MAX_RETRIES:
                _logger.error("RSS fetch failed after %d attempts: %s", _MAX_RETRIES, exc)
                raise
            _logger.warning("RSS fetch attempt %d failed, retrying in %.1fs", attempt, backoff)
            await asyncio.sleep(backoff)
    return []
```
CryptoPanicAdapter signature: `async def fetch_articles(self, coin: str) -> list[RawCryptoPanicArticle]`

**_fetch_raw pattern** (analog lines 58-66):
```python
async def _fetch_raw(self, url: str) -> str:
    if self._client is not None:
        resp = await self._client.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text
```
CryptoPanicAdapter uses `resp.json()` instead of `resp.text`, and calls
`GET https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies={coin}&kind=news&public=true`.

**Error handling pattern** (analog lines 72-76):
```python
try:
    root = ET.fromstring(xml_text)
except ET.ParseError as exc:
    _logger.error("RSS XML parse error: %s", exc)
    return []
```
Mirror for JSON: `try: data = resp.json() except (json.JSONDecodeError, httpx.DecodingError) as exc: _logger.error(...); return []`

---

### `backend/domain/schemas/agent_schemas.py` — add `SentimentLLMOutput` (schema, transform)

**Analog:** `backend/domain/schemas/agent_schemas.py` (existing file, additive)

**Existing imports block** (lines 1-20 — do NOT change):
```python
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "TechnicalView",
    "OnChainView",
    "SentimentView",
    ...
]
```

**Pattern to copy** — add `SentimentLLMOutput` after existing classes, add to `__all__`:
```python
class SentimentLLMOutput(BaseModel):
    """LLM-Ausgabe für SentimentAnalystAgent — ausschliesslich news_surprise.

    §0 Iron Rule: LLM erzeugt KEINE Zahl. score, veto, regime: alle deterministisch in Python.
    """
    news_surprise: bool
    reasoning: str  # <= 3 Sätze
```

Copy from `SentimentView` (lines 56-70) for the BaseModel subclass pattern:
```python
class SentimentView(BaseModel):
    coin: str
    score: float = Field(ge=-1.0, le=1.0)
    regime: Literal["FEAR", "NEUTRAL", "GREED"]
    news_surprise: bool | None = None
    veto: bool = False
    reasoning: str
    sources: list[str] = []
```
`SentimentView` is FROZEN — do NOT modify it.

---

### `backend/domain/entities/news_article.py` — add "CRYPTOPANIC" to `_VALID_SOURCES` (entity, transform)

**Analog:** self (additive change, lines 1-11)

**Current pattern** (line 10):
```python
_VALID_SOURCES = frozenset({"NZZ", "SRF"})
```

**Required change** (one-line diff):
```python
_VALID_SOURCES = frozenset({"NZZ", "SRF", "CRYPTOPANIC"})
```

**Validator pattern to preserve** (lines 25-28):
```python
def __post_init__(self) -> None:
    if self.source not in _VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(_VALID_SOURCES)}, got {self.source!r}")
```

---

### `backend/domain/entities/news_retrieval_result.py` — add `url: str` field (entity, transform)

**Analog:** self (additive dataclass field)

**Current dataclass** (lines 11-22 — all fields):
```python
@dataclass(frozen=True)
class NewsRetrievalResult:
    chunk_id: UUID
    news_document_id: UUID
    chunk_idx: int
    content: str
    similarity: float
    title: str
    source: str
    tickers: tuple[str, ...]
    published_at: datetime | None
    metadata: dict[str, Any]
```

**Add `url: str` field** after `title: str`:
```python
    title: str
    url: str          # ADD: article URL — populated from nd.url in find_nearest()
    source: str
```

---

### `backend/infrastructure/persistence/repositories/news_repository.py` — add `nd.url` to `find_nearest()` SQL (repository, CRUD)

**Analog:** self (additive SQL column + result mapping)

**Current raw SQL SELECT** (lines 93-110):
```python
raw_sql = f"""
    SELECT
        nc.id              AS chunk_id,
        nc.news_document_id,
        nc.chunk_idx,
        nc.content,
        nc.metadata,
        nd.title,
        nd.source,
        nd.tickers,
        nd.published_at,
        1 - ((nc.embedding::halfvec(2048)) <=> ('{query_vector_str}'::vector(2048)::halfvec(2048)))
                           AS similarity
    FROM news_chunks nc
    JOIN news_documents nd ON nd.id = nc.news_document_id
    WHERE 1=1 {ticker_filter}
    ORDER BY ...
    LIMIT :k
"""
```

**Add `nd.url` to SELECT** (insert after `nd.title,`):
```sql
        nd.title,
        nd.url,            -- ADD: for SentimentView.sources citation
        nd.source,
```

**Add `nd.published_at > NOW() - INTERVAL '7 days'` date filter** (optional `max_age_days` param):
Add optional parameter `max_age_days: int | None = None` to `find_nearest()` signature.
When set, append `AND nd.published_at > NOW() - INTERVAL ':max_age_days days'` to WHERE clause.

**Update result construction** (lines 128-141 — add `url=` mapping):
```python
results.append(
    NewsRetrievalResult(
        chunk_id=UUID(str(row["chunk_id"])),
        news_document_id=UUID(str(row["news_document_id"])),
        chunk_idx=int(row["chunk_idx"]),
        content=str(row["content"]),
        similarity=sim,
        title=str(row["title"]),
        url=str(row["url"]),        # ADD: map nd.url
        source=str(row["source"]),
        tickers=tuple(raw_tickers) if raw_tickers else (),
        published_at=published,
        metadata=dict(row["metadata"]) if row["metadata"] else {},
    )
)
```

---

### `backend/application/agents/sentiment_analyst_agent.py` — replace body (agent, request-response)

**Analog:** self V4-3 stub — keep module docstring style, `from __future__ import annotations`, logging pattern, `_FEAR_THRESHOLD`/`_GREED_THRESHOLD` constants, `_fallback()` static method signature.

**Imports pattern to keep and extend** (analog lines 1-19):
```python
from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa

from backend.domain.schemas.agent_schemas import SentimentView

_logger = logging.getLogger(__name__)

_FEAR_THRESHOLD = -0.2
_GREED_THRESHOLD = 0.2
```

Add new imports for V4-4:
```python
from typing import Any, Literal

from backend.domain.schemas.agent_schemas import SentimentLLMOutput, SentimentView
from backend.application.services.news_retrieval_service import NewsRetrievalService
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_VETO_SCORE_THRESHOLD = -0.3
_MIN_ARTICLES_FOR_VOTE_RATIO = 5
```

**Constructor to replace** (analog lines 36-37):
```python
# V4-3 (replace this):
def __init__(self, db_session: Any) -> None:
    self._session = db_session

# V4-4 (new constructor):
def __init__(
    self,
    db_session: Any,
    news_retrieval_service: NewsRetrievalService,
    llm_client: LLMClient,
    prompt_loader: PromptTemplateLoader,
) -> None:
    self._session = db_session
    self._retrieval = news_retrieval_service
    self._llm = llm_client
    self._prompts = prompt_loader
```

**`analyze()` signature** — must accept second positional arg (SignalDirector calls `analyze(coin, {})`):
```python
# V4-3 (current):
async def analyze(self, coin: str) -> SentimentView:

# V4-4 (required — preserves SignalDirector compatibility):
async def analyze(self, coin: str, _context: dict = {}) -> SentimentView:
```

**DB query to keep** (analog lines 49-58 — used for fallback `fg_value`):
```python
result = await self._session.execute(
    sa.text(
        "SELECT fear_greed, fg_classification "
        "FROM market_sentiment "
        "ORDER BY date DESC "
        "LIMIT 1"
    )
)
row = result.first()
```

**`_fallback()` static method pattern** (analog lines 95-110 — copy structure):
```python
@staticmethod
def _fallback(coin: str, fg_value: int, fg_classification: str) -> SentimentView:
    """Deterministic fallback when DB or RAG corpus is unavailable."""
    score = (fg_value - 50) / 50
    return SentimentView(
        coin=coin,
        score=score,
        regime="NEUTRAL",
        news_surprise=None,
        veto=False,
        reasoning=(
            f"Fallback: Fear&Greed index {fg_value} ({fg_classification}). RAG corpus empty/too old."
        ),
        sources=[],
    )
```

**asyncio.to_thread() usage** — see CLAUDE.md rule. All sync operations must use:
```python
result = await asyncio.to_thread(sync_function, arg)
```
Do NOT use `loop.run_in_executor`.

---

### `backend/application/services/news_ingestion_service.py` — add `ingest_cryptopanic()` (service, CRUD)

**Analog:** self (add new method alongside `ingest_all()`)

**Existing `_ingest_feed()` pattern to copy** (lines 60-127):
```python
async def _ingest_feed(self, source: str, feed_url: str) -> dict[str, int]:
    articles = await self._rss.fetch_articles(source=source, feed_url=feed_url)
    stats: dict[str, int] = {"ingested": 0, "skipped_duplicate": 0, "errors": 0}

    for raw in articles:
        try:
            url_hash = NewsArticle.hash_url(raw.url)
            if await self._repo.exists_by_url_hash(url_hash):
                stats["skipped_duplicate"] += 1
                continue
            ...
            await self._repo.save_article(article)
            chunks = _chunk_text(article)
            embeddings = await self._llm.embed(texts=[c.content for c in chunks], ...)
            await self._repo.save_chunks(enriched)
            stats["ingested"] += 1
        except Exception as exc:
            _logger.error("Failed to ingest article %s: %s", raw.url, exc)
            stats["errors"] += 1
    return stats
```

**New `ingest_cryptopanic()` method** — same structure but:
1. Accepts `coins: list[str]` parameter, iterates per-coin.
2. Uses `CryptoPanicAdapter.fetch_articles(coin)` instead of `RssNewsAdapter.fetch_articles()`.
3. No TickerNer needed — `tickers = raw.currencies` directly from CryptoPanic tags.
4. 7-day TTL: filter `published_at > now() - 7d` before creating `NewsArticle`.
5. Chunk metadata includes votes: `metadata={"source": "CRYPTOPANIC", "tickers": tickers, "votes_positive": raw.votes_positive, "votes_negative": raw.votes_negative}`.
6. `source="CRYPTOPANIC"` for all articles.

**Constructor addition** — inject `CryptoPanicAdapter` alongside existing dependencies:
```python
def __init__(
    self,
    news_repo: NewsRepository,
    rss_adapter: RssNewsAdapter,
    ticker_ner: TickerNer,
    llm_client: LLMClient,
    feeds: list[tuple[str, str]] | None = None,
    cryptopanic_adapter: CryptoPanicAdapter | None = None,  # ADD
) -> None:
    ...
    self._cryptopanic = cryptopanic_adapter
```

---

### `backend/application/agents/signal_director.py` — add veto + size-scaling to `_synthesize()` (orchestrator, request-response)

**Analog:** self (targeted insertion in `_synthesize()`)

**Exact insertion point** (after line 151 — `action = _action_from_engine(...)`):
```python
# Line 151 (current):
action = _action_from_engine(engine_signal.action)

# INSERT HERE (D-06 veto — before no-shorting clamp):
from backend.config import get_settings
_settings = get_settings()

if _settings.sentiment_enabled and senti.veto:
    action = "HOLD"  # block BUY; SELL is never upgraded to BUY

# Lines 153-157 (existing no-shorting — do NOT touch):
base_size: float = getattr(engine_signal, "size_factor", 0.5)
size_factor = min(base_size, risk.max_size)
size_factor = max(0.0, size_factor)

# INSERT HERE (D-06 downside-only size scaling — after no-shorting clamp):
if _settings.sentiment_enabled and senti.score < 0:
    size_factor = size_factor * (1 + senti.score * 0.3)
    size_factor = max(0.0, size_factor)  # belt-and-suspenders no-short
```

**`get_settings()` import pattern** (analog: `backend/config.py` line 111-114):
```python
from backend.config import get_settings

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
Do NOT instantiate `Settings()` directly — always use `get_settings()` (singleton via `lru_cache`).

---

### `backend/infrastructure/llm/prompts/sentiment_analyst.de.md.j2` — rewrite (prompt, transform)

**Analog:** self V4-3 (full rewrite — keep template variable syntax `{{ var }}` and Jinja2 StrictUndefined convention)

**V4-3 structure to reference** (all 32 lines):
```
Du bist ein Sentiment-Analyst der PRISMA-Plattform...
## Eiserne Regel (§0)
## Sentiment-Daten
- Fear & Greed Index: {{ fg_value }} / 100
...
## Ausgabe-Format
```json
{ "coin": "{{ coin }}", "score": ..., ... }
```

**V4-4 template variables needed** (replace V4-3 vars):
- `{{ coin }}` — asset ticker (same)
- `{{ fg_value }}` — Fear&Greed integer (same)
- `{{ fg_classification }}` — F&G label (same)
- `{{ rag_chunks }}` — list of retrieved news chunk texts (NEW)
- `{{ n_chunks }}` — count of retrieved chunks (NEW)

**V4-4 JSON output schema** (replaces V4-3's full SentimentView output):
```json
{
  "news_surprise": <true|false>,
  "reasoning": "<= 3 Sätze"
}
```
Only these two fields. No `coin`, `score`, `regime`, `veto`, `sources` in output (§0 Iron Rule: LLM never produces numbers).

---

### `backend/config.py` — add `sentiment_enabled: bool = False` (config)

**Analog:** self (additive field in `Settings` class)

**Existing field pattern to copy** (lines 17-54 — simple bool/str/float field style):
```python
# Existing simple bool/float pattern:
max_concurrent_batch_workers: int = 3
stale_batch_timeout_seconds: int = 600
signal_quant_weight: float = 0.45
```

**Add after `stale_batch_timeout_seconds`** (no validator needed — pydantic-settings reads `SENTIMENT_ENABLED` env var automatically):
```python
# V4-4 Sentiment feature flag (reads SENTIMENT_ENABLED env var)
# Default false: behavior identical to V4-3 until backtest confirms value (D-08)
sentiment_enabled: bool = False
```

---

### `backend/alembic/versions/0042_widen_news_source_column.py` (migration)

**Analog:** `backend/alembic/versions/0041_agent_audit_trail.py`

**Migration boilerplate pattern** (analog lines 1-24):
```python
# backend/alembic/versions/0042_widen_news_source_column.py
"""Widen news_documents.source column from VARCHAR(10) to VARCHAR(20).

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-22

Required for CRYPTOPANIC source (11 chars — exceeds current VARCHAR(10) limit).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
```

**DDL pattern** — use `op.alter_column()`:
```python
def upgrade() -> None:
    op.alter_column(
        "news_documents",
        "source",
        type_=sa.String(20),
        existing_type=sa.String(10),
        nullable=False,
    )

def downgrade() -> None:
    op.alter_column(
        "news_documents",
        "source",
        type_=sa.String(10),
        existing_type=sa.String(20),
        nullable=False,
    )
```

---

### `backend/tests/unit/infrastructure/test_cryptopanic_adapter.py` (test, unit)

**Analog:** `backend/tests/unit/application/test_analyst_agents.py`

**Test file header pattern** (analog lines 1-21):
```python
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit
```

**httpx mock pattern** — mirror RssNewsAdapter test pattern (patch `httpx.AsyncClient.get`):
```python
async def test_fetch_articles_parses_votes(self, httpx_mock) -> None:
    # Use static JSON fixture (no live CryptoPanic API in tests)
    from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "url": "https://cryptopanic.com/news/1/btc-hits-ath",
                "title": "BTC hits ATH",
                "published_at": "2026-06-22T08:30:00Z",
                "votes": {"positive": 11, "negative": 2},
                "currencies": [{"code": "BTC"}],
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    adapter = CryptoPanicAdapter(client=mock_client)
    articles = await adapter.fetch_articles("BTC")
    assert len(articles) == 1
    assert articles[0].votes_positive == 11
    assert articles[0].currencies == ["BTC"]
```

---

### `backend/tests/unit/application/test_news_ingestion_cryptopanic.py` (test, unit)

**Analog:** `backend/tests/unit/application/test_analyst_agents.py`

**Test class pattern** (analog `TestSentimentAnalystAgent` builder style, lines 248-263):
```python
class TestNewsIngestionCryptoPanic:
    def _build_service(self, articles) -> Any:
        from backend.application.services.news_ingestion_service import NewsIngestionService
        from backend.infrastructure.adapters.cryptopanic_adapter import CryptoPanicAdapter

        mock_repo = AsyncMock()
        mock_repo.exists_by_url_hash = AsyncMock(return_value=False)
        mock_repo.save_article = AsyncMock()
        mock_repo.save_chunks = AsyncMock()

        mock_cryptopanic = AsyncMock()
        mock_cryptopanic.fetch_articles = AsyncMock(return_value=articles)

        mock_llm = AsyncMock()
        mock_llm.embed = AsyncMock(return_value=[[0.0] * 2048])

        return NewsIngestionService(
            news_repo=mock_repo,
            rss_adapter=MagicMock(),
            ticker_ner=MagicMock(),
            llm_client=mock_llm,
            cryptopanic_adapter=mock_cryptopanic,
        )
```

---

### `backend/tests/unit/application/test_sentiment_score_formula.py` (test, unit)

**Analog:** `backend/tests/unit/application/test_analyst_agents.py::TestSentimentAnalystAgent`

**Parameterized formula test pattern** (analog lines 283-291):
```python
async def test_normalization_formula(self) -> None:
    for fg in [0, 25, 50, 75, 100]:
        agent = self._build_agent(fg_value=fg)
        result = await agent.analyze("BTC")
        expected = (fg - 50) / 50
        assert abs(result.score - expected) < 1e-12
```

For score formula tests, use `@pytest.mark.parametrize` to cover:
- D-03 blend formula: `score = 0.7 * score_news + 0.3 * fg_norm`
- Fallback (< 5 articles): `score = fg_norm`
- Regime threshold boundaries: score = -0.2 (FEAR boundary), score = 0.2 (GREED boundary)
- Veto truth table: all 8 combinations of `(regime, news_surprise, score < -0.3)`

---

### `backend/tests/integration/test_backtest_sentiment_comparison.py` (test, integration)

**Analog:** `backend/tests/integration/test_agent_mandatory_suite.py`

**Integration test header pattern** (analog lines 1-41):
```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.application.agents.signal_director import SignalDirector

pytestmark = pytest.mark.integration
```

**`_make_director()` factory pattern** (analog lines 130-200 — copy full factory for building SignalDirector with all mocked deps):
```python
def _make_director(...) -> tuple[SignalDirector, MagicMock]:
    """Build a SignalDirector with all dependencies mocked."""
    signal_service = MagicMock()
    signal_service.evaluate = MagicMock(return_value=engine_signal)
    senti_agent = MagicMock()
    senti_agent.analyze = AsyncMock(return_value=senti_view)
    ...
```

Test must verify:
1. `SENTIMENT_ENABLED=true` + `senti.veto=True` → `TradeSignal.action == "HOLD"`
2. `SENTIMENT_ENABLED=false` + `senti.veto=True` → action unchanged (not forced HOLD)
3. `SENTIMENT_ENABLED=true` + `senti.score=-0.5` → `size_factor` scaled down
4. `SENTIMENT_ENABLED=true` + `senti.score=+0.5` → `size_factor` NOT amplified (clamped at original)

---

### `scripts/compare_sentiment_backtest.py` (script, batch)

**Analog:** `scripts/llm_smoke_judge.py` (async main pattern)

**Script header pattern** (analog lines 1-32):
```python
"""compare_sentiment_backtest.py — Walk-forward backtest comparison.

Runs run_walkforward() twice under identical conditions:
  1. SENTIMENT_ENABLED=false — baseline (V4-1/V4-2 signal)
  2. SENTIMENT_ENABLED=true  — sentiment-enhanced (veto + size scaling)

Compare: Sharpe, Calmar, MaxDD, Hit-Rate, # trades vetoed.
Reports honestly per D-08 Ehrlichkeits-Regel.

Ausfuehrung:
    source .venv/bin/activate
    python scripts/compare_sentiment_backtest.py
"""

from __future__ import annotations

import asyncio
import sys

from backend.config import get_settings
```

**asyncio.run main pattern** (analog pattern in smoke scripts):
```python
async def main() -> int:
    ...
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

---

## Shared Patterns

### `from __future__ import annotations`
**Source:** Every file in `backend/` (e.g., `rss_news_adapter.py` line 7, `agent_schemas.py` line 15)
**Apply to:** All new Python files
```python
from __future__ import annotations
```

### asyncio.to_thread() for sync operations
**Source:** `CLAUDE.md` rule + `signal_director.py` line 229
**Apply to:** Any sync I/O wrapped for async callers
```python
# CORRECT (CLAUDE.md mandatory):
result = await asyncio.to_thread(sync_function, arg)

# FORBIDDEN:
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, partial(sync_function, arg))
```

### Retry/backoff constants
**Source:** `backend/infrastructure/adapters/rss_news_adapter.py` lines 19-21
**Apply to:** `CryptoPanicAdapter`
```python
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]
```

### Pydantic BaseModel subclass pattern
**Source:** `backend/domain/schemas/agent_schemas.py` lines 35-44
**Apply to:** `SentimentLLMOutput`
```python
class TechnicalView(BaseModel):
    coin: str
    stance: Literal["BULLISH", "NEUTRAL", "BEARISH"]
    consensus: str
    key_signals: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
```
All bounded floats use `Field(ge=..., le=...)`. Enum fields use `Literal`.

### Module-level `_logger`
**Source:** `rss_news_adapter.py` line 17, `news_ingestion_service.py` line 17
**Apply to:** All new modules
```python
_logger = logging.getLogger(__name__)
```

### `get_settings()` singleton
**Source:** `backend/config.py` lines 111-114
**Apply to:** `signal_director.py` (veto insertion), `scripts/compare_sentiment_backtest.py`
```python
from backend.config import get_settings
_settings = get_settings()  # lru_cache singleton — do NOT instantiate Settings() directly
```

### Alembic migration boilerplate
**Source:** `backend/alembic/versions/0041_agent_audit_trail.py` lines 14-24
**Apply to:** `0042_widen_news_source_column.py`
```python
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
```

### Test file `pytestmark`
**Source:** `test_analyst_agents.py` line 21, `test_agent_mandatory_suite.py` line 41
**Apply to:** All new test files
```python
pytestmark = pytest.mark.unit    # for unit tests
pytestmark = pytest.mark.integration  # for integration tests
```

### `DuplicateUrl` / dedup pattern
**Source:** `backend/application/services/news_ingestion_service.py` lines 66-69
**Apply to:** `ingest_cryptopanic()` method
```python
url_hash = NewsArticle.hash_url(raw.url)
if await self._repo.exists_by_url_hash(url_hash):
    stats["skipped_duplicate"] += 1
    continue
```

### Chunk metadata structure (extended for votes)
**Source:** `backend/application/services/news_ingestion_service.py` lines 141-148 (`_chunk_text()`)
**Apply to:** `ingest_cryptopanic()` chunk creation — extend metadata with votes:
```python
# Current (NZZ/SRF):
metadata={"source": article.source, "tickers": list(article.tickers)}

# CryptoPanic extension (add votes for D-03 formula):
metadata={
    "source": "CRYPTOPANIC",
    "tickers": tickers,
    "votes_positive": raw_article.votes_positive,
    "votes_negative": raw_article.votes_negative,
}
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/domain/repositories/news_repository.py` (port) | repository port | — | Not read — minor additive change; implementation analog (`SQLANewsRepository`) fully covers it |

---

## Critical Blockers Summary (Wave 0 prerequisites)

These four changes MUST land before any ingestion or agent code can run:

1. `backend/domain/entities/news_article.py` — add `"CRYPTOPANIC"` to `_VALID_SOURCES` (line 10)
2. `backend/domain/entities/news_retrieval_result.py` — add `url: str` field
3. `backend/infrastructure/persistence/repositories/news_repository.py` — add `nd.url` to SELECT + result mapping
4. `backend/alembic/versions/0042_widen_news_source_column.py` — widen `source VARCHAR(10)` to `VARCHAR(20)` (BLOCKER: "CRYPTOPANIC" = 11 chars)

---

## Metadata

**Analog search scope:** `backend/infrastructure/adapters/`, `backend/application/agents/`, `backend/application/services/`, `backend/domain/entities/`, `backend/domain/schemas/`, `backend/infrastructure/persistence/repositories/`, `backend/alembic/versions/`, `backend/tests/unit/application/`, `backend/tests/integration/`, `scripts/`, `backend/config.py`
**Files scanned:** 16 source files read directly
**Pattern extraction date:** 2026-06-22
