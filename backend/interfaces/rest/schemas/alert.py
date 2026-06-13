"""Pydantic-Schemas für Alert API."""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# Private / link-local / loopback IPv4 ranges blocked for SSRF protection
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("127.0.0.0/8"),     # loopback
]

# Simple regex to detect bare IPv4 addresses in the hostname
_IPV4_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def _is_private_host(hostname: str) -> bool:
    """Returns True if hostname resolves to a known private/reserved IP range."""
    m = _IPV4_RE.match(hostname)
    if not m:
        return False
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return any(addr in net for net in _BLOCKED_NETWORKS)


class AlertCreateRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    trigger_type: Literal["SIGNAL_CHANGE", "PRICE_CHANGE"]
    threshold: float = Field(default=5.0, ge=0.0, le=100.0)
    channel: Literal["EMAIL", "WEBHOOK"]
    target: str = Field(..., min_length=1, max_length=255)

    @field_validator("ticker")
    @classmethod
    def ticker_upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def validate_webhook_target(self) -> "AlertCreateRequest":
        """For WEBHOOK channel: enforce https:// and block private IP ranges (SSRF prevention)."""
        if self.channel != "WEBHOOK":
            return self
        url = self.target
        if not url.startswith("https://"):
            raise ValueError(
                "Webhook-URL muss mit https:// beginnen (http:// und andere Schemas sind nicht erlaubt)."
            )
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
        except Exception:
            raise ValueError("Ungültige Webhook-URL.")
        if not hostname:
            raise ValueError("Webhook-URL enthält keinen gültigen Hostname.")
        if _is_private_host(hostname):
            raise ValueError(
                "Webhook-URL darf nicht auf private IP-Adressen zeigen "
                "(10.x, 172.16-31.x, 192.168.x, 169.254.x, 127.x sind blockiert)."
            )
        return self


class AlertResponse(BaseModel):
    id: UUID
    ticker: str
    trigger_type: str
    threshold: float
    channel: str
    target: str
    is_active: bool
    created_at: datetime
    last_triggered_at: datetime | None
    last_signal: str | None
    baseline_price: float | None


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]
    total: int
