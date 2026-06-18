from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.domain.schemas.multiagent_schemas import CointelligenceReport

pytestmark = pytest.mark.unit

_MOCK_REPORT = CointelligenceReport(
    coin="BTC",
    price_chf=88000.0,
    mvrv_zone="FAIR",
    fear_greed=50,
    sharpe_crypto=0.8,
    sharpe_smi=0.5,
    chf_usd_impact="NEUTRAL",
    regime_signal="HOLD",
    max_allocation_pct=5.0,
    reasoning="Fair bewertet.",
    disclaimer="Hochspekulative Anlage.",
)


def _make_app() -> FastAPI:
    from backend.interfaces.rest.dependencies import get_cointelligence_agent
    from backend.interfaces.rest.routers.crypto import router as crypto_router

    app = FastAPI()
    app.include_router(crypto_router)
    mock_agent = AsyncMock()
    mock_agent.analyze.return_value = _MOCK_REPORT
    app.dependency_overrides[get_cointelligence_agent] = lambda: mock_agent
    return app


def test_cointelligence_btc_returns_report():
    app = _make_app()
    client = TestClient(app)
    response = client.post("/api/v1/crypto/intelligence", json={"coin": "BTC"})
    assert response.status_code == 200
    data = response.json()
    assert data["coin"] == "BTC"
    assert data["regime_signal"] == "HOLD"
    assert data["max_allocation_pct"] <= 10.0
