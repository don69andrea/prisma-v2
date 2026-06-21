# Phase 3: V4-3 Agentic Layer - Research

**Researched:** 2026-06-21
**Domain:** LLM Multi-Agent Orchestration, Claude Tool-Use API, SQLAlchemy JSONB, FastAPI async
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Agent Orchestration Pattern — Hybrid**
Analysts (TechnicalAnalystAgent, OnChainAnalystAgent, SentimentAnalystAgent, MacroRegimeAgent) run
as Python async functions in parallel via `asyncio.gather()`. Bull/BearResearchAgent + RiskAgent +
SignalDirector.synthesize() use real Claude Tool-Use API loops.

**D-02: Audit Trail Persistence — New DB Table, Append-Only / Immutable**
New table `agent_audit_trail`: id UUID PK, coin VARCHAR, asof DATE, agent_run JSONB, created_at
TIMESTAMPTZ. NO UPDATE, NO DELETE — ever. Two inserts = two rows (test-enforced).
Referenced via `TradeSignal.audit_trail_id: UUID`.

**D-03: MacroRegimeAgent — New LLM Agent (Crypto-Focused)**
New file `backend/application/agents/macro_regime_agent.py`. Existing MacroIntelligenceAgent is
UNTOUCHED. Tools: get_us_realrate, get_dxy, get_btc_risk_correlation, get_fear_greed.
Output: MacroRegime{regime: RISK_ON|NEUTRAL|RISK_OFF, drivers, confidence, reasoning}.
Model: claude-haiku-4-5-20251001. Cache: 1h TTL.

**D-04: SentimentAnalystAgent Stub — Fear&Greed from DB**
Reads real Fear&Greed from `market_sentiment` table. score = (fg_value - 50) / 50.
news_surprise=None, veto=False, sources=[]. Interface is final V4-4-compatible.

**D-05: Pydantic Schemas (New file: backend/domain/schemas/agent_schemas.py)**
TechnicalView, OnChainView, SentimentView, MacroRegime, BullCase, BearCase, RiskVerdict,
TradeSignal — all fully specified in CONTEXT.md.

**D-06: Mandatory Tests (§6 AGENTS.md — all 7 before merge)**
Hallucination-Guard, State-from-Tool, Minority-Protection, Fallback, Pydantic-Schema,
Checkpoint, No-Shorting.

**D-07: REST Endpoint**
GET /api/v1/agent-signal/{coin} → TradeSignal. 404 if unknown coin, 503 if LLM unavailable.

### Claude's Discretion
- Internal module organization within the agents (how to split tool-helper functions)
- Exact Jinja2 prompt template content and filenames
- Wave/task sequencing within the plan
- Whether to use in-memory cache for MacroRegime (TTL 1h) via functools or a module-level dict

### Deferred Ideas (OUT OF SCOPE)
- Real News/RAG for SentimentAnalystAgent (Phase V4-4)
- UI display of audit trail (Phase V4-5)
- EvaluationAgent / Trust-Scores (Phase V4-6)
- MacroRegimeAgent connecting to live FRED/DXY feeds (Phase V4-4 or V4-6)
- Auto-trading / live order execution (NEVER)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-3.1 | TechnicalAnalystAgent — reads indicator state → TechnicalView (Haiku) | SteuerAgent pattern; LLMClient.messages_create with json.loads output |
| REQ-3.2 | OnChainAnalystAgent — reads MVRV-Z/network health → OnChainView (Haiku) | Same pattern; tool stubs mirror signal_service sub_scores dict |
| REQ-3.3 | SentimentAnalystAgent stub — reads Fear&Greed from market_sentiment → SentimentView | market_sentiment table exists (migration 0039); SQLAlchemy async query |
| REQ-3.4 | MacroRegimeAgent — new LLM, crypto-focused, 1h cache → MacroRegime (Haiku) | New file; NOT extending MacroIntelligenceAgent |
| REQ-3.5 | BullResearchAgent + BearResearchAgent — Tool-Use loop → BullCase/BearCase (Sonnet) | Tool-Use pattern from universe_suggestion_service; Pydantic.model_json_schema() as tool input_schema |
| REQ-3.6 | RiskAgent — Tool-Use, veto/cap, exposure from Store/Tool → RiskVerdict (Sonnet) | State-from-Tool pattern; portfolio exposure via injected repository |
| REQ-3.7 | SignalDirector — hybrid Python+LLM orchestration → TradeSignal with HITL | asyncio.gather for analysts; Python-level weighted synthesis; confidence < 0.65 checkpoint |
| REQ-3.8 | New agent_audit_trail DB table + Alembic migration 0041 | Migration pattern from 0040; JSONB column; UUID PK with gen_random_uuid() |
| REQ-3.9 | GET /api/v1/agent-signal/{coin} → TradeSignal | signals.py router pattern; 404/503 error handling |
| REQ-3.10 | All 7 mandatory tests green; Coverage ≥ 80% | pytest.mark.unit; AsyncMock pattern from test_steuer_agent.py |
</phase_requirements>

---

## Summary

