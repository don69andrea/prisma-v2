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

    def test_raises_when_api_key_empty_in_production(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment="production", api_key="", _env_file=None)  # type: ignore[call-arg]
        assert "API_KEY" in str(exc_info.value)

    def test_passes_when_api_key_set_in_production(self) -> None:
        settings = Settings(environment="production", api_key="secret", _env_file=None)  # type: ignore[call-arg]
        assert settings.api_key == "secret"

    def test_passes_in_development_without_api_key(self) -> None:
        settings = Settings(environment="development", api_key="", _env_file=None)  # type: ignore[call-arg]
        assert settings.api_key == ""
