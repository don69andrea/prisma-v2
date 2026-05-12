"""NarrativeService — orchestriert Memo-Generation Ende-zu-Ende.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md.

In dieser Datei (alles Service-internes Detail):
- `UniverseContext` (Pydantic-Value-Object — nur 1 Consumer im MVP)
- `_extract_ranking_for_ticker` (Helper)
- `_build_universe_context` (Helper)
- `NarrativeService` (Klasse mit get_memo + generate_memo)
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError

from backend.domain.entities.research_memo import ResearchMemo
from backend.domain.entities.stock import Stock
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.domain.schemas.research_memo_schema import ResearchMemoSchema
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader


class UniverseContext(BaseModel):
    """Aggregierte Verteilungs-Metadaten fuer den User-Prompt.

    Wird im Service aus dict-list-Results von RankingRunRepository abgeleitet.
    Keine eigene Datei (YAGNI — nur 1 Consumer).
    """

    model_config = {"frozen": True}

    n_stocks: int = Field(..., ge=1)
    median_rank: int = Field(..., ge=1)
    top20_threshold: int = Field(..., ge=1)


def _extract_ranking_for_ticker(results: list[dict[str, Any]], *, ticker: str) -> dict[str, Any]:
    """Filtert den Ranking-Eintrag fuer einen bestimmten Ticker.

    Wirft KeyError, wenn der Ticker nicht im Run vorkommt.
    """
    for row in results:
        if row["ticker"] == ticker:
            return row
    raise KeyError(f"Ticker {ticker} not in run results")


def _build_universe_context(results: list[dict[str, Any]]) -> UniverseContext:
    """Berechnet aggregierte Stats (n, median, top20-threshold) aus dict-list."""
    ranks = sorted(int(r["total_rank"]) for r in results if r.get("total_rank") is not None)
    if not ranks:
        raise ValueError("Keine validen total_ranks in den Results")

    n = len(ranks)
    median_rank = int(median(ranks))
    # 20%-Perzentile via Index-Lookup; fuer kleine N robust ohne numpy
    idx = max(0, int(round(0.20 * (n - 1))))
    top20_threshold = ranks[idx]

    return UniverseContext(n_stocks=n, median_rank=median_rank, top20_threshold=top20_threshold)


def _stringify(obj: Any) -> dict[str, Any]:
    """Fallback-Dump fuer SimpleNamespace und aehnliche Objekte ohne model_dump.

    Note: Lists in __dict__ values stay as lists; their elements are NOT
    recursively expanded. Sufficient for Anthropic-Response shapes where
    nested SimpleNamespace lists end up as repr() strings via json.dumps's
    default=str fallback. If a future shape needs deep dict-form output,
    rewrite to recurse into list elements.
    """
    if hasattr(obj, "__dict__"):
        return {k: _stringify(v) if hasattr(v, "__dict__") else v for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return {"_list": [_stringify(x) if hasattr(x, "__dict__") else x for x in obj]}
    return {"_repr": repr(obj)}


def _rankings_for_template(ranking: dict[str, Any]) -> dict[str, dict[str, float | int]]:
    """Wandelt das per_model_ranks-Dict + weighted_avg in ein
    Template-freundliches dict[name, {rank, score}]-Format um.

    Score-Daten sind zu diesem Zeitpunkt nicht alle in den Run-Results,
    daher Score = 1 / rank als grobe Visualisierung. Spec sagt nichts
    Strenges dazu, das Template zeigt nur eine Sichtbarmachung.
    """
    model_label = {
        "quality_classic": "Quality Classic",
        "alpha": "Alpha",
        "trend_momentum": "Trend Momentum",
        "value_alpha_potential": "Value Alpha Potential",
        "diversification": "Diversification",
    }
    out: dict[str, dict[str, float | int]] = {}
    per_model = ranking.get("per_model_ranks") or {}
    for key, label in model_label.items():
        rank = per_model.get(key)
        if rank is not None:
            out[label] = {"rank": int(rank), "score": round(1.0 / max(int(rank), 1), 4)}
    return out


class NarrativeService:
    """Memo-Generation. Spec §5."""

    def __init__(
        self,
        *,
        memo_repository: ResearchMemoRepository,
        run_repository: RankingRunRepository,
        stock_repository: StockRepository,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._memo_repo = memo_repository
        self._run_repo = run_repository
        self._stock_repo = stock_repository
        self._llm = llm_client
        self._prompts = prompt_loader
        self._model = model

    async def get_memo(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
    ) -> ResearchMemo | None:
        return await self._memo_repo.get(stock_id, model_run_id, language=language)

    async def generate_memo(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
        force_regenerate: bool = False,
    ) -> ResearchMemo:
        # Guard: EN-Template ist Stub (siehe narrative_system.en.md.j2).
        # Frueher Bail-Out verhindert Token-Verbrauch fuer Garbage-Prompt.
        # Wird entfernt sobald EN-Template gefuellt ist (Folge-PR).
        if language == "en":
            raise NotImplementedError(
                "EN-Memos sind in dieser Slice noch nicht implementiert "
                "(narrative_system.en.md.j2 ist Stub). Bitte language='de' nutzen."
            )

        # 1. Cache check
        if not force_regenerate:
            existing = await self._memo_repo.get(stock_id, model_run_id, language=language)
            if existing is not None:
                return existing

        # 2. Daten laden + 404-Pfade (sequenziell, Spec §4).
        # `asyncio.gather` darf hier NICHT verwendet werden: stock_repo und
        # run_repo teilen sich per FastAPI-DI dieselbe AsyncSession, und
        # `AsyncSession` ist nicht safe fuer concurrent use → IllegalStateChangeError.
        stock = await self._stock_repo.get(stock_id)
        if stock is None:
            raise LookupError(f"Stock {stock_id} not found")
        results = await self._run_repo.get_results(model_run_id)
        if results is None:
            raise LookupError(f"Run {model_run_id} not found")

        try:
            ranking = _extract_ranking_for_ticker(results, ticker=stock.ticker)
        except KeyError as exc:
            raise LookupError(f"Stock {stock.ticker} not in run {model_run_id}") from exc

        universe_context = _build_universe_context(results)

        # 3. Prompts rendern
        system_prompt = self._prompts.render(f"narrative_system.{language}.md.j2", {})
        user_prompt = self._prompts.render(
            "narrative_user.md.j2",
            {
                "ticker": stock.ticker,
                "name": stock.name,
                "sector": stock.sector,
                "country": stock.country,
                "run_id": str(model_run_id),
                "universe_name": "Universe",
                "n_stocks": universe_context.n_stocks,
                "median_rank": universe_context.median_rank,
                "top20_threshold": universe_context.top20_threshold,
                "rankings": _rankings_for_template(ranking),
                "total_rank": ranking["total_rank"],
                "sweet_spot": ranking["is_sweet_spot"],
                "weights": "equal-weighted (0.20 each)",
            },
        )

        # 4. LLM-Call mit Tool-use + Caching
        response = await self._llm.messages_create(
            model=self._model,
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
                    "name": "submit_memo",
                    "description": "Submit the structured research memo.",
                    "input_schema": ResearchMemoSchema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "submit_memo"},
            max_tokens=2000,
            feature="narrative_engine",
        )

        # 5. Tool-use Antwort → Pydantic-Validate (oder Error-Memo-Pfad)
        memo_schema = self._try_validate_tool_response(response)
        if memo_schema is None:
            self._dump_malformed_response(response, stock_id=stock_id, run_id=model_run_id)
            memo_schema = self._build_error_memo_schema(stock=stock, ranking=ranking)

        # 6. Persist
        # Defense-in-depth: Entity-Constraints sind heute laxer als Schema
        # (Entity = DB-Längen, Schema = LLM-Output). Falls künftige Drift dazu
        # führt dass ein Schema-valides Output Entity-Validation verletzt
        # (z.B. Schema lockerer als Entity), darf NICHT 500 escalieren —
        # gleicher Error-Memo-Pfad wie bei Schema-Verletzung.
        try:
            memo_entity = self._build_memo_entity(
                memo_schema, stock_id=stock_id, model_run_id=model_run_id, language=language
            )
        except ValidationError:
            self._dump_malformed_response(response, stock_id=stock_id, run_id=model_run_id)
            error_schema = self._build_error_memo_schema(stock=stock, ranking=ranking)
            memo_entity = self._build_memo_entity(
                error_schema, stock_id=stock_id, model_run_id=model_run_id, language=language
            )
        await self._memo_repo.save(memo_entity)

        # UPSERT behaelt bei Konflikt die Original-id und Original-created_at
        # der DB-Row. Damit der Service die *persisted* Werte zurueckgibt
        # (nicht die frisch generierten in-memory Werte), Reload nach save().
        persisted = await self._memo_repo.get(stock_id, model_run_id, language=language)
        if persisted is None:
            raise RuntimeError(
                f"Memo for stock {stock_id} / run {model_run_id} verschwand "
                "zwischen save() und reload — DB-Inkonsistenz?"
            )
        return persisted

    def _build_memo_entity(
        self,
        schema: Any,
        *,
        stock_id: UUID,
        model_run_id: UUID,
        language: Literal["de", "en"],
    ) -> ResearchMemo:
        return ResearchMemo(
            id=uuid4(),
            stock_id=stock_id,
            model_run_id=model_run_id,
            language=language,
            created_at=datetime.now(tz=UTC),
            one_liner=schema.one_liner,
            ranking_interpretation=schema.ranking_interpretation,
            sweet_spot=schema.sweet_spot,
            sweet_spot_explanation=schema.sweet_spot_explanation,
            contradictions=list(schema.contradictions),
            key_strengths=list(schema.key_strengths),
            key_risks=list(schema.key_risks),
            confidence=schema.confidence,
            model_version=schema.model_version,
        )

    def _try_validate_tool_response(self, response: Any) -> ResearchMemoSchema | None:
        """Liefert die validierte Schema-Instanz oder None bei Fehler."""
        for block in response.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == "submit_memo"
            ):
                try:
                    return ResearchMemoSchema.model_validate(block.input)
                except ValidationError:
                    return None
        return None

    def _dump_malformed_response(self, response: Any, *, stock_id: UUID, run_id: UUID) -> None:
        log_dir = Path("logs/malformed_memos")
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = int(datetime.now(tz=UTC).timestamp())
        path = log_dir / f"{run_id}_{stock_id}_{ts}.json"
        try:
            dump = (
                response.model_dump() if hasattr(response, "model_dump") else _stringify(response)
            )
        except Exception:  # noqa: BLE001
            dump = _stringify(response)
        path.write_text(_json.dumps(dump, default=str, indent=2), encoding="utf-8")

    def _build_error_memo_schema(
        self, *, stock: Stock, ranking: dict[str, Any]
    ) -> ResearchMemoSchema:
        return ResearchMemoSchema(
            ticker=stock.ticker,
            total_rank=int(ranking["total_rank"]),
            one_liner="Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
            ranking_interpretation=(
                "Automatisch generiertes Memo nicht erzeugbar. Bitte Raw-Response"
                " in logs/malformed_memos/ pruefen und Run neu starten."
            ),
            sweet_spot=False,
            sweet_spot_explanation=None,
            contradictions=[],
            key_strengths=["—"],
            key_risks=["—"],
            confidence="low",
            generated_at=datetime.now(tz=UTC),
            model_version="error-fallback",
        )
