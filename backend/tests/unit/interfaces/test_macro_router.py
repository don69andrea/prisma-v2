"""Unit-Tests für GET /api/v1/macro/score/{ticker}."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.application.agents.macro_agent import MacroIntelligenceAgent, MacroScore
from backend.application.services.macro_service import MacroService
from backend.application.services.retrieval_service import RetrievalService
from backend.config import Settings, get_settings
from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.value_objects.macro_context import MacroContext
from backend.interfaces.rest.dependencies import (
    get_llm_client,
    get_retrieval_service,
    get_swiss_stock_repository,
)
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
    monkeypatch: pytest.MonkeyPatch,
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

    # Patch MacroIntelligenceAgent.get_macro_score im Modul (via monkeypatch, damit der
    # Patch nach dem Test automatisch zurückgesetzt wird und nicht in andere Tests
    # — z.B. test_score_differs_by_sector_for_unrecognized_tickers — durchsickert).
    original_init = MacroIntelligenceAgent.__init__

    def _patched_init(self: MacroIntelligenceAgent, macro_service: MacroService) -> None:
        original_init(self, macro_service)
        self.get_macro_score = AsyncMock(return_value=macro_score)  # type: ignore[method-assign]

    monkeypatch.setattr(MacroIntelligenceAgent, "__init__", _patched_init)

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

    # Stock-Repository mocken (Sektor-Lookup ist hier irrelevant, da get_macro_score
    # selbst gepatcht ist — aber der Router ruft get_by_ticker in jedem Fall auf).
    mock_stock_repo = AsyncMock()
    mock_stock_repo.get_by_ticker.return_value = None

    async def _mock_get_stock_repo() -> object:
        return mock_stock_repo

    app.dependency_overrides[get_swiss_stock_repository] = _mock_get_stock_repo

    return app, TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_score_endpoint_returns_http_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Score-Endpoint gibt HTTP 200 für bekannten Ticker zurück."""
    _, client = _build_test_app(monkeypatch)
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200


def test_score_is_between_0_and_100(monkeypatch: pytest.MonkeyPatch) -> None:
    """Score liegt im Bereich 0–100."""
    _, client = _build_test_app(monkeypatch)
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    data = response.json()
    assert 0.0 <= data["score"] <= 100.0


def test_unknown_ticker_returns_200_not_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unbekannter Ticker liefert 200 (nicht 404), da MacroAgent rule-based ist."""
    _, client = _build_test_app(monkeypatch, macro_score=_UNKNOWN_TICKER_SCORE)
    response = client.get("/api/v1/macro/score/UNKNOWN.SW")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "UNKNOWN.SW"


def test_score_response_contains_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Response enthält alle Pflichtfelder des MacroScoreResponse-Schemas."""
    _, client = _build_test_app(monkeypatch)
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    data = response.json()
    for field in ("ticker", "score", "leitzins", "chf_eur", "climate", "rag_context_used"):
        assert field in data, f"Pflichtfeld '{field}' fehlt in der Antwort"


def test_rag_context_used_true_when_results_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """rag_context_used ist True wenn RAG Dokumente liefert."""
    from backend.domain.entities.retrieval_result import RetrievalResult

    mock_result = MagicMock(spec=RetrievalResult)
    _, client = _build_test_app(monkeypatch, rag_results=[mock_result])
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    assert response.json()["rag_context_used"] is True


def test_rag_context_used_false_on_rag_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """rag_context_used ist False bei RAG-Fehler (graceful fallback)."""
    _, client = _build_test_app(monkeypatch, rag_raises=True)
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    assert response.json()["rag_context_used"] is False


def test_rag_context_used_false_when_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """rag_context_used ist False wenn RAG keine Dokumente findet."""
    _, client = _build_test_app(monkeypatch, rag_results=[])
    response = client.get("/api/v1/macro/score/NESN.SW")
    assert response.status_code == 200
    assert response.json()["rag_context_used"] is False


