# Phase 4: V4-4 RAG Sentiment — Research

**Researched:** 2026-06-22
**Domain:** CryptoPanic REST adapter, NewsRAG pipeline extension, SentimentAnalystAgent upgrade, SignalDirector veto wiring
**Confidence:** HIGH (all critical integration points verified from live codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** CryptoPanic Free API — `GET https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies={coin}&kind=news`. No auth token required for public feed. Up to 50 articles per run. Votes field contains `positive`, `negative` subfields. Currencies tags map directly to coin tickers.
- **D-02:** Daily ingestion, 7-day TTL, 50 articles/coin. Dedup via `url_hash`. Ingestion runs directly before daily signal generation.
- **D-03:** `score = 0.7 * (positive-negative)/max(1,positive+negative) + 0.3 * (fg-50)/50`. Fallback to `fg_norm` when `<5` articles.
- **D-04:** LLM produces ONLY `news_surprise: bool` + `reasoning: str` via `SentimentLLMOutput` Pydantic schema.
- **D-05:** `veto = (regime == "FEAR" and news_surprise == True and score < -0.3)`.
- **D-06:** SignalDirector: veto → HOLD override + downside-only size scaling, both behind `SENTIMENT_ENABLED` flag (default `false`).
- **D-07:** Reuse existing `news_documents`/`news_chunks` tables with `source='CRYPTOPANIC'`.
- **D-08:** Walk-forward backtest 2× (ENABLED vs DISABLED), honest reporting in `docs/PRISMA_V4_FORTSCHRITT.md`.

### Claude's Discretion

- CryptoPanicAdapter internal structure (dataclass fields, retry constants)
- Exact prompt wording for `sentiment_analyst.de.md.j2` (update for RAG chunks)
- `SentimentAnalystAgent.__init__` new parameter ordering
- Backtest script flag (`--sentiment` or env var approach)

### Deferred Ideas (OUT OF SCOPE)

- Real-time CryptoPanic ingestion (every 30min) → Phase V4-6
- CoinDesk RSS or other news sources → backlog
- UI display of sentiment score/news_surprise/sources → Phase V4-5
- EvaluationAgent using live sentiment metrics → Phase V4-6
- `SENTIMENT_ENABLED=true` as production default → only after positive backtest result

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-4-01 | CryptoPanicAdapter: fetch JSON from free API, retry/backoff, return `list[RawCryptoPanicArticle]` | Adapter pattern from `RssNewsAdapter` verified; API votes structure confirmed |
| REQ-4-02 | Extend `NewsIngestionService.DEFAULT_FEEDS` with CryptoPanic entry | Current `DEFAULT_FEEDS` is `list[tuple[str, str]]` — CryptoPanic does NOT fit this tuple structure (no feed URL); refactoring needed |
| REQ-4-03 | `NewsArticle._VALID_SOURCES` must include `'CRYPTOPANIC'` | BLOCKER: currently frozen to `{"NZZ", "SRF"}` — must be extended |
| REQ-4-04 | `NewsRetrievalResult` must expose article URL for `SentimentView.sources` | BLOCKER: current `find_nearest` SQL does NOT return `nd.url`; `NewsRetrievalResult` has no `url` field |
| REQ-4-05 | `SentimentAnalystAgent.analyze()` body: RAG retrieval → score → LLM call → veto → `SentimentView` | V4-3 stub body confirmed; constructor signature changes needed |
| REQ-4-06 | `SentimentLLMOutput` Pydantic schema: `news_surprise: bool`, `reasoning: str` | New schema, no existing equivalent found |
| REQ-4-07 | Score formula deterministic in Python (D-03) | Formula confirmed via CONTEXT.md; §0 Iron Rule upheld |
| REQ-4-08 | `SignalDirector._synthesize()` veto + size scaling (D-06) | `_synthesize()` signature and body fully read; insertion points identified |
| REQ-4-09 | `settings.sentiment_enabled: bool = False` in `backend/config.py` | Current Settings confirmed — no `sentiment_enabled` field exists yet |
| REQ-4-10 | Walk-forward backtest 2× comparison | `run_walkforward()` signature confirmed; no `sentiment_filter` param exists yet |
| REQ-4-11 | Update `sentiment_analyst.de.md.j2` prompt for RAG chunks | Existing V4-3 prompt confirmed as F&G-only; needs full rewrite for RAG |

</phase_requirements>

---

## Summary

Phase 4 upgrades `SentimentAnalystAgent` from a Fear&Greed-only DB stub to a full News-RAG pipeline. The work splits into three independently testable layers: (1) a new `CryptoPanicAdapter` infra adapter, (2) the upgraded `SentimentAnalystAgent.analyze()` body with deterministic score computation and an LLM call for `news_surprise`, and (3) `SignalDirector._synthesize()` wiring with veto and size-scaling behind `SENTIMENT_ENABLED`.

Three blocking integration gaps were discovered in the existing codebase that the planner MUST address as early Wave 0 or Wave 1 tasks:
1. `NewsArticle._VALID_SOURCES` is frozen to `{"NZZ", "SRF"}` — `"CRYPTOPANIC"` will raise `ValueError` at ingestion time if not added.
2. `NewsRetrievalResult` has no `url` field — the `find_nearest` raw SQL does not SELECT `nd.url`, so `SentimentView.sources` cannot be populated with article URLs without a targeted fix.
3. `DEFAULT_FEEDS: list[tuple[str, str]]` assumes RSS (source_name, feed_url) pairs — CryptoPanic has no feed URL; the ingestion service must be extended to accept adapters alongside raw URL tuples.

**Primary recommendation:** Plan Wave 0 as infrastructure blockers (extend `_VALID_SOURCES`, add `url` to `find_nearest`, extend `DEFAULT_FEEDS` type), then proceed with TDD-first waves for adapter, agent body, and SignalDirector wiring.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CryptoPanic HTTP fetch + retry | Infrastructure (adapter) | — | HTTP I/O with retry/backoff belongs in infrastructure layer |
| Vote-ratio score computation | Application (agent body) | — | Pure deterministic Python math; no DB, no LLM |
| LLM news_surprise call | Application (agent body) | Infrastructure (LLMClient) | Agent owns prompt + Pydantic validation; LLMClient owns HTTP |
| Veto rule evaluation | Application (agent body) | — | Deterministic rule-set, same layer as score |
| RAG retrieval (HNSW query) | Application (service) | Infrastructure (repo + DB) | `NewsRetrievalService` already owns this; agent calls service |
| Article ingestion (chunking + embedding) | Application (service) | Infrastructure (adapter) | `NewsIngestionService` orchestrates; adapter is data source |
| SentimentView persistence | Application (SignalDirector) | Infrastructure (audit trail repo) | `agent_run` JSONB already stores full `senti_view.model_dump()` automatically |
| Veto + size scaling wiring | Application (SignalDirector._synthesize) | — | Pure Python in existing `_synthesize()` function |
| `SENTIMENT_ENABLED` flag | Configuration (Settings) | Application (SignalDirector) | Settings reads env var; SignalDirector reads settings |
| Backtest comparison | Application (walkforward) | — | `run_walkforward()` already exists; add `sentiment_filter` param |

---

## Standard Stack

### Core (no new packages required)

All required packages are already in `pyproject.toml`.

| Library | Current Version | Purpose | Role in V4-4 |
|---------|----------------|---------|--------------|
| `httpx` | ≥0.27 [VERIFIED: pyproject.toml] | Async HTTP | CryptoPanicAdapter HTTP calls |
| `anthropic` | ≥0.25 [VERIFIED: pyproject.toml] | Anthropic SDK | LLM call via existing `LLMClient.messages_create()` |
| `pydantic` | ≥2.6 [VERIFIED: pyproject.toml] | Pydantic v2 | `SentimentLLMOutput` schema + existing `SentimentView` |
| `pydantic-settings` | ≥2.2 [VERIFIED: pyproject.toml] | Env var settings | `sentiment_enabled: bool = False` in `Settings` |
| `voyageai` | ≥0.2 [VERIFIED: pyproject.toml] | Voyage embeddings | Used in `LLMClient.embed()` for RAG retrieval |
| `sqlalchemy[asyncio]` | ≥2.0 [VERIFIED: pyproject.toml] | Async ORM | Existing `SQLANewsRepository.find_nearest()` |
| `pgvector` | ≥0.3 [VERIFIED: pyproject.toml] | HNSW vector search | Existing `find_nearest()` halfvec query |
| `jinja2` | ≥3.1 [VERIFIED: pyproject.toml] | Prompt templates | `PromptTemplateLoader.render()` for updated `.j2` file |

**No new package installations required.** [VERIFIED: pyproject.toml]

### Package Legitimacy Audit

No new packages are introduced in this phase. All dependencies are existing project dependencies verified in `pyproject.toml`.

| Package | Registry | Status | Disposition |
|---------|----------|--------|-------------|
| httpx | PyPI | Pre-existing in project | Approved — in use since Phase 3 |
| anthropic | PyPI | Pre-existing in project | Approved — in use since Phase 3 |
| pydantic | PyPI | Pre-existing in project | Approved |
| voyageai | PyPI | Pre-existing in project | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Critical Blockers (must be in Wave 0)

### Blocker 1: `NewsArticle._VALID_SOURCES` is frozen — CRYPTOPANIC will fail [VERIFIED: codebase]

**File:** `backend/domain/entities/news_article.py:10`

```python
# Current (BLOCKS CryptoPanic ingestion)
_VALID_SOURCES = frozenset({"NZZ", "SRF"})

# Required fix
_VALID_SOURCES = frozenset({"NZZ", "SRF", "CRYPTOPANIC"})
```

The `__post_init__` validator raises `ValueError` if `source not in _VALID_SOURCES`. Any `NewsArticle` created with `source="CRYPTOPANIC"` will fail immediately. This is a domain entity change — it requires a TDD test update (existing tests in `test_news_article.py` or equivalent).

### Blocker 2: `NewsRetrievalResult` has no `url` field — sources cannot be populated [VERIFIED: codebase]

**Files affected:**
- `backend/domain/entities/news_retrieval_result.py` — must add `url: str` field
- `backend/infrastructure/persistence/repositories/news_repository.py` — `find_nearest()` raw SQL must SELECT `nd.url`

The current dataclass has these fields: `chunk_id`, `news_document_id`, `chunk_idx`, `content`, `similarity`, `title`, `source`, `tickers`, `published_at`, `metadata`. No `url`. The raw SQL query selects from `news_documents nd` but does not include `nd.url`.

**Required fix to `find_nearest()` SQL:**
```sql
-- Add nd.url to SELECT list
SELECT
    nc.id              AS chunk_id,
    nc.news_document_id,
    nc.chunk_idx,
    nc.content,
    nc.metadata,
    nd.title,
    nd.url,            -- ADD THIS
    nd.source,
    nd.tickers,
    nd.published_at,
    ...
```

And add `url: str` to `NewsRetrievalResult` dataclass. This is a minor additive change — backward-compatible (NZZ/SRF articles already have URLs in the DB).

### Blocker 3: `DEFAULT_FEEDS` tuple structure incompatible with CryptoPanic adapter [VERIFIED: codebase]

**File:** `backend/application/services/news_ingestion_service.py:25-28`

```python
# Current: list of (source_name, feed_url) tuples — RSS-only
DEFAULT_FEEDS: list[tuple[str, str]] = [
    ("NZZ", "https://www.nzz.ch/finanzen.rss"),
    ("SRF", "https://www.srf.ch/news/bnf/rss/1646"),
]
```

CryptoPanic does NOT work as a static URL tuple — it takes a coin-ticker parameter at call-time and calls the adapter differently. The `_ingest_feed()` method calls `self._rss.fetch_articles(source=source, feed_url=feed_url)` which doesn't fit.

**Two viable approaches:**
1. **Extend service to accept typed adapter list** — `DEFAULT_FEEDS` becomes a protocol-based list; `NewsIngestionService` dispatches to either `RssNewsAdapter` or `CryptoPanicAdapter` depending on type.
2. **Separate ingestion method** — Add `ingest_cryptopanic(coins: list[str])` as a second method in `NewsIngestionService`, called alongside `ingest_all()` in the daily scheduler.

Approach 2 is lower-risk (no change to existing RSS path, no type refactoring). **Recommended.**

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Daily Batch (APScheduler)                                       │
│                                                                  │
│  1. CryptoPanicAdapter.fetch_articles(coin)                     │
│        ↓ list[RawCryptoPanicArticle]                            │
│  2. NewsIngestionService.ingest_cryptopanic(coins=[...])        │
│        ↓ dedup via url_hash → embed via Voyage → save chunks    │
│  3. SignalDirector.run(coin)                                     │
│     ├── signal_service.evaluate() [deterministic engine]        │
│     ├── SentimentAnalystAgent.analyze(coin) ←─────────────────┐ │
│     │     ├── NewsRetrievalService.retrieve(query, ticker=coin)│ │
│     │     │     └── SQLANewsRepository.find_nearest()          │ │
│     │     │          [HNSW, 7-day TTL filter, ticker=coin]     │ │
│     │     ├── score computation (D-03 deterministic Python)    │ │
│     │     ├── LLMClient.messages_create() → SentimentLLMOutput │ │
│     │     │     [news_surprise: bool, reasoning: str ONLY]     │ │
│     │     ├── veto rule (D-05 deterministic Python)            │ │
│     │     └── SentimentView (score, regime, veto, sources[])   │ │
│     └── _synthesize() → TradeSignal                            │ │
│           ├── if SENTIMENT_ENABLED and senti.veto → HOLD        │ │
│           └── if SENTIMENT_ENABLED and score < 0 → scale size  │ │
│                                                                  │
│  SentimentView.sources = [url1, url2, ...]                      │
│  Stored automatically in agent_audit_trail.agent_run JSONB      │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (new files only)

```
backend/
├── infrastructure/adapters/
│   └── cryptopanic_adapter.py      # NEW: CryptoPanicAdapter + RawCryptoPanicArticle
├── domain/schemas/
│   └── agent_schemas.py            # MODIFY: SentimentLLMOutput added (do NOT touch SentimentView)
├── domain/entities/
│   ├── news_article.py             # MODIFY: add "CRYPTOPANIC" to _VALID_SOURCES
│   └── news_retrieval_result.py    # MODIFY: add url: str field
├── infrastructure/persistence/repositories/
│   └── news_repository.py          # MODIFY: find_nearest() SQL adds nd.url
├── application/agents/
│   └── sentiment_analyst_agent.py  # REPLACE BODY: RAG + score + LLM + veto
├── application/services/
│   └── news_ingestion_service.py   # MODIFY: add ingest_cryptopanic() method
├── application/agents/
│   └── signal_director.py          # MODIFY: _synthesize() veto + size scaling
├── infrastructure/llm/prompts/
│   └── sentiment_analyst.de.md.j2  # REWRITE: RAG chunks input, news_surprise output
├── config.py                        # MODIFY: add sentiment_enabled: bool = False
└── tests/unit/application/
    └── test_analyst_agents.py       # MODIFY: replace stub tests with V4-4 tests
```

### Pattern 1: CryptoPanicAdapter (copy from RssNewsAdapter)

**What:** HTTP adapter that fetches JSON from CryptoPanic `/api/v1/posts/` endpoint.
**When to use:** Called by `NewsIngestionService.ingest_cryptopanic()` per coin per day.

```python
# Source: RssNewsAdapter pattern [VERIFIED: backend/infrastructure/adapters/rss_news_adapter.py]
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

_logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]

_BASE_URL = "https://cryptopanic.com/api/v1/posts/"
_MAX_ARTICLES = 50  # D-02: 50 articles per coin per run


@dataclass(frozen=True)
class RawCryptoPanicArticle:
    url: str
    title: str
    published_at: datetime | None
    votes_positive: int
    votes_negative: int
    currencies: list[str]  # ["BTC", "ETH"] from CryptoPanic currencies tags


class CryptoPanicAdapter:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch_articles(self, coin: str) -> list[RawCryptoPanicArticle]:
        """Fetch up to 50 news articles for `coin` from CryptoPanic free API."""
        params = {
            "auth_token": "free",
            "currencies": coin,
            "kind": "news",
            "public": "true",
        }
        for attempt, backoff in enumerate(_RETRY_BACKOFF, start=1):
            try:
                raw_json = await self._fetch_raw(params)
                return _parse_response(raw_json)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= _MAX_RETRIES:
                    _logger.error("CryptoPanic fetch failed after %d attempts: %s", _MAX_RETRIES, exc)
                    raise
                _logger.warning("CryptoPanic attempt %d failed, retrying in %.1fs", attempt, backoff)
                await asyncio.sleep(backoff)
        return []
```

**CryptoPanic API response structure** [VERIFIED: guilyx/cryptopanic Python wrapper + roccomuso Node.js wrapper]:
```json
{
  "count": 50,
  "next": "https://cryptopanic.com/api/v1/posts/?page=2&...",
  "results": [
    {
      "id": 12345,
      "title": "Bitcoin reaches new ATH",
      "url": "https://cryptopanic.com/news/12345/...",
      "source": {"title": "CoinDesk", "domain": "coindesk.com"},
      "currencies": [{"code": "BTC", "title": "Bitcoin"}],
      "votes": {
        "positive": 11,
        "negative": 0,
        "important": 6,
        "liked": 4,
        "disliked": 0,
        "lol": 0,
        "toxic": 0,
        "saved": 2,
        "comments": 3
      },
      "published_at": "2026-06-22T08:30:00Z"
    }
  ]
}
```

**Key fields:** `results[].votes.positive`, `results[].votes.negative`, `results[].currencies[].code` (ticker), `results[].published_at`, `results[].url`. [VERIFIED: guilyx/cryptopanic source code via GitHub search]

**Rate limit:** 5 req/sec per IP; server-side cache updates every ~30 seconds. Free tier: public endpoint, no auth token required beyond `auth_token=free`. [ASSUMED — no official free-tier rate limit documentation found; verify against CryptoPanic developer docs before production deployment]

### Pattern 2: SentimentAnalystAgent V4-4 Constructor

**What:** V4-4 upgrades constructor to inject `NewsRetrievalService` and `LLMClient` alongside existing `db_session`.
**Why this matters:** V4-3 constructor only takes `db_session`. V4-4 must pass `NewsRetrievalService` and `LLMClient` from SignalDirector's DI wiring.

```python
# V4-4 constructor (replaces V4-3 stub)
class SentimentAnalystAgent:
    _MODEL = "claude-haiku-4-5-20251001"

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

**Note:** `SignalDirector` calls `self._senti_agent.analyze(coin, {})` [VERIFIED: signal_director.py:242]. The V4-4 `analyze()` signature must remain `analyze(self, coin: str, _: dict = {}) -> SentimentView` to preserve compatibility without changing `SignalDirector.run()`.

### Pattern 3: Score Computation (D-03 deterministic)

```python
# Source: CONTEXT.md D-03 [VERIFIED]
_FEAR_THRESHOLD = -0.2
_GREED_THRESHOLD = 0.2
_VETO_SCORE_THRESHOLD = -0.3
_MIN_ARTICLES_FOR_VOTE_RATIO = 5


def _compute_score(
    articles: list[NewsRetrievalResult],
    fg_value: int,
) -> tuple[float, Literal["FEAR", "NEUTRAL", "GREED"]]:
    """D-03: deterministic score, never from LLM."""
    fg_norm = (fg_value - 50) / 50

    # Count votes from retrieved articles that have vote metadata
    positive = sum(int(a.metadata.get("votes_positive", 0)) for a in articles)
    negative = sum(int(a.metadata.get("votes_negative", 0)) for a in articles)
    total_votes = positive + negative
    n_articles = len(articles)

    if n_articles >= _MIN_ARTICLES_FOR_VOTE_RATIO:
        score_news = (positive - negative) / max(1, total_votes)
        score = 0.7 * score_news + 0.3 * fg_norm
    else:
        score = fg_norm  # fallback

    # Clamp to [-1, 1] for SentimentView schema
    score = max(-1.0, min(1.0, score))

    if score < _FEAR_THRESHOLD:
        regime: Literal["FEAR", "NEUTRAL", "GREED"] = "FEAR"
    elif score > _GREED_THRESHOLD:
        regime = "GREED"
    else:
        regime = "NEUTRAL"

    return score, regime
```

**Important design note on votes storage:** The CryptoPanicAdapter produces `votes_positive` and `votes_negative` per article. For retrieval-time scoring, these values must be accessible from `NewsRetrievalResult`. Two options:
- Store in `NewsChunk.metadata` at ingestion time: `{"source": "CRYPTOPANIC", "votes_positive": N, "votes_negative": N, "tickers": [...]}` — already accessible via `metadata` field.
- Store at document level (not accessible from chunk retrieval result).

**Recommendation:** Store votes in chunk metadata at ingestion. The `NewsIngestionService._ingest_feed()` method already passes article-level metadata through `_chunk_text()` which sets `metadata={"source": article.source, "tickers": list(article.tickers)}`. The new `ingest_cryptopanic()` method must include votes in metadata.

### Pattern 4: SentimentLLMOutput Schema

```python
# New schema in backend/domain/schemas/agent_schemas.py
# Add to __all__ list
class SentimentLLMOutput(BaseModel):
    """LLM-Ausgabe für SentimentAnalystAgent — ausschliesslich news_surprise.

    §0 Iron Rule: LLM erzeugt KEINE Zahl. score, veto, regime: alle deterministisch in Python.
    """
    news_surprise: bool   # True wenn bedeutendes neues Ereignis erkannt (Hack, Regulation, Partnership)
    reasoning: str        # <= 3 Sätze
```

### Pattern 5: SignalDirector._synthesize() Veto Wiring (D-06)

**Insertion point:** After action is determined (`action = _action_from_engine(engine_signal.action)`), before `size_factor` clamping.

```python
# Source: CONTEXT.md D-06 [VERIFIED]
# ADD after action determination, before no-shorting clamp:

# D-06 Sentiment veto (only when SENTIMENT_ENABLED=true)
from backend.config import get_settings
_settings = get_settings()

if _settings.sentiment_enabled and senti.veto:
    action = "HOLD"  # block BUY; SELL is never upgraded to BUY

# ... existing no-shorting: size_factor = min(base_size, risk.max_size) ...

# D-06 Downside-only size scaling (only when SENTIMENT_ENABLED=true)
if _settings.sentiment_enabled and senti.score < 0:
    size_factor = size_factor * (1 + senti.score * 0.3)
    size_factor = max(0.0, size_factor)  # no-shorting belt-and-suspenders
```

**Settings flag — exact addition to `backend/config.py`:**
```python
# Add to Settings class (reads SENTIMENT_ENABLED env var)
sentiment_enabled: bool = False
```

### Anti-Patterns to Avoid

- **LLM computing score:** The LLM must NEVER receive a request to produce a sentiment score. `SentimentLLMOutput` has exactly two fields: `news_surprise: bool` and `reasoning: str`. Anything else violates §0 Iron Rule.
- **Calling `senti_agent.analyze(coin)` with different signature than existing:** `SignalDirector` calls `self._senti_agent.analyze(coin, {})`. The new `analyze()` must accept a second positional argument `{}` (ignored) to avoid breaking SignalDirector without modifying it.
- **Modifying `SentimentView` schema:** The schema is frozen per CONTEXT.md. Fields are already correct for V4-4: `coin`, `score`, `regime`, `news_surprise`, `veto`, `sources`. Do NOT add fields.
- **Not handling 7-day TTL filter:** Retrieval must filter `published_at > now() - 7d`. The current `find_nearest()` has NO date filter — this must be added either in `NewsRetrievalService.retrieve()` as an optional `max_age_days` param, or in the SQL query itself.
- **Using `run_in_executor` instead of `asyncio.to_thread`:** CLAUDE.md explicitly forbids `run_in_executor`. All sync wrappers must use `asyncio.to_thread()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry with backoff | Custom retry loop from scratch | Copy `_RETRY_BACKOFF` pattern from `RssNewsAdapter` | Exact same backoff constants (`_RETRIES=3`, `_RETRY_BACKOFF=[1.0, 2.0, 4.0]`) already proven |
| LLM Pydantic output validation | Custom JSON parser | `json.loads()` + `SentimentLLMOutput.model_validate(data)` with try/except fallback | Same pattern as `TechnicalAnalystAgent` — handles ValidationError → fallback |
| Vector similarity search | Custom cosine similarity | `SQLANewsRepository.find_nearest()` (already uses HNSW via pgvector) | Re-implemented would lose HNSW index, halfvec optimization |
| Article deduplication | Custom hash tracking | `NewsArticle.hash_url(url)` + `exists_by_url_hash()` | SHA-256 + unique constraint already wired |
| Prompt templating | f-strings | `PromptTemplateLoader.render("sentiment_analyst.de.md.j2", {...})` | Jinja2 `StrictUndefined` catches missing template variables at call time |
| Embedding generation | Direct voyageai calls | `LLMClient.embed(texts, model="voyage-3-large", feature="...")` | LLMClient wraps cost tracking + cap check; direct SDK bypasses budget gate |
| Settings env var loading | `os.getenv()` | `pydantic_settings.BaseSettings` via existing `Settings` class | Type coercion, validation, lru_cache singleton already wired |

---

## Runtime State Inventory

This is not a rename/refactor/migration phase. The tables being reused (`news_documents`, `news_chunks`) already exist with the correct schema from migration `0014`. No data migration is needed.

**Confirmed no-migration required:** [VERIFIED: alembic/versions/0014_create_news_tables.py]
- `news_documents.source` is `String(10)` — "CRYPTOPANIC" is 11 characters. **POTENTIAL ISSUE:** Column length is `String(10)` but "CRYPTOPANIC" is 11 chars. A migration to widen to `String(20)` may be required. [VERIFIED: ORM model line 34, migration line 30]

**String(10) capacity check:**
```
"NZZ"        = 3 chars  ✓
"SRF"        = 3 chars  ✓
"CRYPTOPANIC" = 11 chars  EXCEEDS String(10) — BLOCKER 4
```

This is an additional blocker. A migration `0042_widen_news_source_column.py` must be added to `ALTER TABLE news_documents ALTER COLUMN source TYPE VARCHAR(20)`.

---

## Common Pitfalls

### Pitfall 1: `NewsArticle._VALID_SOURCES` enforcement at instantiation time

**What goes wrong:** `CryptoPanicAdapter` produces articles with `source="CRYPTOPANIC"`. When `NewsIngestionService.ingest_cryptopanic()` creates `NewsArticle(source="CRYPTOPANIC", ...)`, `__post_init__` raises `ValueError("source must be one of ['NZZ', 'SRF'], got 'CRYPTOPANIC'")` immediately.
**Why it happens:** `_VALID_SOURCES` is a frozen module-level constant. It was set up for Swiss RSS sources only.
**How to avoid:** In Wave 0, extend `_VALID_SOURCES` and update existing tests that verify the source allowlist.
**Warning signs:** Integration test fails with `ValueError` on first ingestion attempt.

### Pitfall 2: Missing URL in NewsRetrievalResult breaks sources list

**What goes wrong:** `SentimentView.sources = [r.url for r in results]` raises `AttributeError: 'NewsRetrievalResult' object has no attribute 'url'`.
**Why it happens:** `find_nearest()` raw SQL does not SELECT `nd.url`. `NewsRetrievalResult` dataclass has no `url` field.
**How to avoid:** Add `url: str` to `NewsRetrievalResult` dataclass AND add `nd.url` to the SELECT clause in `find_nearest()` raw SQL AND map `url=str(row["url"])` in the result construction.
**Warning signs:** `AttributeError` in `SentimentAnalystAgent.analyze()` at sources population step.

### Pitfall 3: `String(10)` column overflow for "CRYPTOPANIC"

**What goes wrong:** PostgreSQL raises `DataError: value too long for type character varying(10)` when inserting a news document with `source="CRYPTOPANIC"`.
**Why it happens:** Migration 0014 created `source VARCHAR(10)`. "CRYPTOPANIC" is 11 characters.
**How to avoid:** Migration `0042` must widen the column BEFORE any ingestion runs.
**Warning signs:** DB insert fails with truncation or too-long error.

### Pitfall 4: `senti_agent.analyze(coin, {})` signature mismatch

**What goes wrong:** `SignalDirector` calls `self._senti_agent.analyze(coin, {})` [line 242]. If V4-4's `analyze()` signature is `analyze(self, coin: str) -> SentimentView` (no second arg), `TypeError: analyze() takes 2 positional arguments but 3 were given`.
**Why it happens:** V4-3 stub accepts `(coin, {})` but V4-4 implementor forgets the ignored second parameter.
**How to avoid:** V4-4 signature must be `async def analyze(self, coin: str, _context: dict = {}) -> SentimentView`.
**Warning signs:** `TypeError` when `SignalDirector.run()` is called.

### Pitfall 5: 7-day TTL not enforced in retrieval

**What goes wrong:** Old articles (>7 days) from prior NZZ/SRF ingestion contaminate the CryptoPanic coin-specific retrieval, producing irrelevant chunks.
**Why it happens:** `find_nearest()` has no date filter; the ticker filter `AND :ticker = ANY(nd.tickers)` handles coin specificity but not freshness.
**How to avoid:** Add `AND nd.published_at > NOW() - INTERVAL '7 days'` to the `find_nearest()` raw SQL, OR pass it as an optional parameter from `SentimentAnalystAgent`.
**Warning signs:** Retrieved articles with `published_at` older than 7 days appearing in results; fallback triggering unexpectedly when corpus appears "empty" after filtering.

### Pitfall 6: Votes not in chunk metadata = D-03 formula always uses F&G fallback

**What goes wrong:** `_compute_score()` finds `metadata.get("votes_positive", 0) == 0` for all articles → `total_votes == 0` → falls back to F&G-only score despite corpus having 50 articles.
**Why it happens:** `_chunk_text()` currently sets `metadata={"source": article.source, "tickers": list(article.tickers)}` — no votes. If `ingest_cryptopanic()` doesn't include votes in metadata, the scoring silently degrades.
**How to avoid:** In `ingest_cryptopanic()`, extend chunk metadata: `metadata={"source": "CRYPTOPANIC", "tickers": tickers, "votes_positive": raw_article.votes_positive, "votes_negative": raw_article.votes_negative}`.
**Warning signs:** Score always equals `fg_norm` regardless of news; `positive == 0` and `negative == 0` in score computation logs.

### Pitfall 7: D-06 mandatory suite still passes but new veto tests are missing

**What goes wrong:** Existing 7 D-06 tests all pass (they use mocked `senti_agent`), but no new tests verify the veto and size-scaling logic in `_synthesize()` under `SENTIMENT_ENABLED=true`.
**Why it happens:** D-06 mandatory suite mocks `SentimentView` — it does not test the new `sentiment_enabled` code path.
**How to avoid:** Add new tests to `test_agent_mandatory_suite.py` for: (a) veto triggers HOLD when `SENTIMENT_ENABLED=true`, (b) veto does NOT trigger when `SENTIMENT_ENABLED=false`, (c) size scaling applied only when `score < 0`, (d) positive score does not amplify size.

---

## TDD Mapping

### TDD-Eligible Tasks (RED/GREEN/REFACTOR cycle)

These have well-defined inputs and outputs, making them ideal for test-first development:

| Task | File | TDD Test Type | Why TDD? |
|------|------|---------------|----------|
| `SentimentLLMOutput` Pydantic schema | `agent_schemas.py` | Schema validation tests | Pure data contract; Literal fields, str fields |
| Score formula (D-03) | `sentiment_analyst_agent.py` | Unit: parameterized formulas | Deterministic math; exact expected values computable |
| Regime threshold mapping | `sentiment_analyst_agent.py` | Unit: boundary values | Exact thresholds (-0.2, +0.2) from CONTEXT.md |
| Veto rule (D-05) | `sentiment_analyst_agent.py` | Unit: truth table (8 combinations of regime×news_surprise×score) | Boolean rule-set; all combinations enumerable |
| Fallback chain (corpus empty) | `sentiment_analyst_agent.py` | Unit: mock retrieval returns [] | Defined fallback behavior per CONTEXT.md §9 |
| Fallback chain (LLM fails) | `sentiment_analyst_agent.py` | Unit: mock LLM raises Exception | `news_surprise=None`, `veto=False` per CONTEXT.md §9 |
| `_synthesize()` veto + size scaling | `signal_director.py` | Unit: parametrize SENTIMENT_ENABLED, score, veto values | Pure Python function; all inputs controllable |
| `CryptoPanicAdapter` response parsing | `cryptopanic_adapter.py` | Unit: parse static JSON fixture | No network I/O needed for parser unit test |
| `NewsArticle` CRYPTOPANIC source | `news_article.py` | Unit: constructor accepts new source | Domain entity invariant test |
| `NewsRetrievalResult` url field | `news_retrieval_result.py` | Unit: dataclass instantiation | Field presence + type |

### Standard Execute Tasks (no TDD cycle needed)

| Task | Why No TDD? |
|------|-------------|
| Update `sentiment_analyst.de.md.j2` prompt | Template content — integration tested via agent LLM call |
| Add `sentiment_enabled` to `config.py` | Settings field — trivially correct; tested via env var in integration |
| Alembic migration `0042_widen_news_source_column.py` | DDL only; tested at migration time |
| Widen `find_nearest()` SQL to include `nd.url` | SQL change verified by existing retrieval integration tests |
| `ingest_cryptopanic()` method wiring | Service orchestration; tested via integration with mock adapter |
| Walk-forward backtest `sentiment_filter` parameter | Numeric computation tested in existing walkforward tests; extension is wiring |

---

## Code Examples

### Current `_synthesize()` insertion point for veto

```python
# Source: backend/application/agents/signal_director.py [VERIFIED: lines 113-178]
# Current action determination (line 151):
action = _action_from_engine(engine_signal.action)

# INSERT VETO HERE (between action determination and size_factor clamping):
# if settings.sentiment_enabled and senti.veto:
#     action = "HOLD"

# Existing no-shorting clamp (lines 154-157):
base_size: float = getattr(engine_signal, "size_factor", 0.5)
size_factor = min(base_size, risk.max_size)
size_factor = max(0.0, size_factor)

# INSERT SIZE SCALING HERE (after no-shorting clamp):
# if settings.sentiment_enabled and senti.score < 0:
#     size_factor = size_factor * (1 + senti.score * 0.3)
#     size_factor = max(0.0, size_factor)
```

### Current `SentimentView` fields (FROZEN — do not change)

```python
# Source: backend/domain/schemas/agent_schemas.py [VERIFIED: lines 56-70]
class SentimentView(BaseModel):
    coin: str
    score: float = Field(ge=-1.0, le=1.0)
    regime: Literal["FEAR", "NEUTRAL", "GREED"]
    news_surprise: bool | None = None  # V4-4 fills this
    veto: bool = False                 # V4-4 fills this
    reasoning: str
    sources: list[str] = []            # V4-4 fills with article URLs
```

### `senti_agent.analyze()` call in SignalDirector (must remain compatible)

```python
# Source: backend/application/agents/signal_director.py [VERIFIED: line 242]
self._senti_agent.analyze(coin, {}),  # {} is the ignored context dict
```

### Existing test pattern for SentimentAnalystAgent

```python
# Source: backend/tests/unit/application/test_analyst_agents.py [VERIFIED: lines 248-262]
def _build_agent(self, fg_value: int, fg_classification: str = "Neutral") -> Any:
    from backend.application.agents.sentiment_analyst_agent import SentimentAnalystAgent
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.fear_greed = fg_value
    mock_row.fg_classification = fg_classification
    mock_result.first.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)
    return SentimentAnalystAgent(db_session=mock_session)
# V4-4 builder will need: db_session + news_retrieval_service mock + llm_client mock + prompt_loader mock
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| V4-3: F&G-only stub, no LLM | V4-4: RAG retrieval + deterministic score + LLM news_surprise | This phase | Score gains news signal component |
| V4-3: `news_surprise=None`, `veto=False` | V4-4: populated from LLM + rule | This phase | Veto capability activated |
| `DEFAULT_FEEDS`: RSS-only tuple list | Extended with CryptoPanic adapter method | This phase | Crypto-specific news source |

**Deprecated/outdated in this phase:**
- V4-3 `SentimentAnalystAgent` stub body: the entire `analyze()` method body is replaced. Constructor signature changes. The F&G DB query moves to a helper (still needed for `fg_value` in score formula and fallback).

---

## Open Questions

1. **CryptoPanic free tier rate limit — exact value**
   - What we know: 5 req/sec per IP (from search results); server-side cache at ~30 seconds
   - What's unclear: Whether `auth_token=free` is a literal token or placeholder; whether unauthenticated public feed has pagination beyond page 1
   - Recommendation: Test the endpoint manually once before implementation. The D-02 decision says "50 articles/coin" which fits exactly one page. If pagination is needed, the adapter must iterate `next` URL — plan for it.

2. **7-day TTL filter placement — `find_nearest()` SQL vs. application layer**
   - What we know: D-02 requires retrieval to filter `published_at > now()-7d`; current `find_nearest()` has no date filter
   - What's unclear: Whether to modify the domain port (adding optional `max_age_days` param to `NewsRepository.find_nearest()`), or handle it in `NewsRetrievalService`, or in `SentimentAnalystAgent` as a post-retrieval filter
   - Recommendation: Add `max_age_days: int | None = None` to `NewsRepository.find_nearest()` port and SQL implementation. Most surgical change; backward compatible (default None = no filter).

3. **Backtest walk-forward script location and invocation**
   - What we know: `run_walkforward()` and `run_walkforward_with_details()` exist in `backend/application/backtest/walkforward.py`; they accept `signals: pd.Series` (0/1 position series); no `SENTIMENT_ENABLED` parameter exists
   - What's unclear: Where the D-08 comparison script lives (is it a standalone script or driven through `BacktestService`?), and whether the sentiment signal can be derived post-hoc from stored `agent_audit_trail` records or requires a replay
   - Recommendation: Create `scripts/compare_sentiment_backtest.py` that runs `run_walkforward()` twice: once with positions unchanged (DISABLED) and once with positions zeroed where `senti.veto=True` (ENABLED). This avoids touching `walkforward.py`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL (pgvector) | `find_nearest()` HNSW | Assumed available (Docker) | — | Integration tests skip |
| `httpx` | CryptoPanicAdapter | ✓ | ≥0.27 (pyproject.toml) | — |
| `voyageai` | `LLMClient.embed()` | ✓ | ≥0.2 (pyproject.toml) | — |
| CryptoPanic API | `CryptoPanicAdapter.fetch_articles()` | Unknown (no local test) | — | Mock fixture in tests |
| Anthropic API | `LLMClient.messages_create()` | ✓ (existing agents use it) | — | Fixture mode in CI |

**Missing dependencies with no fallback:** None that block coding.
**Missing dependencies with fallback:** CryptoPanic API — tests use static JSON fixture, not live API.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.1+ with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest backend/tests/unit/application/test_analyst_agents.py -q` |
| Full suite command | `pytest backend/tests/ -q --cov=backend --cov-fail-under=80` |
| Async mode | `asyncio_mode = "auto"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-4-01 | CryptoPanicAdapter parses JSON correctly | unit | `pytest backend/tests/unit/infrastructure/test_cryptopanic_adapter.py -x` | ❌ Wave 0 |
| REQ-4-02 | ingest_cryptopanic() stores articles with source=CRYPTOPANIC | unit | `pytest backend/tests/unit/application/test_news_ingestion_cryptopanic.py -x` | ❌ Wave 0 |
| REQ-4-03 | NewsArticle accepts source=CRYPTOPANIC | unit | `pytest backend/tests/unit/domain/entities/test_news_article.py -x` | ❌ Wave 0 (modify existing) |
| REQ-4-04 | find_nearest() returns url in NewsRetrievalResult | unit | `pytest backend/tests/unit/domain/entities/test_news_retrieval_result.py -x` | ❌ Wave 0 |
| REQ-4-05 | SentimentAnalystAgent.analyze() returns SentimentView with score/veto/sources | unit | `pytest backend/tests/unit/application/test_analyst_agents.py::TestSentimentAnalystAgent -x` | ✅ (replace) |
| REQ-4-06 | SentimentLLMOutput validates news_surprise: bool + reasoning: str | unit | `pytest backend/tests/unit/domain/schemas/test_agent_schemas.py -x` | ❌ Wave 0 |
| REQ-4-07 | D-03 score formula: 8 boundary value tests | unit | `pytest backend/tests/unit/application/test_sentiment_score_formula.py -x` | ❌ Wave 0 |
| REQ-4-08 | _synthesize() veto → HOLD under SENTIMENT_ENABLED=true | unit | `pytest backend/tests/integration/test_agent_mandatory_suite.py -x` | ✅ (extend) |
| REQ-4-09 | settings.sentiment_enabled reads SENTIMENT_ENABLED env var | unit | `pytest backend/tests/unit/test_settings.py -x` | ❌ Wave 0 |
| REQ-4-10 | Backtest comparison produces Sharpe/Calmar for both modes | integration | `pytest backend/tests/integration/test_backtest_sentiment_comparison.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/unit/ -q`
- **Per wave merge:** `pytest backend/tests/ -q --cov=backend --cov-fail-under=80`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/unit/infrastructure/test_cryptopanic_adapter.py` — covers REQ-4-01
- [ ] `backend/tests/unit/application/test_news_ingestion_cryptopanic.py` — covers REQ-4-02
- [ ] `backend/tests/unit/domain/entities/test_news_retrieval_result.py` — covers REQ-4-04 (url field)
- [ ] `backend/tests/unit/domain/schemas/test_agent_schemas.py` — covers REQ-4-06 (SentimentLLMOutput)
- [ ] `backend/tests/unit/application/test_sentiment_score_formula.py` — covers REQ-4-07
- [ ] `backend/tests/unit/test_settings.py` (or extend existing) — covers REQ-4-09
- [ ] `backend/tests/integration/test_backtest_sentiment_comparison.py` — covers REQ-4-10

---

## Security Domain

`security_enforcement` not explicitly set to false — treating as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user auth in this phase |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No new endpoints |
| V5 Input Validation | yes | Pydantic `SentimentLLMOutput.model_validate()` on all LLM output |
| V6 Cryptography | no | No new crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM prompt injection via news article content | Tampering | RAG chunks passed as structured data in system prompt; LLM output schema (Pydantic) validates result |
| CryptoPanic API returning malformed JSON | Tampering | `json.loads()` wrapped in try/except; adapter returns `[]` on parse failure |
| Score hallucination (LLM inventing numeric score) | Tampering | D-04 design: LLM only produces `news_surprise: bool`; score computed deterministically after LLM call |
| Vote stuffing (inflated CryptoPanic votes) | Elevation of Privilege | Score is capped to `[-1, 1]`; veto threshold `score < -0.3` is hard-coded constant |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CryptoPanic `auth_token=free` returns a public feed without registration | Standard Stack / CryptoPanicAdapter | Adapter fails immediately; need to register for actual auth token |
| A2 | `votes` field in CryptoPanic response always contains `positive` and `negative` int subfields | CryptoPanicAdapter pattern | `votes.get("positive", 0)` fallback to 0 handles missing keys; minimal risk |
| A3 | CryptoPanic free tier rate limit is 5 req/sec (same as paid plans) | Open Questions | If lower, daily ingestion of 10 coins could hit limit; add `asyncio.sleep(0.2)` between coin fetches as mitigation |
| A4 | `String(10)` ORM column length is a hard constraint (PostgreSQL VARCHAR(10)) | Runtime State / Blocker 4 | If PostgreSQL silently truncates instead of erroring, `source="CRYPTOPANIC"` becomes `source="CRYPTOPAN"` — articles not retrievable by source filter |

---

## Sources

### Primary (HIGH confidence)
- `backend/application/agents/sentiment_analyst_agent.py` — V4-3 stub body, constructor, fallback [VERIFIED]
- `backend/application/services/news_ingestion_service.py` — `DEFAULT_FEEDS` structure, `ingest_all()`, `_ingest_feed()` [VERIFIED]
- `backend/application/services/news_retrieval_service.py` — `retrieve()` signature: `(query, k=5, ticker=None)` [VERIFIED]
- `backend/application/agents/signal_director.py` — `_synthesize()` body, `_W_SENTIMENT`, call site `senti_agent.analyze(coin, {})` [VERIFIED]
- `backend/domain/schemas/agent_schemas.py` — `SentimentView` fields confirmed frozen [VERIFIED]
- `backend/domain/entities/news_article.py` — `_VALID_SOURCES = frozenset({"NZZ", "SRF"})` BLOCKER confirmed [VERIFIED]
- `backend/domain/entities/news_retrieval_result.py` — no `url` field BLOCKER confirmed [VERIFIED]
- `backend/infrastructure/persistence/repositories/news_repository.py` — `find_nearest()` SQL missing `nd.url` [VERIFIED]
- `backend/infrastructure/adapters/rss_news_adapter.py` — retry pattern to copy [VERIFIED]
- `backend/config.py` — no `sentiment_enabled` field exists yet [VERIFIED]
- `pyproject.toml` — all required packages present, no new installs needed [VERIFIED]
- `backend/alembic/versions/0014_create_news_tables.py` — `source VARCHAR(10)` overflow risk [VERIFIED]
- `backend/tests/unit/application/test_analyst_agents.py` — existing test patterns [VERIFIED]
- `backend/tests/integration/test_agent_mandatory_suite.py` — D-06 mandatory suite [VERIFIED]

### Secondary (MEDIUM confidence)
- CryptoPanic API votes structure: `votes.positive`, `votes.negative`, `currencies[].code` — confirmed via guilyx/cryptopanic Python wrapper + roccomuso Node.js wrapper source code [CITED: github.com/guilyx/cryptopanic, github.com/roccomuso/cryptopanic]
- CryptoPanic endpoint `https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies={coin}&kind=news` — confirmed via glanceapp community widget README [CITED: github.com/glanceapp/community-widgets]
- Rate limit ~5 req/sec — from WebSearch result aggregate [MEDIUM]

### Tertiary (LOW confidence — marked [ASSUMED])
- A1, A3: CryptoPanic free tier behavior (no official docs retrieved due to 403 on developer portal)

---

## Metadata

**Confidence breakdown:**
- Blockers (4 critical gaps): HIGH — verified directly in source files
- Standard stack (no new packages): HIGH — pyproject.toml verified
- CryptoPanic API votes structure: MEDIUM — multiple unofficial wrappers agree
- Architecture patterns: HIGH — derived from verified codebase
- TDD mapping: HIGH — based on verified test patterns in existing test files
- Free tier rate limit: LOW — not officially documented; cross-referenced from multiple sources

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (30 days for stable infra; CryptoPanic API may change sooner)
