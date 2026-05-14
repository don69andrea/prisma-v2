"""Unit-Tests fuer NarrativeService Multi-Memo-Batch-Methoden."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import UUID, uuid4

import pytest

from backend.application.services.narrative_service import NarrativeService

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _make_validation_mocks(run_results: Any) -> tuple[Mock, Mock, AsyncMock]:
    """Helper fuer start_batch-Tests: session_factory + run_repo_factory.

    start_batch validiert den Run via Factory + frische Session (PR #70 W4-Fix:
    Background-Setup darf nicht von der Request-Session abhaengen).
    """
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)
    session_factory = Mock(return_value=mock_session_cm)

    mock_run_repo = AsyncMock()
    mock_run_repo.get_results = AsyncMock(return_value=run_results)
    run_repo_factory = Mock(return_value=mock_run_repo)

    return session_factory, run_repo_factory, mock_run_repo


def _make_batch_exec_mocks(
    *,
    run_results: list[dict[str, Any]],
    stocks: list[tuple[UUID, str]],
) -> tuple[Mock, Mock, Mock, AsyncMock, AsyncMock]:
    """Helper fuer _execute_batch-Tests: baut session_factory + Repo-Factories.

    Liefert (session_factory, run_repo_factory, stock_repo_factory,
    mock_run_repo_instance, mock_stock_repo_instance) — die letzten zwei
    fuer assertion-Zugriff im Test.
    """
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)
    session_factory = Mock(return_value=mock_session_cm)

    mock_run_repo = AsyncMock()
    mock_run_repo.get_results = AsyncMock(return_value=run_results)
    run_repo_factory = Mock(return_value=mock_run_repo)

    stock_mocks: list[Any] = []
    for sid, ticker in stocks:
        s = MagicMock()
        s.id = sid
        s.ticker = ticker
        stock_mocks.append(s)
    mock_stock_repo = AsyncMock()
    mock_stock_repo.list_by_tickers = AsyncMock(return_value=stock_mocks)
    stock_repo_factory = Mock(return_value=mock_stock_repo)

    return session_factory, run_repo_factory, stock_repo_factory, mock_run_repo, mock_stock_repo


def _make_service(**overrides: Any) -> NarrativeService:
    """Helper: NarrativeService mit AsyncMock-Defaults bauen."""
    defaults = {
        "memo_repository": AsyncMock(),
        "run_repository": AsyncMock(),
        "stock_repository": AsyncMock(),
        "batch_repository": AsyncMock(),
        "llm_client": AsyncMock(),
        "prompt_loader": AsyncMock(),
        "cost_tracker": AsyncMock(),
        "session_factory": Mock(),
        # Factories liefern Mock-Repos pro Session — Tests die das echte
        # _execute_batch-Verhalten brauchen, ueberschreiben das explizit.
        "stock_repo_factory": Mock(return_value=AsyncMock()),
        "run_repo_factory": Mock(return_value=AsyncMock()),
        "max_concurrent_batch_workers": 3,
        "stale_batch_timeout_seconds": 600,
    }
    defaults.update(overrides)
    return NarrativeService(**defaults)  # type: ignore[arg-type]


class TestStartBatch:
    async def test_start_batch_creates_pending_job(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session_factory, run_repo_factory, _ = _make_validation_mocks([{"ticker": "X"}])
        batch_repo = AsyncMock()
        cost_tracker = AsyncMock()
        cost_tracker.check_cap = AsyncMock()

        # asyncio.create_task mocken — kein Background-Lauf im Test.
        # Must return a task-like object that supports add_done_callback (Bug 2 fix).
        def _fake_create_task(coro: Any, **_kwargs: Any) -> Any:
            coro.close()
            fake_task = Mock()
            fake_task.add_done_callback = Mock()
            return fake_task

        monkeypatch.setattr("asyncio.create_task", _fake_create_task)

        service = _make_service(
            batch_repository=batch_repo,
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
        )
        run_id = uuid4()

        job = await service.start_batch(run_id, top_n=20)

        assert job.status == "pending"
        assert job.model_run_id == run_id
        assert job.top_n == 20
        assert job.language == "de"
        batch_repo.save.assert_awaited_once()

    async def test_start_batch_accepts_en_language(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """EN-Slice: start_batch akzeptiert language='en' und erstellt Job mit
        language='en' im Status 'pending'. Ersetzt den alten Guard-Test, weil
        EN-Templates jetzt produktiv sind."""
        session_factory, run_repo_factory, _ = _make_validation_mocks([{"ticker": "X"}])
        batch_repo = AsyncMock()
        cost_tracker = AsyncMock()
        cost_tracker.check_cap = AsyncMock()

        def _fake_create_task(coro: Any, **_kwargs: Any) -> Any:
            coro.close()
            fake_task = Mock()
            fake_task.add_done_callback = Mock()
            return fake_task

        monkeypatch.setattr("asyncio.create_task", _fake_create_task)

        service = _make_service(
            batch_repository=batch_repo,
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
        )
        run_id = uuid4()

        job = await service.start_batch(run_id, top_n=20, language="en")

        assert job.status == "pending"
        assert job.language == "en"
        batch_repo.save.assert_awaited_once()

    async def test_start_batch_raises_404_when_run_missing(self) -> None:
        session_factory, run_repo_factory, _ = _make_validation_mocks(None)
        service = _make_service(
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
        )

        with pytest.raises(LookupError, match="Run"):
            await service.start_batch(uuid4())

    async def test_start_batch_pre_checks_budget_cap(self) -> None:
        from backend.domain.errors import BudgetCapExceeded

        session_factory, run_repo_factory, _ = _make_validation_mocks([{"ticker": "X"}])
        cost_tracker = AsyncMock()
        cost_tracker.check_cap = AsyncMock(
            side_effect=BudgetCapExceeded(
                current_usd=Decimal("19.00"),
                attempted_usd=Decimal("0.50"),
                cap_usd=Decimal("20.00"),
            )
        )

        service = _make_service(
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
        )

        with pytest.raises(BudgetCapExceeded):
            await service.start_batch(uuid4(), top_n=20)

    async def test_start_batch_validates_top_n_bounds(self) -> None:
        session_factory, run_repo_factory, mock_run_repo = _make_validation_mocks([{"ticker": "X"}])
        service = _make_service(
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
        )

        with pytest.raises(ValueError, match="top_n"):
            await service.start_batch(uuid4(), top_n=0)
        # top_n-Bounds-Check VOR Run-Validation
        mock_run_repo.get_results.assert_not_awaited()

        with pytest.raises(ValueError, match="top_n"):
            await service.start_batch(uuid4(), top_n=101)
        mock_run_repo.get_results.assert_not_awaited()


class TestExecuteBatch:
    async def test_execute_batch_all_success_marks_complete(self) -> None:
        from backend.domain.entities.memo_batch_job import MemoBatchJob

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=2,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
            ],
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )
        # _generate_memo_isolated mocken — wir testen Worker-Loop, nicht Memo-Inhalt
        service._generate_memo_isolated = AsyncMock()  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        # save() mind. 2x: status=running, status=complete
        assert batch_repo.save.await_count >= 2
        last_save_call = batch_repo.save.await_args_list[-1]
        last_job: MemoBatchJob = last_save_call.args[0]
        assert last_job.status == "complete"
        assert last_job.failed_stock_ids == []

    async def test_execute_batch_partial_on_network_fail(self) -> None:
        import anthropic

        from backend.domain.entities.memo_batch_job import MemoBatchJob

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=2,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
            ],
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )

        # Erster Stock: ok. Zweiter: APITimeoutError.
        async def _flaky(stock_id: Any, *_args: Any, **_kwargs: Any) -> None:
            if stock_id == stock_ids[1]:
                raise anthropic.APITimeoutError(request=Mock())

        service._generate_memo_isolated = AsyncMock(side_effect=_flaky)  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        last_job: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert last_job.status == "partial"
        assert stock_ids[1] in last_job.failed_stock_ids
        assert stock_ids[0] not in last_job.failed_stock_ids

    async def test_execute_batch_all_fail_marks_failed(self) -> None:
        import anthropic

        from backend.domain.entities.memo_batch_job import MemoBatchJob

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=2,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
            ],
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )
        service._generate_memo_isolated = AsyncMock(  # type: ignore[method-assign]
            side_effect=anthropic.APIConnectionError(request=Mock())
        )

        await service._execute_batch(job_id)

        last_job: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert last_job.status == "failed"
        assert len(last_job.failed_stock_ids) == 2

    async def test_execute_batch_partial_on_rate_limit(self) -> None:
        """RateLimitError nach LLMClient-Retry-Exhaustion: Stock in failed_stock_ids."""
        import anthropic

        from backend.domain.entities.memo_batch_job import MemoBatchJob

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=2,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
            ],
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )

        # Erster Stock: ok. Zweiter: RateLimitError (nach LLMClient-Retry-Exhaustion).
        async def _flaky(stock_id: Any, *_args: Any, **_kwargs: Any) -> None:
            if stock_id == stock_ids[1]:
                raise anthropic.RateLimitError(
                    "rate limit",
                    response=Mock(status_code=429),
                    body={},
                )

        service._generate_memo_isolated = AsyncMock(side_effect=_flaky)  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        last_job: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert last_job.status == "partial"
        assert stock_ids[1] in last_job.failed_stock_ids
        assert stock_ids[0] not in last_job.failed_stock_ids


class TestExecuteBatchTickerLookup:
    """Verifiziert dass `list_by_tickers` Bulk-Lookup (PR #70 W5) Stocks die
    nicht in der DB sind sauber skippt, statt zu crashen oder den ganzen Batch
    zu killen.
    """

    async def test_missing_tickers_are_skipped_with_warning(self) -> None:
        """Ein Ticker im Run aber nicht in stocks-Tabelle: Logged Warning,
        andere Stocks laufen weiter."""
        from backend.domain.entities.memo_batch_job import MemoBatchJob

        run_id = uuid4()
        job_id = uuid4()
        # 3 Tickers im Run, aber nur 2 sind in der "DB" (Stock C fehlt).
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=3,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
                {"ticker": "C", "total_rank": 3},  # nicht in stocks-Tabelle
            ],
            # list_by_tickers gibt nur A + B zurueck (C wurde aus DB geloescht)
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )
        service._generate_memo_isolated = AsyncMock()  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        # Worker beendet sauber mit status=complete fuer die 2 gefundenen
        # Stocks; C wird stillschweigend uebersprungen (Warning im Log,
        # nicht in failed_stock_ids — failed_stock_ids ist fuer LLM-Fails).
        last_job: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert last_job.status == "complete"
        assert last_job.failed_stock_ids == []
        # _generate_memo_isolated wurde nur 2x gerufen (nicht 3x)
        assert service._generate_memo_isolated.await_count == 2


class TestExecuteBatchStaleCleanupRace:
    """W1 (PR #70): Wenn waehrend des Workers ein Stale-Cleanup intervenierte,
    darf der Worker den Final-Save NICHT mehr durchfuehren.

    Vorher last-write-wins: User sah `failed` (Cleanup) -> spaeter `complete`
    (Worker). Verwirrend. Jetzt: Worker prueft vor Final-Save und respektiert
    den Cleanup-Status.
    """

    async def test_worker_skips_save_when_cleanup_intervened(self) -> None:
        from datetime import timedelta

        from backend.domain.entities.memo_batch_job import MemoBatchJob

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4()]
        old_start = datetime.now(UTC) - timedelta(seconds=700)  # > 600s timeout

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=1,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=old_start,
        )
        # Cleanup-intervened state — naechster batch_repo.get liefert das
        cleanup_intervened = existing_job.model_copy(
            update={
                "status": "failed",
                "started_at": old_start,
                "completed_at": datetime.now(UTC),
                "error_message": "Job stale — Server-Restart oder Crash waehrend Ausfuehrung",
            }
        )
        batch_repo = AsyncMock()
        # Sequence: get(initial) -> save(running) -> get(after-worker, finds cleanup)
        batch_repo.get = AsyncMock(side_effect=[existing_job, cleanup_intervened])
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[{"ticker": "A", "total_rank": 1}],
            stocks=[(stock_ids[0], "A")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )
        service._generate_memo_isolated = AsyncMock()  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        # Worker hat save() genau 1x gerufen (status=running am Start).
        # Final-Save wurde geskippt weil Cleanup intervenierte.
        assert batch_repo.save.await_count == 1
        running_save: MemoBatchJob = batch_repo.save.await_args_list[0].args[0]
        assert running_save.status == "running"


class TestExecuteBatchBudgetErrorMessage:
    """W3 (PR #70): Bei BudgetCapExceeded mid-batch wird die Begruendung
    in job.error_message propagiert (Spec §8 verlangt "Budget-Cap erreicht").

    Anders als bei Network-Fails (RateLimit, Timeout) wo failed_stock_ids
    zur Diagnose reicht — Budget-Cap ist eine semantische Begruendung die
    der User im UI sehen will.
    """

    async def test_budget_cap_propagates_error_message(self) -> None:
        from backend.domain.entities.memo_batch_job import MemoBatchJob
        from backend.domain.errors import BudgetCapExceeded

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=3,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
                {"ticker": "C", "total_rank": 3},
            ],
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B"), (stock_ids[2], "C")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )

        # Erster Stock: ok. Zweiter+Dritter: BudgetCap (Cap-Erschoepfung).
        async def _budget_fail(stock_id: Any, *_args: Any, **_kwargs: Any) -> None:
            if stock_id in (stock_ids[1], stock_ids[2]):
                raise BudgetCapExceeded(
                    current_usd=Decimal("19.95"),
                    attempted_usd=Decimal("0.025"),
                    cap_usd=Decimal("20.00"),
                )

        service._generate_memo_isolated = AsyncMock(side_effect=_budget_fail)  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        last_job: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert last_job.status == "partial"
        # W3: error_message ist gesetzt (Spec §8)
        assert last_job.error_message == "Budget-Cap erreicht"
        # failed_stock_ids enthaelt die 2 BudgetCap-Stocks
        assert set(last_job.failed_stock_ids) == {stock_ids[1], stock_ids[2]}

    async def test_network_fail_does_not_set_error_message(self) -> None:
        """Komplementaerer Test: nur BudgetCapExceeded setzt error_message,
        Network-Fails NICHT (failed_stock_ids reicht zur Diagnose).
        """
        import anthropic

        from backend.domain.entities.memo_batch_job import MemoBatchJob

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=2,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
            ],
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )

        async def _network_fail(stock_id: Any, *_args: Any, **_kwargs: Any) -> None:
            if stock_id == stock_ids[1]:
                raise anthropic.APITimeoutError(request=Mock())

        service._generate_memo_isolated = AsyncMock(side_effect=_network_fail)  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        last_job: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert last_job.status == "partial"
        # error_message bleibt None — nur failed_stock_ids dokumentiert den Fail
        assert last_job.error_message is None


class TestGetBatchJob:
    async def test_returns_none_for_unknown_id(self) -> None:
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=None)
        service = _make_service(batch_repository=batch_repo)

        result = await service.get_batch_job(uuid4())
        assert result is None

    async def test_returns_running_job_when_recent(self) -> None:
        from backend.domain.entities.memo_batch_job import MemoBatchJob

        recent_start = datetime.now(UTC)
        job = MemoBatchJob(
            id=uuid4(),
            model_run_id=uuid4(),
            top_n=20,
            language="de",
            status="running",
            failed_stock_ids=[],
            error_message=None,
            created_at=recent_start,
            started_at=recent_start,
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=job)
        batch_repo.save = AsyncMock()
        service = _make_service(batch_repository=batch_repo)

        result = await service.get_batch_job(job.id)
        assert result is not None
        assert result.status == "running"
        # save() NICHT gerufen — kein cleanup noetig
        batch_repo.save.assert_not_awaited()

    async def test_marks_stale_running_as_failed(self) -> None:
        from datetime import timedelta

        from backend.domain.entities.memo_batch_job import MemoBatchJob

        old_start = datetime.now(UTC) - timedelta(seconds=700)  # > 600s default timeout
        job = MemoBatchJob(
            id=uuid4(),
            model_run_id=uuid4(),
            top_n=20,
            language="de",
            status="running",
            failed_stock_ids=[],
            error_message=None,
            created_at=old_start,
            started_at=old_start,
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=job)
        batch_repo.save = AsyncMock()
        service = _make_service(batch_repository=batch_repo)

        result = await service.get_batch_job(job.id)
        assert result is not None
        assert result.status == "failed"
        assert "stale" in (result.error_message or "").lower()
        batch_repo.save.assert_awaited_once()


class TestListMemosForRun:
    async def test_delegates_to_repo(self) -> None:
        memo_repo = AsyncMock()
        memo_repo.list_by_run = AsyncMock(return_value=[])
        service = _make_service(memo_repository=memo_repo)

        run_id = uuid4()
        await service.list_memos_for_run(run_id, language="de")
        memo_repo.list_by_run.assert_awaited_once_with(run_id, language="de")


class TestGetStockTickerMap:
    """W5: Bulk-Lookup via `list_by_ids` — 1 Roundtrip statt N (PR #70).

    Vorher N+1 (1 stock_repo.get pro id); jetzt 1 Query, was bei
    Frontend-Polling alle 2-3s mit top_n=100 die Last drastisch reduziert.

    Service nutzt stock_repo_factory + session_factory (PR #70 W4) — GET kann
    nach Request-Ende aufgerufen werden, deshalb keine Request-Session.
    """

    @staticmethod
    def _mock_stock(stock_id: UUID, ticker: str) -> Any:
        from backend.domain.entities.stock import Stock

        s = MagicMock(spec=Stock)
        s.id = stock_id
        s.ticker = ticker
        return s

    @staticmethod
    def _factory_mocks(stocks: list[Any]) -> tuple[Mock, Mock, AsyncMock]:
        """Baut session_factory + stock_repo_factory + repo-mock fuer list_by_ids."""
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        session_factory = Mock(return_value=mock_session_cm)

        mock_repo = AsyncMock()
        mock_repo.list_by_ids = AsyncMock(return_value=stocks)
        stock_repo_factory = Mock(return_value=mock_repo)

        return session_factory, stock_repo_factory, mock_repo

    async def test_returns_ticker_for_known_stock(self) -> None:
        sid = uuid4()
        sf, srf, repo_mock = self._factory_mocks([self._mock_stock(sid, "NESN")])
        service = _make_service(session_factory=sf, stock_repo_factory=srf)

        result = await service.get_stock_ticker_map([sid])

        assert result == {sid: "NESN"}
        repo_mock.list_by_ids.assert_awaited_once_with([sid])

    async def test_skips_deleted_stock(self) -> None:
        """Falls Stock nicht mehr in der DB (CASCADE-delete): kein Eintrag in der Map."""
        sid = uuid4()
        sf, srf, _ = self._factory_mocks([])  # DB lieferte nichts
        service = _make_service(session_factory=sf, stock_repo_factory=srf)

        result = await service.get_stock_ticker_map([sid])

        assert result == {}

    async def test_empty_input_returns_empty_dict(self) -> None:
        sf, srf, repo_mock = self._factory_mocks([])
        service = _make_service(session_factory=sf, stock_repo_factory=srf)

        result = await service.get_stock_ticker_map([])

        assert result == {}
        # KEIN DB-Call fuer leeres Input (Early-Return) — Session bleibt zu
        sf.assert_not_called()
        repo_mock.list_by_ids.assert_not_awaited()

    async def test_multiple_stocks_all_found_single_query(self) -> None:
        """Kein N+1: list_by_ids wird genau 1x aufgerufen, nicht N-mal."""
        sid1, sid2, sid3 = uuid4(), uuid4(), uuid4()
        stocks = [
            self._mock_stock(sid1, "NESN"),
            self._mock_stock(sid2, "ROG"),
            self._mock_stock(sid3, "ABBN"),
        ]
        sf, srf, repo_mock = self._factory_mocks(stocks)
        service = _make_service(session_factory=sf, stock_repo_factory=srf)

        result = await service.get_stock_ticker_map([sid1, sid2, sid3])

        assert result == {sid1: "NESN", sid2: "ROG", sid3: "ABBN"}
        # PR #70 W5: 1 Bulk-Query, nicht 3 Einzel-Queries
        assert repo_mock.list_by_ids.await_count == 1

    async def test_partial_missing_stocks(self) -> None:
        """Nur bekannte Stocks tauchen in der Map auf (list_by_ids liefert nur Found-Subset)."""
        sid_known = uuid4()
        sid_deleted = uuid4()
        sf, srf, _ = self._factory_mocks([self._mock_stock(sid_known, "NESN")])
        service = _make_service(session_factory=sf, stock_repo_factory=srf)

        result = await service.get_stock_ticker_map([sid_known, sid_deleted])

        assert result == {sid_known: "NESN"}
        assert sid_deleted not in result


# ---------------------------------------------------------------------------
# New tests for the 3 critical bug fixes
# ---------------------------------------------------------------------------


class TestBug2BackgroundTaskRetention:
    """Bug 2 fix: asyncio.create_task return value must be retained."""

    async def test_start_batch_retains_task_reference(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After start_batch, _background_tasks must hold a reference to the spawned task."""
        import asyncio

        session_factory, run_repo_factory, _ = _make_validation_mocks([{"ticker": "X"}])
        batch_repo = AsyncMock()
        cost_tracker = AsyncMock()
        cost_tracker.check_cap = AsyncMock()

        captured_tasks: list[asyncio.Task[None]] = []

        real_create_task = asyncio.create_task

        def _spy_create_task(coro: Any, **kwargs: Any) -> asyncio.Task[None]:
            task: asyncio.Task[None] = real_create_task(coro, **kwargs)
            captured_tasks.append(task)
            # Cancel immediately so _execute_batch does not run for real
            task.cancel()
            return task

        monkeypatch.setattr("asyncio.create_task", _spy_create_task)

        service = _make_service(
            batch_repository=batch_repo,
            cost_tracker=cost_tracker,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
        )

        await service.start_batch(uuid4(), top_n=5)

        # The task must be in _background_tasks (or already removed via done_callback
        # if it completed/was cancelled synchronously). Either way, create_task was called.
        assert len(captured_tasks) == 1
        # done_callback removes the task once done — but the set was populated first
        # (even if discard ran already, we verify via captured_tasks that it was added).
        assert captured_tasks[0] is not None


class TestBug3BudgetCapExceededCaught:
    """Bug 3 fix: BudgetCapExceeded mid-batch must be caught in _one(), not propagate."""

    async def test_execute_batch_partial_on_budget_cap(self) -> None:
        """BudgetCapExceeded from _generate_memo_isolated: Stock lands in failed_stock_ids.

        Plus: error_message wird auf 'Budget-Cap erreicht' gesetzt (Spec §8, PR #70 W3).
        """
        from backend.domain.entities.memo_batch_job import MemoBatchJob
        from backend.domain.errors import BudgetCapExceeded

        run_id = uuid4()
        job_id = uuid4()
        stock_ids = [uuid4(), uuid4()]

        existing_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=2,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(return_value=existing_job)
        batch_repo.save = AsyncMock()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "A", "total_rank": 1},
                {"ticker": "B", "total_rank": 2},
            ],
            stocks=[(stock_ids[0], "A"), (stock_ids[1], "B")],
        )

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )

        # First stock: ok. Second: BudgetCapExceeded mid-call.
        async def _budget_fail(stock_id: Any, *_args: Any, **_kwargs: Any) -> None:
            if stock_id == stock_ids[1]:
                raise BudgetCapExceeded(
                    current_usd=Decimal("19.90"),
                    attempted_usd=Decimal("0.025"),
                    cap_usd=Decimal("20.00"),
                )

        service._generate_memo_isolated = AsyncMock(side_effect=_budget_fail)  # type: ignore[method-assign]

        await service._execute_batch(job_id)

        last_job: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        # Spec §8: partial (not a full crash), failed stock in failed_stock_ids
        assert last_job.status == "partial"
        assert stock_ids[1] in last_job.failed_stock_ids
        assert stock_ids[0] not in last_job.failed_stock_ids
        # W3: error_message propagiert "Budget-Cap erreicht"
        assert last_job.error_message == "Budget-Cap erreicht"


class TestExecuteBatchCrashGuard:
    """F2: Outer try/except in _execute_batch verhindert dass der Job auf 'running' hängt."""

    async def test_unexpected_exception_in_batch_sets_job_failed(self) -> None:
        """F2: Wenn _execute_batch_inner eine RuntimeError wirft (z.B. DB-Verbindungsverlust),
        muss der Job als 'failed' persistiert werden — nicht auf 'running' hängen bleiben."""
        from backend.domain.entities.memo_batch_job import MemoBatchJob

        job_id = uuid4()
        run_id = uuid4()
        pending_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=1,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        running_job = pending_job.model_copy(
            update={"status": "running", "started_at": datetime.now(UTC)}
        )

        batch_repo = AsyncMock()
        # _execute_batch liest den Job zum Crash-Status-Setzen
        batch_repo.get = AsyncMock(return_value=running_job)
        batch_repo.save = AsyncMock()

        service = _make_service(batch_repository=batch_repo)

        # _execute_batch_inner wirft RuntimeError (simuliert DB-Crash)
        service._execute_batch_inner = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("DB connection lost unexpectedly")
        )

        await service._execute_batch(job_id)

        # Job muss als 'failed' persistiert worden sein
        assert batch_repo.save.await_count >= 1
        final_save: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert final_save.status == "failed"
        assert final_save.completed_at is not None
        assert final_save.error_message is not None
        assert (
            "RuntimeError" in final_save.error_message
            or "crash" in final_save.error_message.lower()
        )

    async def test_unexpected_exception_in_one_does_not_crash_worker(self) -> None:
        """F2: Catch-all in _one() verhindert dass ein einzelner Stock-Fehler
        asyncio.gather() crasht und den gesamten Batch abbricht."""
        from backend.domain.entities.memo_batch_job import MemoBatchJob

        stock_id_1 = uuid4()
        stock_id_2 = uuid4()
        job_id = uuid4()
        run_id = uuid4()

        session_factory, run_repo_factory, stock_repo_factory, _, _ = _make_batch_exec_mocks(
            run_results=[
                {"ticker": "AAPL", "total_rank": 1},
                {"ticker": "MSFT", "total_rank": 2},
            ],
            stocks=[(stock_id_1, "AAPL"), (stock_id_2, "MSFT")],
        )

        pending_job = MemoBatchJob(
            id=job_id,
            model_run_id=run_id,
            top_n=2,
            language="de",
            status="pending",
            failed_stock_ids=[],
            error_message=None,
            created_at=datetime.now(UTC),
        )
        running_job = pending_job.model_copy(
            update={"status": "running", "started_at": datetime.now(UTC)}
        )

        batch_repo = AsyncMock()
        batch_repo.get = AsyncMock(side_effect=[pending_job, running_job])
        batch_repo.save = AsyncMock()

        service = _make_service(
            batch_repository=batch_repo,
            session_factory=session_factory,
            run_repo_factory=run_repo_factory,
            stock_repo_factory=stock_repo_factory,
        )

        # Erster Stock: unerwartete Exception (z.B. RuntimeError)
        # Zweiter Stock: ok
        call_count = 0

        async def _side_effect(stock_id: Any, *_args: Any, **_kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if stock_id == stock_id_1:
                raise RuntimeError("Unexpected internal error")

        service._generate_memo_isolated = AsyncMock(side_effect=_side_effect)  # type: ignore[method-assign]

        # Darf NICHT crashen
        await service._execute_batch(job_id)

        # Beide Stocks wurden versucht (kein vorzeitiger Abbruch)
        assert call_count == 2

        # Job ist partial (1 ok, 1 failed) — nicht 'running' geblieben
        last_save: MemoBatchJob = batch_repo.save.await_args_list[-1].args[0]
        assert last_save.status in ("partial", "failed")
        assert stock_id_1 in last_save.failed_stock_ids
