# Phase 4: V4-4 RAG Sentiment - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Upgrade `SentimentAnalystAgent` from the Fear&Greed-only stub (V4-3, D-04) to a real
Krypto-News-RAG-powered sentiment system. CryptoPanic articles are ingested into the
existing `news_chunks` pgvector table, embedded with Voyage-3-large, and retrieved
per-coin via HNSW. The LLM interprets chunks to produce `news_surprise: bool` + `reasoning`.
`score` and `veto` are computed deterministically. Sentiment feeds into `TradeSignal` as a
functional FEATURE (downside-only size scaling) and VETO (action override to HOLD).
A walk-forward backtest measures whether sentiment helps or hurts — honestly reported in
`docs/PRISMA_V4_FORTSCHRITT.md`.

**In scope:**
- `CryptoPanicAdapter` — new infra adapter that fetches JSON from CryptoPanic free API
- Extend `NewsIngestionService.DEFAULT_FEEDS` with CryptoPanic (source=`'CRYPTOPANIC'`)
- `SentimentAnalystAgent.analyze()` body: RAG retrieval → score (deterministic vote-ratio)
  → LLM call for `news_surprise` only → `veto` via Python rule-set → `SentimentView`
- Fallback: if CryptoPanic corpus empty/too old → Fear&Greed fallback (existing stub logic)
- `SignalDirector._synthesize()` wiring: veto overrides action; score scales size (downside-only)
- `SENTIMENT_ENABLED` env-var flag (default `false`) guards both veto and size-scaling
- Walk-forward backtest comparison (SENTIMENT_ENABLED=true vs false), Sharpe/Calmar/MaxDD
- Honest reporting in `docs/PRISMA_V4_FORTSCHRITT.md`
- New `sentiment_analyst.de.md.j2` prompt template for LLM call (news_surprise + reasoning only)
- Tests: RAG retrieval works, score formula, veto rule, fallback, Pydantic schema, sources persist

**Out of scope:**
- New DB tables for crypto news (reuse existing `news_documents`/`news_chunks`)
- UI display of sentiment / audit trail (Phase V4-5)
- Real-time ingestion (Phase V4-4 uses scheduled daily; faster ingestion deferred)
- CoinDesk RSS or other sources (CryptoPanic free API is the only source in V4-4)
- `SENTIMENT_ENABLED=true` as production default (gated behind backtest result)
- SMI/3a agents (untouched)
- Auto-trading or live order execution (NEVER)

</domain>

<decisions>
## Implementation Decisions

### D-01: Crypto News Source — CryptoPanic Free API

`CryptoPanicAdapter` fetches `GET https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies={coin}&kind=news`
JSON response, no auth token required for public feed. Up to 50 articles per run.
CryptoPanic articles include `votes: {positive, negative, ...}` and `currencies` tags (direct coin-ticker
mapping — no TickerNer needed for crypto).

### D-02: Ingestion Schedule — Daily, Before Signal-Run

News ingestion runs **daily, ordered directly before signal generation** (same morning batch).
This ensures the corpus is fresh at signal-time. Dedup via `url_hash` (existing pattern) prevents
re-embedding. Soft-TTL: only ingest articles published in the last 7 days; retrieval also filters
on `published_at > now()-7d`. Fallback to Fear&Greed if corpus is empty or all articles > 7d.

Corpus size: 50 articles per coin per ingestion run (CryptoPanic free API limit per page).

### D-03: Score Formula — CryptoPanic Votes-Ratio + F&G Fallback

Score is **deterministically** computed in Python — never from LLM:

```python
# Primary: CryptoPanic votes
positive = sum(a.votes.get("positive", 0) for a in recent_articles)
negative = sum(a.votes.get("negative", 0) for a in recent_articles)
score_news = (positive - negative) / max(1, positive + negative)  # → -1..1

# F&G normalization
fg_norm = (fg_value - 50) / 50  # → -1..1

# Blend (when ≥5 articles with votes available):
score = 0.7 * score_news + 0.3 * fg_norm

# Fallback (<5 articles): score = fg_norm
```

### D-04: LLM Role — news_surprise + reasoning Only

