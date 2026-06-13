# MCP-Server Slice 1 — Implementation Plan

> **For agentic workers:** Implementiere diesen Plan Schritt für Schritt. Schritte nutzen Checkbox-Syntax (`- [ ]`) zum Tracking.

**Goal:** MCP-Server-Skeleton via STDIO mit erstem Tool `run_ranking`, das `POST /api/v1/runs` aufruft. Opt-in X-API-Key-Auth, vollstaendiges Error-Mapping fuer alle 5 Master-Spec-Typen, Integration-Tests via FastAPI-TestClient.

**Architektur:** `backend/interfaces/mcp/` mit FastMCP-Entry-Point, httpx-REST-Client, Error-Mapping-Modul, Tool-Handlern in `tools/`. Tool-Funktionen pure (testbar mit Mock-Client). FastMCP-Decorator nur im `server.py` Entry-Point.

**Tech Stack:** `mcp>=1.2`, `httpx>=0.27` (schon vorhanden), `pytest-asyncio`, FastAPI-TestClient.

**Reality-Check-Drifts gegen Spec (Plan-Phase confirmed):**
- `RunResponse` schema hat kein `universe_name`, kein `name`-Lookup ueber Tickers — MCP-Tool-Output reduziert auf vorhandene Felder
- REST-Schema-Feld heisst `weight_config`, nicht `weights` — Mapping im Tool
- `RankingItem.is_sweet_spot` (REST) → `sweet_spot` (MCP-Output) per Master-Spec-§4.1
- `tool_api_key` ist separates Settings-Feld neben bestehendem `api_key` (Admin-Auth)

---

## File Structure

| Datei | Typ | Verantwortung |
|---|---|---|
| `pyproject.toml` | MODIFY | `mcp>=1.2` Dep adden |
| `backend/config.py` | MODIFY | `tool_api_key: str = ""` ergaenzen |
| `backend/interfaces/rest/dependencies.py` | MODIFY | `require_api_key` neben `require_admin_api_key` |
| `backend/interfaces/rest/routers/runs.py` | MODIFY | `POST /runs` mit opt-in `Depends(require_api_key)` |
| `backend/interfaces/mcp/__init__.py` | CREATE | empty |
| `backend/interfaces/mcp/errors.py` | CREATE | `MCPError` + `raise_mcp_error_for_response` + Network-Error-Wrapper |
| `backend/interfaces/mcp/rest_client.py` | CREATE | async httpx-Wrapper mit X-API-Key + Error-Raising |
| `backend/interfaces/mcp/tools/__init__.py` | CREATE | empty |
| `backend/interfaces/mcp/tools/run_ranking.py` | CREATE | Tool-Handler-Funktion (pure, klient-injiziert) |
| `backend/interfaces/mcp/server.py` | CREATE | FastMCP-Entry-Point, Global-Client-Setup, Tool-Decorator |
| `backend/tests/unit/interfaces/mcp/__init__.py` | CREATE | empty |
| `backend/tests/unit/interfaces/mcp/test_errors.py` | CREATE | 5-Typen-Mapping-Tests |
| `backend/tests/unit/interfaces/mcp/test_rest_client.py` | CREATE | httpx-Mock + Header + Error-Raising |
| `backend/tests/unit/interfaces/mcp/tools/__init__.py` | CREATE | empty |
| `backend/tests/unit/interfaces/mcp/tools/test_run_ranking.py` | CREATE | Tool-Logik + Weight-Validation + Mapping |
| `backend/tests/unit/interfaces/rest/test_require_api_key.py` | CREATE | Auth-Dependency-Tests |
| `backend/tests/integration/test_mcp_run_ranking.py` | CREATE | E2E happy + 404 + 401 |
| `docs/AI-USAGE.md` | MODIFY | Slice-1-Eintrag |

---

## Task 1: Dependencies + Settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/config.py`
- Test: `backend/tests/unit/test_config.py` (existing — falls da)

- [ ] **Step 1.1: `mcp` dep adden**

Edit `pyproject.toml` dependencies-Liste (alphabetisch nach `mcp` einsortieren):

```toml
    "mcp>=1.2",
```

- [ ] **Step 1.2: Install + verify**

```bash
source .venv/bin/activate
uv pip install -e .
python -c "from mcp.server.fastmcp import FastMCP; print(FastMCP.__module__)"
```

Expected: `mcp.server.fastmcp` (kein ImportError)

- [ ] **Step 1.3: `tool_api_key`-Field in Settings**

Edit `backend/config.py` nach Zeile 39 (`api_key`-Block):

```python
    # Tool-API-Key fuer MCP-Server-Calls auf /api/v1/runs. Getrennt vom
    # Admin-Key (`api_key`), damit Tool-Auth unabhaengig rotiert werden
    # kann. Leer = opt-in disabled, kein Auth-Enforcement.
    tool_api_key: str = ""
```

- [ ] **Step 1.4: Commit**

```bash
git add pyproject.toml backend/config.py
git commit -m "feat(deps): mcp>=1.2 + tool_api_key-Settings-Feld (Slice 1 Task 1)"
```

---

## Task 2: `require_api_key` Auth-Dependency

**Files:**
- Modify: `backend/interfaces/rest/dependencies.py`
- Create: `backend/tests/unit/interfaces/rest/test_require_api_key.py`

- [ ] **Step 2.1: Write failing test**

Create `backend/tests/unit/interfaces/rest/test_require_api_key.py`:

