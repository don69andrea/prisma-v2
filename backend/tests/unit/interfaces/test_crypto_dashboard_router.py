"""Unit-Tests für crypto_dashboard router — TDD RED/GREEN phase.

Tests:
  - GET /{coin}/agent-audit: 200 with valid data, 404 when no row
  - GET /{coin}/ohlcv: 200 with bars, 404 for unknown coin
  - POST /{coin}/confirm: 201 for proceed and abort

All repositories and adapters are mocked via FastAPI dependency_overrides.
No real DB connection needed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Minimal FastAPI test app
# ---------------------------------------------------------------------------


def _build_test_app() -> Any:
    """Build a minimal FastAPI app with only the crypto_dashboard router."""
    from fastapi import FastAPI

    from backend.interfaces.rest.routers.crypto_dashboard import router

    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_trail_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_audit_row(audit_trail_id: uuid.UUID) -> MagicMock:
    """Simulates an AgentAuditTrailORM row with a valid agent_run JSONB."""
    row = MagicMock()
    row.id = audit_trail_id
    row.coin = "BTC"
    row.asof = date(2026, 6, 24)
    row.created_at = datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)
    row.agent_run = {
        "technical": {
            "coin": "BTC",
            "stance": "BULLISH",
            "consensus": "3/3",
            "key_signals": ["RSI oversold", "MACD crossover"],
            "confidence": 0.85,
            "reasoning": "Strong technical setup.",
        },
        "onchain": None,
        "sentiment": None,
        "macro": None,
        "bull": None,
        "bear": None,
        "risk": None,
    }
    return row


# ---------------------------------------------------------------------------
# GET /{coin}/agent-audit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_agent_audit_returns_200(
    mock_audit_row: MagicMock,
    audit_trail_id: uuid.UUID,
) -> None:
    """GET /{coin}/agent-audit returns 200 with parsed AgentAuditResponse."""
    from backend.interfaces.rest.routers.crypto_dashboard import get_audit_trail_repo

    app = _build_test_app()

    mock_repo = AsyncMock()
    mock_repo.find_latest_by_coin = AsyncMock(return_value=mock_audit_row)

    app.dependency_overrides[get_audit_trail_repo] = lambda: mock_repo

    with TestClient(app) as client:
        resp = client.get("/api/v1/crypto/BTC/agent-audit")

    assert resp.status_code == 200
    data = resp.json()
    assert data["coin"] == "BTC"
    assert data["audit_trail_id"] == str(audit_trail_id)
    assert data["agent_run"]["technical"]["stance"] == "BULLISH"


@pytest.mark.asyncio
async def test_get_agent_audit_returns_404_when_empty() -> None:
    """GET /{coin}/agent-audit returns 404 when no audit trail exists."""
    from backend.interfaces.rest.routers.crypto_dashboard import get_audit_trail_repo

    app = _build_test_app()

    mock_repo = AsyncMock()
    mock_repo.find_latest_by_coin = AsyncMock(return_value=None)

    app.dependency_overrides[get_audit_trail_repo] = lambda: mock_repo

    with TestClient(app) as client:
        resp = client.get("/api/v1/crypto/BTC/agent-audit")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /{coin}/ohlcv tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ohlcv_returns_bars() -> None:
    """GET /{coin}/ohlcv returns 200 with list of OHLCV bars for known coin."""
    from backend.interfaces.rest.routers.crypto_dashboard import get_crypto_price_adapter

    app = _build_test_app()

    # Build a stub DataFrame like CryptoPriceAdapter returns
    stub_df = pd.DataFrame(
        {
            "date": [date(2026, 6, 1), date(2026, 6, 2)],
            "open": [60000.0, 61000.0],
            "high": [61000.0, 62000.0],
            "low": [59000.0, 60000.0],
            "close": [60500.0, 61500.0],
            "volume": [1000.0, 1200.0],
        }
    )

    mock_adapter = MagicMock()
    mock_adapter.fetch_ohlcv = AsyncMock(return_value=stub_df)

    app.dependency_overrides[get_crypto_price_adapter] = lambda: mock_adapter

    with TestClient(app) as client:
        resp = client.get("/api/v1/crypto/BTC/ohlcv?days=30")

    assert resp.status_code == 200
    data = resp.json()
    assert data["coin"] == "BTC"
    assert data["symbol"] == "BTC-USD"
    assert len(data["bars"]) == 2
    assert data["bars"][0]["close"] == 60500.0


@pytest.mark.asyncio
async def test_get_ohlcv_unknown_coin_returns_404() -> None:
    """GET /{coin}/ohlcv returns 404 for a coin not in the crypto universe."""
    from backend.interfaces.rest.routers.crypto_dashboard import get_crypto_price_adapter

    app = _build_test_app()

    mock_adapter = MagicMock()
    mock_adapter.fetch_ohlcv = AsyncMock()

    app.dependency_overrides[get_crypto_price_adapter] = lambda: mock_adapter

    with TestClient(app) as client:
        resp = client.get("/api/v1/crypto/UNKNOWNCOIN/ohlcv")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /{coin}/confirm tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_hitl_persist_proceed() -> None:
    """POST /{coin}/confirm with decision=proceed returns 201 with HitlConfirmResponse."""
    from backend.interfaces.rest.routers.crypto_dashboard import get_hitl_repo

    app = _build_test_app()

    new_id = uuid.uuid4()
    audit_id = uuid.uuid4()

    mock_repo = AsyncMock()
    mock_repo.insert = AsyncMock(return_value=new_id)

    app.dependency_overrides[get_hitl_repo] = lambda: mock_repo

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/crypto/BTC/confirm",
            json={"audit_trail_id": str(audit_id), "decision": "proceed"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == str(new_id)
    assert data["decision"] == "proceed"
    assert data["coin"] == "BTC"


@pytest.mark.asyncio
async def test_confirm_hitl_persist_abort() -> None:
    """POST /{coin}/confirm with decision=abort returns 201 with HitlConfirmResponse."""
    from backend.interfaces.rest.routers.crypto_dashboard import get_hitl_repo

    app = _build_test_app()

    new_id = uuid.uuid4()
    audit_id = uuid.uuid4()

    mock_repo = AsyncMock()
    mock_repo.insert = AsyncMock(return_value=new_id)

    app.dependency_overrides[get_hitl_repo] = lambda: mock_repo

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/crypto/ETH/confirm",
            json={"audit_trail_id": str(audit_id), "decision": "abort"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["decision"] == "abort"
    assert data["coin"] == "ETH"
