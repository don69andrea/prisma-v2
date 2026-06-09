"""Macro Intelligence Service — SNB + CHF + Narrative für Schweizer Investments."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import yfinance as yf
from pydantic import BaseModel, Field, ValidationError

from backend.domain.value_objects.macro_context import MacroContext
from backend.infrastructure.adapters.snb_adapter import fetch_current_snb_rate

_logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5"
_MAX_TOKENS = 200


class _NarrativeOutput(BaseModel):
    de: str = Field(..., min_length=10, max_length=500)
    en: str = Field(..., min_length=10, max_length=500)


def _fetch_chf_eur() -> float:
    try:
        ticker = yf.Ticker("EURCHF=X")
        hist = ticker.history(period="5d")
        if not hist.empty:
            return round(1.0 / float(hist["Close"].iloc[-1]), 4)
    except Exception:
        _logger.warning("CHF/EUR-Abruf fehlgeschlagen — Fallback 0.93")
    return 0.93


_NARRATIVE_SYSTEM = (
    "Du bist ein präziser Schweizer Finanz-Analyst. "
    "Antworte NUR mit validem JSON ohne Markdown-Codeblock. "
    'Schema: {"de": "<max 2 Sätze DE>", "en": "<max 2 Sätze EN>"}'
)


def _narrative_prompt(leitzins: float, chf_eur: float, climate: str) -> str:
    return (
        f"SNB-Leitzins: {leitzins:.2f}%, CHF/EUR: {chf_eur:.4f}, "
        f"Makro-Klima: {climate}. "
        "Erstelle eine kurze, sachliche Makro-Einschätzung für Schweizer Aktieninvestoren "
        '(freie Mittel, nicht 3a-gebunden). Antworte mit JSON {{"de": "...", "en": "..."}}.'
    )


class MacroService:
    """Berechnet MacroContext inkl. LLM-Narrative für das Makro-Klima-Widget."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    async def get_context(self) -> MacroContext:
        """Erstellt den aktuellen MacroContext (SNB + CHF + Narrative)."""
        leitzins = await fetch_current_snb_rate()
        chf_eur = _fetch_chf_eur()
        today = datetime.now(tz=UTC).date()

        inflation_ch: float | None = None
        pmi_ch: float | None = None

        climate = MacroContext.climate_for(leitzins, inflation_ch)
        narrative_de, narrative_en = await self._generate_narratives(leitzins, chf_eur, climate)

        return MacroContext(
            leitzins=leitzins,
            chf_eur=chf_eur,
            inflation_ch=inflation_ch,
            pmi_ch=pmi_ch,
            snapshot_date=today,
            climate=climate,
            narrative_de=narrative_de,
            narrative_en=narrative_en,
        )

    async def _generate_narratives(
        self, leitzins: float, chf_eur: float, climate: str
    ) -> tuple[str, str]:
        if self._llm is None:
            return self._fallback_narrative(leitzins, chf_eur, climate)

        try:
            import json

            response = await self._llm.messages_create(
                model=_HAIKU,
                system=_NARRATIVE_SYSTEM,
                messages=[
                    {"role": "user", "content": _narrative_prompt(leitzins, chf_eur, climate)}
                ],
                max_tokens=_MAX_TOKENS,
                feature="macro_narrative",
            )
            raw = response.content[0].text.strip()
            parsed = _NarrativeOutput.model_validate(json.loads(raw))
            return parsed.de, parsed.en
        except (ValidationError, Exception):
            _logger.warning("LLM-Narrative fehlgeschlagen — Fallback", exc_info=True)
            return self._fallback_narrative(leitzins, chf_eur, climate)

    @staticmethod
    def _fallback_narrative(leitzins: float, chf_eur: float, climate: str) -> tuple[str, str]:
        de = f"SNB-Leitzins bei {leitzins:.2f}%, CHF/EUR {chf_eur:.4f}. Makro-Klima: {climate}."
        en = f"SNB policy rate at {leitzins:.2f}%, CHF/EUR {chf_eur:.4f}. Macro climate: {climate}."
        return de, en
