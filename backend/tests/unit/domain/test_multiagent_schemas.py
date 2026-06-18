from __future__ import annotations
import pytest
from backend.domain.schemas.multiagent_schemas import (
    DirectorEvent, CointelligenceReport, MacroToolReport
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
