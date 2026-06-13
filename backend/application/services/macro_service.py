"""Macro Intelligence Service — SNB + CHF + Narrative für Schweizer Investments."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import yfinance as yf
from pydantic import BaseModel, Field, ValidationError

from backend.domain.value_objects.macro_context import MacroContext
from backend.infrastructure.adapters.snb_adapter import fetch_current_snb_rate

_logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5"
_MAX_TOKENS = 200
_HTTP_TIMEOUT = 8.0

# Fallback-Werte (CH Inflation YoY ca. 0.3% in 2025/2026; CH Manufacturing PMI ca. 45.5)
_FALLBACK_INFLATION_CH = 0.3
_FALLBACK_PMI_CH = 45.5


class _NarrativeOutput(BaseModel):
    de: str = Field(..., min_length=10, max_length=500)
    en: str = Field(..., min_length=10, max_length=500)


async def _fetch_chf_eur() -> float:
    """Lädt CHF/EUR-Kurs asynchron via asyncio.to_thread, um den Event-Loop nicht zu blockieren."""

    def _sync_fetch() -> float:
        try:
            ticker = yf.Ticker("EURCHF=X")
            hist = ticker.history(period="5d")
            if not hist.empty:
                return round(1.0 / float(hist["Close"].iloc[-1]), 4)
        except Exception:
            pass
        return 0.93

    import asyncio

    try:
        result = await asyncio.to_thread(_sync_fetch)
        return result
    except Exception as exc:
        _logger.warning("CHF/EUR-Abruf fehlgeschlagen (%s) — Fallback 0.93", exc)
        return 0.93


async def _fetch_swiss_inflation() -> float:
    """Holt die aktuelle Schweizer CPI-Inflationsrate (YoY) von der SNB-API.

    Endpunkt: https://data.snb.ch/api/cube/cpichmon/data/json/de
    Fällt bei Netzwerk- oder Parse-Fehlern auf den Fallback-Wert zurück
    (_FALLBACK_INFLATION_CH = 0.3 %, realistisch für 2025/2026).
    """
    url = "https://data.snb.ch/api/cube/cpichmon/data/json/de"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()

            # SNB JSON-Struktur: payload["data"]["dataSets"][0]["series"]
            # Jede Serie enthält "observations" {index: [value]}; wir brauchen
            # die Jahresveränderungsrate (Typ "YoY" / Code "YZ" in der Dimension).
            # Einfachere, robuste Strategie: alle Serien durchsuchen, letzte Beobachtung
            # nehmen und die mit dem kleinsten absoluten Wert (nahe 0–3 %) wählen.
            data_sets = payload.get("data", {}).get("dataSets", [])
            if not data_sets:
                raise ValueError("Keine dataSets in SNB-Antwort")

            series_map = data_sets[0].get("series", {})
            candidates: list[float] = []
            for series_data in series_map.values():
                obs = series_data.get("observations", {})
                if not obs:
                    continue
                last_idx = str(max(int(k) for k in obs))
                value = obs[last_idx][0]
                if value is not None:
                    candidates.append(float(value))

            # Filtere auf plausible Inflationswerte (−2 % … +10 %)
            plausible = [v for v in candidates if -2.0 <= v <= 10.0]
            if plausible:
                # Nimm den Wert, der am nächsten an einem typischen CH-Inflationsbereich liegt
                result = min(plausible, key=lambda v: abs(v - 1.0))
                _logger.info("Schweizer Inflation (SNB API): %.2f%%", result)
                return round(result, 2)

            raise ValueError(f"Keine plausiblen Inflationswerte gefunden: {candidates}")

    except Exception:
        _logger.warning(
            "Schweizer Inflation nicht abrufbar — Fallback %.1f%%",
            _FALLBACK_INFLATION_CH,
            exc_info=True,
        )
    return _FALLBACK_INFLATION_CH


async def _fetch_swiss_pmi() -> float:
    """Holt den aktuellen Schweizer Manufacturing PMI von procure.ch.

    Versucht die procure.ch-Seite zu parsen; fällt bei jedem Fehler auf den
    Fallback-Wert zurück (_FALLBACK_PMI_CH = 45.5, realistisch für 2025/2026).
    """
    url = "https://www.procure.ch/de/swiss-pmi/"
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PRISMA-Macro-Bot/2.0)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text

            # Suche nach PMI-Zahl im HTML: typisch "PMI: 45.5" oder "45,5" in einer
            # data-Tabelle oder einem Headline-Element.
            import re

            # Muster 1: explizite PMI-Angabe wie "PMI 45.5" oder "PMI: 45,5"
            m = re.search(r"PMI[^\d]{0,10}(\d{2}[.,]\d)", text, re.IGNORECASE)
            if m:
                raw = m.group(1).replace(",", ".")
                value = float(raw)
                if 20.0 <= value <= 80.0:
                    _logger.info("Schweizer PMI (procure.ch): %.1f", value)
                    return round(value, 1)

            # Muster 2: Zahl zwischen 20 und 80 direkt nach "aktuell" oder "current"
            m2 = re.search(r"(?:aktuell|current)[^\d]{0,20}(\d{2}[.,]\d)", text, re.IGNORECASE)
            if m2:
                raw2 = m2.group(1).replace(",", ".")
                value2 = float(raw2)
                if 20.0 <= value2 <= 80.0:
                    _logger.info("Schweizer PMI (procure.ch, Muster 2): %.1f", value2)
                    return round(value2, 1)

            raise ValueError("PMI-Wert nicht im HTML gefunden")

    except Exception as exc:
        _logger.warning(
            "Schweizer PMI nicht abrufbar (URL: %s, Fehler: %s) — Fallback %.1f. "
            "Fallback-Wert _FALLBACK_PMI_CH zuletzt validiert: 2025-06-13.",
            url,
            exc,
            _FALLBACK_PMI_CH,
        )
    return _FALLBACK_PMI_CH


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
        chf_eur = await _fetch_chf_eur()
        today = datetime.now(tz=UTC).date()

        # Inflation und PMI parallel abrufen (beide mit robustem Fallback)
        inflation_ch, pmi_ch = await asyncio.gather(
            _fetch_swiss_inflation(),
            _fetch_swiss_pmi(),
        )

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
