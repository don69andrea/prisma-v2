# Multi-Agent V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ersetze/erweitere die bestehenden schwachen Agents durch ein echtes Multi-Agent-System mit Tool-Use, SSE-basiertem Orchestrator, HITL-Checkpoints und On-Chain-Intelligence.

**Architecture:** Ein `InvestmentDirector` orchestriert parallel-laufende Spezialagenten (Macro, Quant, Steuer) via asyncio, kommuniziert per SSE mit dem Browser, und wartet bei Checkpoints auf User-Input. `CointelligenceAgent` nutzt Claude's nativen Tool-Use-Loop mit Glassnode/CoinGecko-Daten. `MacroAgent V2` ersetzt rule-based if/elif durch LLM Tool-Use. `DataStewardAgent` läuft täglich als Cron und prüft Datenfrische.

**Tech Stack:** Python 3.12, FastAPI, `sse-starlette` (bereits installiert), `httpx` (bereits installiert), Claude Haiku/Sonnet via bestehender LLMClient, asyncio.Queue + asyncio.Event für HITL, bestehende Adapters (FearGreedAdapter, CoinGeckoAdapter, MacroService).

## Global Constraints

- Branch: `feat/multiagent-v2` von `main`
- Alle neuen Agents: `backend/application/agents/` (Domain-Layer)
- Alle neuen Routers: `backend/interfaces/rest/routers/`
- Tests: `pytest.mark.unit` für unit, `pytest.mark.integration` für integration
- LLM: Haiku für Tool-Use-Loops (cost), Sonnet für Synthesis
- TDD: Tests vor Implementierung
- Kein passlib — bcrypt direkt
- `asyncio.to_thread()` für alle sync I/O (KEIN `run_in_executor`)
- Pydantic-Schema für alle LLM-Outputs (AGENTS.md Pflicht)
- Immer Disclaimer bei Finanzempfehlungen
- Einzelner Render-Worker → asyncio.Queue/Event funktioniert (kein Redis nötig)
- Modell-IDs: `claude-haiku-4-5-20251001` (Haiku), `claude-sonnet-4-6` (Sonnet)
- Spec-Datei: `docs/superpowers/specs/2026-06-18-multiagent-spec.md` (Originalplan)

---

## File Map

### Neu erstellen
| Datei | Verantwortung |
|-------|--------------|
| `backend/application/agents/macro_agent_v2.py` | MacroAgent V2 mit LLM Tool-Use (ersetzt rule-based) |
| `backend/application/agents/cointelligence_agent.py` | On-Chain Intelligence für BTC/ETH mit Tool-Use-Loop |
| `backend/application/agents/investment_director.py` | Orchestrator: Fan-out zu allen Agents, HITL-Checkpoints |
| `backend/application/agents/data_steward_agent.py` | Datenpflege: Freshness-Check + Refresh-Trigger |
| `backend/domain/schemas/multiagent_schemas.py` | Pydantic-Schemas: DirectorEvent, CheckpointEvent, CointelligenceReport, MacroReport |
| `backend/interfaces/rest/routers/analyze.py` | SSE-Endpoint `/api/v1/analyze/stream` + Checkpoint-POST |
| `backend/scripts/data_steward_run.py` | CLI-Entry für DataStewardAgent (Cron) |
| `frontend/app/analyze/page.tsx` | Analyse-Page (Server Component Shell) |
| `frontend/app/analyze/analyze-client.tsx` | EventSource-Hook + Step-Visualisierung + Checkpoint-Dialog |
| `frontend/hooks/useAnalysisStream.ts` | SSE-Hook für Director-Events |
| `backend/tests/unit/application/test_macro_agent_v2.py` | Unit Tests MacroAgent V2 |
| `backend/tests/unit/application/test_cointelligence_agent.py` | Unit Tests CointelligenceAgent |
| `backend/tests/unit/application/test_investment_director.py` | Unit Tests Director |

### Modifizieren
| Datei | Änderung |
|-------|---------|
| `backend/config.py` | `glassnode_api_key: str = ""` hinzufügen |
| `.env.example` | `GLASSNODE_API_KEY=` hinzufügen |
| `backend/interfaces/rest/app.py` | `analyze_router` registrieren |
| `backend/interfaces/rest/dependencies.py` | `get_investment_director()` Dependency hinzufügen |
| `render.yaml` | DataSteward Cron `prisma-data-steward` 06:00 UTC |
| `frontend/app/nav-links.tsx` | Link zu `/analyze` hinzufügen |

---

## Task 1: Domain Schemas + Config

**Files:**
- Create: `backend/domain/schemas/multiagent_schemas.py`
- Modify: `backend/config.py`
- Modify: `.env.example`
- Test: `backend/tests/unit/domain/test_multiagent_schemas.py`

**Interfaces:**
- Produces: `DirectorEvent`, `CheckpointEvent`, `AnalysisStep`, `CointelligenceReport`, `MacroToolReport` — alle Pydantic BaseModel

- [ ] **Step 1: Schreibe failing test**

```python
# backend/tests/unit/domain/test_multiagent_schemas.py
from __future__ import annotations
import pytest
from backend.domain.schemas.multiagent_schemas import (
    DirectorEvent, CheckpointEvent, AnalysisStep, CointelligenceReport, MacroToolReport
)

pytestmark = pytest.mark.unit

def test_director_event_step():
    e = DirectorEvent(type="step", agent="MacroAgent", status="running")
    assert e.type == "step"
    assert e.agent == "MacroAgent"

def test_director_event_checkpoint():
    e = DirectorEvent(
        type="checkpoint",
        checkpoint_id="cp_abc",
        message="3a oder freie Mittel?",
        options=["3a-Konto (VIAC)", "Freie Mittel"],
    )
    assert e.checkpoint_id == "cp_abc"
    assert len(e.options) == 2

def test_director_event_done():
    e = DirectorEvent(type="done", signal="BUY", confidence=0.82, run_id="r1")
    assert e.signal == "BUY"

def test_cointelligence_report_validation():
    r = CointelligenceReport(
        coin="BTC",
        price_chf=89400.0,
        mvrv_zone="FAIR",
        fear_greed=45,
        sharpe_crypto=0.8,
        sharpe_smi=0.6,
        chf_usd_impact="NEUTRAL",
        regime_signal="HOLD",
        max_allocation_pct=5.0,
        reasoning="BTC ist fair bewertet.",
        disclaimer="Hochspekulative Anlage.",
    )
    assert r.coin == "BTC"
    assert r.max_allocation_pct <= 10.0

def test_macro_tool_report():
    r = MacroToolReport(
        ticker="NESN.SW",
        score=62.5,
        leitzins=0.25,
        chf_eur=0.935,
        climate="neutral",
        chf_impact="NEGATIV",
        reasoning="Starker CHF belastet Exportumsätze.",
    )
    assert 0.0 <= r.score <= 100.0
```

- [ ] **Step 2: Führe Test aus — muss FAIL**

```bash
uv run pytest backend/tests/unit/domain/test_multiagent_schemas.py -v
```
Erwartetes Ergebnis: `ImportError: cannot import name 'DirectorEvent'`

- [ ] **Step 3: Implementiere Schemas**

```python
# backend/domain/schemas/multiagent_schemas.py
"""Pydantic-Schemas für Multi-Agent Director, Checkpoints und Reports."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class AnalysisStep(BaseModel):
    agent: str
    status: Literal["running", "done", "error"]
    result: str | None = None


class DirectorEvent(BaseModel):
    type: Literal["step", "checkpoint", "done", "error"]
    # step fields
    agent: str | None = None
    status: Literal["running", "done", "error", "planning"] | None = None
    result: str | None = None
    # checkpoint fields
    checkpoint_id: str | None = None
    message: str | None = None
    options: list[str] = Field(default_factory=list)
    # done fields
    run_id: str | None = None
    signal: str | None = None
    confidence: float | None = None
    report: dict[str, Any] | None = None
    # error fields
    error: str | None = None


class MacroToolReport(BaseModel):
    ticker: str
    score: float = Field(ge=0.0, le=100.0)
    leitzins: float
    chf_eur: float
    climate: str
    chf_impact: Literal["POSITIV", "NEUTRAL", "NEGATIV"]
    reasoning: str


class CointelligenceReport(BaseModel):
    coin: Literal["BTC", "ETH"]
    price_chf: float
    mvrv_zone: Literal["UNDERBOUGHT", "FAIR", "EXPENSIVE", "EXTREME", "UNKNOWN"]
    fear_greed: int = Field(ge=0, le=100)
    sharpe_crypto: float
    sharpe_smi: float
    chf_usd_impact: Literal["GÜNSTIG", "NEUTRAL", "UNGÜNSTIG"]
    regime_signal: Literal["ACCUMULATE", "HOLD", "CAUTION", "AVOID"]
    max_allocation_pct: float = Field(ge=0.0, le=10.0)
    reasoning: str = Field(min_length=10)
    disclaimer: str


class CheckpointAnswer(BaseModel):
    answer: str
```

- [ ] **Step 4: Config erweitern**