The LLM receives: RAG chunks (k=5 retrieved by HNSW for the coin) + current Fear&Greed value.
It returns **only**:
```python
class SentimentLLMOutput(BaseModel):
    news_surprise: bool   # True if meaningful new event detected (hack, regulation, partnership)
    reasoning: str        # ≤ 3 sentences
```
`score`, `veto`, `regime`, and `sources` are all computed deterministically **after** the LLM call.
This respects the §0 Iron Rule: LLM never produces a number.

### D-05: Veto Trigger — Deterministic Python Rule-Set

```python
# Thresholds — configurable constants, not in prompt
_VETO_SCORE_THRESHOLD = -0.3
_VETO_FEAR_THRESHOLD = -0.2  # F&G already defines FEAR at -0.2 (see sentiment_analyst_agent.py)

veto: bool = (
    regime == "FEAR"           # score < _FEAR_THRESHOLD (-0.2)
    and news_surprise == True  # LLM detected a meaningful new event
    and score < _VETO_SCORE_THRESHOLD  # score < -0.3
)
```

The LLM is **not informed** about veto thresholds in the prompt — it only judges `news_surprise`.

### D-06: Veto Wiring in SignalDirector._synthesize()

Two functional changes behind `SENTIMENT_ENABLED` env flag (default `false`):

**1. Action override (hard veto):**
```python
if settings.sentiment_enabled and senti.veto:
    action = "HOLD"  # block BUY; SELL is never upgraded
```

**2. Downside-only size scaling:**
```python
if settings.sentiment_enabled and senti.score < 0:
    size_factor = size_factor * (1 + senti.score * 0.3)
    size_factor = max(0.0, size_factor)  # no shorting
    # Note: positive score does NOT amplify size (clamp at 1× original)
```

Both changes only activate when `SENTIMENT_ENABLED=true`. When false, behavior is
identical to V4-3 stub (size unchanged, no veto override).

### D-07: Corpus Structure — Reuse Existing Tables

Use existing `news_documents` + `news_chunks` tables with `source='CRYPTOPANIC'`.
All existing infra (`NewsRepository`, `NewsIngestionService`, `NewsRetrievalService`) reused
without modification — only a new `CryptoPanicAdapter` feeds into `NewsIngestionService`
alongside the existing `RssNewsAdapter`.

`tickers: list[str]` field in `news_documents` is populated from CryptoPanic `currencies` tags
(e.g., `["BTC", "ETH"]`) — no TickerNer pass needed.

Retrieval: `NewsRetrievalService.retrieve(query=f"{coin} crypto sentiment news", k=5, ticker=coin)`
returns coin-specific chunks.

**sources** (RAG-Nachweis/Citations): `SentimentView.sources` populated with article URLs from
the retrieved chunks. Persisted in `agent_audit_trail.agent_run` JSONB automatically (D-02 Phase 3).

### D-08: Backtest Measurement — Honest Sentiment Impact

Walk-forward backtest runs **twice** under identical conditions:
1. `SENTIMENT_ENABLED=false` — baseline (same as V4-1/V4-2 signal)
2. `SENTIMENT_ENABLED=true` — sentiment-enhanced

Compare: Sharpe, Calmar, MaxDD, Hit-Rate, # trades vetoed.

**Ehrlichkeits-Regel (wie Meta-Labeling):**
- If sentiment improves Sharpe/Calmar AND reduces MaxDD → enable as production default
- If sentiment is neutral or damages performance → `SENTIMENT_ENABLED=false` stays default;
  optional veto-only mode documented; **honest result documented in `docs/PRISMA_V4_FORTSCHRITT.md`**
- NO overoptimization of thresholds to make backtest look good

### D-09: CryptoPanic Ingestion — Separate Method (Overrides DEFAULT_FEEDS Reference)

CONTEXT.md `canonical_refs` and `code_context` originally referenced "add CryptoPanic to
DEFAULT_FEEDS". RESEARCH.md Blocker B-03 identified that `DEFAULT_FEEDS` is a
`list[tuple[str, str]]` (source_name, feed_url) structure that assumes RSS. CryptoPanic has no
feed URL; injecting it as a tuple would break the existing `ingest_all()` loop.

