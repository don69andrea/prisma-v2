# Phase 3: V4-3 Agentic Layer - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the LLM Agentic Layer on top of the deterministic Signal Engine. Six new agents + one new REST
endpoint. Agents *interpret, debate, and explain* Signal-Engine outputs — they compute nothing
themselves. All numbers come from Tools or the engine; all outputs are Pydantic-validated.

**In scope:**
- `TechnicalAnalystAgent` — reads indicator state from engine, returns `TechnicalView` (Haiku)
- `OnChainAnalystAgent` — reads MVRV-Z / network health from Tools, returns `OnChainView` (Haiku)
- `SentimentAnalystAgent` — stub reading Fear&Greed from `market_sentiment` table; RAG slots empty (Haiku)
- `BullResearchAgent` + `BearResearchAgent` — deliberately one-sided theses; both always persisted in audit trail (Sonnet)
- `RiskAgent` — veto/cap; portfolio exposure from Store/Tool NEVER from LLM memory (Sonnet)
- `SignalDirector` — hybrid orchestration (see D-03); synthesizes to `TradeSignal` with HITL checkpoint (Sonnet)
- New `MacroRegimeAgent` (LLM, crypto-focused, separate from existing `MacroIntelligenceAgent`) (Haiku)
- New `agent_audit_trail` DB table + Alembic migration (append-only, immutable)
- REST endpoint `GET /api/v1/agent-signal/{coin}` → `TradeSignal`
- All §6 AGENTS.md mandatory tests green; Coverage ≥ 80 %

**Out of scope:**
- Real News/RAG for SentimentAnalystAgent (Phase V4-4)
- UI display of audit trail (Phase V4-5)
- Auto-trading or live order execution (NEVER — decision-support only)
- Changes to SMI agents (SteuerAgent, portfolio_agent, existing MacroIntelligenceAgent)
- Meta-labeling integration into agents (already done in V4-2, optionally consumed via engine signal)

</domain>

<decisions>
## Implementation Decisions

### D-01: Agent Orchestration Pattern — Hybrid

Analysts (`TechnicalAnalystAgent`, `OnChainAnalystAgent`, `SentimentAnalystAgent`, `MacroRegimeAgent`)
run as **Python async functions in parallel** — each agent does its own LLM call but is invoked via
`asyncio.gather()` at the Python level. No LLM tool-use API needed at the orchestration layer.

Bull/BearResearchAgent and the final synthesis (`SignalDirector.synthesize()`) + `RiskAgent.assess()`
use **real Claude Tool-Use API loops** — the LLM literally calls tools (e.g., `get_engine_signal`,
`get_portfolio_exposure`) to retrieve data, which enforces the "LLM never invents a number" rule.

```
SignalDirector.run(coin):
  [Python-level parallel]
  engine_signal = await SignalEngine.evaluate(coin)  # deterministisch
  tech, onchain, senti, macro = await asyncio.gather(
      TechnicalAnalystAgent.analyze(engine_signal.sub_scores),
      OnChainAnalystAgent.analyze(coin),
      SentimentAnalystAgent.analyze(coin),           # stub: F&G only
      MacroRegimeAgent.get_regime(),                 # cached 1h
  )
  [LLM Tool-Use API loops]
  bull  = await BullResearchAgent.build_case(tech, onchain, senti, macro, engine_signal)
  bear  = await BearResearchAgent.build_case(tech, onchain, senti, macro, engine_signal)
  risk  = await RiskAgent.assess(coin, engine_signal)          # veto/cap
  [Python synthesis → TradeSignal]
  signal = _synthesize(bull, bear, engine_signal, risk)        # weighted Pydantic assembly
  if signal.confidence < 0.65: await checkpoint(user)          # HITL
  await _persist_audit_trail(coin, tech, onchain, senti, macro, bull, bear, risk, signal)
  return signal
```

### D-02: Audit Trail Persistence — New DB Table, Append-Only / Immutable

