"""Integration-Tests fuer /api/v1/memos/batch + /api/v1/memos/jobs/{id}.

Spec: docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md §6.
Alle Tests nutzen dependency_overrides — kein DB-Zugriff, kein LLM-Call.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.memo_batch_job import MemoBatchJob
from backend.domain.errors import BudgetCapExceeded
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_narrative_service

pytestmark = pytest.mark.integration


def _make_pending_job(
    run_id: UUID | None = None,
    expected_stock_ids: list[UUID] | None = None,
) -> MemoBatchJob:
    return MemoBatchJob(
        id=uuid4(),
        model_run_id=run_id or uuid4(),
        top_n=20,
        language="de",
        status="pending",
        failed_stock_ids=[],
        expected_stock_ids=expected_stock_ids or [],
        error_message=None,
        created_at=datetime.now(UTC),
    )


@pytest_asyncio.fixture
async def app_with_mock_service() -> Any:
    app = create_app()
    mock_service = AsyncMock(spec=NarrativeService)
    app.dependency_overrides[get_narrative_service] = lambda: mock_service
    yield app, mock_service
    app.dependency_overrides.clear()


def test_post_batch_returns_202(app_with_mock_service: Any) -> None:
    app, service = app_with_mock_service
    job = _make_pending_job()
    service.start_batch = AsyncMock(return_value=job)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/batch",
            json={"model_run_id": str(job.model_run_id), "top_n": 20},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert UUID(body["job_id"]) == job.id


def test_post_batch_returns_404_run_missing(app_with_mock_service: Any) -> None:
    app, service = app_with_mock_service
    service.start_batch = AsyncMock(side_effect=LookupError("Run x not found"))

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/batch",
            json={"model_run_id": str(uuid4()), "top_n": 20},
        )

    assert resp.status_code == 404


def test_post_batch_returns_402_budget_exceeded(app_with_mock_service: Any) -> None:
    """W2 (PR #70): BudgetCapExceeded propagiert NICHT mehr per-route, sondern
    durch den globalen Handler — der liefert 402 plus strukturierten Body und
    `Retry-After`-Header. Test prueft beide Aspekte um sicherzustellen, dass
    der globale Handler tatsaechlich aktiv ist (nicht ein vergessener
    per-route-Catch).
    """
    app, service = app_with_mock_service
    service.start_batch = AsyncMock(
        side_effect=BudgetCapExceeded(
            current_usd=Decimal("19.00"),
            attempted_usd=Decimal("0.50"),
            cap_usd=Decimal("20.00"),
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/batch",
            json={"model_run_id": str(uuid4()), "top_n": 20},
        )

    assert resp.status_code == 402
    # Globaler Handler-Fingerabdruck: strukturierter Body (kein simpler HTTPException-detail-Wrap)
    body = resp.json()
    assert body["error"] == "budget_cap_exceeded"
    assert body["current_usd"] == 19.00
    assert body["cap_usd"] == 20.00
    # Retry-After-Header signalisiert dem Client wann das Cap zurueckgesetzt wird
    retry_after = resp.headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) > 0


def test_post_batch_returns_422_on_value_error(app_with_mock_service: Any) -> None:
    """F4: Wenn start_batch ValueError wirft, muss 422 zurückkommen statt 500."""
    app, service = app_with_mock_service
    service.start_batch = AsyncMock(side_effect=ValueError("top_n must be 1..100, got 0"))

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/batch",
            json={"model_run_id": str(uuid4()), "top_n": 20},
        )

    assert resp.status_code == 422
    assert "top_n" in resp.json().get("detail", "").lower()


def test_get_job_returns_404_unknown(app_with_mock_service: Any) -> None:
    app, service = app_with_mock_service
    service.get_batch_job = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{uuid4()}")

    assert resp.status_code == 404


def test_get_job_returns_status_and_progress(app_with_mock_service: Any) -> None:
    app, service = app_with_mock_service
    job = _make_pending_job()
    job_running = job.model_copy(update={"status": "running", "started_at": datetime.now(UTC)})
    service.get_batch_job = AsyncMock(return_value=job_running)
    service.list_memos_for_run = AsyncMock(return_value=[])
    service.get_stock_ticker_map = AsyncMock(return_value={})

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{job.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["progress"]["expected"] == 20
    assert body["progress"]["completed"] == 0
    assert body["progress"]["failed"] == 0


def test_get_job_progress_excludes_preexisting_memos(app_with_mock_service: Any) -> None:
    """F1: progress.completed darf nicht durch Memos aus früheren Batches aufgebläht werden.

    Szenario: Job top_n=3, status=complete, failed=0.
    list_memos_for_run liefert 5 Memos (2 aus einem vorherigen Single-Memo-Call).
    Erwartet: completed=3 (= top_n - failed), nicht 5.
    """
    app, service = app_with_mock_service
    run_id = uuid4()
    job = MemoBatchJob(
        id=uuid4(),
        model_run_id=run_id,
        top_n=3,
        language="de",
        status="complete",
        failed_stock_ids=[],
        error_message=None,
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    service.get_batch_job = AsyncMock(return_value=job)
    # 5 Memos — 2 davon aus früheren Single-Memo-Calls (nicht von diesem Batch)
    mock_memos = [
        AsyncMock(stock_id=uuid4(), one_liner=f"memo {i}", model_version="claude-sonnet-4-6")
        for i in range(5)
    ]
    service.list_memos_for_run = AsyncMock(return_value=mock_memos)
    service.get_stock_ticker_map = AsyncMock(return_value={})

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{job.id}")

    assert resp.status_code == 200
    body = resp.json()
    # completed muss 3 sein (top_n=3 - failed=0), nicht 5
    assert body["progress"]["completed"] == 3
    assert body["progress"]["expected"] == 3
    assert body["progress"]["failed"] == 0


def test_get_job_progress_running_uses_live_memo_count(app_with_mock_service: Any) -> None:
    """F1: Während running zeigt completed=len(memos) als Live-Progress-Indikator."""
    app, service = app_with_mock_service
    job = MemoBatchJob(
        id=uuid4(),
        model_run_id=uuid4(),
        top_n=10,
        language="de",
        status="running",
        failed_stock_ids=[],
        error_message=None,
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
    )
    service.get_batch_job = AsyncMock(return_value=job)
    live_memos = [
        AsyncMock(stock_id=uuid4(), one_liner=f"memo {i}", model_version="claude-sonnet-4-6")
        for i in range(4)
    ]
    service.list_memos_for_run = AsyncMock(return_value=live_memos)
    service.get_stock_ticker_map = AsyncMock(return_value={})

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{job.id}")

    assert resp.status_code == 200
    # Live-Count während running: len(memos) == 4
    assert resp.json()["progress"]["completed"] == 4


def test_get_job_progress_partial_uses_successes(app_with_mock_service: Any) -> None:
    """F1: Bei partial-Status: completed = top_n - failed."""
    app, service = app_with_mock_service
    failed_ids = [uuid4(), uuid4()]
    job = MemoBatchJob(
        id=uuid4(),
        model_run_id=uuid4(),
        top_n=5,
        language="de",
        status="partial",
        failed_stock_ids=failed_ids,
        error_message=None,
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    service.get_batch_job = AsyncMock(return_value=job)
    mock_memos = [
        AsyncMock(stock_id=uuid4(), one_liner=f"m{i}", model_version="claude-sonnet-4-6")
        for i in range(3)
    ]
    service.list_memos_for_run = AsyncMock(return_value=mock_memos)
    service.get_stock_ticker_map = AsyncMock(return_value={})

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{job.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["progress"]["completed"] == 3  # top_n(5) - failed(2)
    assert body["progress"]["failed"] == 2


def test_get_job_passes_expected_stock_ids_as_filter(app_with_mock_service: Any) -> None:
    """Issue #86: Router muss expected_stock_ids als stock_ids-Filter an
    list_memos_for_run uebergeben, damit job-fremde Memos ausgefiltert werden.
    """
    app, service = app_with_mock_service
    stock_a, stock_b, stock_c = uuid4(), uuid4(), uuid4()
    job = MemoBatchJob(
        id=uuid4(),
        model_run_id=uuid4(),
        top_n=3,
        language="de",
        status="running",
        failed_stock_ids=[],
        expected_stock_ids=[stock_a, stock_b, stock_c],
        error_message=None,
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
    )
    service.get_batch_job = AsyncMock(return_value=job)
    filtered_memos = [
        AsyncMock(stock_id=sid, one_liner=f"memo {i}", model_version="claude-sonnet-4-6")
        for i, sid in enumerate([stock_a, stock_b, stock_c])
    ]
    service.list_memos_for_run = AsyncMock(return_value=filtered_memos)
    service.get_stock_ticker_map = AsyncMock(return_value={})

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/jobs/{job.id}")

    assert resp.status_code == 200
    # Router muss stock_ids=[stock_a, stock_b, stock_c] uebergeben haben
    call_kwargs = service.list_memos_for_run.call_args.kwargs
    assert set(call_kwargs.get("stock_ids", [])) == {stock_a, stock_b, stock_c}
    # Response zeigt nur die 3 gefilterten Memos
    body = resp.json()
    assert body["progress"]["completed"] == 3
    assert len(body["memos"]) == 3