Decision: use a separate `async def ingest_cryptopanic(self, coins: list[str]) -> int` method on
`NewsIngestionService`. This is the lower-risk approach and is implemented in plan 04-04. The
original DEFAULT_FEEDS reference in `canonical_refs`/`code_context` is superseded by this
decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Iron Rules
- `docs/PRISMA_V4_AGENTS.md` §3.3 — SentimentAnalystAgent spec: Tool signatures, SentimentView schema, §0 Iron Rule. PRIMARY SPEC.
- `docs/PRISMA_V4_PROJEKTPLAN.md` — V4 overall plan, architecture (Daten→Engine→Agenten→UI), RAG-Vorgabe
- `AGENTS.md` — Repo rules: Spec-First, Test-First, Pydantic, Coverage ≥80%, no direct push
- `CLAUDE.md` — asyncio.to_thread, no run_in_executor, retry pattern

### Existing Stub (to upgrade — NOT replace from scratch)
- `backend/application/agents/sentiment_analyst_agent.py` — V4-3 Fear&Greed stub; SentimentView interface FROZEN; V4-4 replaces stub body only
- `backend/domain/schemas/agent_schemas.py` — `SentimentView` Pydantic schema (frozen, do NOT change)
- `backend/application/agents/signal_director.py` — `_synthesize()` and `_W_SENTIMENT` — modify for D-06 veto wiring
- `backend/infrastructure/llm/prompts/sentiment_analyst.de.md.j2` — existing V4-3 prompt; V4-4 updates this for RAG chunks input

### Existing News-RAG Infra (reuse, do NOT rebuild)
- `backend/application/services/news_ingestion_service.py` — NewsIngestionService with DEFAULT_FEEDS; add CryptoPanic via separate ingest_cryptopanic() method (see D-09)
- `backend/application/services/news_retrieval_service.py` — NewsRetrievalService (Voyage-3-large, HNSW)
- `backend/domain/repositories/news_repository.py` — NewsRepository port (find_nearest with ticker filter)
- `backend/domain/entities/news_chunk.py` + `backend/domain/entities/news_article.py` — domain entities
- `backend/infrastructure/persistence/repositories/news_repository.py` — infra impl (reuse unchanged)
- `backend/infrastructure/persistence/models/news.py` — NewsDocumentORM + NewsChunkORM (reuse unchanged)
- `backend/alembic/versions/0014_create_news_tables.py` — news_documents + news_chunks schema

### Gold Standard Adapter Pattern (copy for CryptoPanicAdapter)
- `backend/infrastructure/adapters/rss_news_adapter.py` — RssNewsAdapter pattern: retry/backoff, httpx, dataclass RawArticle
- `backend/infrastructure/adapters/ticker_ner.py` — TickerNer (NOT needed for CryptoPanic — currencies tags used instead)

### Signal Engine (agents read from here, never write)
- `backend/application/agents/signal_director.py` — `_synthesize()` function — modify `_W_SENTIMENT` usage and add veto logic
- `backend/application/signals/signal_service.py` — `evaluate()` — understand engine_signal structure

### Persistence (audit trail — sources persist automatically)
- `backend/alembic/versions/0041_agent_audit_trail.py` — `agent_audit_trail` table; `agent_run` JSONB stores full SentimentView (incl. sources)
- `backend/infrastructure/persistence/repositories/agent_audit_trail_repository.py` — repo for audit trail

### Test Patterns
- `backend/tests/unit/application/test_analyst_agents.py` — unit test pattern for analyst agents (D-06 guards)
- `backend/tests/integration/test_agent_mandatory_suite.py` — mandatory D-06 test suite (all 7 guards must stay green)
- `pyproject.toml` — pytest config, coverage settings (fail_under=80)