New table `agent_audit_trail`:
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
coin        VARCHAR NOT NULL
asof        DATE NOT NULL
agent_run   JSONB NOT NULL    -- {tech_view, onchain_view, senti_view, macro_regime,
                              --  bull_case, bear_case, risk_verdict, trade_signal}
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

**Immutability contract:** NO UPDATE, NO DELETE on this table — ever. Every new agent run inserts a
new row. Application layer enforces this (no `update` method on repo). Test asserts that calling
`insert()` twice creates two rows. Migration adds a DB-level trigger (or comment if trigger not
supported on SQLite test DB).

Audit trail is referenced via `TradeSignal.audit_trail_id: UUID`.

### D-03: MacroRegimeAgent — New LLM Agent (Crypto-Focused)

Build new `backend/application/agents/macro_regime_agent.py` with:
```python
Tools: get_us_realrate() → {ffr, cpi, real_rate}
       get_dxy() → {index, trend_30d}
       get_btc_risk_correlation() → {corr_spy_30d, risk_on_regime: bool}
       get_fear_greed() → {value, classification, trend_7d}
Output: MacroRegime{
    regime: Literal["RISK_ON", "NEUTRAL", "RISK_OFF"],
    drivers: list[str], confidence: 0..1, reasoning: str(≤2 sentences)}
```

