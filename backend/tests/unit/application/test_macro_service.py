"""Unit-Tests für MacroService und MacroContext."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.application.services.macro_service import MacroService
from backend.domain.value_objects.macro_context import MacroContext

# --- MacroContext.climate_for ---


def test_climate_expansiv_negative_rate() -> None:
    assert MacroContext.climate_for(-0.5, None) == "EXPANSIV"


def test_climate_expansiv_zero_rate() -> None:
    assert MacroContext.climate_for(0.0, 2.0) == "EXPANSIV"


def test_climate_neutral_low_rate_low_inflation() -> None:
    assert MacroContext.climate_for(0.5, 1.5) == "NEUTRAL"


def test_climate_restriktiv_low_rate_high_inflation() -> None:
    assert MacroContext.climate_for(0.5, 3.0) == "RESTRIKTIV"


def test_climate_restriktiv_high_rate() -> None:
    assert MacroContext.climate_for(1.0, None) == "RESTRIKTIV"


def test_climate_neutral_no_inflation_data() -> None:
    assert MacroContext.climate_for(0.25, None) == "NEUTRAL"


# --- MacroService.get_context ---


@pytest.mark.asyncio
async def test_get_context_uses_fallback_narrative_without_llm() -> None:
    """Ohne LLM → Fallback-Narrative enthält SNB-Rate und CHF/EUR."""
    with (
        patch(
            "backend.application.services.macro_service.fetch_current_snb_rate",
            new=AsyncMock(return_value=0.25),
        ),
        patch(
            "backend.application.services.macro_service._fetch_chf_eur",
            return_value=0.932,
        ),
        patch(
            "backend.application.services.macro_service._fetch_swiss_inflation",
            new=AsyncMock(return_value=0.3),
        ),
        patch(
            "backend.application.services.macro_service._fetch_swiss_pmi",
            new=AsyncMock(return_value=45.5),
        ),
    ):
        service = MacroService(llm_client=None)
        ctx = await service.get_context()

    assert ctx.leitzins == 0.25
    assert ctx.chf_eur == 0.932
    assert "0.25" in ctx.narrative_de
    assert "0.25" in ctx.narrative_en
    assert ctx.climate in {"EXPANSIV", "NEUTRAL", "RESTRIKTIV"}
    assert ctx.inflation_ch == 0.3
    assert ctx.pmi_ch == 45.5


@pytest.mark.asyncio
async def test_get_context_llm_narrative_parsed() -> None:
    """LLM liefert valides JSON → Narrative wird geparst."""
    llm = AsyncMock()
    llm_response = MagicMock()
    llm_response.content = [
        MagicMock(
            text=json.dumps(
                {"de": "SNB hält Kurs. Neutrales Umfeld.", "en": "SNB holds steady. Neutral."}
            )
        )
    ]
    llm.messages_create.return_value = llm_response

    with (
        patch(
            "backend.application.services.macro_service.fetch_current_snb_rate",
            new=AsyncMock(return_value=0.25),
        ),
        patch(
            "backend.application.services.macro_service._fetch_chf_eur",
            return_value=0.932,
        ),
    ):
        service = MacroService(llm_client=llm)
        ctx = await service.get_context()

    assert ctx.narrative_de == "SNB hält Kurs. Neutrales Umfeld."
    assert ctx.narrative_en == "SNB holds steady. Neutral."


@pytest.mark.asyncio
async def test_get_context_llm_fails_uses_fallback() -> None:
    """LLM wirft Exception → Fallback-Narrative."""
    llm = AsyncMock()
    llm.messages_create.side_effect = RuntimeError("API down")

    with (
        patch(
            "backend.application.services.macro_service.fetch_current_snb_rate",
            new=AsyncMock(return_value=1.5),
        ),
        patch(
            "backend.application.services.macro_service._fetch_chf_eur",
            return_value=0.91,
        ),
    ):
        service = MacroService(llm_client=llm)
        ctx = await service.get_context()

    assert "1.50" in ctx.narrative_de
    assert ctx.climate == "RESTRIKTIV"


@pytest.mark.asyncio
async def test_get_context_restriktiv_high_rate() -> None:
    """Hoher SNB-Leitzins → RESTRIKTIV."""
    with (
        patch(
            "backend.application.services.macro_service.fetch_current_snb_rate",
            new=AsyncMock(return_value=2.0),
        ),
        patch(
            "backend.application.services.macro_service._fetch_chf_eur",
            return_value=0.90,
        ),
    ):
        service = MacroService(llm_client=None)
        ctx = await service.get_context()

    assert ctx.climate == "RESTRIKTIV"
    assert ctx.leitzins == 2.0


# --- _latest_plausible_cpi (W3-M-16): aktuellster CPI statt "nächster zu 1.0%" ---


def _series(*obs_pairs: tuple[int, float | None]) -> dict:
    return {"observations": {str(idx): [val] for idx, val in obs_pairs}}


def test_latest_plausible_cpi_picks_most_recent_not_nearest_to_one() -> None:
    from backend.application.services.macro_service import _latest_plausible_cpi

    # Ältere Serie exakt bei 1.0% (früher gewählt), neuere Serie bei 2.3%.
    series_map = {
        "0": _series((5, 1.0)),
        "1": _series((10, 2.3)),
    }
    assert _latest_plausible_cpi(series_map) == 2.3


def test_latest_plausible_cpi_uses_last_observation_per_series() -> None:
    from backend.application.services.macro_service import _latest_plausible_cpi

    series_map = {"0": _series((3, 0.8), (12, 1.9))}
    assert _latest_plausible_cpi(series_map) == 1.9


def test_latest_plausible_cpi_filters_implausible_and_none() -> None:
    from backend.application.services.macro_service import _latest_plausible_cpi

    # Aktuellster Wert ist implausibel (99) → nächstplausibler (ältere, 1.5) gewinnt.
    series_map = {
        "0": _series((20, 99.0)),
        "1": _series((15, 1.5)),
        "2": _series((8, None)),
    }
    assert _latest_plausible_cpi(series_map) == 1.5


def test_latest_plausible_cpi_returns_none_when_empty() -> None:
    from backend.application.services.macro_service import _latest_plausible_cpi

    assert _latest_plausible_cpi({}) is None
    assert _latest_plausible_cpi({"0": {"observations": {}}}) is None
