"""Unit-Tests fuer FastAPI-Dependency-Factories.

B2 (PR #64 Deep-Review): Anthropic-SDK muss mit explizitem Timeout und
Retries instanziiert werden (Spec §7 — `timeout=30.0`, `max_retries=3`),
sonst blockiert ein langsam-antwortender Anthropic-Endpoint einen
FastAPI-Worker 10 Minuten (SDK-Default).
"""

from typing import Any
from unittest.mock import patch

import pytest

from backend.config import Settings
from backend.interfaces.rest.dependencies import get_anthropic_client

pytestmark = pytest.mark.unit


def test_get_anthropic_client_uses_timeout_30s_and_max_retries_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # get_anthropic_client is @lru_cache — clear before and after to avoid
    # cross-test contamination.
    get_anthropic_client.cache_clear()
    captured: dict[str, Any] = {}

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        "backend.interfaces.rest.dependencies.anthropic.AsyncAnthropic",
        FakeAsyncAnthropic,
    )
    with patch(
        "backend.interfaces.rest.dependencies.get_settings",
        return_value=Settings(anthropic_api_key="test-key"),
    ):
        get_anthropic_client()

    get_anthropic_client.cache_clear()

    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 30.0
    assert captured["max_retries"] == 3