```python
"""Tests fuer require_api_key — opt-in Auth-Dependency fuer MCP-Tool-Endpoints."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.interfaces.rest.dependencies import get_settings, require_api_key

pytestmark = pytest.mark.unit


def _make_app(*, tool_api_key: str = "") -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def protected(_auth: None = Depends(require_api_key)) -> dict:
        return {"ok": True}

    app.dependency_overrides[get_settings] = lambda: Settings(tool_api_key=tool_api_key)
    return app


class TestRequireApiKey:
    def test_disabled_when_tool_api_key_empty(self) -> None:
        """Default-off: leerer tool_api_key in Settings → keine Auth-Pruefung."""
        app = _make_app(tool_api_key="")
        with TestClient(app) as client:
            response = client.get("/protected")
        assert response.status_code == 200

    def test_rejects_missing_header_when_key_configured(self) -> None:
        app = _make_app(tool_api_key="secret-tool-key")
        with TestClient(app) as client:
            response = client.get("/protected")
        assert response.status_code == 401

    def test_rejects_wrong_header_when_key_configured(self) -> None:
        app = _make_app(tool_api_key="secret-tool-key")
        with TestClient(app) as client:
            response = client.get("/protected", headers={"X-API-Key": "wrong"})
        assert response.status_code == 401

    def test_accepts_correct_header(self) -> None:
        app = _make_app(tool_api_key="secret-tool-key")
        with TestClient(app) as client:
            response = client.get("/protected", headers={"X-API-Key": "secret-tool-key"})
        assert response.status_code == 200
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
pytest backend/tests/unit/interfaces/rest/test_require_api_key.py -v
```

Expected: 4 failures with `ImportError: cannot import name 'require_api_key'`

- [ ] **Step 2.3: Implement `require_api_key`**

Edit `backend/interfaces/rest/dependencies.py` — nach `require_admin_api_key` ergaenzen:

```python
async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Opt-in Tool-Auth: prueft X-API-Key gegen Settings.tool_api_key.

    Default-off: wenn `tool_api_key` leer (Default), wird kein Header
    geprueft — bestehende Aufrufer brechen nicht. Sobald die Env-Var
    `PRISMA_TOOL_API_KEY` gesetzt ist, ist Auth aktiv.

    Konstant-zeitsicher (hmac.compare_digest), gleiche Mechanik wie
    require_admin_api_key. Getrennter Key fuer separate Rotation
    (Spec §6 + §10.4 MCP-Server-Slice-1).
    """
    if not settings.tool_api_key:
        return  # opt-in disabled
    if x_api_key is None or not hmac.compare_digest(x_api_key, settings.tool_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
pytest backend/tests/unit/interfaces/rest/test_require_api_key.py -v
```

Expected: 4/4 passed.

- [ ] **Step 2.5: Commit**

```bash
git add backend/interfaces/rest/dependencies.py backend/tests/unit/interfaces/rest/test_require_api_key.py
git commit -m "feat(rest): require_api_key opt-in Dependency fuer MCP-Tool-Endpoints (Slice 1 Task 2)"
```

---

## Task 3: Apply `require_api_key` on POST /runs

**Files:**
- Modify: `backend/interfaces/rest/routers/runs.py`
- Existing-Test-Check: `backend/tests/integration/test_runs_router.py` oder aehnlich — bleibt gruen wenn `tool_api_key` leer

- [ ] **Step 3.1: Identify existing run-tests**

```bash
grep -rln "POST.*runs\|post.*runs\|test_post_run\|test_runs" backend/tests/ | head -5
```

Falls Tests existieren mit explizitem `tool_api_key`-Setting: pruefen ob sie noch gruen sind nach Task 3. Im opt-in-Default-off-Modell sollten sie unveraendert laufen.

- [ ] **Step 3.2: Add dependency to POST /runs**

Edit `backend/interfaces/rest/routers/runs.py`, line 18-22:

```python
@router.post("", status_code=201, response_model=RunResponse)
async def post_run(
    request: PostRunRequest,
    service: RankingRunService = Depends(get_ranking_run_service),
    _auth: None = Depends(require_api_key),
) -> RunResponse:
```

Import-Block oben ergaenzen:

```python
from backend.interfaces.rest.dependencies import get_ranking_run_service, require_api_key
```

- [ ] **Step 3.3: Run existing run-tests**

```bash
pytest backend/tests/integration/test_runs_router.py -v 2>&1 | tail -20
```

Falls keine Tests existieren: bei der naechsten Suite-Run beobachten. Erwartung: 0 regressions (opt-in default-off).

- [ ] **Step 3.4: Add explicit test for opt-in-off behaviour**

Bestehende Test-Datei `backend/tests/integration/test_runs_endpoint.py` nutzt
`http_client`-Fixture-Pattern (httpx.AsyncClient + ASGITransport, KEIN
sync TestClient). Wir folgen dem Pattern und ergaenzen Auth-Tests:

```python
# Am Anfang der Datei zu den existing imports ergaenzen (falls nicht da)
from backend.config import Settings
from backend.interfaces.rest.dependencies import get_settings


@pytest_asyncio.fixture
async def http_client_with_tool_key() -> AsyncGenerator[AsyncClient, None]:
    """Variant der http_client-Fixture mit tool_api_key gesetzt (Auth aktiv)."""
    universe_repo = InMemoryUniverseRepository()
    await universe_repo.save(_DEMO_UNIVERSE)
    run_repo = InMemoryRankingRunRepository()
    fundamentals_provider = StubFundamentalsProvider()

    app = create_app()
    app.dependency_overrides[get_universe_repository] = lambda: universe_repo
    app.dependency_overrides[get_ranking_run_repository] = lambda: run_repo
    app.dependency_overrides[get_fundamentals_provider] = lambda: fundamentals_provider
    app.dependency_overrides[get_settings] = lambda: Settings(tool_api_key="t-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestPostRunsAuth:
    async def test_post_run_accepts_without_header_when_tool_key_unset(
        self, http_client: AsyncClient
    ) -> None:
        """Opt-in default-off: leerer tool_api_key → POST /runs ohne Header geht durch."""
        response = await http_client.post(
            "/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE.id)}
        )
        # 201 (oder 200) erwartet — definitiv NICHT 401
        assert response.status_code != 401

    async def test_post_run_rejects_without_header_when_tool_key_set(
        self, http_client_with_tool_key: AsyncClient
    ) -> None:
        response = await http_client_with_tool_key.post(
            "/api/v1/runs", json={"universe_id": str(_DEMO_UNIVERSE.id)}
        )
        assert response.status_code == 401

    async def test_post_run_accepts_correct_header_when_tool_key_set(
        self, http_client_with_tool_key: AsyncClient
    ) -> None:
        response = await http_client_with_tool_key.post(
            "/api/v1/runs",
            json={"universe_id": str(_DEMO_UNIVERSE.id)},
            headers={"X-API-Key": "t-secret"},
        )
        assert response.status_code != 401
```