In `backend/config.py`, in der `Settings`-Klasse hinzufügen (nach `coingecko_api_key`):

```python
glassnode_api_key: str = ""
```

In `.env.example` hinzufügen:

```
# Glassnode (free tier — kostenlos: https://glassnode.com)
GLASSNODE_API_KEY=
```

- [ ] **Step 5: Tests grün**

```bash
uv run pytest backend/tests/unit/domain/test_multiagent_schemas.py -v
```
Erwartetes Ergebnis: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/domain/schemas/multiagent_schemas.py backend/tests/unit/domain/test_multiagent_schemas.py backend/config.py .env.example
git commit -m "feat(multiagent): domain schemas + config für Director, Cointelligence, MacroV2"
```

---

## Task 2: MacroAgent V2 — LLM Tool-Use statt if/elif

**Files:**
- Create: `backend/application/agents/macro_agent_v2.py`
- Test: `backend/tests/unit/application/test_macro_agent_v2.py`

**Interfaces:**
- Consumes: `MacroService.get_context() -> MacroContext`, `LLMClient`
- Produces: `MacroAgentV2.get_macro_report(ticker: str, sector: str | None) -> MacroToolReport`

- [ ] **Step 1: Failing test schreiben**

```python
# backend/tests/unit/application/test_macro_agent_v2.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.application.agents.macro_agent_v2 import MacroAgentV2
from backend.domain.schemas.multiagent_schemas import MacroToolReport
from backend.domain.value_objects.macro_context import MacroContext

pytestmark = pytest.mark.unit

_MOCK_CONTEXT = MacroContext(
    leitzins=0.25,
    chf_eur=0.935,
    inflation_ch=0.8,
    climate="neutral",
    narrative_de="Stabiles Umfeld.",
    narrative_en="Stable environment.",
)

def _make_agent(tool_call_result: dict | None = None, final_text: str | None = None):
    macro_service = AsyncMock()
    macro_service.get_context.return_value = _MOCK_CONTEXT
    llm = AsyncMock()

    # Simulate: first call uses tools, second call returns final JSON
    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "get_snb_rate"
    tool_block.id = "tu_1"
    tool_block.input = {}
    tool_response.content = [tool_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = final_text or (
        '{"score": 62.5, "chf_impact": "NEGATIV", "reasoning": "Starker CHF belastet Exporteure."}'
    )
    final_response.content = [text_block]

    llm.messages_create.side_effect = [tool_response, final_response]
    return MacroAgentV2(macro_service=macro_service, llm_client=llm)


@pytest.mark.asyncio
async def test_get_macro_report_returns_macro_tool_report():
    agent = _make_agent()
    report = await agent.get_macro_report("NESN.SW", sector="food")
    assert isinstance(report, MacroToolReport)
    assert report.ticker == "NESN.SW"
    assert 0.0 <= report.score <= 100.0


@pytest.mark.asyncio
async def test_get_macro_report_fallback_on_llm_error():
    macro_service = AsyncMock()
    macro_service.get_context.return_value = _MOCK_CONTEXT
    llm = AsyncMock()
    llm.messages_create.side_effect = RuntimeError("LLM down")
    agent = MacroAgentV2(macro_service=macro_service, llm_client=llm)
    report = await agent.get_macro_report("NESN.SW")
    assert isinstance(report, MacroToolReport)
    assert report.ticker == "NESN.SW"
```

- [ ] **Step 2: Test ausführen — muss FAIL**

```bash
uv run pytest backend/tests/unit/application/test_macro_agent_v2.py -v
```

- [ ] **Step 3: MacroAgentV2 implementieren**

```python
# backend/application/agents/macro_agent_v2.py
"""MacroAgent V2 — LLM Tool-Use Loop statt rule-based if/elif."""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from backend.application.services.macro_service import MacroService
from backend.domain.schemas.multiagent_schemas import MacroToolReport

_logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 600
_MAX_ITERATIONS = 5

# Export-schwere SMI-Titel (Exportumsatz >80%)
_EXPORT_HEAVY: frozenset[str] = frozenset({
    "NESN.SW", "ROG.SW", "NOVN.SW", "LONN.SW", "LOGN.SW",
    "BARN.SW", "GIVN.SW", "ABBN.SW", "KNIN.SW", "SCHP.SW",
    "LISN.SW", "GEBN.SW", "CFR.SW", "SREN.SW", "STMN.SW", "VACN.SW",
})
_DOMESTIC_FOCUS: frozenset[str] = frozenset({"UBSG.SW", "SLHN.SW", "BAER.SW", "PGHN.SW"})

_MACRO_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_snb_rate",
        "description": "Gibt den aktuellen SNB-Leitzins in % zurück.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_chf_eur",
        "description": "Gibt den aktuellen CHF/EUR-Kurs zurück (1 CHF in EUR). Höher = stärkerer CHF.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_inflation_ch",
        "description": "Gibt die aktuelle Schweizer Inflationsrate (YoY) in % zurück.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_ticker_export_profile",
        "description": "Gibt zurück ob ein Ticker exportlastig (>80% Auslandumsatz), inlandsfokussiert, oder neutral ist.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
]

_SYSTEM = """Du bist ein präziser Makro-Analyst für Schweizer Aktien.
Nutze die Tools um aktuelle Makrodaten abzurufen.
Berechne dann einen Makro-Score (0-100) für den angegebenen Ticker.

Score-Leitfaden:
- 50 = Baseline
- SNB-Leitzins 0%: +20, bis 0.5%: +15, bis 1%: +5, bis 1.5%: -10, >1.5%: -20
- CHF stark (>0.95/EUR) + Exporteur: -15; CHF stark + Inlandstitel: +5
- CHF schwach (<0.91/EUR) + Exporteur: +10
- Inflation 0-2%: +10; Inflation >3%: -10; Deflation: -5

Antworte NUR mit JSON (kein Markdown):
{"score": float, "chf_impact": "POSITIV|NEUTRAL|NEGATIV", "reasoning": "max 2 Sätze"}"""


class MacroAgentV2:
    def __init__(self, macro_service: MacroService, llm_client: Any) -> None:
        self._macro = macro_service
        self._llm = llm_client

    async def get_macro_report(self, ticker: str, sector: str | None = None) -> MacroToolReport:
        """Berechnet Makro-Score via Claude Tool-Use Loop."""
        try:
            ctx = await self._macro.get_context()
        except Exception as exc:
            _logger.error("MacroService.get_context() fehlgeschlagen: %s", exc)
            return self._fallback(ticker, 0.25, 0.93)

        # Pre-cache tool results — LLM ruft Tools auf, wir antworten mit echten Daten
        _tool_data: dict[str, Any] = {
            "get_snb_rate": {"leitzins": ctx.leitzins},
            "get_chf_eur": {"chf_eur": ctx.chf_eur},
            "get_inflation_ch": {"inflation_ch": ctx.inflation_ch or 0.8},
            "get_ticker_export_profile": {
                "ticker": ticker.upper(),
                "profile": (
                    "exportlastig" if ticker.upper() in _EXPORT_HEAVY
                    else "inlandsfokussiert" if ticker.upper() in _DOMESTIC_FOCUS
                    else "neutral"
                ),
                "sector": sector or "unbekannt",
            },
        }

        messages: list[dict[str, Any]] = [{
            "role": "user",
            "content": (
                f"Analysiere den Makro-Score für {ticker.upper()}"
                + (f" (Sektor: {sector})" if sector else "")
                + ". Rufe alle relevanten Tools auf und berechne den Score."
            ),
        }]

        try:
            for _ in range(_MAX_ITERATIONS):
                response = await self._llm.messages_create(
                    model=_MODEL,
                    system=_SYSTEM,
                    messages=messages,
                    tools=_MACRO_TOOLS,
                    max_tokens=_MAX_TOKENS,
                    feature="macro_agent_v2",
                )

                if response.stop_reason == "end_turn":
                    text_block = next(
                        (b for b in response.content if getattr(b, "type", None) == "text"), None
                    )
                    if text_block:
                        return self._parse(ticker, text_block.text, ctx.leitzins, ctx.chf_eur)
                    break

                # Tool-Use: Tool-Ergebnisse sammeln und zurückschicken
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        result = _tool_data.get(block.name, {"error": "Tool nicht gefunden"})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            _logger.error("MacroAgentV2 LLM-Loop fehlgeschlagen: %s", exc)

        return self._fallback(ticker, ctx.leitzins, ctx.chf_eur)

    def _parse(self, ticker: str, text: str, leitzins: float, chf_eur: float) -> MacroToolReport:
        try:
            data = json.loads(text.strip())
            return MacroToolReport(
                ticker=ticker.upper(),
                score=float(data["score"]),
                leitzins=leitzins,
                chf_eur=chf_eur,
                climate="tool-use",
                chf_impact=data.get("chf_impact", "NEUTRAL"),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValidationError, KeyError) as exc:
            _logger.warning("MacroAgentV2 parse-Fehler: %s", exc)
            return self._fallback(ticker, leitzins, chf_eur)

    @staticmethod
    def _fallback(ticker: str, leitzins: float, chf_eur: float) -> MacroToolReport:
        score = 50.0
        if leitzins <= 0.5:
            score += 15
        elif leitzins > 1.5:
            score -= 20
        return MacroToolReport(
            ticker=ticker.upper(),
            score=round(score, 2),
            leitzins=leitzins,
            chf_eur=chf_eur,
            climate="fallback",
            chf_impact="NEUTRAL",
            reasoning="Makro-Analyse nicht verfügbar — Fallback verwendet.",
        )
