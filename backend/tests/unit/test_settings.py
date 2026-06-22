"""Unit-Tests für sentiment_enabled Settings-Feld (Phase 04, D-06 / REQ-4-09).

Verifies:
  - Default is False when SENTIMENT_ENABLED env var not set
  - Reads True when SENTIMENT_ENABLED=true in env
  - Reads False when SENTIMENT_ENABLED=false in env
  - Does NOT use get_settings() singleton — uses direct constructor with _env_file=None
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSentimentEnabledSetting:
    """sentiment_enabled must default False and read SENTIMENT_ENABLED env var (D-06)."""

    def test_default_is_false_when_env_unset(self) -> None:
        """With SENTIMENT_ENABLED unset, settings.sentiment_enabled is False."""
        from backend.config import Settings

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.sentiment_enabled is False

    def test_reads_true_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With SENTIMENT_ENABLED=true in env, Settings reads sentiment_enabled True (D-06)."""
        monkeypatch.setenv("SENTIMENT_ENABLED", "true")
        from backend.config import Settings

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.sentiment_enabled is True

    def test_reads_false_from_env_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With SENTIMENT_ENABLED=false explicitly, settings.sentiment_enabled is False."""
        monkeypatch.setenv("SENTIMENT_ENABLED", "false")
        from backend.config import Settings

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.sentiment_enabled is False

    def test_sentiment_enabled_field_exists(self) -> None:
        """Settings class must have a sentiment_enabled field."""
        from backend.config import Settings

        assert "sentiment_enabled" in Settings.model_fields
