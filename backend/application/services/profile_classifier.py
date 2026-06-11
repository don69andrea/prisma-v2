"""ProfileClassifier — Klassifikation von Discovery-Session-Antworten.

Turn 1 (Beruf-Freitext) → Claude Haiku → financial_knowledge + sector_hint.
Turns 2–4 sind regelbasiert (kein LLM).
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel

from backend.domain.entities.investor_profile import InvestorProfile
from backend.infrastructure.llm.client import LLMClient

_logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"


class Turn1Classification(BaseModel):
    """Ergebnis der Haiku-Klassifikation für Turn 1 (Beruf)."""

    financial_knowledge: Literal["low", "medium", "high"]
    sector_hint: str | None = None


_TURN1_SYSTEM = """\
Du klassifizierst Berufsbezeichnungen für einen Investment-App Onboarding-Flow.
Antworte NUR mit einem JSON-Objekt. Kein Text davor oder danach.
Schema: {"financial_knowledge": "low|medium|high", "sector_hint": "consumer|pharma|finance|industrial|tech|null"}
Beispiele:
- "Softwareentwickler" → {"financial_knowledge": "medium", "sector_hint": "tech"}
- "Bankangestellter" → {"financial_knowledge": "high", "sector_hint": "finance"}
- "Pflegefachfrau" → {"financial_knowledge": "low", "sector_hint": "pharma"}
- "Schreiner" → {"financial_knowledge": "low", "sector_hint": null}\
"""

_GOAL_MAP: dict[str, tuple[str, str]] = {
    "Neue Wohnung": ("housing", "short"),
    "Altersvorsorge": ("retirement", "long"),
    "Finanzielle Freiheit": ("freedom", "medium"),
    "Besser als Konto": ("beat_savings", "medium"),
}


class ProfileClassifier:
    """Klassifiziert Nutzer-Antworten in InvestorProfile-Dimensionen.

    Turn 1 benutzt Claude Haiku (Freitext → strukturiertes JSON).
    Turns 2–4 sind rule-based ohne LLM-Aufruf.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def classify_turn1(self, profession_text: str) -> Turn1Classification:
        """Beruf-Freitext → financial_knowledge + optionaler sector_hint."""
        response = await self._llm.messages_create(
            model=_HAIKU_MODEL,
            max_tokens=200,
            feature="profile_classification_turn1",
            system=_TURN1_SYSTEM,
            messages=[{"role": "user", "content": f"Beruf: {profession_text}"}],
        )
        raw = response.content[0].text.strip()
        return Turn1Classification.model_validate(json.loads(raw))

    @staticmethod
    def classify_turn2(goal_selection: str) -> tuple[str, str]:
        """Ziel-Auswahl → (investment_goal, time_horizon)."""
        return _GOAL_MAP.get(goal_selection, ("other", "medium"))

    @staticmethod
    def classify_turn3(emoji_choice: str) -> str:
        """Risk-Feeling (conservative/moderate/aggressive) → risk_profile."""
        valid = {"conservative", "moderate", "aggressive"}
        return emoji_choice if emoji_choice in valid else "moderate"

    @staticmethod
    def classify_turn4(
        clicked_tickers: list[str],
        brand_data: dict[str, dict],
    ) -> tuple[list[str], list[str]]:
        """Brand-Klicks → (sector_affinity, known_tickers).

        brand_data maps ticker → {"sector": str, ...}
        """
        sectors = list({brand_data[t]["sector"] for t in clicked_tickers if t in brand_data})
        return sectors, list(clicked_tickers)

    @staticmethod
    def calculate_confidence(profile: InvestorProfile) -> float:
        """Wie vollständig ist das Profil? 0.0–1.0.

        < 0.6: weitere Fragen stellen
        ≥ 0.8: Profil komplett, Discovery starten
        """
        score = 0.0
        if profile.financial_knowledge != "low" or profile.profession is not None:
            score += 0.2
        if profile.investment_goal != "beat_savings":
            score += 0.2
        if profile.risk_profile != "moderate":
            score += 0.3
        if len(profile.known_tickers) >= 2:
            score += 0.2
        if len(profile.sector_affinity) >= 1:
            score += 0.1
        return min(score, 1.0)