```

- [ ] **Step 4: Tests grün**

```bash
uv run pytest backend/tests/unit/application/test_macro_agent_v2.py -v
```
Erwartetes Ergebnis: `2 passed`

- [ ] **Step 5: Lint**

```bash
uv run ruff check backend/application/agents/macro_agent_v2.py backend/tests/unit/application/test_macro_agent_v2.py && uv run ruff format --check backend/application/agents/macro_agent_v2.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/application/agents/macro_agent_v2.py backend/tests/unit/application/test_macro_agent_v2.py
git commit -m "feat(multiagent): MacroAgent V2 — LLM Tool-Use statt rule-based if/elif"
```

---

## Task 3: CointelligenceAgent — On-Chain Intelligence mit Tool-Use

**Files:**
- Create: `backend/application/agents/cointelligence_agent.py`
- Test: `backend/tests/unit/application/test_cointelligence_agent.py`

**Interfaces:**
- Consumes: `CoinGeckoAdapter`, `FearGreedAdapter`, `MacroService.get_context()`, `LLMClient`, `Settings.glassnode_api_key`
- Produces: `CointelligenceAgent.analyze(coin: Literal["BTC","ETH"]) -> CointelligenceReport`

- [ ] **Step 1: Failing tests schreiben**

```python
# backend/tests/unit/application/test_cointelligence_agent.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.application.agents.cointelligence_agent import CointelligenceAgent
from backend.domain.schemas.multiagent_schemas import CointelligenceReport

pytestmark = pytest.mark.unit


def _make_agent(final_json: str | None = None):
    cg = AsyncMock()
    cg.get_market_data.return_value = [{
        "id": "bitcoin", "current_price": 95000.0,
        "market_cap": 1.8e12, "total_volume": 30e9,
        "price_change_percentage_24h_in_currency": 2.1,
    }]
    fg = AsyncMock()
    fg.get.return_value = {"value": 55, "label": "Greed"}
    macro = AsyncMock()
    macro_ctx = MagicMock()
    macro_ctx.chf_eur = 0.935
    macro.get_context.return_value = macro_ctx
    llm = AsyncMock()

    # Simulate tool-use loop: first response requests tools, second returns JSON
    tool_resp = MagicMock()
    tool_resp.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "get_coin_data"
    tool_block.id = "tu_1"
    tool_block.input = {"coin": "bitcoin"}
    tool_resp.content = [tool_block]

    final_resp = MagicMock()
    final_resp.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = final_json or """{
        "price_chf": 88825.0,
        "mvrv_zone": "FAIR",
        "fear_greed": 55,
        "sharpe_crypto": 0.9,
        "sharpe_smi": 0.5,
        "chf_usd_impact": "NEUTRAL",
        "regime_signal": "HOLD",
        "max_allocation_pct": 5.0,
        "reasoning": "BTC ist fair bewertet laut MVRV.",
        "disclaimer": "Hochspekulative Anlage. Keine Anlageberatung."
    }"""
    final_resp.content = [text_block]

    llm.messages_create.side_effect = [tool_resp, final_resp]
    return CointelligenceAgent(
        coingecko=cg, fear_greed=fg, macro_service=macro, llm_client=llm, glassnode_api_key=""
    )


@pytest.mark.asyncio
async def test_analyze_btc_returns_report():
    agent = _make_agent()
    report = await agent.analyze("BTC")
    assert isinstance(report, CointelligenceReport)
    assert report.coin == "BTC"
    assert report.regime_signal in ("ACCUMULATE", "HOLD", "CAUTION", "AVOID")
    assert report.max_allocation_pct <= 10.0
    assert "disclaimer" in report.disclaimer.lower() or len(report.disclaimer) > 10


@pytest.mark.asyncio
async def test_analyze_eth_works():
    agent = _make_agent()
    report = await agent.analyze("ETH")
    assert isinstance(report, CointelligenceReport)


@pytest.mark.asyncio
async def test_analyze_fallback_on_llm_error():
    cg = AsyncMock()
    cg.get_market_data.return_value = []
    fg = AsyncMock()
    fg.get.return_value = {"value": 50, "label": "Neutral"}
    macro = AsyncMock()
    ctx = MagicMock()
    ctx.chf_eur = 0.93
    macro.get_context.return_value = ctx
    llm = AsyncMock()
    llm.messages_create.side_effect = RuntimeError("API down")
    agent = CointelligenceAgent(
        coingecko=cg, fear_greed=fg, macro_service=macro, llm_client=llm, glassnode_api_key=""
    )
    report = await agent.analyze("BTC")
    assert isinstance(report, CointelligenceReport)
    assert report.regime_signal in ("ACCUMULATE", "HOLD", "CAUTION", "AVOID")
```

- [ ] **Step 2: Test ausführen — muss FAIL**

```bash
uv run pytest backend/tests/unit/application/test_cointelligence_agent.py -v
```

- [ ] **Step 3: CointelligenceAgent implementieren**

```python
# backend/application/agents/cointelligence_agent.py
"""CointelligenceAgent — On-Chain Intelligence für BTC/ETH via Claude Tool-Use."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from backend.application.services.macro_service import MacroService
from backend.domain.schemas.multiagent_schemas import CointelligenceReport
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter

_logger = logging.getLogger(__name__)
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024
_MAX_ITERATIONS = 6
_DISCLAIMER = (
    "Kryptowährungen sind hochspekulative Anlagen mit erheblichem Verlustrisiko. "
    "Diese Analyse ist keine Anlageberatung. Nie mehr als 5–10% des freien Vermögens."
)

_COIN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_coin_data",
        "description": "Aktueller Preis (USD + CHF), Market Cap, 24h-Veränderung für BTC oder ETH.",
        "input_schema": {
            "type": "object",
            "properties": {"coin": {"type": "string", "enum": ["bitcoin", "ethereum"]}},
            "required": ["coin"],
        },
    },
    {
        "name": "get_mvrv_z_score",
        "description": "Bitcoin MVRV-Z-Score (>7=EXTREME teuer, 3-7=EXPENSIVE, 0-3=FAIR, <0=UNDERBOUGHT). Nur für BTC.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fear_greed_index",
        "description": "Crypto Fear & Greed Index (0=extreme Angst, 100=extreme Gier).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_sharpe_comparison",
        "description": "Vergleicht annualisierte Sharpe Ratio von BTC oder ETH vs. ^SSMI (SMI) über 365 Tage.",
        "input_schema": {
            "type": "object",
            "properties": {"coin": {"type": "string", "enum": ["BTC-USD", "ETH-USD"]}},
            "required": ["coin"],
        },
    },
    {
        "name": "get_chf_usd_rate",
        "description": "Aktueller CHF/USD-Kurs (relevant für Schweizer Investoren).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

_SYSTEM = """Du bist ein nüchterner Krypto-Analyst für Schweizer Privatanleger (freie Mittel, NICHT 3a).
Nutze alle verfügbaren Tools um ein vollständiges Bild zu bekommen.
Berücksichtige: CHF-Denomination, On-Chain-Bewertung (MVRV), Risikostimmung (Fear&Greed), Sharpe vs. SMI.

Antworte NUR mit JSON (kein Markdown, kein Text davor/danach):
{
  "price_chf": float,
  "mvrv_zone": "UNDERBOUGHT|FAIR|EXPENSIVE|EXTREME|UNKNOWN",
  "fear_greed": int,
  "sharpe_crypto": float,
  "sharpe_smi": float,
  "chf_usd_impact": "GÜNSTIG|NEUTRAL|UNGÜNSTIG",
  "regime_signal": "ACCUMULATE|HOLD|CAUTION|AVOID",
  "max_allocation_pct": float,
  "reasoning": "max 3 Sätze, nüchtern, faktenbasiert",
  "disclaimer": "Kryptowährungen sind hochspekulative Anlagen..."
}

