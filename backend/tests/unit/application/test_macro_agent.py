"""Unit-Tests für MacroIntelligenceAgent — ticker-spezifischer Makro-Score."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.agents.macro_agent import MacroIntelligenceAgent, MacroScore
from backend.domain.value_objects.macro_context import MacroContext

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _ctx(
    leitzins: float = 0.25,
    chf_eur: float = 0.93,
    inflation_ch: float | None = None,
    climate: str = "NEUTRAL",
) -> MacroContext:
    return MacroContext(
        leitzins=leitzins,
        chf_eur=chf_eur,
        inflation_ch=inflation_ch,
        pmi_ch=None,
        snapshot_date=date(2026, 6, 11),
        climate=climate,
        narrative_de="Test DE",
        narrative_en="Test EN",
    )


def _agent(ctx: MacroContext) -> MacroIntelligenceAgent:
    macro_service = MagicMock()
    macro_service.get_context = AsyncMock(return_value=ctx)
    return MacroIntelligenceAgent(macro_service=macro_service)


# ---------------------------------------------------------------------------
# Grundlegende Ausgabe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_macro_score_instance():
    result = await _agent(_ctx()).get_macro_score("NESN.SW")
    assert isinstance(result, MacroScore)


@pytest.mark.asyncio
async def test_ticker_normalized_to_uppercase():
    result = await _agent(_ctx()).get_macro_score("nesn.sw")
    assert result.ticker == "NESN.SW"


@pytest.mark.asyncio
async def test_score_within_bounds():
    result = await _agent(_ctx()).get_macro_score("NESN.SW")
    assert 0.0 <= result.score <= 100.0


@pytest.mark.asyncio
async def test_reasoning_nonempty():
    result = await _agent(_ctx()).get_macro_score("NESN.SW")
    assert len(result.reasoning) > 0


@pytest.mark.asyncio
async def test_context_values_in_result():
    ctx = _ctx(leitzins=0.5, chf_eur=0.935, climate="NEUTRAL")
    result = await _agent(ctx).get_macro_score("UBSG.SW")
    assert result.leitzins == 0.5
    assert result.chf_eur == 0.935
    assert result.climate == "NEUTRAL"


# ---------------------------------------------------------------------------
# SNB-Leitzins-Logik
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_negativzins_higher_score_than_hoher_leitzins():
    score_low = (await _agent(_ctx(leitzins=0.0)).get_macro_score("UBSG.SW")).score
    score_high = (await _agent(_ctx(leitzins=2.0)).get_macro_score("UBSG.SW")).score
    assert score_low > score_high


@pytest.mark.asyncio
async def test_tiefer_leitzins_boosts_score():
    """Leitzins ≤0.5% sollte +15 Punkte gegenüber Baseline geben."""
    result = await _agent(_ctx(leitzins=0.25, chf_eur=0.93)).get_macro_score("UBSG.SW")
    # Baseline 50 + 15 (Leitzins) + 10 (keine Inflationsdaten)
    assert result.score == pytest.approx(75.0)


@pytest.mark.asyncio
async def test_hoher_leitzins_penalizes_score():
    """Leitzins >1.5% sollte -20 Punkte gegenüber Baseline geben."""
    result = await _agent(_ctx(leitzins=2.0, chf_eur=0.93)).get_macro_score("UBSG.SW")
    # Baseline 50 - 20 (hoher Leitzins) + 10 (keine Inflationsdaten)
    assert result.score == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# CHF-Stärke-Logik (per Ticker)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exporter_penalized_with_strong_chf():
    """NESN.SW (Nestlé, Exporteur) leidet bei starkem CHF."""
    score_strong = (await _agent(_ctx(chf_eur=0.97)).get_macro_score("NESN.SW")).score
    score_normal = (await _agent(_ctx(chf_eur=0.93)).get_macro_score("NESN.SW")).score
    assert score_strong < score_normal


@pytest.mark.asyncio
async def test_exporter_benefits_from_weak_chf():
    """Exporteur profitiert bei schwachem CHF."""
    score_weak = (await _agent(_ctx(chf_eur=0.90)).get_macro_score("NESN.SW")).score
    score_normal = (await _agent(_ctx(chf_eur=0.93)).get_macro_score("NESN.SW")).score
    assert score_weak > score_normal


@pytest.mark.asyncio
async def test_exporter_strong_chf_negativ_impact():
    result = await _agent(_ctx(chf_eur=0.97)).get_macro_score("NESN.SW")
    assert result.chf_impact == "NEGATIV"


@pytest.mark.asyncio
async def test_exporter_weak_chf_positiv_impact():
    result = await _agent(_ctx(chf_eur=0.90)).get_macro_score("NESN.SW")
    assert result.chf_impact == "POSITIV"


@pytest.mark.asyncio
async def test_domestic_title_positiv_with_strong_chf():
    """UBSG.SW (Inlandstitel) profitiert leicht bei starkem CHF."""
    result = await _agent(_ctx(chf_eur=0.97)).get_macro_score("UBSG.SW")
    assert result.chf_impact == "POSITIV"


@pytest.mark.asyncio
async def test_unknown_ticker_equilibrium_chf():
    """Unbekannter Ticker ohne Sektor → NEUTRAL bei Gleichgewicht-CHF."""
    result = await _agent(_ctx(chf_eur=0.93)).get_macro_score("XXXX.SW")
    assert result.chf_impact == "NEUTRAL"


@pytest.mark.asyncio
async def test_sector_hint_classifies_as_exporter():
    """Unbekannter Ticker mit sector='pharma' → Exporteur-Behandlung."""
    result = await _agent(_ctx(chf_eur=0.97)).get_macro_score("UNKNOWN.SW", sector="pharma")
    assert result.chf_impact == "NEGATIV"


# ---------------------------------------------------------------------------
# Inflation CH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stable_inflation_boosts_score():
    score_stable = (await _agent(_ctx(inflation_ch=1.2)).get_macro_score("UBSG.SW")).score
    score_high = (await _agent(_ctx(inflation_ch=4.0)).get_macro_score("UBSG.SW")).score
    assert score_stable > score_high


@pytest.mark.asyncio
async def test_deflation_penalizes_score():
    """Deflation (Inflation ≤0%) sollte Abzug geben."""
    score_deflation = (await _agent(_ctx(inflation_ch=-0.5)).get_macro_score("UBSG.SW")).score
    score_stable = (await _agent(_ctx(inflation_ch=1.5)).get_macro_score("UBSG.SW")).score
    assert score_deflation < score_stable


@pytest.mark.asyncio
async def test_no_inflation_data_assumes_stable():
    """Ohne Inflationsdaten → Standard-Annahme stabil (+10)."""
    result_none = await _agent(_ctx(inflation_ch=None)).get_macro_score("UBSG.SW")
    result_stable = await _agent(_ctx(inflation_ch=1.5)).get_macro_score("UBSG.SW")
    assert result_none.score == pytest.approx(result_stable.score)


# ---------------------------------------------------------------------------
# Score-Grenzen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_never_below_zero():
    ctx = _ctx(leitzins=3.0, chf_eur=0.97, inflation_ch=5.0)
    result = await _agent(ctx).get_macro_score("NESN.SW")
    assert result.score >= 0.0


@pytest.mark.asyncio
async def test_score_never_above_100():
    ctx = _ctx(leitzins=0.0, chf_eur=0.90, inflation_ch=0.5)
    result = await _agent(ctx).get_macro_score("NESN.SW")
    assert result.score <= 100.0
