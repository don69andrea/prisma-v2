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
        events_seen = []
        # Drain queue to find checkpoint
        while not queue.empty():
            events_seen.append(queue.get_nowait())
        cp = next((e for e in events_seen if e.get("type") == "checkpoint"), None)
        if cp:
            await director.resolve_checkpoint(cp["checkpoint_id"], "3a-Konto (VIAC)")
        # Put events back
        for e in events_seen:
            await queue.put(e)

    task = asyncio.create_task(resolve_after_delay())
    await director.run_with_events(
        ticker="NESN.SW", context="unknown", run_id="r2", event_queue=queue
    )
    await task
    events = []
    while not queue.empty():
        events.append(await queue.get())
    assert any(e["type"] == "done" for e in events)


@pytest.mark.asyncio
async def test_director_resolve_checkpoint():
    director = _make_director()
    event = asyncio.Event()
    director._checkpoints["cp_test"] = event
    director._checkpoint_answers["cp_test"] = None
    await director.resolve_checkpoint("cp_test", "3a")
    assert director._checkpoint_answers["cp_test"] == "3a"
    assert event.is_set()