Regeln:
- max_allocation_pct NIEMALS über 10
- Bei MVRV > 5 oder Fear&Greed > 80: regime_signal = CAUTION oder AVOID
- Bei MVRV < 0: regime_signal = ACCUMULATE möglich
- Immer CHF-Währungsrisiko erwähnen im reasoning"""


class CointelligenceAgent:
    def __init__(
        self,
        coingecko: CoinGeckoAdapter,
        fear_greed: FearGreedAdapter,
        macro_service: MacroService,
        llm_client: Any,
        glassnode_api_key: str = "",
    ) -> None:
        self._cg = coingecko
        self._fg = fear_greed
        self._macro = macro_service
        self._llm = llm_client
        self._glassnode_key = glassnode_api_key

    async def analyze(self, coin: Literal["BTC", "ETH"]) -> CointelligenceReport:
        coingecko_id = "bitcoin" if coin == "BTC" else "ethereum"
        yf_ticker = "BTC-USD" if coin == "BTC" else "ETH-USD"

        # Pre-fetch alle Daten für Tool-Antworten
        tool_cache = await self._prefetch(coingecko_id, yf_ticker, coin)

        messages: list[dict[str, Any]] = [{
            "role": "user",
            "content": (
                f"Analysiere {coin} für einen Schweizer Privatanleger (freie Mittel, nicht 3a). "
                "Nutze alle Tools um ein vollständiges Bild zu bekommen. "
                "Berücksichtige CHF-Denomination, On-Chain-Bewertung, Risikostimmung, Sharpe vs. SMI."
            ),
        }]

        try:
            for _ in range(_MAX_ITERATIONS):
                response = await self._llm.messages_create(
                    model=_MODEL,
                    system=_SYSTEM,
                    messages=messages,
                    tools=_COIN_TOOLS,
                    max_tokens=_MAX_TOKENS,
                    feature="cointelligence",
                )

                if response.stop_reason == "end_turn":
                    text_block = next(
                        (b for b in response.content if getattr(b, "type", None) == "text"), None
                    )
                    if text_block:
                        return self._parse(coin, text_block.text, tool_cache)
                    break

                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        result = tool_cache.get(block.name, {"error": "Tool nicht gefunden"})
                        if block.name == "get_coin_data":
                            result = tool_cache.get(f"get_coin_data_{block.input.get('coin','bitcoin')}", result)
                        elif block.name == "get_sharpe_comparison":
                            result = tool_cache.get(f"get_sharpe_{block.input.get('coin','BTC-USD')}", result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            _logger.error("CointelligenceAgent fehlgeschlagen: %s", exc)

        return self._fallback(coin, tool_cache)

    async def _prefetch(self, coingecko_id: str, yf_ticker: str, coin: str) -> dict[str, Any]:
        """Lädt alle Daten vorab (parallel) für schnelle Tool-Antworten."""
        cache: dict[str, Any] = {}

        async def _safe(key: str, coro: Any) -> None:
            try:
                cache[key] = await coro
            except Exception as exc:
                _logger.warning("Prefetch %s fehlgeschlagen: %s", key, exc)
                cache[key] = {"error": str(exc)}

        # Makro-Kontext für CHF/USD
        try:
            ctx = await self._macro.get_context()
            chf_usd = round(ctx.chf_eur / 1.08, 4)  # CHF/EUR * EUR/USD ≈ CHF/USD
        except Exception:
            chf_usd = 0.89

        # CoinGecko
        try:
            market = await self._cg.get_market_data([coingecko_id])
            if market:
                d = market[0]
                price_usd = float(d.get("current_price", 0))
                price_chf = round(price_usd * chf_usd, 2)
                cache[f"get_coin_data_{coingecko_id}"] = {
                    "coin": coingecko_id,
                    "price_usd": price_usd,
                    "price_chf": price_chf,
                    "market_cap_usd": d.get("market_cap", 0),
                    "price_change_24h_pct": d.get("price_change_percentage_24h_in_currency", 0),
                }
                cache["get_coin_data"] = cache[f"get_coin_data_{coingecko_id}"]
        except Exception as exc:
            _logger.warning("CoinGecko prefetch fehlgeschlagen: %s", exc)

        # Fear & Greed
        try:
            fg = await self._fg.get()
            cache["get_fear_greed_index"] = {"value": fg["value"], "label": fg["label"]}
        except Exception:
            cache["get_fear_greed_index"] = {"value": 50, "label": "Neutral"}

        # CHF/USD
        cache["get_chf_usd_rate"] = {"chf_usd": chf_usd, "note": "Approximation via CHF/EUR"}

        # Glassnode MVRV (nur für BTC)
        if coin == "BTC" and self._glassnode_key:
            await _safe("get_mvrv_z_score", self._fetch_mvrv())
        else:
            cache["get_mvrv_z_score"] = {"mvrv_z": None, "zone": "UNKNOWN", "note": "Kein Glassnode-Key"}

        # Sharpe (async via to_thread)
        await _safe(f"get_sharpe_{yf_ticker}", self._calc_sharpe(yf_ticker))
        cache["get_sharpe_comparison"] = cache.get(f"get_sharpe_{yf_ticker}", {})

        return cache

    async def _fetch_mvrv(self) -> dict[str, Any]:
        url = "https://api.glassnode.com/v1/metrics/market/mvrv_z_score"
        params = {"a": "BTC", "api_key": self._glassnode_key, "i": "24h", "f": "JSON"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            if r.status_code == 200:
                data = r.json()
                latest = data[-1]["v"] if data else None
                zone = (
                    "EXTREME" if latest and latest > 7
                    else "EXPENSIVE" if latest and latest > 3
                    else "FAIR" if latest and latest > 0
                    else "UNDERBOUGHT" if latest is not None
                    else "UNKNOWN"
                )
                return {"mvrv_z": latest, "zone": zone}
        return {"mvrv_z": None, "zone": "UNKNOWN"}

    async def _calc_sharpe(self, yf_ticker: str) -> dict[str, Any]:
        def _sync() -> dict[str, Any]:
            import numpy as np
            import yfinance as yf  # noqa: PLC0415
            rf = 0.0025 / 252
            try:
                coin_hist = yf.Ticker(yf_ticker).history(period="365d")["Close"].pct_change().dropna()
                smi_hist = yf.Ticker("^SSMI").history(period="365d")["Close"].pct_change().dropna()

                def sharpe(r: Any) -> float:
                    std = float(r.std())
                    return float((r.mean() - rf) / std * (252**0.5)) if std > 1e-8 else 0.0

                return {"crypto_sharpe": round(sharpe(coin_hist), 3), "smi_sharpe": round(sharpe(smi_hist), 3)}
            except Exception:
                return {"crypto_sharpe": 0.0, "smi_sharpe": 0.0}
        return await asyncio.to_thread(_sync)

    def _parse(self, coin: Literal["BTC", "ETH"], text: str, cache: dict[str, Any]) -> CointelligenceReport:
        try:
            # JSON aus Text extrahieren (falls LLM Text voranstellt)
            start = text.find("{")
            end = text.rfind("}") + 1
            data = json.loads(text[start:end])
            sharpe = cache.get("get_sharpe_comparison", {})
            return CointelligenceReport(
                coin=coin,
                price_chf=float(data.get("price_chf", 0)),
                mvrv_zone=data.get("mvrv_zone", "UNKNOWN"),
                fear_greed=int(data.get("fear_greed", 50)),
                sharpe_crypto=float(data.get("sharpe_crypto", sharpe.get("crypto_sharpe", 0.0))),
                sharpe_smi=float(data.get("sharpe_smi", sharpe.get("smi_sharpe", 0.0))),
                chf_usd_impact=data.get("chf_usd_impact", "NEUTRAL"),
                regime_signal=data.get("regime_signal", "HOLD"),
                max_allocation_pct=min(float(data.get("max_allocation_pct", 5.0)), 10.0),
                reasoning=data.get("reasoning", ""),
                disclaimer=data.get("disclaimer", _DISCLAIMER),
            )
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            _logger.warning("CointelligenceAgent parse-Fehler: %s", exc)
            return self._fallback(coin, cache)

    @staticmethod
    def _fallback(coin: Literal["BTC", "ETH"], cache: dict[str, Any]) -> CointelligenceReport:
        fg = cache.get("get_fear_greed_index", {}).get("value", 50)
        coin_data = cache.get("get_coin_data", {})
        price_chf = float(coin_data.get("price_chf", 0))
        regime = "CAUTION" if fg > 75 else "HOLD"
        return CointelligenceReport(
            coin=coin,
            price_chf=price_chf,
            mvrv_zone="UNKNOWN",
            fear_greed=fg,
            sharpe_crypto=0.0,
            sharpe_smi=0.0,
            chf_usd_impact="NEUTRAL",
            regime_signal=regime,
            max_allocation_pct=5.0,
            reasoning="Analyse nicht verfügbar — Fallback verwendet.",
            disclaimer=_DISCLAIMER,
        )
```

- [ ] **Step 4: Tests grün**

```bash
uv run pytest backend/tests/unit/application/test_cointelligence_agent.py -v
```

- [ ] **Step 5: Lint**

```bash
uv run ruff check backend/application/agents/cointelligence_agent.py && uv run ruff format --check backend/application/agents/cointelligence_agent.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/application/agents/cointelligence_agent.py backend/tests/unit/application/test_cointelligence_agent.py
git commit -m "feat(multiagent): CointelligenceAgent — On-Chain Tool-Use für BTC/ETH"
```

---

## Task 4: InvestmentDirector — SSE-Orchestrator mit HITL

**Files:**
- Create: `backend/application/agents/investment_director.py`
- Test: `backend/tests/unit/application/test_investment_director.py`

**Interfaces:**
- Consumes: `MacroAgentV2`, `SwissQuantScorer` (via StockService), `SteuerAgent`, `LLMClient`
- Produces:
  - `InvestmentDirector.run_with_events(ticker, context, run_id, queue)` — schreibt `DirectorEvent` in Queue
  - `InvestmentDirector.resolve_checkpoint(cp_id, answer)` — löst HITL auf
  - `InvestmentDirector` als Singleton über app-state

- [ ] **Step 1: Failing tests**

```python
# backend/tests/unit/application/test_investment_director.py
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.application.agents.investment_director import InvestmentDirector
from backend.domain.schemas.multiagent_schemas import MacroToolReport

pytestmark = pytest.mark.unit


def _make_director():
    macro = AsyncMock()
    macro.get_macro_report.return_value = MacroToolReport(
        ticker="NESN.SW", score=62.5, leitzins=0.25, chf_eur=0.935,
        climate="tool-use", chf_impact="NEGATIV", reasoning="Starker CHF."
    )
    stock_service = AsyncMock()
    mock_stock = MagicMock()
    mock_stock.quant_score = 72.0
    mock_stock.signal = "BUY"
    stock_service.get_decision.return_value = mock_stock
    steuer = AsyncMock()
    mock_steuer = MagicMock()
    mock_steuer.steuerarten = ["Verrechnungssteuer (35%)"]
    mock_steuer.hinweise = ["Kapitalgewinne steuerfrei für Privatpersonen."]
    steuer.einschaetzen.return_value = mock_steuer
    return InvestmentDirector(
        macro_agent=macro,
        stock_service=stock_service,
        steuer_agent=steuer,
    )


@pytest.mark.asyncio
async def test_director_emits_events():
    director = _make_director()
    queue: asyncio.Queue = asyncio.Queue()
    await director.run_with_events(
        ticker="NESN.SW", context="freie_mittel", run_id="r1", event_queue=queue
    )
    events = []
    while not queue.empty():
        events.append(await queue.get())
    types = [e["type"] for e in events]
    assert "step" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_director_emits_checkpoint_when_context_unknown():
    director = _make_director()
    queue: asyncio.Queue = asyncio.Queue()

    async def resolve_after_delay():
        await asyncio.sleep(0.05)
        events = []
        while not queue.empty():
            events.append(await queue.get())
        cp = next((e for e in events if e["type"] == "checkpoint"), None)
        if cp:
            await director.resolve_checkpoint(cp["checkpoint_id"], "3a-Konto (VIAC)")

    asyncio.create_task(resolve_after_delay())
    await director.run_with_events(
        ticker="NESN.SW", context="unknown", run_id="r2", event_queue=queue
    )
    events = []
    while not queue.empty():
        events.append(await queue.get())
    all_events = events
    assert any(e["type"] == "done" for e in all_events)


@pytest.mark.asyncio
async def test_director_resolve_checkpoint():
    director = _make_director()
    # Register a fake checkpoint
    event = asyncio.Event()
    director._checkpoints["cp_test"] = event  # type: ignore[attr-defined]
    director._checkpoint_answers["cp_test"] = None  # type: ignore[attr-defined]
    await director.resolve_checkpoint("cp_test", "3a")
    assert director._checkpoint_answers["cp_test"] == "3a"  # type: ignore[attr-defined]
    assert event.is_set()
```

- [ ] **Step 2: Test ausführen — muss FAIL**

```bash
uv run pytest backend/tests/unit/application/test_investment_director.py -v
```

- [ ] **Step 3: InvestmentDirector implementieren**

```python
# backend/application/agents/investment_director.py
"""InvestmentDirector — SSE-Orchestrator mit HITL-Checkpoints.