**Why this pattern, not TestClient:** Projekt-Konvention in
`test_runs_endpoint.py` ist `httpx.AsyncClient + ASGITransport`. `_DEMO_UNIVERSE`,
`InMemory*Repositories` und die Repo-Fixtures sind bereits in der Datei
definiert — wir wiederverwenden sie.

- [ ] **Step 3.5: Run tests**

```bash
pytest backend/tests/integration/test_runs_router.py -v
```

Expected: all green inkl. 2 neue Auth-Tests.

- [ ] **Step 3.6: Commit**

```bash
git add backend/interfaces/rest/routers/runs.py backend/tests/integration/test_runs_router.py
git commit -m "feat(rest): opt-in require_api_key auf POST /runs (Slice 1 Task 3)"
```

---

## Task 4: MCP Errors Module

**Files:**
- Create: `backend/interfaces/mcp/__init__.py` (empty)
- Create: `backend/interfaces/mcp/errors.py`
- Create: `backend/tests/unit/interfaces/mcp/__init__.py` (empty)
- Create: `backend/tests/unit/interfaces/mcp/test_errors.py`

- [ ] **Step 4.1: Create `__init__.py` stubs**

```bash
mkdir -p backend/interfaces/mcp backend/tests/unit/interfaces/mcp
touch backend/interfaces/mcp/__init__.py
touch backend/tests/unit/interfaces/mcp/__init__.py
```

- [ ] **Step 4.2: Write failing tests**

Create `backend/tests/unit/interfaces/mcp/test_errors.py`:

```python
"""Tests fuer MCP-Error-Mapping (Master-Spec MCP-Server §8)."""

import httpx
import pytest

from backend.interfaces.mcp.errors import (
    MCPError,
    raise_mcp_error_for_response,
    wrap_network_error,
)

pytestmark = pytest.mark.unit


def _response(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(status_code=status, json=body or {})


class TestRaiseMCPErrorForResponse:
    def test_200_does_not_raise(self) -> None:
        raise_mcp_error_for_response(_response(200))

    def test_201_does_not_raise(self) -> None:
        raise_mcp_error_for_response(_response(201))

    def test_401_raises_auth_failed(self) -> None:
        with pytest.raises(MCPError) as exc:
            raise_mcp_error_for_response(_response(401))
        assert exc.value.code == "AUTH_FAILED"
        assert "PRISMA_API_KEY" in exc.value.fields.get("hint", "")

    def test_404_raises_not_found_with_detail(self) -> None:
        with pytest.raises(MCPError) as exc:
            raise_mcp_error_for_response(_response(404, {"detail": "Universum X nicht gefunden"}))
        assert exc.value.code == "NOT_FOUND"
        assert "Universum X" in str(exc.value.fields.get("detail", ""))

    def test_404_without_body_still_raises(self) -> None:
        with pytest.raises(MCPError) as exc:
            raise_mcp_error_for_response(_response(404))
        assert exc.value.code == "NOT_FOUND"

    def test_422_raises_invalid_input(self) -> None:
        with pytest.raises(MCPError) as exc:
            raise_mcp_error_for_response(_response(422, {"detail": [{"loc": ["body", "x"], "msg": "Bad"}]}))
        assert exc.value.code == "INVALID_INPUT"

    def test_500_raises_internal(self) -> None:
        with pytest.raises(MCPError) as exc:
            raise_mcp_error_for_response(_response(500))
        assert exc.value.code == "INTERNAL"
        assert exc.value.fields.get("upstream_status") == 500

    def test_503_raises_internal(self) -> None:
        with pytest.raises(MCPError) as exc:
            raise_mcp_error_for_response(_response(503))
        assert exc.value.code == "INTERNAL"

    def test_unhandled_4xx_raises_internal(self) -> None:
        """400, 403 — kein dedizierter Code → INTERNAL mit upstream_status."""
        with pytest.raises(MCPError) as exc:
            raise_mcp_error_for_response(_response(400))
        assert exc.value.code == "INTERNAL"


class TestWrapNetworkError:
    async def test_connect_error_raises_upstream_unavailable(self) -> None:
        async def boom() -> None:
            raise httpx.ConnectError("connection refused")

        with pytest.raises(MCPError) as exc:
            async with wrap_network_error():
                await boom()
        assert exc.value.code == "UPSTREAM_UNAVAILABLE"
        assert exc.value.fields.get("retry_after_seconds") == 30

    async def test_timeout_raises_upstream_unavailable(self) -> None:
        async def boom() -> None:
            raise httpx.TimeoutException("timed out")

        with pytest.raises(MCPError):
            async with wrap_network_error():
                await boom()

    async def test_other_exceptions_pass_through(self) -> None:
        async def boom() -> None:
            raise ValueError("not a network error")

        with pytest.raises(ValueError):
            async with wrap_network_error():
                await boom()
```

- [ ] **Step 4.3: Run tests to verify they fail**

```bash
pytest backend/tests/unit/interfaces/mcp/test_errors.py -v 2>&1 | tail -10
```

Expected: ImportError, no module `backend.interfaces.mcp.errors`.

- [ ] **Step 4.4: Implement `errors.py`**

Create `backend/interfaces/mcp/errors.py`:

