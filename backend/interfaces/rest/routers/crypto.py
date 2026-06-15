"""REST-Router für /api/v1/crypto/*."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from backend.application.services.crypto_scoring_service import CryptoScoringService
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.interfaces.rest.dependencies import (
    get_coingecko_adapter,
    get_crypto_scoring_service,
    get_fear_greed_adapter,
)
from backend.interfaces.rest.schemas.crypto import CryptoSignalResponse

router = APIRouter(prefix="/api/v1/crypto", tags=["crypto"])


@router.get("/signals", response_model=list[CryptoSignalResponse])
async def get_crypto_signals(
    service: CryptoScoringService = Depends(get_crypto_scoring_service),
) -> list[CryptoSignalResponse]:
    """PRISMA-Signale für alle 10 unterstützten Kryptowährungen (sortiert nach Score)."""
    signals = await service.score_all()
    return [CryptoSignalResponse.from_domain(s) for s in signals]


@router.get("/signals/{ticker}", response_model=CryptoSignalResponse)
async def get_crypto_signal(
    ticker: str = Path(..., pattern=r"^[A-Z]{2,10}$"),
    service: CryptoScoringService = Depends(get_crypto_scoring_service),
) -> CryptoSignalResponse:
    """Einzelnes Signal für einen Ticker (z.B. BTC, ETH, SOL)."""
    signal = await service.score_one(ticker.upper())
    if signal is None:
        raise HTTPException(status_code=404, detail=f"{ticker} nicht unterstützt oder keine Daten.")
    return CryptoSignalResponse.from_domain(signal)


@router.get("/fear-greed")
async def get_fear_greed(
    adapter: FearGreedAdapter = Depends(get_fear_greed_adapter),
) -> dict:
    """Aktueller Crypto Fear & Greed Index (0–100)."""
    return await adapter.get_current()


@router.get("/market")
async def get_crypto_market(
    cg: CoinGeckoAdapter = Depends(get_coingecko_adapter),
) -> list[dict]:
    """Markt-Übersicht für alle 10 Kryptos: Preis CHF, Market Cap, 24h/7d Änderung."""
    from backend.domain.entities.crypto_asset import SUPPORTED_CRYPTOS
    return await cg.get_market_data([c[0] for c in SUPPORTED_CRYPTOS])
