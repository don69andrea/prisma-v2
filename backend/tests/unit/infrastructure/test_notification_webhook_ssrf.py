"""Regression: send_webhook re-validiert das Ziel (SSRF, DNS-Rebinding-Schutz)."""

from __future__ import annotations

import socket
from typing import Any

import httpx
import pytest

from backend.infrastructure.adapters import notification_adapter

pytestmark = pytest.mark.unit


def _resolves_to(ip: str) -> Any:
    def _inner(host: str, port: int, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

    return _inner


@pytest.mark.asyncio
async def test_send_webhook_rejects_private_target_without_posting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("169.254.169.254"))

    def _boom(*args: object, **kwargs: object) -> Any:
        raise AssertionError("httpx.AsyncClient darf bei blockiertem Ziel nicht erstellt werden")

    monkeypatch.setattr(httpx, "AsyncClient", _boom)

    result = await notification_adapter.send_webhook(
        "https://metadata.evil.example/hook", {"msg": "x"}
    )
    assert result is False


@pytest.mark.asyncio
async def test_send_webhook_rejects_non_https(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: object, **kwargs: object) -> Any:
        raise AssertionError("kein Request bei http://")

    monkeypatch.setattr(httpx, "AsyncClient", _boom)

    result = await notification_adapter.send_webhook("http://hooks.example.com/x", {"msg": "x"})
    assert result is False
