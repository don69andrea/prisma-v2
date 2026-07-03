"""Unit-Tests: AlertCreateRequest-Webhook-Validierung nutzt den SSRF-Guard (H-01)."""

from __future__ import annotations

import socket
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from backend.interfaces.rest.schemas.alert import AlertCreateRequest

pytestmark = pytest.mark.unit


def _fake_getaddrinfo(ip: str) -> Callable[..., list[tuple[object, ...]]]:
    def _inner(host: str, port: int, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

    return _inner


def _webhook(target: str) -> AlertCreateRequest:
    return AlertCreateRequest(
        ticker="NESN",
        trigger_type="PRICE_CHANGE",
        threshold=5.0,
        channel="WEBHOOK",
        target=target,
    )


def test_email_channel_skips_ssrf_check() -> None:
    req = AlertCreateRequest(
        ticker="NESN",
        trigger_type="PRICE_CHANGE",
        threshold=5.0,
        channel="EMAIL",
        target="user@example.com",
    )
    assert req.channel == "EMAIL"


def test_public_webhook_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    req = _webhook("https://hooks.example.com/abc")
    assert req.target == "https://hooks.example.com/abc"


def test_http_webhook_rejected() -> None:
    with pytest.raises(ValidationError):
        _webhook("http://hooks.example.com/abc")


def test_private_resolving_webhook_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254"))
    with pytest.raises(ValidationError):
        _webhook("https://metadata.evil.example/latest")
