"""Unit-Tests für sentiment_enabled Settings-Feld (Phase 04-01, D-06).

TDD RED: written before sentiment_enabled exists in config.py.
Verifies:
  - Default is False when SENTIMENT_ENABLED env var not set
  - Reads True when SENTIMENT_ENABLED=true in env
  - Does NOT instantiate Settings() directly — uses direct constructor with _env_file=None
    to isolate from local .env (pattern from test_config.py)
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

        # Build a fresh Settings instance — do NOT use get_settings() (lru_cache singleton)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.sentiment_enabled is True

    def test_reads_false_from_env_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With SENTIMENT_ENABLED=false explicitly, settings.sentiment_enabled is False."""
        monkeypatch.setenv("SENTIMENT_ENABLED", "false")
        from backend.config import Settings

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.sentiment_enabled is False