Fan-out: MacroAgentV2 + StockService (Quant) + SteuerAgent (parallel)
HITL:   asyncio.Event wartet auf User-Antwort über /checkpoint-Endpoint
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from backend.application.agents.macro_agent_v2 import MacroAgentV2
from backend.application.agents.steuer_agent import SteuerAgent
from backend.domain.schemas.multiagent_schemas import DirectorEvent

_logger = logging.getLogger(__name__)
_CHECKPOINT_TIMEOUT = 600  # 10 Minuten


class InvestmentDirector:
    def __init__(
        self,
        macro_agent: MacroAgentV2,
        stock_service: Any,
        steuer_agent: SteuerAgent,
    ) -> None:
        self._macro = macro_agent
        self._stocks = stock_service
        self._steuer = steuer_agent
        self._checkpoints: dict[str, asyncio.Event] = {}
        self._checkpoint_answers: dict[str, str | None] = {}

    async def run_with_events(
        self,
        ticker: str,
        context: str,
        run_id: str,
        event_queue: asyncio.Queue,
    ) -> None:
        """Orchestriert alle Agents und schreibt Events in die Queue."""

        async def emit(event: dict[str, Any]) -> None:
            await event_queue.put(event)

        await emit({"type": "step", "agent": "Director", "status": "planning",
                    "result": f"Starte Analyse für {ticker}..."})

        # --- Fan-out: Macro + Quant parallel ---
        await emit({"type": "step", "agent": "MacroAgent V2", "status": "running"})
        await emit({"type": "step", "agent": "QuantAgent", "status": "running"})

        macro_task = asyncio.create_task(self._run_macro(ticker))
        quant_task = asyncio.create_task(self._run_quant(ticker))

        macro_result, quant_result = await asyncio.gather(macro_task, quant_task, return_exceptions=True)

        if isinstance(macro_result, Exception):
            await emit({"type": "step", "agent": "MacroAgent V2", "status": "error",
                        "result": str(macro_result)})
            macro_result = None
        else:
            await emit({"type": "step", "agent": "MacroAgent V2", "status": "done",
                        "result": f"Score: {macro_result.score:.0f}/100 | {macro_result.chf_impact}"})

        if isinstance(quant_result, Exception):
            await emit({"type": "step", "agent": "QuantAgent", "status": "error",
                        "result": str(quant_result)})
            quant_result = None
        else:
            quant_display = getattr(quant_result, 'signal', '?')
            quant_score = getattr(quant_result, 'quant_score', 0)
            await emit({"type": "step", "agent": "QuantAgent", "status": "done",
                        "result": f"Signal: {quant_display} | Score: {quant_score:.0f}"})

        # --- HITL: Kontext klären ---
        if context == "unknown":
            cp_id = f"cp_{uuid.uuid4().hex[:8]}"
            await emit({
                "type": "checkpoint",
                "checkpoint_id": cp_id,
                "message": f"Für welches Konto analysiere ich {ticker}?",
                "options": ["3a-Konto (VIAC)", "Freie Mittel", "Beides analysieren"],
            })
            context = await self._wait_for_checkpoint(cp_id)

        # Kontext auf SteuerAgent-Profil mappen
        anlegerprofil = "vorsorge_3a" if "3a" in context.lower() else "privatperson"

        # --- SteuerAgent ---
        await emit({"type": "step", "agent": "SteuerAgent", "status": "running"})
        try:
            steuer_result = await self._steuer.einschaetzen(
                ticker=ticker,
                anlegerprofil=anlegerprofil,
                halteperiode_jahre=3,
            )
            await emit({"type": "step", "agent": "SteuerAgent", "status": "done",
                        "result": f"{anlegerprofil} | {', '.join(steuer_result.steuerarten[:2])}"})
        except Exception as exc:
            _logger.warning("SteuerAgent fehlgeschlagen: %s", exc)
            steuer_result = None
            await emit({"type": "step", "agent": "SteuerAgent", "status": "error",
                        "result": str(exc)})

        # --- Finale Synthese ---
        signal = (getattr(quant_result, 'signal', 'HOLD') if quant_result else "HOLD")
        confidence = self._calc_confidence(macro_result, quant_result)

        await emit({
            "type": "done",
            "run_id": run_id,
            "signal": signal,
            "confidence": confidence,
            "report": {
                "ticker": ticker,
                "context": context,
                "macro_score": macro_result.score if macro_result else None,
                "macro_reasoning": macro_result.reasoning if macro_result else None,
                "chf_impact": macro_result.chf_impact if macro_result else None,
                "quant_signal": getattr(quant_result, 'signal', None),
                "quant_score": getattr(quant_result, 'quant_score', None),
                "steuer_arten": steuer_result.steuerarten if steuer_result else [],
                "steuer_hinweise": steuer_result.hinweise[:2] if steuer_result else [],
                "anlegerprofil": anlegerprofil,
            },
        })

    async def resolve_checkpoint(self, checkpoint_id: str, answer: str) -> None:
        """Vom Checkpoint-Endpoint aufgerufen wenn User antwortet."""
        self._checkpoint_answers[checkpoint_id] = answer
        event = self._checkpoints.get(checkpoint_id)
        if event:
            event.set()

    async def _wait_for_checkpoint(self, cp_id: str) -> str:
        event = asyncio.Event()
        self._checkpoints[cp_id] = event
        self._checkpoint_answers[cp_id] = None
        try:
            await asyncio.wait_for(event.wait(), timeout=_CHECKPOINT_TIMEOUT)
        except asyncio.TimeoutError:
            _logger.warning("Checkpoint %s timed out nach %ds", cp_id, _CHECKPOINT_TIMEOUT)
        finally:
            self._checkpoints.pop(cp_id, None)
        return self._checkpoint_answers.pop(cp_id, None) or "freie_mittel"

    async def _run_macro(self, ticker: str) -> Any:
        return await self._macro.get_macro_report(ticker)

    async def _run_quant(self, ticker: str) -> Any:
        return await self._stocks.get_decision(ticker)

    @staticmethod
    def _calc_confidence(macro: Any, quant: Any) -> float:
        score = 0.5
        if macro is not None:
            score += (macro.score - 50) / 200  # [-0.25, +0.25]
        if quant is not None:
            qs = getattr(quant, 'quant_score', 50)
            score += (qs - 50) / 200
        return round(min(max(score, 0.0), 1.0), 3)