```python
"""MCP-Error-Mapping fuer REST-Antworten und Netzwerk-Fehler.

Mappt REST-HTTP-Statuscodes auf die 5 MCP-Error-Codes aus
docs/specs/2026-04-28-mcp-server.md §8:

- UPSTREAM_UNAVAILABLE: Netzwerk down (ConnectError, Timeout)
- AUTH_FAILED: 401
- NOT_FOUND: 404
- INVALID_INPUT: 422
- INTERNAL: 5xx oder unmapped 4xx
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx


class MCPError(Exception):
    """Strukturierter Tool-Fehler.

    Tool-Handler raisen das; FastMCP serialisiert es ins MCP-Wire-Format.
    `code` ist der Master-Spec-§8-String, `fields` zusaetzliche Hinweise
    fuer den Caller (z.B. retry_after_seconds, upstream_status).
    """

    def __init__(self, code: str, **fields: Any) -> None:
        self.code = code
        self.fields = fields
        super().__init__(f"{code}: {fields}")


def raise_mcp_error_for_response(response: httpx.Response) -> None:
    """Raises passenden MCPError fuer non-2xx-Responses. 2xx -> kein Effekt."""
    status = response.status_code
    if 200 <= status < 300:
        return

    if status == 401:
        raise MCPError("AUTH_FAILED", hint="Check PRISMA_API_KEY env var")

    if status == 404:
        detail = _safe_detail(response)
        raise MCPError("NOT_FOUND", detail=detail)

    if status == 422:
        detail = _safe_detail(response)
        raise MCPError("INVALID_INPUT", detail=detail)

    if status >= 500:
        raise MCPError("INTERNAL", upstream_status=status)

    # 4xx other than 401/404/422 (z.B. 400, 403) → INTERNAL mit upstream_status
    raise MCPError("INTERNAL", upstream_status=status)


def _safe_detail(response: httpx.Response) -> str:
    """JSON-Body-Detail extrahieren, kollabiert auf leer-string bei Decode-Fehler."""
    try:
        body = response.json()
    except Exception:
        return ""
    if isinstance(body, dict):
        return str(body.get("detail", ""))
    return str(body)


@asynccontextmanager
async def wrap_network_error() -> AsyncIterator[None]:
    """Async-Context-Manager: faengt httpx-Netzwerk-Errors und wirft MCPError(UPSTREAM_UNAVAILABLE).

    Andere Exceptions (ValueError, etc.) passieren durch — die sind nicht
    netzwerk-bedingt.
    """
    try:
        yield
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise MCPError("UPSTREAM_UNAVAILABLE", retry_after_seconds=30) from exc
```

- [ ] **Step 4.5: Run tests to verify they pass**

```bash
pytest backend/tests/unit/interfaces/mcp/test_errors.py -v
```

Expected: 12/12 passed.

- [ ] **Step 4.6: Commit**

```bash
git add backend/interfaces/mcp/__init__.py backend/interfaces/mcp/errors.py \
        backend/tests/unit/interfaces/mcp/__init__.py backend/tests/unit/interfaces/mcp/test_errors.py
git commit -m "feat(mcp): Error-Mapping fuer 5 Master-Spec-§8-Typen (Slice 1 Task 4)"
```

---

## Task 5: REST-Client

**Files:**
- Create: `backend/interfaces/mcp/rest_client.py`
- Create: `backend/tests/unit/interfaces/mcp/test_rest_client.py`

- [ ] **Step 5.1: Write failing tests**

Create `backend/tests/unit/interfaces/mcp/test_rest_client.py`:

```python
"""Tests fuer RESTClient — async httpx-Wrapper mit X-API-Key + Error-Mapping."""

import httpx
import pytest

from backend.interfaces.mcp.errors import MCPError
from backend.interfaces.mcp.rest_client import RESTClient

pytestmark = pytest.mark.unit


def _mock_transport(handler):  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


class TestRESTClient:
    async def test_post_sends_api_key_header(self) -> None:
        captured: dict[str, str] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            captured["x-api-key"] = req.headers.get("x-api-key", "")
            return httpx.Response(201, json={"id": "abc"})

        client = RESTClient(base_url="http://test", api_key="my-key", transport=_mock_transport(handler))
        result = await client.post("/api/v1/runs", json={"universe_id": "u1"})
        await client.close()

        assert result == {"id": "abc"}
        assert captured["x-api-key"] == "my-key"

    async def test_post_omits_header_when_key_empty(self) -> None:
        captured: dict[str, str] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(req.headers)
            return httpx.Response(201, json={})

        client = RESTClient(base_url="http://test", api_key="", transport=_mock_transport(handler))
        await client.post("/x", json={})
        await client.close()

        assert "x-api-key" not in {k.lower() for k in captured["headers"]}

    async def test_get_returns_json(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": [1, 2, 3]})

        client = RESTClient(base_url="http://test", api_key="k", transport=_mock_transport(handler))
        result = await client.get("/api/v1/runs/abc/rankings")
        await client.close()
        assert result == {"items": [1, 2, 3]}

    async def test_404_raises_not_found(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "Universe missing"})

        client = RESTClient(base_url="http://test", api_key="k", transport=_mock_transport(handler))
        with pytest.raises(MCPError) as exc:
            await client.post("/api/v1/runs", json={"universe_id": "u1"})
        await client.close()
        assert exc.value.code == "NOT_FOUND"

    async def test_401_raises_auth_failed(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Invalid API key"})

        client = RESTClient(base_url="http://test", api_key="bad", transport=_mock_transport(handler))
        with pytest.raises(MCPError) as exc:
            await client.post("/api/v1/runs", json={})
        await client.close()
        assert exc.value.code == "AUTH_FAILED"

    async def test_connect_error_raises_upstream_unavailable(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = RESTClient(base_url="http://test", api_key="k", transport=_mock_transport(handler))
        with pytest.raises(MCPError) as exc:
            await client.get("/api/v1/runs/abc")
        await client.close()
        assert exc.value.code == "UPSTREAM_UNAVAILABLE"
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
pytest backend/tests/unit/interfaces/mcp/test_rest_client.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 5.3: Implement `rest_client.py`**

Create `backend/interfaces/mcp/rest_client.py`:

```python
"""Async httpx-Client mit X-API-Key-Header und MCP-Error-Mapping.

Wird vom MCP-Server-Entry-Point (server.py) per from_env() konstruiert und
in alle Tool-Handler hineingereicht (testbarkeit > globaler State).
"""

import os
from typing import Any

import httpx

from backend.interfaces.mcp.errors import raise_mcp_error_for_response, wrap_network_error


