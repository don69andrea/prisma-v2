"""Append-only repository for the agent_audit_trail table (D-02).

IMMUTABILITY CONTRACT:
- This repository intentionally exposes ONLY insert() — no update(), no delete(), no save().
- Every agent run creates a new row; rows are never mutated or removed.
- Application-layer enforcement of the D-02 "append-only / immutable" requirement.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.persistence.models.agent_audit_trail import AgentAuditTrailORM


class AgentAuditTrailRepository:
    """Insert-only repository for agent audit trail records.

    Deliberately has NO update(), delete(), or save() method.
    Calling insert() twice with the same coin/asof creates two separate rows —
    this is intentional and required by D-02 (append-only / immutable audit trail).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        coin: str,
        asof: date,
        agent_run: dict,
    ) -> uuid.UUID:
        """Persist a new agent run record and return its generated UUID.

        Args:
            coin: Crypto ticker symbol (e.g. "BTC", "ETH").
            asof: The date for which the agent run was executed.
            agent_run: Arbitrary dict containing all agent outputs:
                {tech_view, onchain_view, senti_view, macro_regime,
                 bull_case, bear_case, risk_verdict, trade_signal}.

        Returns:
            The UUID primary key of the newly inserted row.
        """
        orm = AgentAuditTrailORM(
            coin=coin,
            asof=asof,
            agent_run=agent_run,
        )
        self._session.add(orm)
        await self._session.flush()
        return orm.id