The V4-3 Agentic Layer builds 7 LLM agents on top of the existing deterministic Signal Engine. The
codebase already provides all required infrastructure: a working `LLMClient.messages_create()`,
the `SteuerAgent` as a gold-standard pattern for constructor injection + Pydantic output +
fallback, and the `UniverseSuggestionService` as the only existing example of Claude Tool-Use API
in production code. The Tool-Use pattern is single-turn (no loop needed) — the LLM is forced via
`tool_choice: {"type": "tool", "name": "..."}` to output exactly one structured call, which is
then extracted from `response.content` blocks where `block.type == "tool_use"`.

The audit trail table follows the `backtest_results` ORM model pattern (UUID PK, JSONB column,
append-only semantics). The next migration number is **0041**. All Alembic migrations use a flat
integer prefix and the `down_revision` chaining pattern. The REST endpoint extends the existing
signals router with the same 404/503 error pattern already used for `GET /api/v1/signals/{coin}`
and `GET /api/v1/backtest/{coin}`.

The Checkpoint-HITL pattern for `confidence < 0.65` does not exist as a reusable module yet — it
exists only as a pyc-compiled artifact (`investment_director.cpython-313.pyc`), meaning the source
was removed or is not in the current tree. The planner must treat the HITL checkpoint as **new
code to build**, not something to import.

**Primary recommendation:** Copy SteuerAgent constructor-injection + fallback structure for all
four Analyst agents (no Tool-Use needed there); use UniverseSuggestionService tool-use pattern
for Bull/Bear/Risk; build SignalDirector as the orchestration hub with asyncio.gather + Python
synthesis. Build in wave order: Schemas → DB → Analysts → Research → Risk → Director → REST →
Tests.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Agent orchestration (asyncio.gather) | Application (SignalDirector) | — | Pure Python async; no LLM at coordination layer |
| LLM Tool-Use loops (Bull/Bear/Risk) | Application (individual agents) | Infrastructure (LLMClient) | Agents call LLMClient; client handles retry/cost |
| Pydantic schema definitions | Domain (agent_schemas.py) | — | Domain layer owns data contracts |
| Audit trail persistence | Infrastructure (repo + ORM) | Application (via repo interface) | Repository pattern; domain entity injected |
| REST endpoint | Interfaces (signals router) | Application (SignalDirector) | Router calls Director; no business logic in router |
| Fear&Greed DB read | Infrastructure (SQLAlchemy) | Application (SentimentAnalystAgent) | Agent receives session via injection |
| Checkpoint HITL | Application (SignalDirector) | — | New code; inline in `run()` method |
| Tool stub functions (get_indicator_state etc.) | Application (agents, as private helpers) | — | Tool definitions are per-agent; not shared infrastructure |

---

## Standard Stack

### Core (all already in project, no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` SDK | existing in venv | `messages.create` with `tools=`, `tool_choice=` | Single LLM provider; LLMClient wraps it |
| `pydantic` v2 | existing | Schema validation for all agent outputs | AGENTS.md §3 mandate |
| `sqlalchemy` 2.0 async | existing | ORM model + async session for audit trail | Project standard |
| `alembic` | existing | Migration 0041 for agent_audit_trail | Project standard |
| `fastapi` | existing | REST router extension | Project standard |
| `asyncio` stdlib | stdlib | `gather()` for parallel analysts | CLAUDE.md mandate |
| `functools.lru_cache` or module-level dict | stdlib | 1h TTL cache for MacroRegime | No Redis needed for in-process cache |

### No New Packages Required

This phase installs zero new Python packages. All dependencies are already present.

---

## Package Legitimacy Audit

No new packages are introduced in this phase. Section not applicable.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
GET /api/v1/agent-signal/{coin}
         |
         v
[signals router] ──────────────────────────────────────────────────
         |
         v
[SignalDirector.run(coin)]
  |
  ├─ [1] SignalEngine.evaluate(coin) → SignalVector       (deterministic)
  |
  ├─ [2] asyncio.gather() ─────────────────────────────────────────
  |         ├── TechnicalAnalystAgent.analyze(sub_scores)  → TechnicalView
  |         ├── OnChainAnalystAgent.analyze(coin)          → OnChainView
  |         ├── SentimentAnalystAgent.analyze(coin)        → SentimentView
  |         └── MacroRegimeAgent.get_regime()  [1h cached] → MacroRegime
  |
  ├─ [3] BullResearchAgent.build_case(views + engine_signal) → BullCase
  |       [Claude Tool-Use API: get_engine_signal tool]
  ├─ [3] BearResearchAgent.build_case(views + engine_signal) → BearCase
  |       [Claude Tool-Use API: get_engine_signal tool]
  |
  ├─ [4] RiskAgent.assess(coin, engine_signal) → RiskVerdict
  |       [Claude Tool-Use API: get_portfolio_exposure, get_vol_forecast, get_drawdown_state]
  |
  ├─ [5] _synthesize(bull, bear, engine_signal, risk) → TradeSignal  (Python Pydantic assembly)
  |
  ├─ [6] if signal.confidence < 0.65: checkpoint(user)   (HITL — new code)
  |
  └─ [7] _persist_audit_trail(...)  → audit_trail_id inserted into agent_audit_trail
         return TradeSignal

