"""Notification-Adapter: E-Mail via SendGrid API + Webhook via httpx."""

from __future__ import annotations

import logging
import os

import httpx

_logger = logging.getLogger(__name__)

_SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"
_FROM_EMAIL = "alerts@prisma-v2.app"
_TIMEOUT = 10.0

# Bekannte Platzhalter-Werte, die in .env-Templates oder Demo-Setups vorkommen.
# Ein Key aus dieser Menge löst denselben graceful-Skip aus wie ein leerer Key.
_PLACEHOLDER_KEYS = {"your-sendgrid-key", "your-key", "placeholder", "change-me"}


async def send_email(to: str, subject: str, body: str) -> bool:
    """Sendet E-Mail via SendGrid. Gibt True zurück wenn erfolgreich."""
    api_key = os.environ.get("SENDGRID_API_KEY", "")
    if not api_key or api_key.lower() in _PLACEHOLDER_KEYS:
        _logger.warning("SENDGRID_API_KEY nicht konfiguriert — E-Mail nicht gesendet an %s", to)
        return False

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": _FROM_EMAIL},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _SENDGRID_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code in (200, 202):
                return True
            _logger.warning("SendGrid HTTP %d für %s", resp.status_code, to)
            return False
    except httpx.TimeoutException:
        _logger.warning("SendGrid Timeout für %s", to)
        return False
    except Exception:
        _logger.exception("SendGrid Fehler für %s", to)
        return False


async def send_webhook(url: str, payload: dict[str, object]) -> bool:
    """Sendet HTTP POST an Webhook-URL. Gibt True zurück wenn 2xx."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if 200 <= resp.status_code < 300:
                return True
            _logger.warning("Webhook HTTP %d für %s", resp.status_code, url)
            return False
    except httpx.TimeoutException:
        _logger.warning("Webhook Timeout für %s", url)
        return False
    except Exception:
        _logger.exception("Webhook Fehler für %s", url)
        return False