```

- [ ] **Step 4: Tests grün**

```bash
uv run pytest backend/tests/unit/application/test_investment_director.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/application/agents/investment_director.py backend/tests/unit/application/test_investment_director.py
git commit -m "feat(multiagent): InvestmentDirector — SSE-Orchestrator mit HITL-Checkpoints"
```

---

## Task 5: Analyze Router + SSE Endpoint

**Files:**
- Create: `backend/interfaces/rest/routers/analyze.py`
- Modify: `backend/interfaces/rest/app.py`
- Modify: `backend/interfaces/rest/dependencies.py`
- Test: `backend/tests/unit/interfaces/test_analyze_router.py`

**Interfaces:**
- Consumes: `InvestmentDirector` (singleton via app state)
- Produces:
  - `GET /api/v1/analyze/stream?ticker=NESN.SW&context=unknown` → SSE
  - `POST /api/v1/analyze/checkpoint/{cp_id}` → JSON

- [ ] **Step 1: Failing test**

```python
# backend/tests/unit/interfaces/test_analyze_router.py
from __future__ import annotations
import asyncio
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.unit


def _make_app():
    from backend.interfaces.rest.routers.analyze import router as analyze_router
    from backend.interfaces.rest.dependencies import get_investment_director
    from backend.domain.schemas.multiagent_schemas import DirectorEvent

    app = FastAPI()
    app.include_router(analyze_router, prefix="/api/v1")

    mock_director = AsyncMock()

    async def _fake_run(ticker, context, run_id, event_queue):
        await event_queue.put({"type": "step", "agent": "Director", "status": "planning"})
        await event_queue.put({"type": "done", "run_id": run_id, "signal": "BUY", "confidence": 0.7})

    mock_director.run_with_events.side_effect = _fake_run
    mock_director.resolve_checkpoint = AsyncMock(return_value=None)

    app.dependency_overrides[get_investment_director] = lambda: mock_director
    return app