[Infrastructure]
  LLMClient ← all LLM calls route through here (cost-tracking, retry)
  SQLAlchemy AsyncSession ← AgentAuditTrailRepository.insert()
  market_sentiment table ← SentimentAnalystAgent reads Fear&Greed
```

### Recommended Project Structure

```
backend/
├── domain/
│   └── schemas/
│       └── agent_schemas.py          # NEW: TechnicalView, OnChainView, SentimentView,
│                                     #      MacroRegime, BullCase, BearCase,
│                                     #      RiskVerdict, TradeSignal
├── application/
│   └── agents/
│       ├── technical_analyst_agent.py   # NEW (Haiku, no tool-use)
│       ├── onchain_analyst_agent.py     # NEW (Haiku, no tool-use)
│       ├── sentiment_analyst_agent.py   # NEW (Haiku, stub, reads market_sentiment)
│       ├── macro_regime_agent.py        # NEW (Haiku, 1h cache, no tool-use)
│       ├── bull_research_agent.py       # NEW (Sonnet, Tool-Use)
│       ├── bear_research_agent.py       # NEW (Sonnet, Tool-Use)
│       ├── risk_agent.py                # NEW (Sonnet, Tool-Use)
│       └── signal_director.py          # NEW (Sonnet, hybrid orchestrator)
├── infrastructure/
│   ├── llm/
│   │   └── prompts/
│   │       ├── technical_analyst_system.md.j2   # NEW
│   │       ├── onchain_analyst_system.md.j2     # NEW
│   │       ├── sentiment_analyst_system.md.j2   # NEW
│   │       ├── macro_regime_system.md.j2        # NEW
│   │       ├── bull_research_system.md.j2       # NEW
│   │       ├── bear_research_system.md.j2       # NEW
│   │       └── risk_agent_system.md.j2          # NEW
│   └── persistence/
│       ├── models/
│       │   └── agent_audit_trail.py     # NEW ORM model
│       └── repositories/
│           └── agent_audit_trail_repository.py  # NEW (insert-only)
├── interfaces/
│   └── rest/
│       └── routers/
│           └── signals.py               # EXTEND: add agent-signal endpoint
└── alembic/
    └── versions/
        └── 0041_agent_audit_trail.py    # NEW migration
```

---

## Pattern 1: Analyst Agent (No Tool-Use — SteuerAgent Copy)

For TechnicalAnalystAgent, OnChainAnalystAgent, SentimentAnalystAgent, MacroRegimeAgent.
The LLM receives data in the prompt (not via tools) and outputs JSON that is Pydantic-validated.

```python
# Source: backend/application/agents/steuer_agent.py (GOLD STANDARD — verified in codebase)
from __future__ import annotations
import json
import logging
from pydantic import ValidationError
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
from backend.domain.schemas.agent_schemas import TechnicalView

_logger = logging.getLogger(__name__)
_MODEL_FAST = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 512

class TechnicalAnalystAgent:
    def __init__(self, llm_client: LLMClient, prompt_loader: PromptTemplateLoader) -> None:
        self._llm = llm_client
        self._prompts = prompt_loader

    async def analyze(self, coin: str, sub_scores: dict) -> TechnicalView:
        system_prompt = self._prompts.render("technical_analyst_system.md.j2", {})
        user_prompt = self._prompts.render("technical_analyst_user.md.j2", {
            "coin": coin, "sub_scores": sub_scores
        })
        try:
            response = await self._llm.messages_create(
                model=_MODEL_FAST,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=_MAX_TOKENS,
                feature="technical_analyst",
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},  # mandatory for long system prompts
                }],
            )
            raw_text: str = response.content[0].text
            data = json.loads(raw_text)
            data["coin"] = coin
            return TechnicalView.model_validate(data)
        except (json.JSONDecodeError, ValidationError, KeyError, IndexError) as exc:
            _logger.error("TechnicalAnalystAgent LLM output failed: %s", exc)
            return self._fallback(coin, sub_scores)

    @staticmethod
    def _fallback(coin: str, sub_scores: dict) -> TechnicalView:
        # Derive stance from engine signal directly — never invent a number
        ma = int(sub_scores.get("ma_signal", 0))
        macd = int(sub_scores.get("macd_signal", 0))
        rsi = int(sub_scores.get("rsi_signal", 0))
        n_active = ma + macd + rsi
        stance = "BULLISH" if n_active >= 2 else "BEARISH" if n_active == 0 else "NEUTRAL"
        return TechnicalView(
            coin=coin,
            stance=stance,
            consensus=f"{n_active}/3",
            key_signals=["Fallback: engine signals only"],
            confidence=0.3,
            reasoning="LLM unavailable — derived from engine signal directly.",
        )
```

**Key points:**
- `cache_control: {"type": "ephemeral"}` on system prompt — MANDATORY for all long prompts
- `json.loads(response.content[0].text)` — SteuerAgent pattern, not tool_use
- Always override mandatory fields after parse (e.g. `data["coin"] = coin`)
- `_fallback()` is `@staticmethod` — never uses LLM, derives from engine data only

---

## Pattern 2: Tool-Use Agent (Claude forced structured output)

For BullResearchAgent, BearResearchAgent, RiskAgent. The LLM is forced to call a single named
tool via `tool_choice: {"type": "tool", "name": "..."}`. Output extracted from block where
`block.type == "tool_use"`.

```python
# Source: backend/application/services/universe_suggestion_service.py (verified in codebase)
from pydantic import ValidationError
from backend.domain.schemas.agent_schemas import BullCase

