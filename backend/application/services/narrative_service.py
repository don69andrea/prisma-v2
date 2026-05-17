"""NarrativeService — orchestriert Memo-Generation Ende-zu-Ende.

Spec: docs/specs/2026-05-04-narrative-engine-single-memo.md.

In dieser Datei (alles Service-internes Detail):
- `UniverseContext` (Pydantic-Value-Object — nur 1 Consumer im MVP)
- `_extract_ranking_for_ticker` (Helper)
- `_build_universe_context` (Helper)
- `NarrativeService` (Klasse mit get_memo + generate_memo)
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any, Literal
from uuid import UUID, uuid4

import anthropic
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.cost_tracker import CostTracker
from backend.domain.entities.memo_batch_job import MemoBatchJob
from backend.domain.entities.research_memo import ERROR_FALLBACK_MODEL_VERSION, ResearchMemo
from backend.domain.entities.stock import Stock
from backend.domain.errors import BudgetCapExceeded
from backend.domain.repositories.memo_batch_job_repository import MemoBatchJobRepository
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.domain.schemas.research_memo_schema import ResearchMemoSchema
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

# Hexagonal: Application-Layer importiert KEINE konkreten Infrastructure-Klassen.
# Repo-Konstruktion fuer Background-Worker laeuft ueber injizierte Factories
# (`stock_repo_factory`, `run_repo_factory`) — Wiring in dependencies.py.


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


def _rankings_for_template(ranking: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Wandelt das per_model_ranks-Dict in ein Template-freundliches
    dict[name, {rank}]-Format um.

    Score-Werte werden bewusst NICHT mitgeführt: vor Issue #66 wurde
    score = 1 / rank als Proxy berechnet, was die LLM als echte
    quantitative Aussage interpretiert hat (Hallucination-Quelle).
    Sobald echte per-Modell-Scores in Run-Results landen, kann der
    Slot reaktiviert werden.
    """
    model_label = {
        "quality_classic": "Quality Classic",
        "alpha": "Alpha",
        "trend_momentum": "Trend Momentum",
        "value_alpha_potential": "Value Alpha Potential",
        "diversification": "Diversification",
    }
    out: dict[str, dict[str, int]] = {}
    per_model = ranking.get("per_model_ranks") or {}
    for key, label in model_label.items():
        rank = per_model.get(key)
        if rank is not None:
            out[label] = {"rank": int(rank)}
    return out


