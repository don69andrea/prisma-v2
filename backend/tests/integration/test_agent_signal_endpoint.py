"""Integration tests for GET /api/v1/agent-signal/{coin}.

D-06 Plan 03-06 Task 1: endpoint + DI factory tests.

Covers:
  - 200 + TradeSignal body for known coin (mocked SignalDirector)
  - 404 for unknown coin
  - 503 when SignalDirector raises an unrecoverable exception
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.domain.schemas.agent_schemas import TradeSignal
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_signal_director

pytestmark = pytest.mark.integration

# ── Fixtures ──────────────────────────────────────────────────────────────────

_AUDIT_UUID = uuid.uuid4()

_TRADE_SIGNAL = TradeSignal(
    coin="BTC-USD",
    action="BUY",
    size_factor=0.7,
    confidence=0.82,
    rationale_by_layer={
        "technical": "Strong uptrend.",
        "onchain": "Fair value.",
        "sentiment": "Neutral sentiment.",
        "macro": "Risk-on macro.",
        "bull": "Institutional adoption driving price.",
        "bear": "Regulatory risk remains.",
        "risk": "Within position limits.",
    },
    audit_trail_id=_AUDIT_UUID,
    disclaimer="Entscheidungsunterstützung, kein Anlagerat. Kein Auto-Trading.",
)


def _make_mock_director(
    return_value: TradeSignal | None = None, raises: Exception | None = None
) -> MagicMock:
    director = MagicMock()
    if raises is not None:
        director.run = AsyncMock(side_effect=raises)
    else:
        director.run = AsyncMock(return_value=return_value or _TRADE_SIGNAL)
    return director


def _make_test_client(director_override: MagicMock) -> TestClient:
    """Build a TestClient with the SignalDirector overridden."""
    from backend.config import Settings

    app = create_app()

    async def _override_director() -> MagicMock:
        return director_override

    def _override_settings() -> Settings:
        return Settings(environment="test", api_key="", anthropic_api_key="test-key")

    app.dependency_overrides[get_signal_director] = _override_director
    app.dependency_overrides[get_settings] = _override_settings

    return TestClient(app, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_get_agent_signal_known_coin_returns_200_with_trade_signal() -> None:
    """GET /api/v1/agent-signal/BTC-USD returns 200 + valid TradeSignal JSON body."""
    director = _make_mock_director()
    client = _make_test_client(director)

    response = client.get("/api/v1/agent-signal/BTC-USD")

    assert response.status_code == 200, response.text
    body = response.json()

    # Validate as TradeSignal
    signal = TradeSignal.model_validate(body)
    assert signal.coin == "BTC-USD"
    assert signal.action in ("BUY", "HOLD", "SELL")
    assert 0.0 <= signal.size_factor <= 1.5
    assert 0.0 <= signal.confidence <= 1.0
    assert signal.audit_trail_id is not None
    assert isinstance(signal.rationale_by_layer, dict)

    # Director.run was called with uppercase coin
    director.run.assert_called_once_with("BTC-USD")


def test_get_agent_signal_lowercase_coin_normalised() -> None:
    """GET /api/v1/agent-signal/btc-usd (lowercase) → uppercase → 200."""
    director = _make_mock_director()
    client = _make_test_client(director)

    response = client.get("/api/v1/agent-signal/btc-usd")

    assert response.status_code == 200, response.text
    director.run.assert_called_once_with("BTC-USD")


def test_get_agent_signal_unknown_coin_returns_404() -> None:
    """GET /api/v1/agent-signal/FOO (not in _CRYPTO_UNIVERSE) returns 404."""
    director = _make_mock_director()
    client = _make_test_client(director)

    response = client.get("/api/v1/agent-signal/FOO")

    assert response.status_code == 404, response.text
    assert "Crypto-Universe" in response.json()["detail"]
    # Director.run must NOT be called for unknown coins
    director.run.assert_not_called()


def test_get_agent_signal_llm_unavailable_returns_503() -> None:
    """When SignalDirector raises an unrecoverable exception, endpoint returns 503."""
    director = _make_mock_director(raises=RuntimeError("LLM provider unreachable"))
    client = _make_test_client(director)

    response = client.get("/api/v1/agent-signal/BTC-USD")

    assert response.status_code == 503, response.text
    assert "BTC-USD" in response.json()["detail"]
