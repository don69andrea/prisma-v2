"""REST Router: V4-5 Crypto Dashboard API.

Endpoints:
  GET  /api/v1/crypto/{coin}/agent-audit  → AgentAuditResponse
  GET  /api/v1/crypto/{coin}/ohlcv        → OHLCVResponse
  POST /api/v1/crypto/{coin}/confirm      → HitlConfirmResponse (201)

All endpoints are read-only or append-only (HITL confirm only logs decisions).
IRON RULE: No auto-trading logic anywhere in this router.
SELL = cash/exposure 0, never short. UI is read-only.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.adapters.crypto_price_adapter import CryptoPriceAdapter
from backend.infrastructure.persistence.repositories.agent_audit_trail_repository import (
    AgentAuditTrailRepository,
)
from backend.infrastructure.persistence.repositories.hitl_confirmation_repository import (
    HitlConfirmationRepository,
)
from backend.interfaces.rest.dependencies import get_session
from backend.interfaces.rest.schemas.crypto_dashboard import (
    AgentAuditResponse,
    AgentRunDetail,
    HitlConfirmRequest,
    HitlConfirmResponse,
    OHLCVBar,
    OHLCVResponse,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/crypto", tags=["crypto-dashboard"])

# Crypto universe allowlist — coin must appear in this list (without -USD suffix)
_CRYPTO_UNIVERSE_COINS: frozenset[str] = frozenset(
    [
        "BTC",
        "ETH",
        "BNB",
        "SOL",
        "XRP",
        "ADA",
        "AVAX",
        "MATIC",
        "DOT",
        "LINK",
    ]
)


# ---------------------------------------------------------------------------
# Dependency factories (used for testing via dependency_overrides)
# ---------------------------------------------------------------------------


async def get_audit_trail_repo(
    session: AsyncSession = Depends(get_session),
) -> AgentAuditTrailRepository:
    """DI factory for AgentAuditTrailRepository."""
    return AgentAuditTrailRepository(session=session)


async def get_hitl_repo(
    session: AsyncSession = Depends(get_session),
) -> HitlConfirmationRepository:
    """DI factory for HitlConfirmationRepository."""
    return HitlConfirmationRepository(session=session)


async def get_crypto_price_adapter() -> CryptoPriceAdapter:
    """DI factory for CryptoPriceAdapter."""
    return CryptoPriceAdapter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{coin}/agent-audit",
    response_model=AgentAuditResponse,
    summary="Latest agent audit trail entry for a coin",
    description=(
        "Returns the most recent agent_audit_trail row for the given coin. "
        "Parsed as AgentRunDetail (technical/onchain/sentiment/macro/bull/bear/risk). "
        "404 if no audit trail exists for the coin."
    ),
)
async def get_agent_audit(
    coin: str,
    audit_repo: AgentAuditTrailRepository = Depends(get_audit_trail_repo),
) -> AgentAuditResponse:
    """GET /api/v1/crypto/{coin}/agent-audit → AgentAuditResponse."""
    row = await audit_repo.find_latest_by_coin(coin.upper())
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit trail found for {coin.upper()}",
        )
    agent_run = AgentRunDetail.model_validate(row.agent_run)
    return AgentAuditResponse(
        audit_trail_id=row.id,
        coin=row.coin,
        asof=row.asof,
        agent_run=agent_run,
        created_at=row.created_at,
    )


@router.get(
    "/{coin}/ohlcv",
    response_model=OHLCVResponse,
    summary="OHLCV candlestick data for a coin",
    description=(
        "Returns daily OHLCV bars for the given coin via CryptoPriceAdapter (yfinance). "
        "coin must be in the crypto universe (BTC, ETH, BNB, SOL, XRP, ADA, AVAX, MATIC, DOT, LINK). "
        "days: number of calendar days to look back (7–365, default 120). "
        "404 if coin not in universe."
    ),
)
async def get_ohlcv(
    coin: str,
    days: int = Query(default=120, ge=7, le=365),
    adapter: CryptoPriceAdapter = Depends(get_crypto_price_adapter),
) -> OHLCVResponse:
    """GET /api/v1/crypto/{coin}/ohlcv?days=120 → OHLCVResponse."""
    coin_upper = coin.upper()
    if coin_upper not in _CRYPTO_UNIVERSE_COINS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Coin '{coin_upper}' is not in the crypto universe. "
                f"Available: {sorted(_CRYPTO_UNIVERSE_COINS)}"
            ),
        )

    symbol = f"{coin_upper}-USD"
    start = (date.today() - timedelta(days=days)).isoformat()

    try:
        df = await adapter.fetch_ohlcv(symbol=symbol, start=start)
    except Exception as exc:
        _logger.error("fetch_ohlcv failed for %s: %s", symbol, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OHLCV data temporarily unavailable for {coin_upper}.",
        ) from exc

    # yfinance returns date as DatetimeIndex — promote to column so row["date"] works
    df = df.reset_index()
    df = df.rename(columns={"Date": "date", "Datetime": "date"})

    bars = [
        OHLCVBar(
            date=row["date"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for _, row in df.iterrows()
    ]

    return OHLCVResponse(coin=coin_upper, symbol=symbol, bars=bars)


@router.post(
    "/{coin}/confirm",
    response_model=HitlConfirmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a HITL proceed/abort decision",
    description=(
        "Persists a human-in-the-loop decision (proceed/abort) against an agent audit trail entry. "
        "READ-ONLY UI: this endpoint ONLY logs the decision, NEVER triggers trades. "
        "SELL = cash/exposure 0, never short. Append-only log."
    ),
)
async def confirm_hitl(
    coin: str,
    body: HitlConfirmRequest,
    repo: HitlConfirmationRepository = Depends(get_hitl_repo),
) -> HitlConfirmResponse:
    """POST /api/v1/crypto/{coin}/confirm → HitlConfirmResponse (201).

    IRON RULE: this only LOGS the decision. No auto-trading. Ever.
    """
    coin_upper = coin.upper()
    new_id = await repo.insert(
        audit_trail_id=body.audit_trail_id,
        coin=coin_upper,
        decision=body.decision,
    )
    return HitlConfirmResponse(
        id=new_id,
        audit_trail_id=body.audit_trail_id,
        coin=coin_upper,
        decision=body.decision,
        decided_at=datetime.now(tz=UTC),
    )
