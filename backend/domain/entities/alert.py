"""Alert-Entity — Nutzer-definierte Preis- oder Signal-Alerts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class Alert:
    """Repräsentiert einen konfigurierten Alert für einen Ticker.

    trigger_type:
      SIGNAL_CHANGE — feuert wenn BUY/HOLD/SELL-Signal sich ändert
      PRICE_CHANGE  — feuert wenn Kurs um mehr als `threshold`% ändert (seit Erstellung)

    channel:
      EMAIL   — Benachrichtigung via SendGrid (SENDGRID_API_KEY Env-Variable)
      WEBHOOK — HTTP POST an `target`-URL
    """

    id: UUID
    ticker: str
    trigger_type: Literal["SIGNAL_CHANGE", "PRICE_CHANGE"]
    threshold: float
    channel: Literal["EMAIL", "WEBHOOK"]
    target: str
    is_active: bool
    created_at: datetime
    last_triggered_at: datetime | None
    last_signal: str | None
    baseline_price: float | None