class RESTClient:
    """Duenne httpx.AsyncClient-Huelle mit Auth-Header und Error-Mapping."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> "RESTClient":
        """Konstruktor aus Env-Vars: PRISMA_API_URL + PRISMA_API_KEY."""
        return cls(
            base_url=os.environ.get("PRISMA_API_URL", "http://localhost:8000"),
            api_key=os.environ.get("PRISMA_API_KEY", ""),
        )

    async def post(self, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        async with wrap_network_error():
            response = await self._client.post(path, json=json)
        raise_mcp_error_for_response(response)
        return response.json()

    async def get(self, path: str) -> Any:
        async with wrap_network_error():
            response = await self._client.get(path)
        raise_mcp_error_for_response(response)
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
pytest backend/tests/unit/interfaces/mcp/test_rest_client.py -v
```

Expected: 6/6 passed.

- [ ] **Step 5.5: Commit**

```bash
git add backend/interfaces/mcp/rest_client.py backend/tests/unit/interfaces/mcp/test_rest_client.py
git commit -m "feat(mcp): RESTClient mit X-API-Key + Error-Mapping (Slice 1 Task 5)"
```

---

## Task 6: Tool `run_ranking`

**Files:**
- Create: `backend/interfaces/mcp/tools/__init__.py` (empty)
- Create: `backend/interfaces/mcp/tools/run_ranking.py`
- Create: `backend/tests/unit/interfaces/mcp/tools/__init__.py` (empty)
- Create: `backend/tests/unit/interfaces/mcp/tools/test_run_ranking.py`

- [ ] **Step 6.1: Create `__init__.py` stubs**

```bash
mkdir -p backend/interfaces/mcp/tools backend/tests/unit/interfaces/mcp/tools
touch backend/interfaces/mcp/tools/__init__.py
touch backend/tests/unit/interfaces/mcp/tools/__init__.py
```

- [ ] **Step 6.2: Write failing tests**

Create `backend/tests/unit/interfaces/mcp/tools/test_run_ranking.py`:

```python
"""Tests fuer run_ranking-Tool-Handler — pure Funktion mit injiziertem Client."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.interfaces.mcp.tools.run_ranking import run_ranking

pytestmark = pytest.mark.unit


def _make_client(*, post_return: dict, get_return: list[dict]) -> AsyncMock:
    client = AsyncMock()
    client.post = AsyncMock(return_value=post_return)
    client.get = AsyncMock(return_value=get_return)
    return client


class TestRunRankingTool:
    async def test_happy_path_maps_response(self) -> None:
        run_id = uuid4()
        universe_id = uuid4()
        client = _make_client(
            post_return={
                "id": str(run_id),
                "status": "succeeded",
                "universe_id": str(universe_id),
                "created_at": "2026-05-11T10:00:00Z",
            },
            get_return=[
                {"ticker": f"T{i:02d}", "total_rank": i, "weighted_avg": 1.0,
                 "is_sweet_spot": i <= 3, "per_model_ranks": {}}
                for i in range(1, 16)
            ],
        )
        result = await run_ranking(client, universe_id=str(universe_id))

        # Strukturelle Erwartungen
        assert result["model_run_id"] == str(run_id)
        assert result["n_stocks"] == 15
        assert len(result["top_10_summary"]) == 10
        # Mapping is_sweet_spot -> sweet_spot
        assert result["top_10_summary"][0]["sweet_spot"] is True
        assert result["top_10_summary"][0]["ticker"] == "T01"
        assert result["top_10_summary"][0]["total_rank"] == 1

    async def test_sends_weight_config_when_provided(self) -> None:
        universe_id = str(uuid4())
        client = _make_client(
            post_return={"id": str(uuid4()), "status": "succeeded",
                          "universe_id": universe_id, "created_at": "2026-05-11T10:00:00Z"},
            get_return=[],
        )
        weights = {
            "quality_classic": 0.2,
            "alpha": 0.2,
            "trend_momentum": 0.2,
            "value_alpha_potential": 0.2,
            "diversification": 0.2,
        }
        await run_ranking(client, universe_id=universe_id, weights=weights)

        # Verify REST-Field heisst weight_config (nicht weights)
        post_call = client.post.call_args
        assert post_call.kwargs["json"]["weight_config"] == weights

    async def test_validates_weight_sum_locally(self) -> None:
        client = _make_client(post_return={}, get_return=[])
        weights = {"quality_classic": 0.4, "alpha": 0.4}  # sum=0.8
        with pytest.raises(ValueError, match="weights must sum to 1.0"):
            await run_ranking(client, universe_id=str(uuid4()), weights=weights)

    async def test_omits_weight_config_when_none(self) -> None:
        universe_id = str(uuid4())
        client = _make_client(
            post_return={"id": str(uuid4()), "status": "succeeded",
                          "universe_id": universe_id, "created_at": "2026-05-11T10:00:00Z"},
            get_return=[],
        )
        await run_ranking(client, universe_id=universe_id)

        assert "weight_config" not in client.post.call_args.kwargs["json"]

    async def test_top_10_summary_caps_at_10_when_more_rankings(self) -> None:
        client = _make_client(
            post_return={"id": str(uuid4()), "status": "succeeded",
                          "universe_id": str(uuid4()), "created_at": "2026-05-11T10:00:00Z"},
            get_return=[{"ticker": f"T{i}", "total_rank": i, "weighted_avg": 1.0,
                         "is_sweet_spot": False, "per_model_ranks": {}} for i in range(1, 25)],
        )
        result = await run_ranking(client, universe_id=str(uuid4()))
        assert len(result["top_10_summary"]) == 10
        assert result["n_stocks"] == 24

    async def test_top_10_summary_fewer_than_10_when_small_universe(self) -> None:
        client = _make_client(
            post_return={"id": str(uuid4()), "status": "succeeded",
                          "universe_id": str(uuid4()), "created_at": "2026-05-11T10:00:00Z"},
            get_return=[{"ticker": "A", "total_rank": 1, "weighted_avg": 1.0,
                         "is_sweet_spot": True, "per_model_ranks": {}}],
        )
        result = await run_ranking(client, universe_id=str(uuid4()))
        assert len(result["top_10_summary"]) == 1
        assert result["n_stocks"] == 1

    async def test_sorts_rankings_when_backend_returns_unsorted(self) -> None:
        """Backend garantiert keine Pre-Sortierung; total_rank ist Optional.
        Tool sortiert: kleinster Rank zuerst, None ans Ende.
        """
        client = _make_client(
            post_return={"id": str(uuid4()), "status": "succeeded",
                          "universe_id": str(uuid4()), "created_at": "2026-05-11T10:00:00Z"},
            get_return=[
                {"ticker": "C", "total_rank": 3, "weighted_avg": 1.0,
                 "is_sweet_spot": False, "per_model_ranks": {}},
                {"ticker": "NULL", "total_rank": None, "weighted_avg": None,
                 "is_sweet_spot": False, "per_model_ranks": {}},
                {"ticker": "A", "total_rank": 1, "weighted_avg": 1.0,
                 "is_sweet_spot": True, "per_model_ranks": {}},
                {"ticker": "B", "total_rank": 2, "weighted_avg": 1.0,
                 "is_sweet_spot": True, "per_model_ranks": {}},
            ],
        )
        result = await run_ranking(client, universe_id=str(uuid4()))
        tickers = [r["ticker"] for r in result["top_10_summary"]]
        assert tickers == ["A", "B", "C", "NULL"]