class NarrativeService:
    """Memo-Generation. Spec §5."""

    def __init__(
        self,
        *,
        memo_repository: ResearchMemoRepository,
        run_repository: RankingRunRepository,
        stock_repository: StockRepository,
        batch_repository: MemoBatchJobRepository,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
        cost_tracker: CostTracker,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        stock_repo_factory: Callable[[AsyncSession], StockRepository],
        run_repo_factory: Callable[[AsyncSession], RankingRunRepository],
        model: str = "claude-sonnet-4-6",
        max_concurrent_batch_workers: int = 3,
        stale_batch_timeout_seconds: int = 600,
    ) -> None:
        self._memo_repo = memo_repository
        self._run_repo = run_repository
        self._stock_repo = stock_repository
        self._batch_repo = batch_repository
        self._llm = llm_client
        self._prompts = prompt_loader
        self._cost_tracker = cost_tracker
        self._session_factory = session_factory
        # Factories fuer Background-Worker-Repos: Constructor-DI statt Module-
        # Import (Hexagonal). Werden in _execute_batch mit eigenen Sessions
        # aus session_factory aufgerufen.
        self._stock_repo_factory = stock_repo_factory
        self._run_repo_factory = run_repo_factory
        self._model = model
        self._max_concurrent_batch_workers = max_concurrent_batch_workers
        self._stale_batch_timeout_seconds = stale_batch_timeout_seconds
        self._logger = logging.getLogger("backend.narrative_service")
        # Bug 2 fix: retain strong references so GC cannot cancel mid-execution tasks.
        # Python asyncio docs: "Save a reference to the result of create_task()."
        self._background_tasks: set[asyncio.Task[None]] = set()

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
        return await self._generate_memo_isolated(
            stock_id,
            model_run_id,
            language=language,
            force_regenerate=force_regenerate,
            stock_repo=self._stock_repo,
            run_repo=self._run_repo,
        )

    async def start_batch(
        self,
        model_run_id: UUID,
        *,
        top_n: int = 20,
        language: Literal["de", "en"] = "de",
    ) -> MemoBatchJob:
        """Validiert Run, erstellt Job, spawned Background-Task, returnt sofort."""
        # top_n-Bounds
        if not (1 <= top_n <= 100):
            raise ValueError(f"top_n must be 1..100, got {top_n}")

        # Run existiert? Via Factory + frische Session (nicht self._run_repo) —
        # start_batch ist Background-Setup und darf nicht von der Request-
        # Session abhaengen (die ist nach 202-Response moeglicherweise schon zu).
        async with self._session_factory() as session:
            validation_run_repo = self._run_repo_factory(session)
            results = await validation_run_repo.get_results(model_run_id)
        if results is None:
            raise LookupError(f"Run {model_run_id} not found")

        # Cost-Pre-Check (konservativ ~$0.025/Memo).
        # Note: CostTracker.check_cap ist ein Soft-Limit ohne DB-Lock (Spec §5
        # Cost-Tracker). Bei concurrent Batches koennen zwei Pre-Checks beide
        # passieren und dann beide realen Kosten anfallen. Akzeptabel fuer
        # Capstone-Volumen. Mid-Batch-BudgetCapExceeded fangen wir in _one()
        # ab und propagieren in error_message.
        estimated_usd = Decimal(top_n) * Decimal("0.025")
        await self._cost_tracker.check_cap(estimated_usd=estimated_usd)

        # Job anlegen
        job = MemoBatchJob(
            id=uuid4(),
            model_run_id=model_run_id,
            top_n=top_n,
            language=language,
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(tz=UTC),
        )
        await self._batch_repo.save(job)

        # Background-Task spawnen — strong reference retained to prevent GC cancellation.
        # Python asyncio docs: "Save a reference to the result of create_task()."
        task = asyncio.create_task(self._execute_batch(job.id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return job

    async def _execute_batch(self, job_id: UUID) -> None:
        """Background-Worker. Wird via asyncio.create_task gestartet.

        WICHTIG: Der Worker nutzt KEINE Service-eigenen Stock/Run-Repos
        (die sind an die Request-Session des start_batch-Aufrufers gebunden,
        die laengst geschlossen ist). Stattdessen baut er pro parallelem
        Sub-Task eigene Sessions via session_factory (B1-Lehre).
        """
        # F2: Outer try/except stellt sicher dass der Job nie auf 'running' hängen
        # bleibt wenn der Worker unerwartet crasht (z.B. DB-Verbindungsverlust,
        # ImportError, unerwartete RuntimeError ausserhalb von _one()).
        # _one() hat bereits einen eigenen Catch-all — dieser hier fängt alles andere.
        try:
            await self._execute_batch_inner(job_id)
        except Exception as exc:
            self._logger.exception("Batch %s: worker crashed unexpectedly: %s", job_id, exc)
            try:
                crashed = await self._batch_repo.get(job_id)
                if crashed is not None and crashed.status == "running":
                    await self._batch_repo.save(
                        crashed.model_copy(
                            update={
                                "status": "failed",
                                "completed_at": datetime.now(tz=UTC),
                                "error_message": (f"Worker crash: {type(exc).__name__}: {exc}")[
                                    :1000
                                ],
                            }
                        )
                    )
            except Exception:
                self._logger.exception(
                    "Batch %s: failed to persist crash status — job may stay 'running'", job_id
                )

    async def _execute_batch_inner(self, job_id: UUID) -> None:
        """Innerer Worker-Body — aufgerufen von _execute_batch mit Crash-Guard."""
        # _batch_repo is SQLAMemoBatchJobRepository which opens its own session per
        # call — safe to use from background worker (unlike stock/run repos which
        # would share the closed request session).
        job = await self._batch_repo.get(job_id)
        if job is None:
            return  # Sollte nicht passieren — job war grade erstellt

        # Status auf running setzen
        running = job.model_copy(update={"status": "running", "started_at": datetime.now(tz=UTC)})
        await self._batch_repo.save(running)

        # Top-N stocks aus Run-Results bestimmen (eine eigene Session fuer den Lookup)
        async with self._session_factory() as session:
            run_repo_init = self._run_repo_factory(session)
            results = await run_repo_init.get_results(running.model_run_id)

        if results is None:
            # Sollte nicht passieren (start_batch hat schon validiert), aber defensiv
            failed = running.model_copy(
                update={
                    "status": "failed",
                    "completed_at": datetime.now(tz=UTC),
                    "error_message": "Run results disappeared mid-batch",
                }
            )
            await self._batch_repo.save(failed)
            return

        # Sort by total_rank ASC, take top_n entries.
        # Bug 1 fix: RankingRunService stores ticker/total_rank/etc. — no stock_id.
        # Resolve tickers to stock_ids via Bulk-Query (1 Roundtrip statt N).
        sorted_results = sorted(results, key=lambda r: int(r["total_rank"]))
        top_stocks = sorted_results[: running.top_n]
        top_tickers = [row["ticker"] for row in top_stocks]

        async with self._session_factory() as lookup_session:
            lookup_stock_repo = self._stock_repo_factory(lookup_session)
            stocks_by_ticker = {
                s.ticker: s for s in await lookup_stock_repo.list_by_tickers(top_tickers)
            }

        stock_ids: list[UUID] = []
        for ticker in top_tickers:
            stock = stocks_by_ticker.get(ticker)
            if stock is None:
                self._logger.warning(
                    "Batch %s: ticker %s not found in DB, skipping",
                    job_id,
                    ticker,
                )
                continue
            stock_ids.append(stock.id)

        self._logger.info(
            "Batch %s running: %d stocks",
            job_id,
            len(stock_ids),
        )

        # Concurrency-Limit
        semaphore = asyncio.Semaphore(self._max_concurrent_batch_workers)

        async def _one(stock_id: UUID) -> tuple[str, UUID, str | None]:
            """Liefert (status, stock_id, error_reason).

            error_reason wird nur bei BudgetCapExceeded gesetzt (Spec §8 verlangt
            "Budget-Cap erreicht" als job.error_message). Network-Fails liefern
            None — failed_stock_ids reicht zur Diagnose.
            """
            async with semaphore, self._session_factory() as worker_session:
                # Factory pro Worker — eigene Session (B1-Lehre).
                isolated_stock_repo = self._stock_repo_factory(worker_session)
                isolated_run_repo = self._run_repo_factory(worker_session)
                try:
                    await self._generate_memo_isolated(
                        stock_id,
                        running.model_run_id,
                        language=running.language,
                        stock_repo=isolated_stock_repo,
                        run_repo=isolated_run_repo,
                    )
                    return ("ok", stock_id, None)
                except BudgetCapExceeded as exc:
                    self._logger.warning(
                        "Batch %s memo failed for stock %s: BudgetCapExceeded %s",
                        job_id,
                        stock_id,
                        exc,
                    )
                    return ("failed", stock_id, "Budget-Cap erreicht")
                except (
                    anthropic.APITimeoutError,
                    anthropic.APIConnectionError,
                    anthropic.RateLimitError,
                ) as exc:
                    self._logger.warning(
                        "Batch %s memo failed for stock %s: %s",
                        job_id,
                        stock_id,
                        exc,
                    )
                    return ("failed", stock_id, None)
                except Exception as exc:
                    # F2: Catch-all fuer unerwartete Exceptions (z.B. anthropic.APIStatusError,
                    # ValidationError, DB-Fehler). Verhindert dass ein einzelner Stock-Fehler
                    # asyncio.gather() crasht und den gesamten Worker abbricht.
                    self._logger.exception(
                        "Batch %s: unexpected error for stock %s: %s",
                        job_id,
                        stock_id,
                        exc,
                    )
                    return ("failed", stock_id, None)

        results_per_stock = await asyncio.gather(*[_one(s) for s in stock_ids])
        failed_ids = [sid for status, sid, _ in results_per_stock if status == "failed"]
        budget_reasons = [r for status, _, r in results_per_stock if status == "failed" and r]

        n_failed = len(failed_ids)
        if n_failed == 0:
            final_status: str = "complete"
        elif n_failed == len(stock_ids):
            final_status = "failed"
        else:
            final_status = "partial"

        self._logger.info(
            "Batch %s %s: %d ok, %d failed",
            job_id,
            final_status,
            len(stock_ids) - n_failed,
            n_failed,
        )

        # W1 Race-Fix: Vor dem Final-Save prüfen ob ein Stale-Cleanup (in
        # get_batch_job) den Job zwischenzeitlich auf 'failed' gesetzt hat.
        # Falls ja: NICHT überschreiben — User würde sonst kurzzeitig
        # 'failed' sehen und später 'complete' (last-write-wins-Race).
        #
        # F5 — TOCTOU-Fenster: Zwischen re-read (unten) und final save besteht
        # ein kleines Fenster in dem get_batch_job den Job auf 'failed' setzen
        # könnte: (1) re-read → still "running", (2) GET-Request kommt rein und
        # setzt "failed", (3) Worker schreibt "complete".
        # Das Fenster ist <1ms (zwei aufeinanderfolgende await-Punkte ohne I/O
        # dazwischen) — für Capstone-Volumen akzeptabel.
        # Echte Lösung: optimistic locking mit version-column oder DB-CAS.
        current = await self._batch_repo.get(job_id)
        if current is not None and current.status == "failed" and current.started_at is not None:
            elapsed = (datetime.now(tz=UTC) - current.started_at).total_seconds()
            if elapsed > self._stale_batch_timeout_seconds:
                self._logger.info(
                    "Batch %s stale-cleanup intervened during run; preserving failed status",
                    job_id,
                )
                return

        # error_message: erstes Budget-Cap-Vorkommnis spiegelt sich im Job.
        # Spec §8: bei BudgetCapExceeded mid-batch -> error_message="Budget-Cap erreicht".
        error_message = budget_reasons[0] if budget_reasons else None

        final = running.model_copy(
            update={
                "status": final_status,
                "failed_stock_ids": failed_ids,
                "error_message": error_message,
                "completed_at": datetime.now(tz=UTC),
            }
        )
        await self._batch_repo.save(final)

    async def get_batch_job(self, job_id: UUID) -> MemoBatchJob | None:
        """Laedt Job; bei status=running mit started_at>STALE_TIMEOUT macht
        lazy-cleanup (Stale-Job-Recovery nach Server-Crash).

        Spec §8 Stale-Job-Cleanup: Job-Status bleibt nach Server-Crash auf
        'running'. Wir markieren ihn beim ersten GET als 'failed', damit
        der User klar sieht dass der Batch tot ist.
        """
        job = await self._batch_repo.get(job_id)
        if job is None:
            return None
        if job.status == "running" and job.started_at is not None:
            elapsed = (datetime.now(tz=UTC) - job.started_at).total_seconds()
            if elapsed > self._stale_batch_timeout_seconds:
                stale = job.model_copy(
                    update={
                        "status": "failed",
                        "completed_at": datetime.now(tz=UTC),
                        "error_message": (
                            "Job stale — Server-Restart oder Crash waehrend Ausfuehrung"
                        ),
                    }
                )
                await self._batch_repo.save(stale)
                return stale
        return job

    async def list_memos_for_run(
        self,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
    ) -> list[ResearchMemo]:
        """Helper fuer GET /jobs/{id}-Response: alle Memos fuer den Run + Sprache."""
        return await self._memo_repo.list_by_run(model_run_id, language=language)

    async def get_stock_ticker_map(self, stock_ids: list[UUID]) -> dict[UUID, str]:
        """Lookup-Map stock_id -> ticker, fuer GET /jobs/{id}-Response.

        Bulk-Query via `list_by_ids` (1 Roundtrip). Wichtig fuer Frontend-Polling
        alle 2-3s bei top_n bis 100: vermeidet N+1-Last.

        Nutzt Factory + frische Session statt self._stock_repo: GET /jobs/{id}
        kann lange nach Request-Ende aufgerufen werden (Polling), und Background-
        Worker-Setup (PR #70 W4) soll konsistent von Request-Session entkoppelt
        sein.
        """
        if not stock_ids:
            return {}
        async with self._session_factory() as session:
            repo = self._stock_repo_factory(session)
            stocks = await repo.list_by_ids(stock_ids)
        return {s.id: s.ticker for s in stocks}

    async def _generate_memo_isolated(
        self,
        stock_id: UUID,
        model_run_id: UUID,
        *,
        language: Literal["de", "en"] = "de",
        force_regenerate: bool = False,
        stock_repo: StockRepository,
        run_repo: RankingRunRepository,
    ) -> ResearchMemo:
        """Memo-Generation mit explizit injizierten Repos.

        Public generate_memo nutzt Service-eigene Repos. Background-Worker
        (_execute_batch in Task 8) nutzt isolated Repos via session_factory
        pro Worker (B1-Lehre — geteilte AsyncSession ist nicht concurrent-safe).
        """
        # 1. Cache check
        if not force_regenerate:
            existing = await self._memo_repo.get(stock_id, model_run_id, language=language)
            if existing is not None:
                return existing

        # 2. Daten laden + 404-Pfade (sequenziell, Spec §4).
        # `asyncio.gather` darf hier NICHT verwendet werden: stock_repo und
        # run_repo teilen sich per FastAPI-DI dieselbe AsyncSession, und
        # `AsyncSession` ist nicht safe fuer concurrent use → IllegalStateChangeError.
        stock = await stock_repo.get(stock_id)
        if stock is None:
            raise LookupError(f"Stock {stock_id} not found")
        results = await run_repo.get_results(model_run_id)
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
            f"narrative_user.{language}.md.j2",
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
            is_error=(schema.model_version == ERROR_FALLBACK_MODEL_VERSION),
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
            model_version=ERROR_FALLBACK_MODEL_VERSION,
        )
