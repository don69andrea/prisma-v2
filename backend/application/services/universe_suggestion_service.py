"""UniverseSuggestionService — LLM-Wizard für Universe-Vorschläge."""

import logging
from dataclasses import dataclass
from pathlib import Path

from backend.application.services.stock_service import StockService
from backend.domain.schemas.universe_suggestion_schema import UniverseSuggestionSchema
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"
_MAX_TOKENS = 500


class EmptySuggestion(Exception):
    """LLM-Output enthielt nach Filterung weniger als 2 valide Tickers."""


class InvalidLLMOutput(Exception):
    """LLM gab nicht-parsbare Antwort (kein tool_use oder Schema-Verletzung)."""


@dataclass(frozen=True)
class UniverseSuggestion:
    name: str
    region: str
    tickers: list[str]
    reasoning: str
    available_tickers: list[str]


class UniverseSuggestionService:
    """Generiert Universe-Vorschläge via Claude Haiku + Stock-Katalog-Whitelist."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        stock_service: StockService,
        prompts_dir: Path | None = None,
    ) -> None:
        self._llm = llm_client
        self._stock_service = stock_service
        if prompts_dir is None:
            prompts_dir = (
                Path(__file__).resolve().parent.parent.parent / "infrastructure" / "llm" / "prompts"
            )
        self._loader = PromptTemplateLoader(prompts_dir)

    async def suggest(self, description: str) -> UniverseSuggestion:
        """Holt LLM-Vorschlag und filtert gegen Stock-Katalog."""
        stocks = await self._stock_service.list_stocks(limit=200, offset=0)
        if not stocks:
            raise EmptySuggestion("Stock-Katalog ist leer.")

        catalog_tickers = {s.ticker for s in stocks}

        system_prompt = self._loader.render(
            "universe_suggestion_system.de.md.j2", {"available_stocks": stocks}
        )
        user_prompt = self._loader.render(
            "universe_suggestion_user.de.md.j2", {"description": description}
        )

        response = await self._llm.messages_create(
            model=_MODEL,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
            tools=[
                {
                    "name": "submit_universe_suggestion",
                    "description": "Submit the universe suggestion.",
                    "input_schema": UniverseSuggestionSchema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "submit_universe_suggestion"},
            max_tokens=_MAX_TOKENS,
            feature="universe_suggestion",
        )

        schema = self._extract_schema(response)
        filtered = [t for t in schema.tickers if t in catalog_tickers]
        if len(filtered) < 2:
            raise EmptySuggestion(
                f"Nach Filter gegen Katalog blieben nur {len(filtered)} Tickers übrig."
            )

        return UniverseSuggestion(
            name=schema.name,
            region=schema.region,
            tickers=filtered,
            reasoning=schema.reasoning,
            available_tickers=sorted(catalog_tickers),
        )

    @staticmethod
    def _extract_schema(response: object) -> UniverseSuggestionSchema:
        """Zieht das tool_use-Output aus der Anthropic-Response."""
        from pydantic import ValidationError

        content = getattr(response, "content", [])
        for block in content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return UniverseSuggestionSchema.model_validate(block.input)
                except ValidationError as exc:
                    _logger.warning("LLM-Output-Schema-Verletzung: %s", exc)
                    raise InvalidLLMOutput(str(exc)) from exc
        raise InvalidLLMOutput("Keine tool_use-Antwort vom LLM erhalten.")