```

- [ ] **Step 6.3: Run tests to verify they fail**

```bash
pytest backend/tests/unit/interfaces/mcp/tools/test_run_ranking.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 6.4: Implement `run_ranking.py`**

Create `backend/interfaces/mcp/tools/run_ranking.py`:

```python
"""MCP-Tool: run_ranking.

Loest einen Ranking-Run aus und liefert ein Top-10-Summary.

Pure Funktion mit explizit injiziertem REST-Client → trivial testbar mit
Mock-Client. Die FastMCP-Decorator-Registrierung passiert in server.py.

Drift vs. Master-Spec §4.1:
- `name`/`universe_name` werden nicht zurueckgegeben (kein Backend-Endpoint
  liefert das aktuell — Folge-Slice kann das ergaenzen).
- REST-API erwartet `weight_config`, nicht `weights` — der Tool-Param
  heisst `weights` (User-facing-naming aus Master-Spec) und wird intern
  als `weight_config` an die REST-API geschickt.
"""

from typing import Any


async def run_ranking(
    client: Any,  # RESTClient — Any vermeidet zirkulaere Imports in Tests
    *,
    universe_id: str,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Startet einen neuen Ranking-Lauf.

    Args:
        client: REST-Client (httpx-Wrapper mit X-API-Key).
        universe_id: UUID des zu rankenden Universums.
        weights: Optional. Gewichte pro Modell — muss zu 1.0 (Tol 0.01) summieren.

    Returns:
        Dict mit `model_run_id`, `n_stocks`, `top_10_summary` (siehe Tests).

    Raises:
        ValueError: weights-Summe nicht ~1.0.
        MCPError: Backend-Fehler (NOT_FOUND, AUTH_FAILED, INVALID_INPUT, etc.).
    """
    # Local sanity check — Backend prueft strenger (Toleranz 1e-6), aber
    # fast-fail spart einen Round-Trip bei offensichtlichen Fehlern.
    if weights is not None:
        total = sum(weights.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"weights must sum to 1.0, got {total:.4f}")

    payload: dict[str, Any] = {"universe_id": universe_id}
    if weights is not None:
        payload["weight_config"] = weights

    run = await client.post("/api/v1/runs", json=payload)
    rankings = await client.get(f"/api/v1/runs/{run['id']}/rankings")

    # Explizite Sortierung: total_rank ist `int | None` (schemas/runs.py:54),
    # Backend garantiert keine Pre-Sortierung. Items mit total_rank=None
    # landen ans Ende (sentinel = unendlich).
    sorted_rankings = sorted(
        rankings,
        key=lambda r: (r["total_rank"] is None, r["total_rank"] or 0),
    )

    top_10 = [
        {
            "ticker": r["ticker"],
            "total_rank": r["total_rank"],
            "sweet_spot": r["is_sweet_spot"],
        }
        for r in sorted_rankings[:10]
    ]
    return {
        "model_run_id": run["id"],
        "n_stocks": len(rankings),
        "top_10_summary": top_10,
    }
```

- [ ] **Step 6.5: Run tests to verify they pass**

```bash
pytest backend/tests/unit/interfaces/mcp/tools/test_run_ranking.py -v
```

Expected: 7/7 passed.

- [ ] **Step 6.6: Commit**

```bash
git add backend/interfaces/mcp/tools/__init__.py backend/interfaces/mcp/tools/run_ranking.py \
        backend/tests/unit/interfaces/mcp/tools/__init__.py \
        backend/tests/unit/interfaces/mcp/tools/test_run_ranking.py
git commit -m "feat(mcp): run_ranking Tool-Handler — pure mit injiziertem Client (Slice 1 Task 6)"
```

---

## Task 7: MCP-Server-Entry-Point

**Files:**
- Create: `backend/interfaces/mcp/server.py`

- [ ] **Step 7.1: Verify FastMCP-Signatur aus installiertem SDK**

```bash
source .venv/bin/activate
python -c "from mcp.server.fastmcp import FastMCP; help(FastMCP.__init__)" 2>&1 | head -20
python -c "from mcp.server.fastmcp import FastMCP; m = FastMCP('test'); print([a for a in dir(m) if not a.startswith('_')])" 2>&1 | head -10
```

Notiere konkret: hat `FastMCP.tool()` einen Decorator-Pattern wie `@mcp.tool()`? Wenn `mcp.run(transport="stdio")` der korrekte Entry-Point?

Falls API anders ist als Master-Spec annahm: hier dokumentieren und entsprechend implementieren. Plan-Beispiel folgt der Spec-Annahme.

- [ ] **Step 7.2: Implement `server.py`**

Create `backend/interfaces/mcp/server.py`:

