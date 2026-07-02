"""Tests für den Production-Boot-Validator in backend.config.Settings.

Hintergrund: Render-Deploys von `prisma-backend` brachen mit "Exited with
status 1" ab, weil `_api_key_required_in_production` einen leeren API_KEY
in der Production-Umgebung als ValidationError eskaliert — und API_KEY
nirgends in den Render-Env-Vars deklariert war. Diese Tests verriegeln
das Verhalten, damit ein künftiges Schweigen des Validators sofort
sichtbar wird.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import Settings


class TestApiKeyProductionValidator:
    """`_api_key_required_in_production` darf nur in Production zuschlagen."""

    # _env_file=None entkoppelt jeden Test von einer lokalen .env; sonst
    # könnte ein dort gesetztes API_KEY den Production-Fail-Case maskieren.
    # mypy kennt das pydantic-settings-Dunder-Kwarg nicht — daher gezielter
    # call-arg-Ignore pro Aufruf statt einer Class-weiten Suppression.

    def test_raises_when_api_key_empty_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # CI=true würde den Validator skippen — für diesen Test explizit deaktivieren.
        monkeypatch.delenv("CI", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment="production", api_key="", _env_file=None)  # type: ignore[call-arg]
        assert "API_KEY" in str(exc_info.value)

    def test_passes_when_api_key_set_in_production(self) -> None:
        settings = Settings(  # type: ignore[call-arg]
            environment="production",
            api_key="secret",
            anthropic_api_key="sk-ant-test",
            jwt_secret="test-jwt-secret",
            _env_file=None,
        )
        assert settings.api_key == "secret"

    def test_passes_in_development_without_api_key(self) -> None:
        settings = Settings(environment="development", api_key="", _env_file=None)  # type: ignore[call-arg]
        assert settings.api_key == ""


class TestJwtSecretProductionValidator:
    """`_jwt_secret_required_in_production` — Pflicht in Prod, Bypass in CI (H-11)."""

    def test_raises_when_jwt_secret_empty_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CI", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            # api_key/anthropic gesetzt, damit nur der JWT-Validator zuschlägt.
            Settings(  # type: ignore[call-arg]
                environment="production",
                api_key="secret",
                anthropic_api_key="sk-ant-test",
                jwt_secret="",
                _env_file=None,
            )
        assert "JWT_SECRET" in str(exc_info.value)

    def test_skips_jwt_check_when_ci_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Scheduled Worker (GH Actions, CI=true) setzen ENVIRONMENT=production,
        # nutzen aber kein JWT — Boot darf nicht crashen.
        monkeypatch.setenv("CI", "true")
        settings = Settings(  # type: ignore[call-arg]
            environment="production", jwt_secret="", api_key="", _env_file=None
        )
        assert settings.jwt_secret == ""

    def test_passes_in_production_with_jwt_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CI", raising=False)
        settings = Settings(  # type: ignore[call-arg]
            environment="production",
            api_key="secret",
            anthropic_api_key="sk-ant-test",
            jwt_secret="a-real-secret",
            _env_file=None,
        )
        assert settings.jwt_secret == "a-real-secret"