### Honest Reporting
- `docs/PRISMA_V4_FORTSCHRITT.md` — where backtest results (with/without sentiment) are documented honestly

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NewsIngestionService` + `NewsRepository` + `NewsRetrievalService`: fully functional; only new CryptoPanic feed needed as input source
- `RssNewsAdapter`: pattern to copy for `CryptoPanicAdapter` (httpx, retry/backoff, `RawArticle` dataclass)
- `SentimentAnalystAgent` stub body: replace body, keep constructor signature, keep `SentimentView` output
- `LLMClient`: existing `messages_create()` with Pydantic-output pattern (see `steuer_agent.py` for Tool-Use pattern)
- `PromptTemplateLoader`: existing Jinja2 system; update `sentiment_analyst.de.md.j2`
- `agent_audit_trail` JSONB: `senti_view` already stored automatically by SignalDirector (sources included)

### Established Patterns
- `asyncio.to_thread()` for all sync operations (CLAUDE.md mandatory)
- Retry: `_RETRIES = 2`, `_BASE_DELAY = 1.0`, exponential backoff (copy from `RssNewsAdapter`)
- All Pydantic models: `from __future__ import annotations` + `Field(ge=..., le=...)`
- Prompt-caching: `cache_control: ephemeral` on repeated system prompts
- Model: `claude-haiku-4-5-20251001` for SentimentAnalystAgent (fast, cheap)
- Dedup pattern: `url_hash` unique constraint (idempotent ingestion)
- CryptoPanic `currencies` tags → `tickers[]` field (no TickerNer pass needed)

### Integration Points
- `NewsIngestionService` → add CryptoPanic via separate `ingest_cryptopanic(coins)` method (D-09; NOT via DEFAULT_FEEDS — see D-09)
- `SentimentAnalystAgent.__init__` → inject `NewsRetrievalService` + `LLMClient` + `db_session`
- `SignalDirector.__init__` → `senti_agent` already injected; `_synthesize()` gets veto logic
- `backend/config.py` → add `sentiment_enabled: bool = False` (reads from `SENTIMENT_ENABLED` env var)
- Walk-forward backtest script → add `--sentiment` flag (or use env var)

</code_context>

<specifics>
## Specific Requirements from Discussion

1. **Score is ALWAYS deterministic** — CryptoPanic vote-ratio (0.7 weight) + F&G-norm (0.3 weight).
   Formula: `score = 0.7 * (positive-negative)/max(1,positive+negative) + 0.3 * (fg-50)/50`
   when ≥5 articles with votes; pure F&G fallback otherwise.

2. **LLM produces ONLY `news_surprise: bool` + `reasoning: str`** — Pydantic `SentimentLLMOutput` schema.
   Prompt: N RAG chunks for `{coin}` + `fear_greed_value`. No score, no veto, no regime in prompt output.

3. **Veto-Trigger rule** (deterministic Python, NOT prompt instruction):
   `veto = (regime == "FEAR" and news_surprise and score < -0.3)`. Threshold `_VETO_SCORE_THRESHOLD = -0.3`.

4. **Downside-only size scaling**: `size_factor *= (1 + min(0, score * 0.3))`. Positive score = no amplification.
   Clamp: `size_factor = max(0.0, size_factor)`.

5. **`SENTIMENT_ENABLED=false` default** — both veto and size-scaling guarded behind this flag.
   When false: behavior identical to V4-3 stub (score used only for confidence weighting, unchanged).

6. **Ingestion ordering**: CryptoPanic ingestion runs DIRECTLY BEFORE daily signal generation.
   7-day TTL (soft): ingest only articles `published_at > now() - 7d`; retrieval filters same.

7. **sources list** = URLs from retrieved `NewsChunk` objects (RAG-Nachweis/Citations).
   Populated in Python after retrieval, passed to `SentimentView.sources`. No extra persistence needed
   (automatically stored in `agent_audit_trail.agent_run` JSONB).

8. **Backtest honesty protocol** (same as Meta-Labeling): run 2× walk-forward, compare Sharpe/Calmar/MaxDD.
   If sentiment hurts/neutral → `SENTIMENT_ENABLED=false` stays default, document honestly in `FORTSCHRITT.md`.
   NO threshold-tuning to make backtest look good.

9. **Fallback chain**: 
   - RAG corpus available → CryptoPanic vote-ratio + LLM news_surprise → full SentimentView
   - RAG corpus empty/too old (>7d) → Fear&Greed fallback (existing stub logic), `news_surprise=None`, `veto=False`
   - LLM call fails → `news_surprise=None`, deterministic score from votes/F&G, `veto=False`

</specifics>

<deferred>
## Deferred Ideas

- Real-time CryptoPanic ingestion (every 30min) → if backtest shows value, **Phase V4-6 / operations**
- CoinDesk RSS or other news sources → backlog, revisit if CryptoPanic coverage insufficient
- UI display of sentiment score / news_surprise / sources → **Phase V4-5**
- EvaluationAgent using live sentiment metrics → **Phase V4-6**
- Trust-scores for SentimentAnalystAgent (accuracy over time) → **Phase V4-6**
- `SENTIMENT_ENABLED=true` as default → only after confirmed positive backtest result

</deferred>

---

*Phase: 4 - V4-4 RAG Sentiment*
*Context gathered: 2026-06-22*
