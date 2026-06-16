"""Integration-Tests fuer /api/v1/memos/* via FastAPI-TestClient."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.application.services.narrative_service import NarrativeService
from backend.domain.entities.research_memo import ResearchMemo
from backend.domain.errors import BudgetCapExceeded
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_narrative_service

pytestmark = pytest.mark.integration


def _sample_memo() -> ResearchMemo:
    return ResearchMemo(
        id=uuid4(),
        stock_id=uuid4(),
        model_run_id=uuid4(),
        language="de",
        created_at=datetime.now(tz=UTC),
        one_liner="One-Liner.",
        ranking_interpretation="x" * 120,
        sweet_spot=True,
        sweet_spot_explanation="Top 25% in 4 Modellen.",
        contradictions=[],
        key_strengths=["Top 10% Quality"],
        key_risks=["Bewertungs-Multiples"],
        confidence="high",
        model_version="claude-sonnet-4-6",
    )


@pytest_asyncio.fixture
async def app_with_mock_service() -> Any:
    app = create_app()
    mock_service = AsyncMock(spec=NarrativeService)
    app.dependency_overrides[get_narrative_service] = lambda: mock_service
    yield app, mock_service
    app.dependency_overrides.clear()


def test_post_generate_returns_201_with_memo(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    memo = _sample_memo()
    mock_service.generate_memo = AsyncMock(return_value=memo)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={
                "stock_id": str(memo.stock_id),
                "model_run_id": str(memo.model_run_id),
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["one_liner"] == "One-Liner."
    assert body["is_error"] is False


def test_post_generate_returns_404_when_stock_missing(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    mock_service.generate_memo = AsyncMock(side_effect=LookupError("Stock not found"))

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={"stock_id": str(uuid4()), "model_run_id": str(uuid4())},
        )

    assert resp.status_code == 404


def test_get_memo_returns_200_when_exists(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    memo = _sample_memo()
    mock_service.get_memo = AsyncMock(return_value=memo)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/{memo.stock_id}/{memo.model_run_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == "high"


def test_get_memo_returns_404_when_missing(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    mock_service.get_memo = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/{uuid4()}/{uuid4()}")

    assert resp.status_code == 404


def test_post_generate_returns_504_on_anthropic_timeout(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    """B2 (PR #64 Deep-Review): SDK wirft APITimeoutError nach max_retries
    erschoepft. Router mappt das auf 504 Gateway Timeout, damit der Client
    'transient — retry' versteht (nicht 500 'permanent error').
    """
    import anthropic
    import httpx

    app, mock_service = app_with_mock_service
    mock_service.generate_memo = AsyncMock(
        side_effect=anthropic.APITimeoutError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={"stock_id": str(uuid4()), "model_run_id": str(uuid4())},
        )

    assert resp.status_code == 504
    assert "timeout" in resp.json()["detail"].lower()


def test_post_generate_returns_402_on_budget_cap_exceeded(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    """W2 (PR #70): BudgetCapExceeded bei /memos/generate muss 402 liefern,
    nicht 503. Globaler Handler in exception_handlers.py ist zustaendig."""
    app, mock_service = app_with_mock_service
    mock_service.generate_memo = AsyncMock(
        side_effect=BudgetCapExceeded(
            current_usd=Decimal("99.00"),
            attempted_usd=Decimal("1.00"),
            cap_usd=Decimal("100.00"),
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={"stock_id": str(uuid4()), "model_run_id": str(uuid4())},
        )

    assert resp.status_code == 402


def test_post_generate_sets_is_error_when_fallback_memo(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    app, mock_service = app_with_mock_service
    memo = _sample_memo().model_copy(
        update={
            "model_version": "error-fallback",
            "one_liner": "Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
            "confidence": "low",
            "is_error": True,  # Router liest is_error direkt (#67)
        }
    )
    mock_service.generate_memo = AsyncMock(return_value=memo)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/memos/generate",
            json={"stock_id": str(memo.stock_id), "model_run_id": str(memo.model_run_id)},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_error"] is True


def test_get_memo_is_error_true_for_explicit_flag_without_sentinel(
    app_with_mock_service: tuple[Any, AsyncMock],
) -> None:
    """Router liest memo.is_error direkt — kein String-Match, kein
    model_version-Inferieren (#67).

    Edge-Case: memo mit normalem model_version aber is_error=True muss
    von der API als is_error=True zurueckkommen.
    """
    app, mock_service = app_with_mock_service
    memo = _sample_memo().model_copy(
        update={
            "model_version": "claude-sonnet-4-6",  # NICHT der Sentinel
            "one_liner": "Ein normaler Memo-Titel ohne Error-Wording",
            "is_error": True,  # nur das Flag gesetzt
        }
    )
    mock_service.get_memo = AsyncMock(return_value=memo)

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/memos/{memo.stock_id}/{memo.model_run_id}")

    assert resp.status_code == 200
    assert resp.json()["is_error"] is True