class BullResearchAgent:
    def __init__(self, llm_client: LLMClient, prompt_loader: PromptTemplateLoader) -> None:
        self._llm = llm_client
        self._prompts = prompt_loader

    async def build_case(
        self,
        coin: str,
        tech: TechnicalView,
        onchain: OnChainView,
        senti: SentimentView,
        macro: MacroRegime,
        engine_signal: SignalVector,
    ) -> BullCase:
        system_prompt = self._prompts.render("bull_research_system.md.j2", {})
        user_prompt = self._prompts.render("bull_research_user.md.j2", {
            "coin": coin,
            "tech": tech.model_dump(),
            "onchain": onchain.model_dump(),
            "senti": senti.model_dump(),
            "macro": macro.model_dump(),
            "engine_signal": engine_signal.model_dump(),
        })

        # Tool definition: Pydantic schema as input_schema — forces structured output
        tools = [{
            "name": "submit_bull_case",
            "description": "Submit the bull research case.",
            "input_schema": BullCase.model_json_schema(),
        }]

        response = await self._llm.messages_create(
            model=_MODEL_SYNTH,   # claude-sonnet-4-6
            system=[{"type": "text", "text": system_prompt,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
            tools=tools,
            tool_choice={"type": "tool", "name": "submit_bull_case"},
            max_tokens=1024,
            feature="bull_research",
        )

        # Extract tool_use block
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return BullCase.model_validate(block.input)
                except ValidationError as exc:
                    _logger.warning("BullResearchAgent schema violation: %s", exc)
                    break

        # Fallback: deterministic BullCase from engine signal
        return BullCase(
            thesis=f"Engine signal is {engine_signal.action} for {coin}.",
            strongest_points=[f"Consensus: {engine_signal.consensus}"],
            risks_acknowledged=["LLM unavailable — fallback from engine signal only."],
        )
```

**Key points:**
- `tool_choice={"type": "tool", "name": "submit_bull_case"}` — forces exactly one structured call
- `BullCase.model_json_schema()` as `input_schema` — Pydantic generates JSON Schema automatically
- Extract from `response.content` by checking `block.type == "tool_use"` then `block.input`
- `block.input` is already a dict — pass directly to `Pydantic.model_validate()`
- NO multi-turn loop needed (single forced tool call is sufficient here)

---

## Pattern 3: asyncio.gather for Parallel Analysts

```python
# Source: CONTEXT.md D-01 + stdlib asyncio (verified)
async def run(self, coin: str) -> TradeSignal:
    engine_signal = await signal_service.evaluate(
        coin=coin, asof=date.today(), prices_df=prices_df
    )

    tech, onchain, senti, macro = await asyncio.gather(
        self._technical.analyze(coin, engine_signal.sub_scores),
        self._onchain.analyze(coin),
        self._sentiment.analyze(coin),
        self._macro.get_regime(),
    )
    # If any analyst raises, asyncio.gather propagates the FIRST exception.
    # Wrap in try/except and fall back to deterministic signal.
```

**Important:** `asyncio.gather()` raises on the first exception by default. Use
`return_exceptions=True` if individual analyst failures should be tolerated; then check each
result for `isinstance(result, Exception)` and substitute fallback values.

---

## Pattern 4: ORM Model with JSONB (agent_audit_trail)

```python
# Source: backend/infrastructure/persistence/models/backtest_result.py (verified in codebase)
import uuid
from datetime import date, datetime
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.infrastructure.persistence.base import Base

class AgentAuditTrailORM(Base):
    __tablename__ = "agent_audit_trail"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    coin: Mapped[str] = mapped_column(sa.String(20), nullable=False, index=True)
    asof: Mapped[date] = mapped_column(sa.Date, nullable=False)
    agent_run: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    # IMMUTABILITY: NO update() method on repository. INSERT-ONLY.
```

**Repository pattern (insert-only):**
```python
class AgentAuditTrailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, record: AgentAuditTrailORM) -> uuid.UUID:
        self._session.add(record)
        await self._session.flush()
        return record.id
    # NOTE: No update(), no delete() methods — immutability contract enforced at application layer
```

---

## Pattern 5: Alembic Migration 0041

```python
# Source: backend/alembic/versions/0040_vol_forecast.py (verified in codebase)
# backend/alembic/versions/0041_agent_audit_trail.py
"""Create agent_audit_trail table — append-only audit for V4-3 Agentic Layer.

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-21
"""
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "agent_audit_trail",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("coin", sa.String(20), nullable=False),
        sa.Column("asof", sa.Date(), nullable=False),
        sa.Column("agent_run", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_agent_audit_trail_coin", "agent_audit_trail", ["coin"])
    op.create_index("ix_agent_audit_trail_asof", "agent_audit_trail", ["asof"])
    # NOTE: No UPDATE or DELETE triggers — immutability enforced at application layer.
    # (SQLite test DB does not support CREATE TRIGGER; skip for portability.)

def downgrade() -> None:
    op.drop_index("ix_agent_audit_trail_asof", table_name="agent_audit_trail")
    op.drop_index("ix_agent_audit_trail_coin", table_name="agent_audit_trail")
    op.drop_table("agent_audit_trail")
```

**Key:** `gen_random_uuid()` is PostgreSQL-native. SQLite used in unit tests does not support it;
use `default=uuid.uuid4` on the ORM model column as a Python-side fallback.

---

## Pattern 6: REST Endpoint Extension

```python
# Source: backend/interfaces/rest/routers/signals.py (verified in codebase)
# Add to existing signals.py router (same file — no new router needed)

_AGENT_SIGNAL_ROUTER = APIRouter(prefix="/api/v1", tags=["agent-signal"])

@_AGENT_SIGNAL_ROUTER.get(
    "/agent-signal/{coin}",
    response_model=TradeSignal,
    summary="Agentic TradeSignal for a coin",
)
async def get_agent_signal(coin: str) -> TradeSignal:
    coin_upper = coin.upper()
    if coin_upper not in _CRYPTO_UNIVERSE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Coin '{coin_upper}' not in crypto universe.",
        )
    try:
        return await signal_director.run(coin_upper)
    except LLMUnavailableError:
        # SignalDirector fallback already returns a TradeSignal;
        # only raise 503 if even the deterministic fallback failed.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent signal temporarily unavailable.",
        )