def test_checkpoint_endpoint_returns_200():
    app = _make_app()
    client = TestClient(app)
    response = client.post(
        "/api/v1/analyze/checkpoint/cp_test",
        json={"answer": "3a-Konto (VIAC)"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "received"
```

- [ ] **Step 2: Test ausführen — muss FAIL**

```bash
uv run pytest backend/tests/unit/interfaces/test_analyze_router.py -v
```

- [ ] **Step 3: Analyze Router implementieren**

```python
# backend/interfaces/rest/routers/analyze.py
"""Analyze Router — SSE-Stream + HITL-Checkpoint für InvestmentDirector."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.domain.schemas.multiagent_schemas import CheckpointAnswer
from backend.interfaces.rest.dependencies import get_investment_director

router = APIRouter(tags=["analyze"])


@router.get("/analyze/stream")
async def analyze_stream(
    ticker: str,
    context: str = "unknown",
    director: Any = Depends(get_investment_director),
) -> StreamingResponse:
    """SSE-Endpoint: InvestmentDirector schreibt Events in Queue → Browser."""
    run_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()

    asyncio.create_task(
        director.run_with_events(
            ticker=ticker,
            context=context,
            run_id=run_id,
            event_queue=queue,
        )
    )

    async def event_stream() -> AsyncIterator[str]:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"error\", \"error\": \"Timeout\"}\n\n"
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze/checkpoint/{checkpoint_id}")
async def submit_checkpoint(
    checkpoint_id: str,
    body: CheckpointAnswer,
    director: Any = Depends(get_investment_director),
) -> dict[str, str]:
    """User-Antwort auf einen Director-Checkpoint."""
    await director.resolve_checkpoint(checkpoint_id, body.answer)
    return {"status": "received"}
```

- [ ] **Step 4: `get_investment_director()` Dependency hinzufügen**

In `backend/interfaces/rest/dependencies.py` am Ende hinzufügen:

```python
# --- InvestmentDirector ---
_director_instance: Any = None


def get_investment_director() -> Any:
    """Gibt den InvestmentDirector-Singleton zurück (lazy init)."""
    global _director_instance
    if _director_instance is None:
        from backend.application.agents.investment_director import InvestmentDirector
        from backend.application.agents.macro_agent_v2 import MacroAgentV2
        _director_instance = InvestmentDirector(
            macro_agent=MacroAgentV2(
                macro_service=get_macro_service(),
                llm_client=get_llm_client(),
            ),
            stock_service=get_stock_service(),
            steuer_agent=get_steuer_agent(),
        )
    return _director_instance
```

- [ ] **Step 5: Router in `app.py` registrieren**

In `backend/interfaces/rest/app.py`, nach den bestehenden `app.include_router(...)` Aufrufen:

```python
from backend.interfaces.rest.routers.analyze import router as analyze_router
app.include_router(analyze_router, prefix="/api/v1")
```

- [ ] **Step 6: Tests grün**

```bash
uv run pytest backend/tests/unit/interfaces/test_analyze_router.py -v
uv run pytest backend/tests/unit -q --tb=short 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add backend/interfaces/rest/routers/analyze.py backend/tests/unit/interfaces/test_analyze_router.py backend/interfaces/rest/dependencies.py backend/interfaces/rest/app.py
git commit -m "feat(multiagent): SSE analyze-stream Endpoint + HITL-Checkpoint Router"
```

---

## Task 6: DataStewardAgent — Datenpflege Cron

**Files:**
- Create: `backend/application/agents/data_steward_agent.py`
- Create: `backend/scripts/data_steward_run.py`
- Modify: `render.yaml`
- Test: `backend/tests/unit/application/test_data_steward_agent.py`

**Interfaces:**
- Consumes: `SwissStockRepository`, `YFinanceSwissAdapter`, `MacroService`, `CronRunRepository`
- Produces: `DataStewardAgent.run_check() -> DataStewardReport`

- [ ] **Step 1: Failing tests**

```python
# backend/tests/unit/application/test_data_steward_agent.py
from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from backend.application.agents.data_steward_agent import DataStewardAgent, DataStewardReport

pytestmark = pytest.mark.unit


def _make_agent(stocks=None, price_age_hours=48):
    repo = AsyncMock()
    mock_stock = MagicMock()
    mock_stock.ticker = "NESN.SW"
    mock_stock.last_updated_at = datetime.now(UTC) - timedelta(hours=price_age_hours)
    repo.list_all.return_value = stocks or [mock_stock]

    yf = AsyncMock()
    yf.get_latest_price.return_value = 105.2

    macro = AsyncMock()
    macro_ctx = MagicMock()
    macro_ctx.fetched_at = datetime.now(UTC) - timedelta(hours=8)
    macro.get_context.return_value = macro_ctx

    return DataStewardAgent(stock_repo=repo, yf_adapter=yf, macro_service=macro)


@pytest.mark.asyncio
async def test_stale_price_triggers_refresh():
    agent = _make_agent(price_age_hours=40)  # > 36h threshold
    report = await agent.run_check()
    assert isinstance(report, DataStewardReport)
    assert "NESN.SW" in report.refreshed_tickers


@pytest.mark.asyncio
async def test_fresh_price_no_refresh():
    agent = _make_agent(price_age_hours=10)  # < 36h
    report = await agent.run_check()
    assert "NESN.SW" not in report.refreshed_tickers


@pytest.mark.asyncio
async def test_price_spike_quarantined():
    repo = AsyncMock()
    mock_stock = MagicMock()
    mock_stock.ticker = "NESN.SW"
    mock_stock.last_updated_at = datetime.now(UTC) - timedelta(hours=40)
    mock_stock.last_price = 100.0
    repo.list_all.return_value = [mock_stock]
    yf = AsyncMock()
    yf.get_latest_price.return_value = 120.0  # +20% → Spike
    macro = AsyncMock()
    macro.get_context.return_value = MagicMock()
    agent = DataStewardAgent(stock_repo=repo, yf_adapter=yf, macro_service=macro)
    report = await agent.run_check()
    assert "NESN.SW" in report.quarantined_tickers
```

- [ ] **Step 2: Test ausführen — muss FAIL**

```bash
uv run pytest backend/tests/unit/application/test_data_steward_agent.py -v
```

- [ ] **Step 3: DataStewardAgent implementieren**

```python
# backend/application/agents/data_steward_agent.py
"""DataStewardAgent — automatische Datenpflege und Freshness-Check."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

_logger = logging.getLogger(__name__)

_PRICE_STALE_HOURS = 36
_PRICE_SPIKE_PCT = 15.0  # Preissprung >15% → Quarantäne


class DataStewardReport(BaseModel):
    run_at: datetime
    checked_tickers: list[str]
    refreshed_tickers: list[str]
    quarantined_tickers: list[str]
    errors: list[str]
    duration_seconds: float


class DataStewardAgent:
    def __init__(
        self,
        stock_repo: Any,
        yf_adapter: Any,
        macro_service: Any,
    ) -> None:
        self._repo = stock_repo
        self._yf = yf_adapter
        self._macro = macro_service

    async def run_check(self) -> DataStewardReport:
        start = datetime.now(UTC)
        refreshed: list[str] = []
        quarantined: list[str] = []
        errors: list[str] = []
        checked: list[str] = []

        try:
            stocks = await self._repo.list_all()
        except Exception as exc:
            _logger.error("DataSteward: list_all() fehlgeschlagen: %s", exc)
            return DataStewardReport(
                run_at=start, checked_tickers=[], refreshed_tickers=[],
                quarantined_tickers=[], errors=[str(exc)],
                duration_seconds=0.0,
            )

        now = datetime.now(UTC)
        stale_threshold = now - timedelta(hours=_PRICE_STALE_HOURS)

        for stock in stocks:
            ticker = stock.ticker
            checked.append(ticker)
            last_price = getattr(stock, "last_price", None)
            last_updated = getattr(stock, "last_updated_at", None)

            if last_updated is None or last_updated < stale_threshold:
                try:
                    new_price = await self._yf.get_latest_price(ticker)
                    if last_price and last_price > 0:
                        change_pct = abs(new_price - last_price) / last_price * 100
                        if change_pct > _PRICE_SPIKE_PCT:
                            _logger.warning(
                                "Preissprung %s: %.1f%% (alt: %.2f, neu: %.2f) → Quarantäne",
                                ticker, change_pct, last_price, new_price,
                            )
                            quarantined.append(ticker)
                            continue
                    refreshed.append(ticker)
                    _logger.info("Preis-Refresh %s: %.2f CHF", ticker, new_price)
                except Exception as exc:
                    errors.append(f"{ticker}: {exc}")
                    _logger.error("Preis-Refresh %s fehlgeschlagen: %s", ticker, exc)

        duration = (datetime.now(UTC) - start).total_seconds()
        _logger.info(
            "DataSteward fertig: %d geprüft, %d refreshed, %d quarantiniert, %d Fehler (%.1fs)",
            len(checked), len(refreshed), len(quarantined), len(errors), duration,
        )
        return DataStewardReport(
            run_at=start,
            checked_tickers=checked,
            refreshed_tickers=refreshed,
            quarantined_tickers=quarantined,
            errors=errors,
            duration_seconds=duration,
        )
```

- [ ] **Step 4: Cron-Script erstellen**

```python
# backend/scripts/data_steward_run.py
"""Data Steward Cron — täglich 06:00 UTC via Render."""
from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("data_steward_run")


async def main() -> None:
    from backend.config import get_settings
    from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
    from backend.infrastructure.persistence.session import get_session_factory
    from backend.infrastructure.persistence.repositories.swiss_stock_repository import SwissStockSQLARepository
    from backend.application.services.macro_service import MacroService
    from backend.application.agents.data_steward_agent import DataStewardAgent

    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        repo = SwissStockSQLARepository(session)
        yf = YFinanceSwissAdapter()
        macro = MacroService(llm_client=None)
        agent = DataStewardAgent(stock_repo=repo, yf_adapter=yf, macro_service=macro)
        report = await agent.run_check()
        log.info(
            "=== DataSteward Report: %d refreshed, %d quarantiniert, %d Fehler ===",
            len(report.refreshed_tickers),
            len(report.quarantined_tickers),
            len(report.errors),
        )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: render.yaml Cron hinzufügen**

Im `render.yaml`, nach dem bestehenden `prisma-stock-daily` Cron-Block:

```yaml
  - type: cron
    name: prisma-data-steward
    runtime: python
    buildCommand: pip install uv && uv sync
    schedule: "0 6 30 * *"
    startCommand: uv run python -m backend.scripts.data_steward_run
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: prisma-db
          property: connectionString
      - key: ANTHROPIC_API_KEY
        sync: false
```

- [ ] **Step 6: Tests grün**

```bash
uv run pytest backend/tests/unit/application/test_data_steward_agent.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/application/agents/data_steward_agent.py backend/scripts/data_steward_run.py backend/tests/unit/application/test_data_steward_agent.py render.yaml
git commit -m "feat(multiagent): DataStewardAgent — Freshness-Check + Preis-Refresh-Trigger + Cron"
```

---

## Task 7: CointelligenceAgent Endpoint + Dependency

**Files:**
- Modify: `backend/interfaces/rest/routers/crypto.py`
- Modify: `backend/interfaces/rest/dependencies.py`
- Test: `backend/tests/unit/interfaces/rest/test_cointelligence_endpoint.py`

**Interfaces:**
- Consumes: `CointelligenceAgent` (via Dependency)
- Produces: `POST /api/v1/crypto/intelligence {"coin": "BTC"}` → `CointelligenceReport`

- [ ] **Step 1: Failing test**

```python
# backend/tests/unit/interfaces/rest/test_cointelligence_endpoint.py
from __future__ import annotations
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from backend.domain.schemas.multiagent_schemas import CointelligenceReport

pytestmark = pytest.mark.unit

_MOCK_REPORT = CointelligenceReport(
    coin="BTC", price_chf=88000.0, mvrv_zone="FAIR", fear_greed=50,
    sharpe_crypto=0.8, sharpe_smi=0.5, chf_usd_impact="NEUTRAL",
    regime_signal="HOLD", max_allocation_pct=5.0,
    reasoning="Fair bewertet.", disclaimer="Hochspekulative Anlage."
)


def _make_app():
    from backend.interfaces.rest.routers.crypto import router as crypto_router
    from backend.interfaces.rest.dependencies import get_cointelligence_agent
    app = FastAPI()
    app.include_router(crypto_router, prefix="/api/v1")
    mock_agent = AsyncMock()
    mock_agent.analyze.return_value = _MOCK_REPORT
    app.dependency_overrides[get_cointelligence_agent] = lambda: mock_agent
    return app


def test_cointelligence_btc_returns_report():
    app = _make_app()
    client = TestClient(app)
    response = client.post("/api/v1/crypto/intelligence", json={"coin": "BTC"})
    assert response.status_code == 200
    data = response.json()
    assert data["coin"] == "BTC"
    assert data["regime_signal"] == "HOLD"
    assert data["max_allocation_pct"] <= 10.0
```

- [ ] **Step 2: `get_cointelligence_agent()` Dependency hinzufügen**

In `backend/interfaces/rest/dependencies.py`:

```python
_cointelligence_instance: Any = None


def get_cointelligence_agent() -> Any:
    global _cointelligence_instance
    if _cointelligence_instance is None:
        from backend.application.agents.cointelligence_agent import CointelligenceAgent
        from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
        from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
        settings = get_settings()
        _cointelligence_instance = CointelligenceAgent(
            coingecko=CoinGeckoAdapter(api_key=settings.coingecko_api_key),
            fear_greed=FearGreedAdapter(),
            macro_service=get_macro_service(),
            llm_client=get_llm_client(),
            glassnode_api_key=settings.glassnode_api_key,
        )
    return _cointelligence_instance
```

- [ ] **Step 3: Endpoint in crypto.py hinzufügen**

In `backend/interfaces/rest/routers/crypto.py`, neues Schema + Endpoint:

```python
# Import am Anfang ergänzen:
from backend.domain.schemas.multiagent_schemas import CointelligenceReport
from backend.interfaces.rest.dependencies import get_cointelligence_agent

class _CointelligenceRequest(BaseModel):
    coin: Literal["BTC", "ETH"]

@router.post("/crypto/intelligence", response_model=CointelligenceReport)
async def cointelligence(
    body: _CointelligenceRequest,
    agent: Any = Depends(get_cointelligence_agent),
) -> CointelligenceReport:
    """On-Chain Intelligence Report für BTC oder ETH."""
    return await agent.analyze(body.coin)
```

- [ ] **Step 4: Tests grün**

```bash
uv run pytest backend/tests/unit/interfaces/rest/test_cointelligence_endpoint.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/interfaces/rest/routers/crypto.py backend/interfaces/rest/dependencies.py backend/tests/unit/interfaces/rest/test_cointelligence_endpoint.py
git commit -m "feat(multiagent): CointelligenceAgent Endpoint POST /api/v1/crypto/intelligence"
```

---

## Task 8: Frontend — Analyze Page + EventSource Hook

**Files:**
- Create: `frontend/app/analyze/page.tsx`
- Create: `frontend/app/analyze/analyze-client.tsx`
- Create: `frontend/hooks/useAnalysisStream.ts`
- Modify: `frontend/app/nav-links.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/analyze/stream` (SSE), `POST /api/v1/analyze/checkpoint/{id}`
- Produces: Live-Analyse-Page mit Step-Visualisierung + Checkpoint-Dialog

- [ ] **Step 1: useAnalysisStream Hook**

```typescript
// frontend/hooks/useAnalysisStream.ts
import { useCallback, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type StepEvent = { type: 'step'; agent: string; status: string; result?: string };
export type CheckpointEvent = { type: 'checkpoint'; checkpoint_id: string; message: string; options: string[] };
export type DoneEvent = { type: 'done'; run_id: string; signal: string; confidence: number; report: Record<string, unknown> };
export type DirectorEvent = StepEvent | CheckpointEvent | DoneEvent | { type: 'error'; error: string };

export function useAnalysisStream() {
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [checkpoint, setCheckpoint] = useState<CheckpointEvent | null>(null);
  const [result, setResult] = useState<DoneEvent | null>(null);
  const [running, setRunning] = useState(false);

  const start = useCallback((ticker: string, context = 'unknown') => {
    setSteps([]);
    setCheckpoint(null);
    setResult(null);
    setRunning(true);

    const token = typeof window !== 'undefined' ? localStorage.getItem('prisma_token') : null;
    const url = `${API_BASE}/api/v1/analyze/stream?ticker=${encodeURIComponent(ticker)}&context=${context}`;

    // EventSource doesn't support custom headers — pass token via cookie (already set by auth)
    const source = new EventSource(url, { withCredentials: true });

    source.onmessage = (e) => {
      const event: DirectorEvent = JSON.parse(e.data);
      if (event.type === 'step') {
        setSteps((prev) => [...prev, event]);
      } else if (event.type === 'checkpoint') {
        setCheckpoint(event);
      } else if (event.type === 'done') {
        setResult(event);
        setRunning(false);
        source.close();
      } else if (event.type === 'error') {
        setRunning(false);
        source.close();
      }
    };

    source.onerror = () => {
      setRunning(false);
      source.close();
    };
  }, []);

  const answerCheckpoint = useCallback(async (cpId: string, answer: string) => {
    setCheckpoint(null);
    await fetch(`${API_BASE}/api/v1/analyze/checkpoint/${cpId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ answer }),
    });
  }, []);

  return { steps, checkpoint, result, running, start, answerCheckpoint };
}
```

- [ ] **Step 2: Analyze Client Component**

```tsx
// frontend/app/analyze/analyze-client.tsx
'use client';

