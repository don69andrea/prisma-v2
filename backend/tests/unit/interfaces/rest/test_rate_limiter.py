"""Tests für LLMRateLimiterMiddleware — F-PERF-1 / K-5.

_LLM_PREFIXES matchte bisher per startswith() zu breit und erfasste auch
reine GET-Lese-Endpoints unter /api/v1/stocks und /api/v1/runs, die keinen
LLM- oder Embedding-Call auslösen. Diese Tests verifizieren das Pfad-Matching
der Middleware direkt (ohne DB/Netzwerk-Abhängigkeiten):

- LLM-freie Endpoints dürfen NIE 429 erhalten, egal wie viele Requests.
- Echte LLM/Embedding-Endpoints bleiben nach _MAX_CALLS limitiert
  (Regressionsschutz).
"""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.interfaces.rest.rate_limiter import (
    _LLM_PREFIXES,
    _MAX_CALLS,
    LLMRateLimiterMiddleware,
)


def _probe_app() -> TestClient:
    """Minimal-App mit echter Middleware + Catch-All-Probe-Route.

    Die Probe-Route antwortet immer mit 200, unabhängig vom Pfad — so wird
    ausschliesslich das Pfad-Matching der Middleware getestet, nicht die
    Business-Logik der echten Router (kein DB-/LLM-Mocking nötig).
    """
    app = FastAPI()
    app.add_middleware(LLMRateLimiterMiddleware)

    @app.get("/{full_path:path}")
    async def probe(full_path: str) -> dict:  # type: ignore[type-arg]
        return {"path": full_path}

    return TestClient(app, raise_server_exceptions=False)


def _raising_app(path: str, status_code: int, detail: str) -> TestClient:
    """App deren Route eine HTTPException mit gegebenem Status wirft.

    Regressionsschutz: die Middleware darf den Status/Detail einer absichtlich
    geworfenen HTTPException (z.B. 503 bei Yahoo-Finance-Block) NICHT pauschal
    auf 500 'Interner Serverfehler.' überschreiben.
    """
    app = FastAPI()
    app.add_middleware(LLMRateLimiterMiddleware)

    @app.get(path)
    async def raiser() -> dict:  # type: ignore[type-arg]
        raise HTTPException(status_code=status_code, detail=detail)

    return TestClient(app, raise_server_exceptions=False)


def test_stocks_list_never_rate_limited() -> None:
    """GET /api/v1/stocks macht keinen LLM-Call — darf nie 429 liefern."""
    client = _probe_app()
    statuses = [client.get("/api/v1/stocks").status_code for _ in range(_MAX_CALLS + 5)]
    assert all(status == 200 for status in statuses), statuses


def test_stocks_factsheet_never_rate_limited() -> None:
    """GET /api/v1/stocks/{ticker}/factsheet macht keinen LLM-Call — darf nie 429 liefern."""
    client = _probe_app()
    statuses = [
        client.get("/api/v1/stocks/NESN/factsheet").status_code for _ in range(_MAX_CALLS + 5)
    ]
    assert all(status == 200 for status in statuses), statuses


def test_runs_list_never_rate_limited() -> None:
    """GET /api/v1/runs macht keinen LLM-Call — darf nie 429 liefern."""
    client = _probe_app()
    statuses = [client.get("/api/v1/runs").status_code for _ in range(_MAX_CALLS + 5)]
    assert all(status == 200 for status in statuses), statuses


def test_chat_endpoint_still_rate_limited_after_max_calls() -> None:
    """POST /api/v1/chat löst einen Claude-Call aus — bleibt nach _MAX_CALLS limitiert."""
    client = _probe_app()
    statuses = [client.get("/api/v1/chat").status_code for _ in range(_MAX_CALLS + 1)]
    assert statuses[:_MAX_CALLS] == [200] * _MAX_CALLS
    assert statuses[_MAX_CALLS] == 429


def test_discovery_endpoint_still_rate_limited_after_max_calls() -> None:
    """POST /api/v1/discovery/answer löst einen Claude-Call aus — bleibt limitiert."""
    client = _probe_app()
    statuses = [client.get("/api/v1/discovery/answer").status_code for _ in range(_MAX_CALLS + 1)]
    assert statuses[:_MAX_CALLS] == [200] * _MAX_CALLS
    assert statuses[_MAX_CALLS] == 429


