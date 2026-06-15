"""SteuerAgent — RAG-basierter Agent für Steuer-Implikationen bei CH-Aktienanlagen.

Alle LLM-Outputs werden Pydantic-schema-validiert (AGENTS.md-Pflicht).
Immer Disclaimer "Keine Steuerberatung" (AGENTS.md-Pflicht).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Literal

from pydantic import ValidationError

from backend.application.services.retrieval_service import RetrievalService
from backend.domain.schemas.steuer_schema import PFLICHT_DISCLAIMER, SteuerEinschätzung
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024
_RAG_K = 5  # max RAG-Chunks für Steuer-Kontext
_VERRECHNUNGSSTEUER_RATE = 0.35  # Verrechnungssteuer Schweiz: 35% (Art. 4 VStG)

AnlegerprofitTyp = Literal["privatperson", "vorsorge_3a", "vorsorge_2a", "institution"]


class SteuerAgent:
    """Orchestriert RAG-Retrieval + LLM-Call für Steuereinschätzungen.

    Design: fail-safe — bei LLM-Fehler wird eine Fallback-Einschätzung zurückgegeben
    (mit explizitem Hinweis auf Fehler), damit der Endpoint nie 500 wirft.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        retrieval_service: RetrievalService,
        prompt_loader: PromptTemplateLoader,
    ) -> None:
        self._llm = llm_client
        self._retrieval = retrieval_service
        self._prompts = prompt_loader

    async def einschaetzen(
        self,
        ticker: str,
        anlegerprofil: AnlegerprofitTyp,
        halteperiode_jahre: int,
    ) -> SteuerEinschätzung:
        """Erstellt eine strukturierte Steuereinschätzung für eine Anlageposition."""
        upper = ticker.upper()
        now = datetime.now(UTC)

        # RAG: suche relevante Steuer-Dokumente (toleriert leeres Ergebnis)
        rag_query = f"Steuerimplikationen {upper} {anlegerprofil} Schweiz 3a Dividenden"
        try:
            rag_chunks = await self._retrieval.retrieve(query=rag_query, k=_RAG_K, ticker=upper)
        except Exception as exc:
            _logger.warning("RAG retrieval failed, proceeding without context: %s", exc)
            rag_chunks = []

        system_prompt = self._prompts.render(
            "steuer_system.de.md.j2",
            {
                "rag_chunks": [
                    {"doc_type": r.doc_type, "ticker": r.ticker, "content": r.content}
                    for r in rag_chunks
                ],
            },
        )
        user_prompt = self._prompts.render(
            "steuer_user.de.md.j2",
            {
                "ticker": upper,
                "anlegerprofil": anlegerprofil,
                "halteperiode_jahre": halteperiode_jahre,
                "current_date": now.strftime("%Y-%m-%d"),
                "generated_at": now.isoformat(),
                "model_version": _MODEL,
            },
        )

        try:
            response = await self._llm.messages_create(
                model=_MODEL,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=_MAX_TOKENS,
                feature="steuer_agent",
                system=system_prompt,
            )
            raw_text: str = response.content[0].text
            data = json.loads(raw_text)
            # Pflicht-Disclaimer immer setzen (überschreibt LLM-Output)
            data["disclaimer"] = PFLICHT_DISCLAIMER
            data["ticker"] = upper
            data["anlegerprofil"] = anlegerprofil
            data["halteperiode_jahre"] = halteperiode_jahre
            data.setdefault("generated_at", now.isoformat())
            data.setdefault("model_version", _MODEL)
            return SteuerEinschätzung.model_validate(data)
        except (json.JSONDecodeError, ValidationError, KeyError, IndexError) as exc:
            _logger.error("SteuerAgent LLM output validation failed: %s", exc)
            return self._fallback(upper, anlegerprofil, halteperiode_jahre, now)

    @staticmethod
    def _fallback(
        ticker: str,
        anlegerprofil: AnlegerprofitTyp,
        halteperiode_jahre: int,
        now: datetime,
    ) -> SteuerEinschätzung:
        # Ticker-spezifische Kontextualisierung des Fallback-Textes
        profil_label = {
            "privatperson": "Privatperson",
            "vorsorge_3a": "Säule-3a-Investor",
            "vorsorge_2a": "Säule-2a-Investor (Pensionskasse)",
            "institution": "Institutioneller Anleger",
        }.get(anlegerprofil, anlegerprofil)

        halte_hinweis = (
            f"Bei {halteperiode_jahre} Jahren Haltedauer gilt in der Schweiz: "
            "Kapitalgewinne sind für Privatpersonen steuerfrei (keine Kapitalertragssteuer)."
            if anlegerprofil == "privatperson"
            else f"Bei {halteperiode_jahre} Jahren Haltedauer — steuerliche Behandlung abhängig vom Rechtsträger."
        )

        return SteuerEinschätzung(
            ticker=ticker,
            anlegerprofil=anlegerprofil,
            halteperiode_jahre=halteperiode_jahre,
            steuerarten=[
                f"Verrechnungssteuer ({int(_VERRECHNUNGSSTEUER_RATE * 100)}%)",
                "Vermögenssteuer",
            ],
            pflichten=[
                f"Dividenden von {ticker} als Einkommen deklarieren (Formular DA-1 für Rückerstattung).",
                "VST-Rückerstattung via Formular 103 (bei Schweizer Aktien) beantragen.",
                f"Kurswert {ticker} per 31.12. in der Vermögenserklärung angeben.",
            ],
            hinweise=[
                f"Profil: {profil_label}. {halte_hinweis}",
                "Steuerliche Behandlung variiert je nach Wohnsitzkanton — lokales Steueramt konsultieren.",
                "Diese Einschätzung wurde durch einen Fallback generiert — KI-Analyse nicht verfügbar.",
            ],
            quellen=["ESTV — Verrechnungssteuer", "DBG Art. 20", f"Ticker: {ticker}"],
            disclaimer=PFLICHT_DISCLAIMER,
            generated_at=now,
            model_version="fallback",
        )
