"""Unit-Tests für den SSRF-Guard (H-01)."""

from __future__ import annotations

import socket
from collections.abc import Callable

import pytest

from backend.infrastructure.security.ssrf import (
    SSRFValidationError,
    is_public_https_url,
    validate_public_https_url,
)

pytestmark = pytest.mark.unit


def _fake_getaddrinfo(*ips: str) -> Callable[..., list[tuple[object, ...]]]:
    """Erzeugt einen getaddrinfo-Ersatz, der genau die angegebenen IPs liefert."""

    def _inner(host: str, port: int, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        out: list[tuple[object, ...]] = []
        for ip in ips:
            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            sockaddr: tuple[object, ...] = (ip, port, 0, 0) if ":" in ip else (ip, port)
            out.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
        return out

    return _inner


def test_public_host_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    validate_public_https_url("https://example.com/webhook")
    assert is_public_https_url("https://example.com/webhook") is True


def test_non_https_rejected() -> None:
    with pytest.raises(SSRFValidationError):
        validate_public_https_url("http://example.com/webhook")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.1.2.3",  # RFC-1918
        "172.16.5.5",  # RFC-1918
        "192.168.1.1",  # RFC-1918
        "169.254.169.254",  # link-local / AWS-GCP metadata
        "0.0.0.0",  # unspecified
    ],
)
def test_dns_name_resolving_to_private_ipv4_rejected(
    ip: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(ip))
    with pytest.raises(SSRFValidationError):
        validate_public_https_url("https://evil.example.com/webhook")


@pytest.mark.parametrize("ip", ["::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1"])
def test_ipv6_private_rejected(ip: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(ip))
    with pytest.raises(SSRFValidationError):
        validate_public_https_url("https://evil.example.com/webhook")


def test_any_private_ip_in_resolution_set_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auch wenn nur EINE aufgelöste IP privat ist, wird abgelehnt (Rebinding)."""
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34", "127.0.0.1"))
    with pytest.raises(SSRFValidationError):
        validate_public_https_url("https://mixed.example.com/webhook")


def test_encoded_ipv4_literal_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dezimal-kodierte Loopback-IP (2130706433 == 127.0.0.1) wird via Resolver normalisiert."""
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(SSRFValidationError):
        validate_public_https_url("https://2130706433/webhook")


def test_unresolvable_host_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    with pytest.raises(SSRFValidationError):
        validate_public_https_url("https://does-not-exist.invalid/webhook")