def test_memos_generate_still_rate_limited_after_max_calls() -> None:
    """POST /api/v1/memos/generate löst einen Claude-Call aus — bleibt limitiert."""
    client = _probe_app()
    statuses = [client.get("/api/v1/memos/generate").status_code for _ in range(_MAX_CALLS + 1)]
    assert statuses[:_MAX_CALLS] == [200] * _MAX_CALLS
    assert statuses[_MAX_CALLS] == 429


def test_steuer_endpoint_still_rate_limited_after_max_calls() -> None:
    """POST /api/v1/steuer/einschaetzung nutzt einen LLM-Agenten — bleibt limitiert."""
    client = _probe_app()
    statuses = [
        client.get("/api/v1/steuer/einschaetzung").status_code for _ in range(_MAX_CALLS + 1)
    ]
    assert statuses[:_MAX_CALLS] == [200] * _MAX_CALLS
    assert statuses[_MAX_CALLS] == 429


def test_news_ingest_still_rate_limited_after_max_calls() -> None:
    """POST /api/v1/news/ingest nutzt VoyageAI-Embeddings — bleibt limitiert."""
    client = _probe_app()
    statuses = [client.get("/api/v1/news/ingest").status_code for _ in range(_MAX_CALLS + 1)]
    assert statuses[:_MAX_CALLS] == [200] * _MAX_CALLS
    assert statuses[_MAX_CALLS] == 429


def test_portfolio_allocate_still_rate_limited_after_max_calls() -> None:
    """POST /api/v1/portfolio/allocate generiert eine LLM-Narrative — bleibt limitiert."""
    client = _probe_app()
    statuses = [client.get("/api/v1/portfolio/allocate").status_code for _ in range(_MAX_CALLS + 1)]
    assert statuses[:_MAX_CALLS] == [200] * _MAX_CALLS
    assert statuses[_MAX_CALLS] == 429


def test_portfolio_monte_carlo_never_rate_limited() -> None:
    """POST /api/v1/portfolio/monte-carlo ist reine GBM-Simulation, kein LLM-Call."""
    client = _probe_app()
    statuses = [
        client.get("/api/v1/portfolio/monte-carlo").status_code for _ in range(_MAX_CALLS + 5)
    ]
    assert all(status == 200 for status in statuses), statuses


def test_llm_prefixes_no_longer_contains_bare_stocks_or_runs() -> None:
    """Regressionsschutz für die Konstante selbst: keine zu breiten Prefixe mehr."""
    assert "/api/v1/stocks" not in _LLM_PREFIXES
    assert "/api/v1/runs" not in _LLM_PREFIXES
    # bare /api/v1/portfolio (matcht auch monte-carlo) darf nicht mehr drin sein
    assert "/api/v1/portfolio" not in _LLM_PREFIXES


def test_http_exception_status_passthrough_on_llm_free_path() -> None:
    """503 aus einem LLM-freien Endpoint (z.B. Yahoo-Finance-Block) darf nicht zu 500 werden.

    Vor diesem Fix fing der `except Exception`-Block in der Middleware auch
    absichtlich geworfene HTTPExceptions und überschrieb sie pauschal mit
    500 'Interner Serverfehler.' — der echte Status (z.B. 503) und die
    Detail-Message gingen verloren.
    """
    client = _raising_app(
        "/api/v1/stocks/NESN/dividends",
        status_code=503,
        detail="Marktdaten momentan nicht verfügbar (Yahoo Finance API eingeschränkt).",
    )
    response = client.get("/api/v1/stocks/NESN/dividends")
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Marktdaten momentan nicht verfügbar (Yahoo Finance API eingeschränkt)."
    )


def test_http_exception_status_passthrough_on_llm_path() -> None:
    """Dieselbe Garantie gilt auch für Pfade unter den _LLM_PREFIXES."""
    client = _raising_app(
        "/api/v1/chat",
        status_code=404,
        detail="Nicht gefunden.",
    )
    response = client.get("/api/v1/chat")
    assert response.status_code == 404
    assert response.json()["detail"] == "Nicht gefunden."


def test_generic_exception_still_returns_500_on_llm_free_path() -> None:
    """Echte unbehandelte Exceptions (kein HTTPException) bleiben ein 500 (Regressionsschutz)."""
    app = FastAPI()
    app.add_middleware(LLMRateLimiterMiddleware)

    @app.get("/api/v1/stocks/boom")
    async def raiser() -> dict:  # type: ignore[type-arg]
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/stocks/boom")
    assert response.status_code == 500
    assert response.json()["detail"] == "Interner Serverfehler."
