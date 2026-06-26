"""Append-only repository for the hitl_confirmations table.

IMMUTABILITY CONTRACT:
- Exposes ONLY insert() — no update(), no delete(), no save().
- HITL decisions are logged; they never trigger trades.
- Multiple rows per audit_trail_id are intentional (audit log semantics).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.persistence.models.hitl_confirmation import HitlConfirmationORM


class HitlConfirmationRepository:
    """Insert-only repository for HITL decision records.

    Deliberately has NO update(), delete(), or save() method.
    SELL = cash/exposure 0 — never short. UI is read-only.
    This repository ONLY logs decisions, never triggers trading.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        audit_trail_id: uuid.UUID,
        coin: str,
        decision: str,
    ) -> uuid.UUID:
        """Persist a new HITL decision and return its generated UUID.

        Args:
            audit_trail_id: UUID of the agent_audit_trail row this decision references.
            coin: Crypto ticker symbol (e.g. "BTC", "ETH").
            decision: Either "proceed" or "abort".

        Returns:
            The UUID primary key of the newly inserted row.
        """
        orm = HitlConfirmationORM(
            audit_trail_id=audit_trail_id,
            coin=coin,
            decision=decision,
        )
        self._session.add(orm)
        await self._session.flush()
        return orm.id