# ---------------------------------------------------------------------------
# F-MACRO-1 (Audit W-10): Sektor-Hint muss tatsächlich an den Agent
# durchgereicht werden, sonst ist der Export-Sektor-Bonus für jeden Ticker
# identisch (Endpoint behauptet "basierend auf ... Exportprofil").
# ---------------------------------------------------------------------------


def _build_e2e_test_app(sector_by_ticker: dict[str, str | None]) -> tuple[FastAPI, TestClient]:
    """Baut eine Testapp, die die ECHTE MacroIntelligenceAgent-Logik durchläuft.

    Im Gegensatz zu `_build_test_app` wird `get_macro_score` NICHT gemockt —
    nur `MacroService.get_context` und das Stock-Repository. So wird
    sichtbar, ob der Router den Sektor tatsächlich an den Agent weitergibt.
    """
    app = FastAPI()
    app.include_router(router)

    settings = Settings(
        database_url="postgresql+asyncpg://x:x@x/x",
        environment="test",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    ctx = MacroContext(
        leitzins=0.25,
        chf_eur=0.97,  # starker CHF -> Export-Sektor-Bonus/-Malus greift sichtbar
        inflation_ch=None,
        pmi_ch=None,
        snapshot_date=date(2026, 6, 11),
        climate="NEUTRAL",
        narrative_de="Test DE",
        narrative_en="Test EN",
    )
    mock_macro_service = MagicMock(spec=MacroService)
    mock_macro_service.get_context = AsyncMock(return_value=ctx)

    async def _mock_get_macro_service() -> MacroService:
        return mock_macro_service

    app.dependency_overrides[get_macro_service] = _mock_get_macro_service

    def _make_repo() -> AsyncMock:
        repo = AsyncMock()

        async def _get_by_ticker(ticker: str) -> SwissStock | None:
            sector = sector_by_ticker.get(ticker.upper())
            return SwissStock(
                id=__import__("uuid").uuid4(),
                ticker=ticker.upper(),
                isin="CH0012032048",
                name=ticker,
                exchange="XSWX",
                sector=sector,
                market_cap_chf=None,
            )

        repo.get_by_ticker.side_effect = _get_by_ticker
        return repo

    mock_repo = _make_repo()

    async def _mock_get_repo() -> object:
        return mock_repo

    app.dependency_overrides[get_swiss_stock_repository] = _mock_get_repo

    mock_retrieval = AsyncMock(spec=RetrievalService)
    mock_retrieval.retrieve.return_value = []

    async def _mock_get_retrieval() -> RetrievalService:
        return mock_retrieval

    app.dependency_overrides[get_retrieval_service] = _mock_get_retrieval
    app.dependency_overrides[get_llm_client] = AsyncMock()

    return app, TestClient(app, raise_server_exceptions=False)


def test_score_differs_by_sector_for_unrecognized_tickers() -> None:
    """Zwei Ticker (nicht in _EXPORT_HEAVY/_DOMESTIC_FOCUS) mit unterschiedlichem
    Sektor müssen unterschiedliche Scores erhalten, sobald CHF stark ist —
    nur einer der beiden Sektoren liegt in _EXPORT_SECTORS.
    """
    _, client = _build_e2e_test_app(
        {
            "PHCO.SW": "pharma",  # in _EXPORT_SECTORS -> Export-Malus bei starkem CHF
            "BNKX.SW": "banking",  # NICHT in _EXPORT_SECTORS -> kein Malus
        }
    )

    resp_pharma = client.get("/api/v1/macro/score/PHCO.SW")
    resp_banking = client.get("/api/v1/macro/score/BNKX.SW")

    assert resp_pharma.status_code == 200
    assert resp_banking.status_code == 200

    score_pharma = resp_pharma.json()["score"]
    score_banking = resp_banking.json()["score"]

    assert score_pharma != score_banking, (
        "Pharma-Ticker (Export-Sektor) und Banking-Ticker müssen bei starkem CHF "
        "unterschiedliche Makro-Scores erhalten — der sector-Hint muss an "
        "get_macro_score durchgereicht werden."
    )
