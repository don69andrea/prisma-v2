"""Unit-Tests für den FastAPI-BudgetCapExceeded-Handler.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §8.

Testet die Handler-Funktion direkt (ohne FastAPI-Request-Loop) — die
Wire-Up via `@app.exception_handler` wird in app.py-Tests separat geprüft.
"""

import json
from decimal import Decimal
from unittest.mock import Mock

import pytest

from backend.domain.errors import BudgetCapExceeded
from backend.interfaces.rest.exception_handlers import handle_budget_cap_exceeded

pytestmark = pytest.mark.unit


def _make_exc(
    *,
    current: str = "99.50",
    attempted: str = "0.60",
    cap: str = "100.00",
) -> BudgetCapExceeded:
    return BudgetCapExceeded(
        current_usd=Decimal(current),
        attempted_usd=Decimal(attempted),
        cap_usd=Decimal(cap),
    )


class TestBudgetCapExceededHandler:
    async def test_status_code_is_402(self) -> None:
        # 402 (Payment Required) — konsistent mit POST /memos/batch.
        # Vorher 503; siehe PR #70 W2 Diskussion.
        response = await handle_budget_cap_exceeded(Mock(), _make_exc())
        assert response.status_code == 402

    async def test_body_contains_structured_error(self) -> None:
        response = await handle_budget_cap_exceeded(Mock(), _make_exc())
        body = json.loads(bytes(response.body).decode())
        assert body["error"] == "budget_cap_exceeded"
        assert "Monatliches AI-Budget erschöpft" in body["message"]
        assert "Reset" in body["message"]

    async def test_body_includes_current_and_cap_amounts(self) -> None:
        exc = _make_exc(current="42.50", cap="100.00")
        response = await handle_budget_cap_exceeded(Mock(), exc)
        body = json.loads(bytes(response.body).decode())
        # Werte werden als Floats serialisiert (JSON kennt kein Decimal).
        # Verlässlichkeit reicht im Cent-Bereich; Backend hat Decimal-Wahrheit
        # in der DB.
        assert body["current_usd"] == pytest.approx(42.50)
        assert body["cap_usd"] == pytest.approx(100.00)

    async def test_retry_after_header_is_positive_integer(self) -> None:
        response = await handle_budget_cap_exceeded(Mock(), _make_exc())
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert retry_after.isdigit()
        seconds = int(retry_after)
        assert seconds > 0

    async def test_retry_after_does_not_exceed_one_month(self) -> None:
        # Maximal-Wert ist Anfang des laufenden Monats — ein Monat = 32 Tage Puffer
        response = await handle_budget_cap_exceeded(Mock(), _make_exc())
        seconds = int(response.headers["Retry-After"])
        max_seconds = 32 * 24 * 60 * 60  # 32 days
        assert seconds < max_seconds
