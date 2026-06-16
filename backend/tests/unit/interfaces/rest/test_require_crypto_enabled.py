"""Tests für require_crypto_enabled — gattet das Crypto-Modul über CRYPTO_FEATURE_ENABLED."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.interfaces.rest.dependencies import require_crypto_enabled


def _app_with_flag(crypto_feature_enabled: bool) -> TestClient:
    app = FastAPI()
    settings = Settings(
        database_url="postgresql+asyncpg://x:x@x/x",
        environment="test",
        crypto_feature_enabled=crypto_feature_enabled,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/probe")
    async def probe(_flag: None = Depends(require_crypto_enabled)) -> dict:  # type: ignore[type-arg]
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_feature_enabled_allows_request() -> None:
    client = _app_with_flag(crypto_feature_enabled=True)
    assert client.get("/probe").status_code == 200


def test_feature_disabled_returns_404() -> None:
    client = _app_with_flag(crypto_feature_enabled=False)
    response = client.get("/probe")
    assert response.status_code == 404
    assert response.json()["detail"] == "Crypto-Feature ist deaktiviert."
