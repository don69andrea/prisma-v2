# Spec: MCP-Server Slice 1 — Skeleton + `run_ranking`

**Status:** Draft v1.0 — 2026-05-11
**Parent-Spec:** `docs/specs/2026-04-28-mcp-server.md`
**Issue:** #35 (Slice 1 von ~4)
**Rolle:** B — AI Engineer (Sheyla)

---

## 1. Zweck & Slice-Position

Slice 1 etabliert die **MCP-Server-Architektur end-to-end** mit dem einfachsten
Action-Tool (`run_ranking`). Beweist:

- FastMCP-Setup funktioniert via STDIO
- REST-Client mit `X-API-Key`-Header erreicht Backend
- Backend lehnt fehlende/falsche Keys ab (401)
- Error-Mapping uebersetzt REST-Fehler in MCP-Errors
- Integration-Test in CI gegen FastAPI-TestClient

**Was fehlt nach Slice 1:**
- `get_factsheet`, `compare_stocks`, `trigger_backtest` (je 1 Folge-Slice)
- Rate-Limit-Middleware (Slice 5 = Demo-Hardening)
- Setup-Doku + Demo-Screenshots (Slice 5)

## 2. Bewusste Abweichungen vom Master-Spec

| Master-Spec | Slice-Verhalten | Begruendung |
|---|---|---|
| §4: alle 4 Tools | nur `run_ranking` | Skeleton-Slice — `get_factsheet` ist auf `/api/v1/stocks/{ticker}/factsheet` angewiesen (Issue #38, open). Pivot auf `run_ranking` weil `POST /api/v1/runs` schon existiert. |
| §6: Team-API-Key | `require_api_key` auf `POST /runs` aktiviert | Spec sagt "1 Team = 1 Key" — wiederverwendbar fuer alle anderen Tool-Endpoints. Wir setzen die Enforcement schon hier durch, damit nachfolgende Slices den Auth-Path nicht selbst bauen muessen. |
| §10 (Observability) | minimale `stderr`-Logs ueber `logging` | Strukturiertes JSON-Logging ist Wave-3 — fuer Slice 1 reicht stderr-Tool-Call-Trace fuer Debug. |
| §11 (Deployment) | nicht beruehrt | MCP-Server ist Client-Code — kein Render-Deploy. `pipx`-Stretch bleibt ausserhalb. |
| §14 (Akzeptanz: Demo-Screenshots) | nicht in dieser Slice | Slice 5 sammelt Screenshots, sobald alle 4 Tools fertig. |

## 3. Architektur

```
backend/interfaces/mcp/                              (NEU — kompletter Ordner)
├── __init__.py
├── server.py                  # FastMCP-Entry-Point + Tool-Registration
├── rest_client.py             # async httpx-Client mit X-API-Key-Header
├── errors.py                  # MCP-Error-Mapping (5 Typen aus Master-Spec §8)
└── tools/
    ├── __init__.py
    └── run_ranking.py         # Tool-Handler fuer `run_ranking`

backend/interfaces/rest/dependencies.py              (MODIFIZIERT)
└── require_api_key            # NEU: gleiche Mechanik wie require_admin_api_key,
                               # aber separat — admin-key bleibt fuer /admin/costs

backend/interfaces/rest/routers/runs.py              (MODIFIZIERT)
└── POST /api/v1/runs          # bekommt _auth: None = Depends(require_api_key)

backend/tests/unit/interfaces/mcp/                   (NEU)
├── test_rest_client.py        # httpx-Mock-Tests
├── test_errors.py             # Mapping-Tests fuer alle 5 Fehlertypen
└── tools/
    └── test_run_ranking.py    # Tool-Handler mit Mock-REST-Client

backend/tests/integration/test_mcp_run_ranking.py    (NEU)
└── E2E: MCP-Tool -> echte Backend-Logik via FastAPI-TestClient

pyproject.toml                                       (MODIFIZIERT)
└── + "mcp>=1.2", "httpx>=0.27"  (httpx ggf. schon Test-Dep)
```

```
Claude Desktop
    |
    | STDIO (MCP-Protocol)
    v
PRISMA MCP-Server  (backend/interfaces/mcp/server.py)
    |
    | run_ranking(universe_id, weights)
    v
Tool-Handler       (tools/run_ranking.py)
    |
    | POST /api/v1/runs
    | X-API-Key: <env PRISMA_API_KEY>
    v
RESTClient         (rest_client.py)
    |
    | HTTPS
    v
FastAPI Backend    (POST /api/v1/runs mit require_api_key)
```

## 4. Auth-Strategie

**Master-Spec §6.3:** 1 Team = 1 Key.

**Slice-Entscheidung:** wir trennen den Tool-Key von dem Admin-Key, weil:
- `/admin/costs` ist eine Operator-Operation (Cost-Auditing)
- `/runs` ist Tool-Triggering — soll fuer Team + MCP-Demo verfuegbar sein
- Bei Schluesseltausch muss `/admin/costs` nicht mit rotieren

**Implementation:**
```python
# dependencies.py — neue Funktion analog require_admin_api_key
async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.tool_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if x_api_key is None or not hmac.compare_digest(x_api_key, settings.tool_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
```

**Settings-Erweiterung:**
```python
# config.py
tool_api_key: str = Field(default="", description="MCP-Tool-API-Key (X-API-Key Header)")
```

Env-Var: `PRISMA_TOOL_API_KEY` (Backend), `PRISMA_API_KEY` (MCP-Client — Spec §7 nennt das so).

**Backwards-Compat:** Bestehende `POST /api/v1/runs`-Aufrufer (z.B. via Frontend) sind aktuell **nicht authentifiziert** — werden mit Slice nach 401 zurueckgewiesen, **bis** sie den Header schicken. Mitigation:
- Frontend hat noch keinen production-Use von POST /runs (Nicolas Issues #49/#50 noch offen)
- Tests in `test_runs.py` muessen `X-API-Key`-Header bekommen
- Falls Sheyla das nicht will: alternativ `require_api_key` *opt-in* (nur wenn `settings.tool_api_key` gesetzt). Default-Verhalten dann gleich wie heute.

**Entscheidung in Slice-Plan:** Strict-Auth ist sauberer (deviation-from-spec klein), aber bricht potentiell andere Pfade. **Default: opt-in** — wenn `tool_api_key` leer (default), kein Enforcement. Sobald Env-Var gesetzt wird, ist Auth aktiv. Tests setzen Settings explizit.

## 5. Tool-Implementation: `run_ranking`

> **Reference-Draft** — der executable Code lebt im Plan-Dokument (Task 6.4) nach Reality-Check. Diese Sektion zeigt die Intention, nicht den final-Stand.

**Drifts gegen diesen Draft (siehe Plan §6.4):**
- REST-API-Feld heisst `weight_config`, nicht `weights` → Mapping im Tool
- `RunResponse` enthaelt **kein** `universe_name` → wird aus MCP-Output gestrichen
- `RankingItem` enthaelt **kein** `name`-Feld → top_10 nur mit `ticker`
- `total_rank` ist `int | None` → explizite Sortierung im Tool (Backend-Pre-Sortierung nicht garantiert)

```python
# Intention — siehe Plan Task 6.4 fuer executable Form
async def run_ranking(client, *, universe_id, weights=None) -> dict:
    """Loest einen neuen Ranking-Run aus.

    Returns:
        {
          "model_run_id": str,
          "n_stocks": int,
          "top_10_summary": [
            {"ticker": str, "total_rank": int, "sweet_spot": bool}
          ]
        }
    """
    # 1. Validate weights sum locally (fast-fail)
    # 2. POST /api/v1/runs mit weight_config-Feld
    # 3. GET /api/v1/runs/{id}/rankings
    # 4. Sort by total_rank (None ans Ende), nimm Top-10
    # 5. Mappe is_sweet_spot -> sweet_spot
```

## 6. REST-Client

```python
# backend/interfaces/mcp/rest_client.py
import os
import httpx


class RESTClient:
    """Async httpx-Client mit X-API-Key-Header und Error-Mapping."""

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"X-API-Key": api_key} if api_key else {},
        )

    @classmethod
    def from_env(cls) -> "RESTClient":
        return cls(
            base_url=os.environ.get("PRISMA_API_URL", "http://localhost:8000"),
            api_key=os.environ.get("PRISMA_API_KEY", ""),
        )

    async def post(self, path: str, json: dict) -> dict:
        response = await self._client.post(path, json=json)
        _raise_mcp_error(response)
        return response.json()

    async def get(self, path: str) -> dict:
        response = await self._client.get(path)
        _raise_mcp_error(response)
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
```

## 7. Error-Mapping (alle 5 Typen)

```python
# backend/interfaces/mcp/errors.py
import httpx


class MCPError(Exception):
    """Basis-Exception. Tool-Handler raisen das; FastMCP fangt + serialisiert."""

    def __init__(self, code: str, **fields: Any) -> None:
        self.code = code
        self.fields = fields
        super().__init__(f"{code}: {fields}")


def _raise_mcp_error(response: httpx.Response) -> None:
    if response.status_code == 200 or response.status_code == 201:
        return
    if response.status_code == 401:
        raise MCPError("AUTH_FAILED", hint="Check PRISMA_API_KEY env var")
    if response.status_code == 404:
        # entity/identifier aus Body falls vorhanden
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = ""
        raise MCPError("NOT_FOUND", detail=detail)
    if response.status_code == 422:
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = ""
        raise MCPError("INVALID_INPUT", detail=str(detail))
    if response.status_code >= 500:
        raise MCPError("INTERNAL", upstream_status=response.status_code)
    # Network errors landen im httpx.RequestError-Catch, separat behandelt
    raise MCPError("INTERNAL", upstream_status=response.status_code)
```

UPSTREAM_UNAVAILABLE wird im RESTClient-Try-Except gefangen (httpx.ConnectError, TimeoutException).

## 8. Tests

### 8.1 Unit
- `test_rest_client.py`: Mock httpx-Transport, prueft X-API-Key-Header + Base-URL
- `test_errors.py`: 5 Status-Code-Klassen → korrekter MCPError-Code
- `test_run_ranking.py`: Tool mit Mock-RESTClient, prueft Weight-Validation + Response-Mapping
- `test_run_ranking_validates_weights_sum.py`: weights=0.5 → ValueError

### 8.2 Integration
- `test_mcp_run_ranking.py`: in-process FastAPI-TestClient, MCP-Tool ruft echte Backend-Logik
  - happy path: Universum existiert, Run wird erstellt, Top-10 returned
  - 404 path: Universum existiert nicht, MCPError("NOT_FOUND") raised
  - 401 path: kein API-Key gesetzt UND `tool_api_key` in Settings gesetzt → AUTH_FAILED

### 8.3 Manuell (NICHT in Slice 1)
- Real Claude-Desktop-E2E kommt in Slice 5

## 9. Acceptance Criteria

- [ ] `mcp>=1.2` und `httpx>=0.27` in pyproject.toml
- [ ] `backend/interfaces/mcp/`-Ordner mit `server.py`, `rest_client.py`, `errors.py`, `tools/run_ranking.py`
- [ ] `server.py` startet via `python -m backend.interfaces.mcp.server` (STDIO)
- [ ] Settings-Erweiterung: `tool_api_key` (opt-in)
- [ ] `require_api_key`-Dependency neben `require_admin_api_key`
- [ ] `POST /api/v1/runs` opt-in mit `require_api_key`
- [ ] Bestehende Run-Tests gruen (mit oder ohne `tool_api_key`)
- [ ] Error-Mapping fuer alle 5 Typen aus Master-Spec §8
- [ ] Unit-Tests >=85% Coverage (auf `backend/interfaces/mcp/`)
- [ ] Integration-Test mit FastAPI-TestClient gruen
- [ ] mypy strict + ruff clean
- [ ] AI-USAGE.md-Eintrag

## 10. Risiken & Mitigation

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| MCP-SDK-API hat sich geaendert (>=1.2) | mittel | Plan-Phase verifiziert konkrete Imports + FastMCP-Signatur |
| `RunResponse` enthaelt keinen `universe_name` | **bestaetigt** | Aus MCP-Output gestrichen (kein Backend-Change) |
| `RankingItem.total_rank` ist `int \| None` + Backend-Sortierung nicht garantiert | bestaetigt | Tool sortiert explizit (None ans Ende), bevor Top-10 geschnitten wird |
| `require_api_key` bricht bestehende Frontend-Calls | niedrig (opt-in default-off) | Tests behalten current behavior, solange `tool_api_key` leer |
| Universum-Existenz vor MCP-Tool unbekannt | mittel | Slice deckt nur happy-404 ab; `list_universes` ist Folge-Tool |

## 11. Q-by-Q-Decisions (Audit-Trail)

| # | Frage | Entscheidung | Datum |
|---|---|---|---|
| 1 | Slicing-Strategie? | Skeleton + 1 Tool end-to-end | 2026-05-11 |
| 2 | Welches Tool? | Pivot von `get_factsheet` auf `run_ranking` — `/factsheet`-Endpoint nicht da (#38) | 2026-05-11 |
| 3 | Test-Strategie? | Unit + Integration via FastAPI-TestClient (Master-Spec §9.2) | 2026-05-11 |
| 4 | Auth-Behandlung? | X-API-Key durchgereicht; Backend enforced opt-in (default-off, damit nichts bricht) | 2026-05-11 |
| 5 | Error-Mapping-Coverage? | Alle 5 Typen (one-time setup, fuer Folge-Slices wiederverwendbar) | 2026-05-11 |

## 12. Folge-Slices (nicht Teil von Slice 1)

- **Slice 2:** `get_factsheet` — wartet auf #38 (Andrea, `/factsheet`-Endpoint)
- **Slice 3:** `compare_stocks` — wartet auf evtl. Backend-Erweiterung (`name`-Lookup, Multi-Ticker-Filter)
- **Slice 4:** `trigger_backtest` — wartet auf Backtest-Endpoint (nicht gespect/im MVP unklar)
- **Slice 5:** Hardening — Rate-Limit-Middleware, Setup-Doku, Demo-Screenshots, Render-Env

## 13. Aenderungshistorie

| Version | Datum | Autor | Aenderung |
|---|---|---|---|
| Draft v1.0 | 2026-05-11 | Claude Code fuer Sheyla | Slice-Spec aufgesetzt nach Q-by-Q-Brainstorming + Reality-Check (Endpoint-Bestand) |
