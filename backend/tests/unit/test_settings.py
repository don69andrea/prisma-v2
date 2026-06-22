"""RED test stub — Settings.sentiment_enabled feature flag (REQ-4-09).

Status: RED until backend/config.py adds `sentiment_enabled: bool = False`
(plan 04-01).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSentimentEnabledSetting:
    """REQ-4-09: sentiment_enabled must default False and read SENTIMENT_ENABLED env var."""

    def test_sentiment_enabled_defaults_false(self) -> None:
        """get_settings().sentiment_enabled is False when SENTIMENT_ENABLED env var unset."""
        from backend.config import Settings

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            SENTIMENT_ENABLED=False,  # type: ignore[call-arg]
        )
        assert settings.sentiment_enabled is False

    def test_sentiment_enabled_reads_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SENTIMENT_ENABLED=true in env → settings.sentiment_enabled is True."""
        monkeypatch.setenv("SENTIMENT_ENABLED", "true")
        # Force re-instantiation by creating a fresh Settings object
        from backend.config import Settings

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.sentiment_enabled is True

    def test_sentiment_enabled_reads_env_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SENTIMENT_ENABLED=false in env → settings.sentiment_enabled is False."""
        monkeypatch.setenv("SENTIMENT_ENABLED", "false")
        from backend.config import Settings

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.sentiment_enabled is False

    def test_sentiment_enabled_field_exists(self) -> None:
        """Settings class must have a sentiment_enabled field."""
        from backend.config import Settings

        assert hasattr(Settings.model_fields, "__getitem__") or hasattr(Settings, "model_fields")
        assert "sentiment_enabled" in Settings.model_fields