```python
"""MCP-Server-Entry-Point — STDIO-Transport, FastMCP-Tool-Registration.

Start via:
    python -m backend.interfaces.mcp.server

Konfiguriert ueber Env-Vars (siehe RESTClient.from_env):
    PRISMA_API_URL   (Default: http://localhost:8000)
    PRISMA_API_KEY   (X-API-Key Header — leer = opt-in disabled)

Logs gehen nach stderr (STDIO-Protokoll verwendet stdout).
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from backend.interfaces.mcp.rest_client import RESTClient
from backend.interfaces.mcp.tools.run_ranking import run_ranking as _run_ranking_impl

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("prisma.mcp")

mcp = FastMCP("prisma")
_client: RESTClient | None = None


def _get_client() -> RESTClient:
    global _client
    if _client is None:
        _client = RESTClient.from_env()
        logger.info("RESTClient initialized")
    return _client


@mcp.tool()
async def run_ranking(
    universe_id: str,
    weights: dict[str, float] | None = None,
) -> dict:
    """Loest einen neuen Ranking-Lauf auf einem bestehenden Universum.

    Args:
        universe_id: UUID des zu rankenden Universums (z.B. SMI, S&P-Subset).
        weights: Optional. Gewichte pro Modell — z.B.
                 {"quality_classic": 0.2, "alpha": 0.2, "trend_momentum": 0.2,
                  "value_alpha_potential": 0.2, "diversification": 0.2}.
                 Muss zu 1.0 summieren. Fehlt: Backend-Default.

    Returns:
        {
          "model_run_id": str,
          "n_stocks": int,
          "top_10_summary": [{"ticker": str, "total_rank": int, "sweet_spot": bool}]
        }
    """
    return await _run_ranking_impl(_get_client(), universe_id=universe_id, weights=weights)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 7.3: Verify import doesn't crash**

```bash
python -c "from backend.interfaces.mcp import server; print(server.mcp.name)" 2>&1 | tail -5
```

Expected: `prisma` (no exceptions during import).

- [ ] **Step 7.4: Commit**

```bash
git add backend/interfaces/mcp/server.py
git commit -m "feat(mcp): server.py Entry-Point mit FastMCP + run_ranking-Tool (Slice 1 Task 7)"
```

---

## Task 8: Integration-Test E2E

**Files:**
- Create: `backend/tests/integration/test_mcp_run_ranking.py`

- [ ] **Step 8.1: Write integration-Test**

Create `backend/tests/integration/test_mcp_run_ranking.py`:

```python
"""Integration-Test: MCP run_ranking Tool gegen In-Process-FastAPI-TestClient.

Validiert end-to-end:
- Tool ruft echte REST-Endpoints
- Auth-Header wird durchgereicht
- Error-Mapping greift (404, 401)
- Top-10-Summary wird korrekt aus Backend-Response abgeleitet

Spec: docs/specs/2026-05-11-mcp-server-slice-1-skeleton.md §8.2
"""

from typing import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.application.services.ranking_run_service import UniverseNotFound
from backend.config import Settings
from backend.interfaces.mcp.errors import MCPError
from backend.interfaces.mcp.rest_client import RESTClient
from backend.interfaces.mcp.tools.run_ranking import run_ranking
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_ranking_run_service, get_settings

pytestmark = pytest.mark.integration


def _fastapi_transport_client(app, settings: Settings) -> RESTClient:
    """Baut RESTClient, der ueber httpx.ASGITransport gegen die FastAPI-App
    laeuft — keine echte Netzwerk-Connection.
    """
    app.dependency_overrides[get_settings] = lambda: settings
    transport = httpx.ASGITransport(app=app)
    return RESTClient(
        base_url="http://testserver",
        api_key=settings.tool_api_key,
        transport=transport,
    )


class TestMCPRunRankingE2E:
    async def test_happy_path_via_fastapi_testclient(self) -> None:
        """Tool ruft Run-Service, bekommt Top-10 zurueck."""
        app = create_app()
        # Mock-Service: Run + Rankings synthetisch
        run_id = uuid4()
        universe_id = uuid4()
        mock_service = AsyncMock()
        # service.create_and_execute_run returns a RankingRun-like with .id, .status, .universe_id, .created_at
        mock_service.create_and_execute_run = AsyncMock(return_value=_fake_run(run_id, universe_id))
        mock_service.get_rankings = AsyncMock(return_value=[_fake_rank(i) for i in range(1, 16)])
        app.dependency_overrides[get_ranking_run_service] = lambda: mock_service

        client = _fastapi_transport_client(app, Settings(tool_api_key=""))
        result = await run_ranking(client, universe_id=str(universe_id))
        await client.close()

        assert result["model_run_id"] == str(run_id)
        assert result["n_stocks"] == 15
        assert len(result["top_10_summary"]) == 10
        assert result["top_10_summary"][0]["total_rank"] == 1

    async def test_404_when_universe_missing(self) -> None:
        app = create_app()
        mock_service = AsyncMock()
        mock_service.create_and_execute_run = AsyncMock(side_effect=UniverseNotFound("Universum nicht da"))
        app.dependency_overrides[get_ranking_run_service] = lambda: mock_service

        client = _fastapi_transport_client(app, Settings(tool_api_key=""))
        with pytest.raises(MCPError) as exc:
            await run_ranking(client, universe_id=str(uuid4()))
        await client.close()
        assert exc.value.code == "NOT_FOUND"

    async def test_401_when_tool_key_set_but_client_misses_header(self) -> None:
        app = create_app()
        # Settings mit gesetztem Key → Auth aktiv. Client OHNE Key → 401.
        client_settings = Settings(tool_api_key="server-secret")
        app.dependency_overrides[get_settings] = lambda: client_settings
        transport = httpx.ASGITransport(app=app)
        client = RESTClient(base_url="http://testserver", api_key="", transport=transport)

        with pytest.raises(MCPError) as exc:
            await run_ranking(client, universe_id=str(uuid4()))
        await client.close()
        assert exc.value.code == "AUTH_FAILED"


# ----------- Test-Helpers -----------

def _fake_run(run_id, universe_id):  # type: ignore[no-untyped-def]
    """Minimaler Stand-in fuer RankingRun, der RunResponse.from_domain frisst."""
    from datetime import UTC, datetime

    from backend.domain.entities.ranking_run import RankingRun, RankingRunStatus
    return RankingRun(
        id=run_id,
        universe_id=universe_id,
        status=RankingRunStatus.SUCCEEDED,
        created_at=datetime.now(UTC),
        # ggf. weitere Pflichtfelder hier ergaenzen wenn das Domain-Modell mehr verlangt
    )