```

**Or** add to existing `router` in `signals.py` directly (same `prefix="/api/v1/signals"` won't
work for `/agent-signal/{coin}` — use a separate `APIRouter(prefix="/api/v1")` or register the
endpoint at app level). Check `backend/interfaces/rest/app.py` for router registration.

---

## Pattern 7: SentimentAnalystAgent Stub — DB Query

```python
# Source: market_sentiment table from migration 0039 (verified)
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa

async def _get_fear_greed(session: AsyncSession, asof: date) -> tuple[int, str]:
    """Reads latest Fear&Greed at or before asof from market_sentiment table."""
    stmt = (
        sa.select(sa.column("fear_greed"), sa.column("fg_classification"))
        .select_from(sa.table("market_sentiment"))
        .where(sa.column("date") <= asof)
        .order_by(sa.column("date").desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return 50, "Neutral"  # neutral fallback
    return int(row.fear_greed), str(row.fg_classification)

# Normalization per D-04:
score = (fg_value - 50) / 50   # range: -1.0 (extreme fear) to +1.0 (extreme greed)
```

---

## Pattern 8: HITL Checkpoint (New Code — No Existing Module)

The source file for `InvestmentDirector` was not found in the repository tree (only a .pyc
remains). The Checkpoint-HITL must be implemented fresh in SignalDirector.

```python
# New code — referenced pattern from CONTEXT.md D-01
async def _checkpoint(self, signal: TradeSignal, coin: str) -> TradeSignal:
    """HITL: presents ≤4 options when confidence < 0.65. UI constraint from AGENTS.md."""
    # In the current V4-3 scope: log + return signal unchanged.
    # Full interactive checkpoint (MCP-based user prompt) can be wired in V4-5 when UI exists.
    _logger.warning(
        "HITL checkpoint triggered for %s: confidence=%.2f (< 0.65). "
        "Signal returned with lowered confidence and disclaimer.",
        coin, signal.confidence,
    )
    return signal.model_copy(update={
        "disclaimer": (
            "ACHTUNG: Konfidenz < 65 %. Manueller Review empfohlen. "
            + signal.disclaimer
        )
    })
```

**Note for planner:** The test for Checkpoint (D-06 test #6) verifies that `confidence < 0.65`
triggers exactly one HITL call. The test must mock the checkpoint function and assert call_count
== 1. The ≤4 options UI constraint applies when a real interactive UI is wired (V4-5).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output | Custom JSON parsing with regex | `Pydantic.model_json_schema()` as tool `input_schema` + `model_validate(block.input)` | Already in production in universe_suggestion_service |
| Retry on HTTP 429 | Custom retry lib | `LLMClient.messages_create()` — built-in 3-attempt retry | Already handles 429 with exponential backoff |
| Cost tracking | Manual token counting | `LLMClient.messages_create()` with `feature=` tag | CostTracker runs automatically inside LLMClient |
| Async sync ML calls | `loop.run_in_executor()` | `asyncio.to_thread()` | CLAUDE.md mandate |
| UUID generation | `str(uuid.uuid4())` strings | `uuid.UUID` type + SQLAlchemy `UUID(as_uuid=True)` | Consistent with all existing models |
| In-process TTL cache | Redis or external store | `functools.lru_cache` with TTL or module-level dict + `time.monotonic()` | MacroRegime changes slowly; no external dependency needed |

**Key insight:** The LLMClient already handles the entire HTTP lifecycle (auth, retry, cost
tracking, rate limiting). Agents must never instantiate `anthropic.AsyncAnthropic` directly —
always inject `LLMClient`.

---

## Common Pitfalls

### Pitfall 1: Tool-Use vs JSON-in-text Confusion
**What goes wrong:** Implementing BullResearchAgent with `json.loads(response.content[0].text)`
instead of the Tool-Use loop — LLM returns a tool_use block, not text, so `.text` raises
`AttributeError`.
**Why it happens:** SteuerAgent uses text output; BullResearchAgent uses `tool_choice=forced`.
They look similar but have different response shapes.
**How to avoid:** When `tool_choice` is set, always check `block.type == "tool_use"` and access
`block.input` (a dict). Never call `.text` on tool_use responses.
**Warning signs:** `AttributeError: 'ToolUseBlock' object has no attribute 'text'`

### Pitfall 2: asyncio.gather Exception Propagation
**What goes wrong:** One analyst (e.g. OnChainAnalystAgent) raises; `asyncio.gather()` cancels
all others and raises immediately — TradeSignal never produced.
**Why it happens:** Default `asyncio.gather()` propagates the first exception.
**How to avoid:** Use `asyncio.gather(..., return_exceptions=True)` and check each result. Or
wrap each analyst call in a try/except that returns a fallback object.
**Warning signs:** Intermittent 503 errors when only one data source is unavailable.

### Pitfall 3: LLM Inventing Numbers (§0 Iron Rule Violation)
**What goes wrong:** Bull/Bear/Risk prompt does not explicitly provide the numbers, so LLM
generates plausible-sounding but hallucinated values in its output.
**Why it happens:** LLM fills gaps in context from training data.
**How to avoid:** All tool input data must be in the user prompt (serialized Pydantic dicts).
The Hallucination-Guard test (D-06 #1) enforces this by diffing agent float fields against
engine/tool values.
**Warning signs:** Test D-06 #1 fails with Diff > 1e-9.

### Pitfall 4: No-Shorting Invariant
**What goes wrong:** Python synthesis sets `size_factor` to a negative value when action=SELL,
or RiskVerdict.max_size is set to a negative float.
**Why it happens:** Naive weighted arithmetic between Bull (positive bias) and Bear (negative).
**How to avoid:** `_synthesize()` must clamp: `size_factor = max(0.0, computed_size)`. When
`action == "SELL"`, force `size_factor = 0.0`. Test D-06 #7 enforces this.
**Warning signs:** Test asserts `signal.size_factor >= 0.0` fails.

### Pitfall 5: UUID PK with gen_random_uuid() on SQLite
**What goes wrong:** Alembic migration 0041 uses `server_default=sa.text("gen_random_uuid()")`
which is PostgreSQL-only. Unit tests using SQLite will fail on table creation.
**Why it happens:** Tests use in-memory SQLite, production uses PostgreSQL.
**How to avoid:** Set `default=uuid.uuid4` on the ORM model's Python column definition (Python-
side default). `server_default` is only used by the DB server. Unit tests never call the DB —
use `uuid.uuid4()` directly when constructing ORM objects in tests.
**Warning signs:** `OperationalError: no such function: gen_random_uuid`

### Pitfall 6: Prompt Caching Not Applied
**What goes wrong:** Long system prompts (analyst instructions + tool schemas) sent on every
request without cache_control, burning input tokens and increasing latency.
**Why it happens:** Forgetting to wrap system prompt in list-of-blocks format.
**How to avoid:** Always use `system=[{"type": "text", "text": ..., "cache_control":
{"type": "ephemeral"}}]` (not `system="..."` string form) for long prompts.
**Warning signs:** CostTracker shows high per-call cost; no cache_read_input_tokens in usage.

---

## Code Examples

### Extracting tool_use block (verified pattern from universe_suggestion_service.py)
```python
# Source: backend/application/services/universe_suggestion_service.py line 105-118
content = getattr(response, "content", [])
for block in content:
    if getattr(block, "type", None) == "tool_use":
        try:
            return MySchema.model_validate(block.input)
        except ValidationError as exc:
            raise InvalidLLMOutput(str(exc)) from exc
raise InvalidLLMOutput("No tool_use block in LLM response.")
```

### Mandatory cache_control pattern (verified from universe_suggestion_service.py)
```python
system=[
    {
        "type": "text",
        "text": system_prompt,
        "cache_control": {"type": "ephemeral"},
    }
]
```

### Fear&Greed normalization per D-04
```python
score: float = (fg_value - 50) / 50  # -1.0 = extreme fear, +1.0 = extreme greed
regime: str = "FEAR" if score < -0.2 else "GREED" if score > 0.2 else "NEUTRAL"
```

### Model constants (verified from CONTEXT.md + codebase)
```python
_MODEL_FAST  = "claude-haiku-4-5-20251001"   # Analyst agents
_MODEL_SYNTH = "claude-sonnet-4-6"            # Bull/Bear/Risk/Director
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic LLM agent | Multi-agent with specialized roles | TradingAgents paper (arXiv 2412.20138) | Reduces single-model bias; adds Bull/Bear debate |
| LLM computes numbers | LLM interprets; numbers from Tools/Engine | §0 iron rule | Eliminates hallucinated metrics |
| Text output + json.loads | Tool-Use with forced tool_choice | Anthropic API evolution | Structured output guaranteed; no regex parsing |
| Pydantic v1 `.parse_obj()` | Pydantic v2 `.model_validate()` | Pydantic v2 (project uses v2) | Use `model_validate`, not `parse_obj` |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8+ with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest backend/tests/unit/application/ -q -x` |
| Full suite command | `pytest backend/tests/ -q --cov=backend --cov-report=term-missing` |

### Phase Requirements → Test Map (D-06 Mandatory 7)

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-06-1 | Hallucination-Guard: every float in agent output == engine/tool float (diff < 1e-9) | unit | `pytest backend/tests/unit/application/test_signal_director.py::test_hallucination_guard -x` | ❌ Wave 0 |
| D-06-2 | State-from-Tool: RiskAgent reads exposure from mocked Store, no invented value | unit | `pytest ... ::test_state_from_tool -x` | ❌ Wave 0 |
| D-06-3 | Minority-Protection: 1 Bear vs 3 Bulls → audit trail contains Bear | unit | `pytest ... ::test_minority_protection -x` | ❌ Wave 0 |
| D-06-4 | Fallback: LLM raises → TradeSignal returned, confidence lowered, disclaimer set | unit | `pytest ... ::test_fallback_on_llm_error -x` | ❌ Wave 0 |
| D-06-5 | Pydantic-Schema: all agent outputs schema-validated; no freetext | unit | `pytest ... ::test_pydantic_schema_all_agents -x` | ❌ Wave 0 |
| D-06-6 | Checkpoint: confidence < 0.65 → exactly 1 HITL call, ≤4 options | unit | `pytest ... ::test_checkpoint_trigger -x` | ❌ Wave 0 |
| D-06-7 | No-Shorting: action==SELL → size_factor==0.0 and max_size==0.0; never negative | unit | `pytest ... ::test_no_shorting -x` | ❌ Wave 0 |
| REQ-3.3 | SentimentAnalystAgent reads real F&G from market_sentiment (not hardcoded) | unit | `pytest ... ::test_sentiment_reads_db -x` | ❌ Wave 0 |
| REQ-3.8 | Audit trail immutability: 2 inserts → 2 rows (no overwrite) | unit | `pytest ... ::test_audit_trail_immutable -x` | ❌ Wave 0 |

All test files go in `backend/tests/unit/application/test_signal_director.py` (primary) and
`backend/tests/unit/application/test_<agent_name>.py` per agent.

All test files must include `pytestmark = pytest.mark.unit` (verified pattern from
test_steuer_agent.py).

### Sampling Rate
- **Per task commit:** `pytest backend/tests/unit/application/ -q -x`
- **Per wave merge:** `pytest backend/tests/ -q --cov=backend --cov-report=term-missing`
- **Phase gate:** Full suite green + coverage ≥ 80% before PR merge

### Wave 0 Gaps
- [ ] `backend/tests/unit/application/test_signal_director.py` — covers D-06 mandatory 7
- [ ] `backend/tests/unit/application/test_technical_analyst_agent.py`
- [ ] `backend/tests/unit/application/test_onchain_analyst_agent.py`
- [ ] `backend/tests/unit/application/test_sentiment_analyst_agent.py`
- [ ] `backend/tests/unit/application/test_macro_regime_agent.py`
- [ ] `backend/tests/unit/application/test_bull_bear_research_agents.py`
- [ ] `backend/tests/unit/application/test_risk_agent.py`
- [ ] All use `AsyncMock` + `MagicMock` pattern from `test_steuer_agent.py`

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| anthropic SDK | LLMClient (all agents) | ✓ | existing in venv | — |
| pydantic v2 | agent_schemas.py | ✓ | existing | — |
| sqlalchemy 2.0 async | AgentAuditTrailRepository | ✓ | existing | — |
| alembic | migration 0041 | ✓ | existing | — |
| fastapi | REST endpoint | ✓ | existing | — |
| PostgreSQL | prod DB (JSONB, UUID) | ✓ (prod) | 16 | SQLite for unit tests (with Python-side uuid4) |
| pytest-asyncio | async unit tests | ✓ | ≥0.23 in pyproject.toml | — |

**Missing dependencies with no fallback:** none — all in project already.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Endpoint is read-only GET; existing auth middleware covers it |
| V5 Input Validation | yes | `coin` path param validated against `_CRYPTO_UNIVERSE` whitelist (404 if not found) |
| V6 Cryptography | no | No crypto operations in this phase |
| V5 Output Encoding | yes | All LLM outputs Pydantic-validated before returning to caller; no freetext to UI |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM hallucinating financial metrics | Information Disclosure / Tampering | Hallucination-Guard test (D-06-1); all numbers from Tools |
| Prompt injection via coin name | Tampering | coin validated against whitelist before any LLM call |
| Audit trail tampering | Tampering | Insert-only repository; no update/delete API |
| API key exposure | Information Disclosure | LLMClient uses env vars; `API_KEY` never in logs (AGENTS.md §7) |

---

## Open Questions (RESOLVED)

1. **Checkpoint HITL — Interactive or Log-only in V4-3?**
   - What we know: CONTEXT.md says `confidence < 0.65 → checkpoint(user)`. The source of the
     existing `InvestmentDirector` checkpoint is not in the repository tree (only .pyc).
   - What's unclear: Does V4-3 need an interactive user prompt (blocking until user responds) or
     just a logged warning with disclaimer? Interactive MCP-based HITL requires a UI that doesn't
     exist until V4-5.
   - RESOLVED: Implement as log + disclaimer in V4-3 (non-blocking). The test asserts
     "exactly one HITL call" — mock the checkpoint function (logging.warning). Document that real
     interactive HITL is wired in V4-5. Implemented in Plan 03-05 Task 2.

2. **SignalDirector Dependency Injection — how to get AsyncSession to router**
   - What we know: SentimentAnalystAgent and AgentAuditTrailRepository need an AsyncSession.
     FastAPI uses `Depends()` for session injection.
   - What's unclear: Whether a `get_signal_director()` dependency factory already exists or must
     be built.
   - RESOLVED: Build a `get_signal_director` FastAPI `Depends` factory in
     `backend/interfaces/rest/dependencies.py` following the pattern of existing dependency
     factories. Implemented in Plan 03-06 Task 1.

3. **MacroRegime 1h Cache — Module-level or injected?**
   - What we know: CONTEXT.md says "Cache: 1h TTL". No Redis available.
   - What's unclear: Whether cache should be module-level dict (simplest) or injected TTL cache.
   - RESOLVED: Module-level dict `_regime_cache: dict[str, tuple[float, MacroRegime]]`
     with `time.monotonic()` check, matching the `_signal_cache` pattern in `signals.py`.
     Implemented in Plan 03-03 Task 2.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | InvestmentDirector source code is not in the repo tree (only .pyc) — checkpoint must be built new | Pattern 8 / Open Questions | If source exists elsewhere, could reuse existing HITL logic |
| A2 | `backend/interfaces/rest/app.py` includes `signals.py` router already; no changes needed there | REST Pattern | If not auto-included, new router must be registered manually |
| A3 | `market_sentiment` table is populated (seeded in V4-1) with at least some rows | Pattern 7 | If empty, SentimentAnalystAgent falls back to fg_value=50 (neutral) — acceptable |
| A4 | SQLite is used for unit tests (not PostgreSQL Testcontainer) | Pitfall 5 / Alembic Pattern | If Testcontainer is used, gen_random_uuid() works and Python-side default is redundant but harmless |

**If this table is empty:** All other claims in this research were verified or cited from the codebase.

---

## Sources

### Primary (HIGH confidence — verified in codebase)
- `backend/application/agents/steuer_agent.py` — Gold Standard pattern: constructor injection, json.loads output, fallback, disclaimer
- `backend/application/services/universe_suggestion_service.py` — Only production Tool-Use pattern: `tools=`, `tool_choice=`, `block.type == "tool_use"`, `block.input`
- `backend/infrastructure/llm/client.py` — LLMClient API: `messages_create(model, messages, max_tokens, feature, system, **kwargs)`
- `backend/application/signals/signal_service.py` — `evaluate(coin, asof, prices_df, ...) → SignalVector`; sub_scores dict structure
- `backend/interfaces/rest/routers/signals.py` — 404/503 error pattern; `_CRYPTO_UNIVERSE` whitelist; in-memory cache pattern
- `backend/infrastructure/persistence/models/backtest_result.py` — JSONB + UUID column pattern
- `backend/infrastructure/persistence/repositories/decision_audit_repository.py` — Repository insert pattern with AsyncSession
- `backend/alembic/versions/0040_vol_forecast.py` — Alembic migration format; revision chaining
- `backend/alembic/versions/0039_market_sentiment.py` — `market_sentiment` table columns confirmed
- `backend/tests/unit/application/test_steuer_agent.py` — `pytestmark = pytest.mark.unit`; `AsyncMock` + `MagicMock` test pattern
- `pyproject.toml` — `asyncio_mode = "auto"`, `fail_under = 80`, `pytest.mark.unit`
- `docs/PRISMA_V4_AGENTS.md` — Authoritative spec: agent list, tool signatures, §0 iron rule, §6 tests, §7 build order
- `.planning/phases/PRISMA-03-v4-3-agentic-layer-planned/03-CONTEXT.md` — All locked decisions

### Secondary (MEDIUM confidence)
- `backend/application/agents/__pycache__/investment_director.cpython-313.pyc` — Source no longer in tree; HITL pattern must be rebuilt
- CLAUDE.md — `asyncio.to_thread` mandate, retry pattern, model routing constants

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all libraries verified present in codebase; no new installs
- Architecture Patterns: HIGH — SteuerAgent and UniverseSuggestionService patterns verified line-by-line
- Tool-Use API: HIGH — verified from production code in universe_suggestion_service.py
- ORM/Migration pattern: HIGH — verified from backtest_result.py and 0040 migration
- Pitfalls: HIGH — derived from code inspection and §0 iron rule
- HITL Checkpoint: MEDIUM — source not found; reconstructed from CONTEXT.md spec + pyc artifact

**Research date:** 2026-06-21
**Valid until:** 2026-07-21 (stable stack — Anthropic tool-use API shape is stable)
