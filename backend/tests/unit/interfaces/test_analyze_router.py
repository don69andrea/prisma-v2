from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def _make_app():
    from backend.interfaces.rest.dependencies import get_investment_director
    from backend.interfaces.rest.routers.analyze import router as analyze_router

    app = FastAPI()
    app.include_router(analyze_router, prefix="/api/v1")

    mock_director = AsyncMock()

    async def _fake_run(ticker, context, run_id, event_queue):
        await event_queue.put({"type": "step", "agent": "Director", "status": "planning"})
        await event_queue.put({"type": "done", "run_id": run_id, "signal": "BUY", "confidence": 0.7})

    mock_director.run_with_events.side_effect = _fake_run
    mock_director.resolve_checkpoint = AsyncMock(return_value=None)

    app.dependency_overrides[get_investment_director] = lambda: mock_director
    return app


def test_checkpoint_endpoint_returns_200():
    app = _make_app()
    client = TestClient(app)
    response = client.post(
        "/api/v1/analyze/checkpoint/cp_test",
        json={"answer": "3a-Konto (VIAC)"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "received"
