"""Unit-Tests für GET /api/v1/macro/score/{ticker}."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.application.agents.macro_agent import MacroIntelligenceAgent, MacroScore
from backend.application.services.macro_service import MacroService
from backend.application.services.retrieval_service import RetrievalService
from backend.config import Settings, get_settings
from backend.interfaces.rest.dependencies import get_llm_client, get_retrieval_service
from backend.interfaces.rest.routers.macro import get_macro_service, router

# ---------------------------------------------------------------------------
# Test-Fixtures
# ---------------------------------------------------------------------------

_DEFAULT_MACRO_SCORE = MacroScore(
    ticker="NESN.SW",
    score=65.0,
    leitzins=0.25,
    chf_eur=0.93,
    climate="NEUTRAL",
    chf_impact="NEGATIV",
    reasoning="Tiefer Leitzins (0.25%) — akkommodativ | Starker CHF (0.9400/EUR) belastet Exportumsätze",
)

_UNKNOWN_TICKER_SCORE = MacroScore(
    ticker="UNKNOWN.SW",
    score=55.0,
    leitzins=0.25,
    chf_eur=0.93,
    climate="NEUTRAL",
    chf_impact="NEUTRAL",
    reasoning="Tiefer Leitzins (0.25%) — akkommodativ | CHF im Gleichgewicht (0.9300/EUR)",
)


def _build_test_app(
    macro_score: MacroScore = _DEFAULT_MACRO_SCORE,
    rag_results: list[object] | None = None,
    rag_raises: bool = False,
) -> tuple[FastAPI, TestClient]:
    """Erstellt eine isolierte FastAPI-Testapp mit gemockten Services."""
    app = FastAPI()
    app.include_router(router)

    settings = Settings(
        database_url="postgresql+asyncpg://x:x@x/x",
        environment="test",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    # Mock MacroService → MacroIntelligenceAgent.get_macro_score gibt fixen Score zurück
    mock_macro_service = MagicMock(spec=MacroService)

    async def _mock_get_macro_service() -> MacroService:
        return mock_macro_service

    app.dependency_overrides[get_macro_service] = _mock_get_macro_service

    # Patch MacroIntelligenceAgent.get_macro_score im Modul
    original_init = MacroIntelligenceAgent.__init__

    def _patched_init(self: MacroIntelligenceAgent, macro_service: MacroService) -> None:
        original_init(self, macro_service)
        self.get_macro_score = AsyncMock(return_value=macro_score)  # type: ignore[method-assign]

    MacroIntelligenceAgent.__init__ = _patched_init  # type: ignore[method-assign]

    # Mock RetrievalService
    mock_retrieval = AsyncMock(spec=RetrievalService)
    if rag_raises:
        mock_retrieval.retrieve.side_effect = RuntimeError("RAG unavailable")
    else:
        mock_retrieval.retrieve.return_value = rag_results if rag_results is not None else []

    async def _mock_get_retrieval() -> RetrievalService:
        return mock_retrieval

    app.dependency_overrides[get_retrieval_service] = _mock_get_retrieval
    app.dependency_overrides[get_llm_client] = AsyncMock()

    return app, TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_score_endpoint_returns_http_200() -> None:
    """Score-Endpoint gibt HTTP 200 für bekannten Ticker zurück."""
    _, client = _build_test_app()
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200


def test_score_is_between_0_and_100() -> None:
    """Score liegt im Bereich 0–100."""
    _, client = _build_test_app()
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    data = response.json()
    assert 0.0 <= data["score"] <= 100.0


def test_unknown_ticker_returns_200_not_404() -> None:
    """Unbekannter Ticker liefert 200 (nicht 404), da MacroAgent rule-based ist."""
    _, client = _build_test_app(macro_score=_UNKNOWN_TICKER_SCORE)
    response = client.get("/api/v1/macro/score/UNKNOWN.SW")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "UNKNOWN.SW"


def test_score_response_contains_required_fields() -> None:
    """Response enthält alle Pflichtfelder des MacroScoreResponse-Schemas."""
    _, client = _build_test_app()
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    data = response.json()
    for field in ("ticker", "score", "leitzins", "chf_eur", "climate", "rag_context_used"):
        assert field in data, f"Pflichtfeld '{field}' fehlt in der Antwort"


def test_rag_context_used_true_when_results_available() -> None:
    """rag_context_used ist True wenn RAG Dokumente liefert."""
    from backend.domain.entities.retrieval_result import RetrievalResult

    mock_result = MagicMock(spec=RetrievalResult)
    _, client = _build_test_app(rag_results=[mock_result])
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    assert response.json()["rag_context_used"] is True


def test_rag_context_used_false_on_rag_error() -> None:
    """rag_context_used ist False bei RAG-Fehler (graceful fallback)."""
    _, client = _build_test_app(rag_raises=True)
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    assert response.json()["rag_context_used"] is False


def test_rag_context_used_false_when_no_results() -> None:
    """rag_context_used ist False wenn RAG keine Dokumente findet."""
    _, client = _build_test_app(rag_results=[])
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    assert response.json()["rag_context_used"] is False