def _fake_rank(rank: int) -> dict:
    """Liefert ein RankingItem-Dict-Shape.

    `RankingRunService.get_rankings` ist typed `list[dict[str, Any]]` und gibt
    Dicts aus dem RankingRunRepository (`get_results`) zurueck. Der Router in
    `routers/runs.py:54` ruft `RankingItem.model_validate(r)` auf den Dicts —
    Pydantic erwartet hier Mapping-Keys, NICHT Objekt-Attribute (model_validate
    mit Objekten braeuchte `from_attributes=True` config, was nicht gesetzt ist).

    Daher: Mock returns dicts mit exakt den RankingItem-Field-Namen.
    """
    return {
        "ticker": f"T{rank:02d}",
        "total_rank": rank,
        "weighted_avg": 1.0,
        "is_sweet_spot": rank <= 3,
        "per_model_ranks": {},
    }
```

- [ ] **Step 8.2: Run integration-Test**

```bash
pytest backend/tests/integration/test_mcp_run_ranking.py -v
```

Expected: 3/3 passed.

**Falls Test-Helper `_fake_run` nicht zum aktuellen `RankingRun`-Domain-Modell passt:** Schema lesen (`backend/domain/entities/ranking_run.py`), Helper anpassen. Falls `get_rankings` Domain-Objekte returns die `RankingItem.model_validate` nicht frisst: passend casten.

- [ ] **Step 8.3: Commit**

```bash
git add backend/tests/integration/test_mcp_run_ranking.py
git commit -m "test(mcp): Integration-Test fuer run_ranking E2E via FastAPI-TestClient (Slice 1 Task 8)"
```

---

## Task 9: Pre-Push CI-Mirror + AI-USAGE-Eintrag + Final Verify

**Files:**
- Modify: `docs/AI-USAGE.md`

- [ ] **Step 9.1: Full CI-Mirror lokal + Coverage**

```bash
source .venv/bin/activate
mypy backend/
ruff check backend/
ruff format --check backend/
pytest backend/tests/unit -q
pytest backend/tests/integration/test_mcp_run_ranking.py -q

# Coverage-Messung fuer die neue MCP-Schicht (Spec §9 Akzeptanz: >=85%)
pytest backend/tests/unit/interfaces/mcp/ \
    --cov=backend/interfaces/mcp \
    --cov-report=term-missing \
    --cov-fail-under=85
```

Expected: alles gruen, Coverage >= 85% auf `backend/interfaces/mcp/`. Falls Coverage unter Schwelle: fehlende Branches identifizieren (`term-missing`-Output) und Tests ergaenzen, bevor weiter.

- [ ] **Step 9.2: AI-USAGE-Eintrag verfassen**

Edit `docs/AI-USAGE.md` — neuen Eintrag oben (oder am chronologisch passenden Ort) mit:

- Datum
- Slice-Spec + Plan-Doc-Pfade
- Patterns angewandt: P1 (Q-by-Q-Brainstorming), P2 (Reality-Check vor Code — `/factsheet`-Pivot dokumentiert), P4 (verbindliche Planstruktur), P6 (Strict-Scope: opt-in Auth statt strict-by-default)
- Anti-Pattern vermieden: A1 (Plan-Code-Drift) — durch Reality-Check vermieden
- Test-Coverage: unit + integration
- Cost: ggf. Inference-Tokens fuer Plan-Phase notieren

- [ ] **Step 9.3: Commit AI-USAGE**

```bash
git add docs/AI-USAGE.md
git commit -m "docs(ai-usage): Slice 1 MCP-Server-Eintrag (Slice 1 Task 9)"
```

- [ ] **Step 9.4: Push und PR oeffnen (oder bestehenden Spec-PR erweitern)**

Entscheidung: PR #78 ist Spec-only. Implementation kommt entweder
- (a) in einem neuen PR `feat/mcp-server-slice-1` mit base auf main (nach Spec-Merge)
- (b) als zweite Commit-Reihe in PR #78 (Spec+Plan+Impl gebundled — wie PR #75 vorgehensweise)

Entscheidung in Plan-Phase nicht final festgelegt — kommentieren bei Push.

---

## Self-Review

Nach Plan-Schreiben mit frischen Augen:

**1. Spec-Coverage:** Jede Spec-Sektion adressiert?
- §3 Architektur: ✅ Task 4-7
- §4 Auth-Strategie: ✅ Task 2-3
- §5 Tool-Implementation: ✅ Task 6
- §6 REST-Client: ✅ Task 5
- §7 Error-Mapping: ✅ Task 4
- §8 Tests: ✅ Task 6 (unit) + Task 8 (integration)
- §9 Acceptance: alle Punkte adressiert
- §10 Risiken: Plan-Phase-Reality-Check dokumentiert die confirmed drifts

**2. Placeholder-Scan:**
- Task 3 erwaehnt "app_with_runs"-Fixture-Pattern — falls existing-Fixture-Convention abweicht: an `test_memo_batch_endpoint.py` orientieren. **Akzeptiert**: Plan kennt nicht jede Fixture-Konvention bis ins Detail; Pattern-Match auf existing-Tests ist explizit angesagt.
- Task 8 `_fake_run`-Helper hat "ggf. weitere Pflichtfelder" — RankingRun-Modell beim Execute lesen. **Akzeptiert**: Domain-Modell evolviert, Plan nennt das Vorgehen.
- Task 7 FastMCP-API-Verify ist explizit als Step 7.1 drin. **Akzeptiert**: Reality-Check vor Implementation.

**3. Type-Consistency:**
- `RESTClient` Signature: einheitlich `post(self, path, *, json)` und `get(self, path)` in Task 5 + Task 6 + Task 8 ✓
- `MCPError(code, **fields)` einheitlich ✓
- `run_ranking(client, *, universe_id, weights=None)` einheitlich ✓

## Execution Handoff

**Plan saved to:** `docs/specs/2026-05-11-mcp-server-slice-1-plan.md`

Empfohlene Ausführung: parallele Agent-Ausführung (je Task ein frischer Agent). Tasks sind weitgehend unabhaengig — jede Task ist 1 Datei + 1 Test-File, Reviewer-fokussiert mit klaren Erwartungen.

Sequenz strict (kein Reordering): Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9.

Estimated Execution: ~90-120 min (9 Tasks, je 5-15 min mechanisch).
