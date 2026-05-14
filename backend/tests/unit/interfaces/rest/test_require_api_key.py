"""Tests für require_api_key — opt-in Auth-Dependency."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.interfaces.rest.dependencies import require_api_key

_BASE_SETTINGS = Settings(
    database_url="postgresql+asyncpg://x:x@x/x",
    environment="test",
)


def _app_with_key(tool_api_key: str = "") -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    settings = Settings(
        database_url="postgresql+asyncpg://x:x@x/x",
        environment="test",
        tool_api_key=tool_api_key,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/probe")
    async def probe(_auth: None = Depends(require_api_key)) -> dict:  # type: ignore[type-arg]
        return {"ok": True}

    return app, TestClient(app, raise_server_exceptions=False)


def test_no_key_configured_allows_any_request() -> None:
    _, client = _app_with_key(tool_api_key="")
    assert client.get("/probe").status_code == 200


def test_key_configured_rejects_missing_header() -> None:
    _, client = _app_with_key(tool_api_key="secret")
    assert client.get("/probe").status_code == 401


def test_key_configured_rejects_wrong_header() -> None:
    _, client = _app_with_key(tool_api_key="secret")
    assert client.get("/probe", headers={"X-API-Key": "wrong"}).status_code == 401


def test_key_configured_accepts_correct_header() -> None:
    _, client = _app_with_key(tool_api_key="secret")
    assert client.get("/probe", headers={"X-API-Key": "secret"}).status_code == 200