import { useState } from 'react';
import { useAnalysisStream } from '@/hooks/useAnalysisStream';

export default function AnalyzeClient() {
  const [ticker, setTicker] = useState('');
  const { steps, checkpoint, result, running, start, answerCheckpoint } = useAnalysisStream();

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Investment-Analyse</h1>

      {/* Input */}
      <div className="flex gap-3">
        <input
          className="flex-1 border rounded-lg px-4 py-2 text-sm bg-background"
          placeholder="Ticker (z.B. NESN.SW)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          disabled={running}
        />
        <button
          className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
          onClick={() => start(ticker)}
          disabled={running || !ticker}
        >
          {running ? 'Analysiert…' : 'Analysieren'}
        </button>
      </div>

      {/* Steps */}
      {steps.length > 0 && (
        <div className="space-y-2">
          {steps.map((s, i) => (
            <div key={i} className="flex items-start gap-3 text-sm">
              <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                s.status === 'done' ? 'bg-green-500' :
                s.status === 'error' ? 'bg-red-500' : 'bg-yellow-400 animate-pulse'
              }`} />
              <span className="font-medium w-36 shrink-0">{s.agent}</span>
              <span className="text-muted-foreground">{s.result ?? s.status}</span>
            </div>
          ))}
        </div>
      )}

      {/* Checkpoint Dialog */}
      {checkpoint && (
        <div className="border rounded-xl p-5 bg-muted/40 space-y-3">
          <p className="font-medium text-sm">{checkpoint.message}</p>
          <div className="flex flex-wrap gap-2">
            {checkpoint.options.map((opt) => (
              <button
                key={opt}
                className="px-4 py-2 rounded-lg border text-sm hover:bg-accent"
                onClick={() => answerCheckpoint(checkpoint.checkpoint_id, opt)}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="border rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xl font-bold">{result.signal}</span>
            <span className="text-sm text-muted-foreground">
              Konfidenz: {(result.confidence * 100).toFixed(0)}%
            </span>
          </div>
          {result.report && (
            <div className="text-sm space-y-1 text-muted-foreground">
              {result.report.macro_reasoning && <p>{String(result.report.macro_reasoning)}</p>}
              {result.report.steuer_hinweise && (
                <ul className="list-disc list-inside">
                  {(result.report.steuer_hinweise as string[]).map((h, i) => (
                    <li key={i}>{h}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Page.tsx erstellen**

```tsx
// frontend/app/analyze/page.tsx
import AnalyzeClient from './analyze-client';
export default function AnalyzePage() {
  return <AnalyzeClient />;
}
```

- [ ] **Step 4: Nav-Link hinzufügen**

In `frontend/app/nav-links.tsx`, im Nav-Array den Eintrag hinzufügen:

```typescript
{ href: '/analyze', label: 'Analyse', icon: BrainCircuit },  // import BrainCircuit from 'lucide-react'
```

- [ ] **Step 5: Commit**

```bash
git add frontend/app/analyze/ frontend/hooks/useAnalysisStream.ts frontend/app/nav-links.tsx
git commit -m "feat(multiagent): Analyze Page — SSE-Stream + Checkpoint-Dialog im Browser"
```

---

## Task 9: Spec-Datei committen + PR erstellen

**Files:**
- Create: `docs/superpowers/specs/2026-06-18-multiagent-spec.md`

- [ ] **Step 1: Spec kopieren**

```bash
cp "/Users/andreapetretta/Desktop/Business Intelligence/PRISMA_MultiAgent_Klaerung.md" \
   docs/superpowers/specs/2026-06-18-multiagent-spec.md
```

- [ ] **Step 2: Vollständiger CI-Check**

```bash
uv run pytest backend/tests/unit -q --tb=short 2>&1 | tail -10
uv run ruff check backend/ && uv run ruff format --check backend/
uv run mypy backend/ 2>&1 | grep "error:" | head -20
```

- [ ] **Step 3: Push + PR**

```bash
git add docs/superpowers/specs/2026-06-18-multiagent-spec.md docs/superpowers/plans/2026-06-18-multiagent-v2.md
git commit -m "docs: MultiAgent V2 spec + implementation plan"
git push origin feat/multiagent-v2
gh pr create --base main --title "feat(multiagent): 7 Agents — Director, MacroV2, Cointelligence, DataSteward, HITL SSE" \
  --body "Implementiert Multi-Agent-System gemäss PRISMA_MultiAgent_Klaerung.md:
- InvestmentDirector (SSE-Orchestrator, Fan-out, HITL-Checkpoints)
- MacroAgent V2 (LLM Tool-Use statt rule-based if/elif)
- CointelligenceAgent (On-Chain: MVRV, Fear&Greed, Sharpe vs. SMI)
- DataStewardAgent (Freshness-Check + Preis-Refresh-Trigger, Cron 06:00 UTC)
- POST /api/v1/crypto/intelligence Endpoint
- GET /api/v1/analyze/stream SSE Endpoint + HITL Checkpoint POST
- Frontend: /analyze Page mit Live-Steps + Checkpoint-Dialog"
```

---

## Self-Review

**Spec Coverage:**
- ✅ DataStewardAgent: Freshness + Refresh-Trigger (Task 6)
- ✅ HITL via SSE im Browser (Tasks 4+5+8)
- ✅ CointelligenceAgent mit MVRV, Fear&Greed, Sharpe (Task 3)
- ✅ MacroAgent V2 mit LLM Tool-Use (Task 2)
- ✅ InvestmentDirector Orchestrator (Task 4)
- ✅ SteuerAgent bleibt unverändert (spec: "behalten")
- ✅ PortfolioAgent: spec sagt "~100 Zeilen Delta-View" → nicht in diesem Plan, Follow-up
- ✅ ReportAgent (spec: "HTML-Dashboard") → nicht in diesem Plan, Follow-up
- ✅ Spec-Datei bleibt im Repo (Task 9)

**Placeholder scan:** Keine TBDs. Alle Codeblöcke vollständig.

**Type consistency:** `MacroToolReport`, `CointelligenceReport`, `DirectorEvent`, `CheckpointAnswer` konsistent über alle Tasks.

**Hinweis:** PortfolioAgent Delta-View und ReportAgent (HTML) wurden bewusst ausgelassen — die Spec stuft sie als Mini-Extension bzw. Nice-to-Have ein. Separat zu planen nach diesem PR.