Model: `claude-haiku-4-5-20251001` (fast, cheap — regime doesn't change intraday).
Cache: 1h TTL (regime changes slowly). Existing `MacroIntelligenceAgent` (SMI) is untouched.

### D-04: SentimentAnalystAgent Stub — Fear&Greed from DB

Stub reads real Fear&Greed from `market_sentiment` table (already seeded in V4-1):
```python
Output: SentimentView{
    coin,
    score: float(-1..1),   # Fear&Greed normalized: (fg_value - 50) / 50
    regime: "FEAR"|"NEUTRAL"|"GREED",
    news_surprise: None,   # RAG pending V4-4
    veto: False,           # no veto in stub
    reasoning: "Fear&Greed index {fg_value} ({fg_classification}). News-RAG: V4-4 pending.",
    sources: []            # RAG pending V4-4
}
```

This satisfies the "all numbers from Tools" iron rule immediately (real data from DB, not invented).
V4-4 replaces the stub body with real pgvector RAG, keeping the same `SentimentView` Pydantic schema.

### D-05: Pydantic Schemas (New)

```python
# backend/domain/schemas/agent_schemas.py  (new file)

class TechnicalView(BaseModel):
    coin: str
    stance: Literal["BULLISH", "NEUTRAL", "BEARISH"]
    consensus: str  # e.g. "3/3", "2/3"
    key_signals: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str  # ≤ 3 sentences

class OnChainView(BaseModel):
    coin: str
    valuation: Literal["CHEAP", "FAIR", "EXPENSIVE"]
    network_health: Literal["STRONG", "NEUTRAL", "WEAK"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

class SentimentView(BaseModel):
    coin: str
    score: float = Field(ge=-1.0, le=1.0)
    regime: Literal["FEAR", "NEUTRAL", "GREED"]
    news_surprise: bool | None = None
    veto: bool = False
    reasoning: str
    sources: list[str] = []

class MacroRegime(BaseModel):
    regime: Literal["RISK_ON", "NEUTRAL", "RISK_OFF"]
    drivers: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

class BullCase(BaseModel):
    thesis: str
    strongest_points: list[str]
    risks_acknowledged: list[str]

class BearCase(BaseModel):
    thesis: str
    strongest_points: list[str]
    counter_to_bull: list[str]

class RiskVerdict(BaseModel):
    approve: bool
    max_size: float = Field(ge=0.0, le=1.5)
    breaches: list[str]
    reasoning: str

class TradeSignal(BaseModel):
    coin: str
    action: Literal["BUY", "HOLD", "SELL"]   # SELL = cash (exposure 0), NEVER short
    size_factor: float = Field(ge=0.0, le=1.5)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale_by_layer: dict[str, str]        # {"technical": ..., "onchain": ..., "sentiment": ..., "macro": ..., "bull": ..., "bear": ..., "risk": ...}
    audit_trail_id: UUID
    disclaimer: str = "Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading."
```

### D-06: Mandatory Tests (§6 AGENTS.md — all 7 required before merge)

1. **Hallucinations-Guard**: Every number in agent output == corresponding Engine/Tool number (Diff < 1e-9). Implemented via monkeypatch + assertion on all float fields.
2. **State-from-Tool**: RiskAgent reads exposure from mocked Store; test asserts no value appears from LLM memory (prompt inspection).
3. **Minority-Protection**: Scenario with 1 strong Bear vs 3 Bulls → audit trail CONTAINS Bear case; RiskAgent CAN overrule.
4. **Fallback**: LLM raises Exception → TradeSignal still returned (from deterministic engine_signal), confidence lowered, disclaimer set.
5. **Pydantic Schema**: All agent outputs schema-validated; no freetext in any field.
6. **Checkpoint**: confidence < 0.65 → exactly one HITL call, ≤4 options presented (UI constraint from existing Checkpoint pattern).
7. **No-Shorting**: action == "SELL" → size_factor == 0.0 AND RiskVerdict.max_size == 0.0; never negative.

### D-07: REST Endpoint (Phase 3)

`GET /api/v1/agent-signal/{coin}` → `TradeSignal`

- Triggers full SignalDirector pipeline (Engine → Analysts → Bull/Bear → Risk → Synthesis)
- Read-only GET (no side effects except persisting audit trail)
- asyncio.to_thread() for sync ML calls within the pipeline
- Returns 404 if coin not in universe, 503 if LLM unavailable (fallback still works via D-01 Fallback)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Iron Rules
- `docs/PRISMA_V4_AGENTS.md` — PRIMARY SPEC for this phase: agent list, tool signatures, Pydantic schemas, §0 iron rule, §6 mandatory tests, §7 build order, §8 forbidden patterns. MUST READ.
- `docs/PRISMA_V4_PROJEKTPLAN.md` — V4 overall plan, architecture diagram (Daten→Engine→Agenten→UI)
- `AGENTS.md` — Repo rules: Spec-First, Test-First, Pydantic, Coverage ≥80%, no direct push to develop/main
- `CLAUDE.md` — Claude Code conventions (asyncio.to_thread, no run_in_executor, retry pattern, etc.)

### Gold Standard Patterns (copy, don't reinvent)
- `backend/application/agents/steuer_agent.py` — GOLD STANDARD pattern: constructor injection, Tool-Use loop, Pydantic output, deterministic fallback, mandatory disclaimer
- `backend/application/agents/macro_agent.py` — pure-Python agent pattern (contrast with new LLM agents)
- `backend/infrastructure/llm/client.py` — LLMClient usage pattern (tool_use, caching, model selection)
- `backend/infrastructure/llm/prompts/prompt_loader.py` — PromptTemplateLoader pattern

### Signal Engine (agents read from here, never write)
- `backend/application/signals/signal_service.py` — `evaluate(coin, asof, prices_df, ...) → SignalVector`; agents call this as their primary data source
- `backend/interfaces/rest/schemas/signals.py` — `SignalVector`, `BacktestReport`, `MetaLabelReport` — what the engine produces
- `backend/application/signals/indicators.py` — indicator values that TechnicalAnalystAgent interprets
- `backend/application/signals/factors.py` — momentum_rank, onchain_health_score

### Database / Persistence
- `backend/infrastructure/persistence/models/` — existing ORM model patterns (copy for agent_audit_trail)
- `backend/alembic/versions/` — latest migration: 0040; next migration for audit trail: 0041
- `backend/infrastructure/persistence/repositories/` — repository pattern to follow

### Existing Router / Schema Patterns
- `backend/interfaces/rest/routers/signals.py` — REST router pattern to extend (add agent-signal endpoint)
- `backend/interfaces/rest/schemas/signals.py` — existing Pydantic schema pattern

### Test Patterns
- `backend/tests/unit/application/` — unit test structure (copy for new agents)
- `backend/tests/unit/application/test_meta_label.py` — example of monkeypatch + Pydantic validation tests
- `pyproject.toml` — pytest config, coverage settings (fail_under=80)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SteuerAgent`: entire constructor-injection + fallback pattern copied verbatim for each new agent
- `LLMClient`: already handles tool_use loop, caching, model selection — agents call it directly
- `PromptTemplateLoader`: existing Jinja2 prompt system — create `backend/infrastructure/llm/prompts/` templates for each new agent
- Existing `checkpoint` pattern from `InvestmentDirector` / existing director (check `backend/application/agents/`) for HITL — reuse for `confidence < 0.65` gate
- `market_sentiment` table: already seeded with Fear&Greed — SentimentAnalystAgent stub reads from here

### Established Patterns
- `asyncio.to_thread()` for ALL sync ML calls (mandatory per CLAUDE.md)
- Retry: `_RETRIES = 2`, `_BASE_DELAY = 1.0`, exponential backoff — copy from `YFinanceSwissAdapter`
- All Pydantic models use `from __future__ import annotations` + `Field(ge=..., le=...)`
- Prompt-caching: `cache_control: ephemeral` on repeated system prompts (mandatory for long system prompts)
- Model constants: `_MODEL_FAST = "claude-haiku-4-5-20251001"`, `_MODEL_SYNTH = "claude-sonnet-4-6"`

### Integration Points
- `backend/interfaces/rest/routers/signals.py` → add `GET /api/v1/agent-signal/{coin}` to existing signals router
- `backend/alembic/versions/` → migration 0041 for `agent_audit_trail` table
- `backend/infrastructure/persistence/models/` → new `AgentAuditTrail` ORM model
- `backend/infrastructure/persistence/repositories/` → new `AgentAuditTrailRepository` (insert-only, no update/delete)
- `backend/interfaces/rest/app.py` → no changes needed (router already included)

</code_context>

<specifics>
## Specific Requirements from Discussion

1. **Audit Trail is immutable** — append-only. No UPDATE/DELETE API, no `.update()` method on repo. Every agent run creates a new row. A test must assert that two calls create two distinct rows (not overwritten).
2. **Hybrid orchestration** — Analysts parallel via `asyncio.gather()` in Python; Bull/Bear + Risk via LLM Tool-Use API; synthesis in Python (weighted Pydantic assembly, not LLM free-form).
3. **MacroRegimeAgent is NEW** (not extending existing MacroIntelligenceAgent). Existing SMI MacroIntelligenceAgent is UNTOUCHED.
4. **SentimentAnalystAgent stub uses real Fear&Greed data** (not hardcoded NEUTRAL). Interface identical to final V4-4 version — only stub body differs.
5. **No-Shorting**: Tests must assert size_factor == 0.0 when action == "SELL", never negative.

</specifics>

<deferred>
## Deferred Ideas

- Real News/RAG for SentimentAnalystAgent → **Phase V4-4**
- UI rendering of audit trail / reasoning chain → **Phase V4-5**
- EvaluationAgent (interprets live performance metrics) → **Phase V4-6**
- Trust-Scores and agent performance tracking → **Phase V4-6**
- MacroRegimeAgent connecting to live FRED / DXY feeds (currently mock/tool stubs) → **Phase V4-4 or V4-6**
- Auto-advance of TradeSignal to execution → **NEVER** (Decision-Support only)

</deferred>

---

*Phase: 3 - V4-3 Agentic Layer*
*Context gathered: 2026-06-21*
