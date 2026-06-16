"""REST-Router für /api/v1/crypto/*."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from backend.application.services.crypto_agent_service import CryptoAgentService
from backend.application.services.crypto_pattern_service import CryptoPatternService
from backend.application.services.crypto_scoring_service import CryptoScoringService
from backend.domain.repositories.crypto_signal_repository import CryptoSignalRepository
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.interfaces.rest.dependencies import (
    get_coingecko_adapter,
    get_crypto_agent_service,
    get_crypto_pattern_service,
    get_crypto_scoring_service,
    get_crypto_signal_repository,
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
) -> dict[str, Any]:
    """Aktueller Crypto Fear & Greed Index (0–100)."""
    return await adapter.get_current()


@router.get("/market")
async def get_crypto_market(
    cg: CoinGeckoAdapter = Depends(get_coingecko_adapter),
) -> list[dict[str, Any]]:
    """Markt-Übersicht für alle 10 Kryptos: Preis CHF, Market Cap, 24h/7d Änderung."""
    from backend.domain.entities.crypto_asset import SUPPORTED_CRYPTOS

    return await cg.get_market_data([c[0] for c in SUPPORTED_CRYPTOS])


@router.get("/history/{ticker}", summary="Signal-History (letzte N Tage)")
async def get_signal_history(
    ticker: str = Path(..., pattern=r"^[A-Z]{2,10}$"),
    days: int = Query(default=30, ge=1, le=365),
    repo: CryptoSignalRepository = Depends(get_crypto_signal_repository),
) -> list[dict[str, Any]]:
    records = await repo.get_history(ticker.upper(), days=days)
    return [
        {
            "date": r.created_at.date().isoformat() if r.created_at else None,
            "signal": r.signal,
            "score": round(r.score, 1),
            "price_chf": r.price_chf,
            "fear_greed_value": r.fear_greed_value,
            "rsi_14": round(r.rsi_14, 1) if r.rsi_14 is not None else None,
            "detected_patterns": r.detected_patterns,
            "pattern_score": r.pattern_score,
        }
        for r in records
    ]


@router.get("/history", summary="Letzter Signal-Stand aller Ticker")
async def get_latest_signals_overview(
    repo: CryptoSignalRepository = Depends(get_crypto_signal_repository),
) -> list[dict[str, Any]]:
    records = await repo.get_latest_all()
    return [
        {
            "ticker": r.ticker,
            "signal": r.signal,
            "score": round(r.score, 1),
            "price_chf": r.price_chf,
            "price_change_24h": r.price_change_24h,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "detected_patterns": r.detected_patterns,
            "agent_analysis": r.agent_analysis,
        }
        for r in records
    ]


@router.post(
    "/analyze/{ticker}",
    summary="Agent-Chartanalyse (SSE-Stream)",
    description=(
        "Streamt eine 2-Satz deutsche KI-Kurzanalyse zum aktuellen Signal + erkannten "
        "Patterns eines Tickers. Frontend: EventSource('/api/v1/crypto/analyze/BTC')."
    ),
)
async def analyze_ticker_stream(
    ticker: str = Path(..., pattern=r"^[A-Z]{2,10}$"),
    scoring_service: CryptoScoringService = Depends(get_crypto_scoring_service),
    pattern_service: CryptoPatternService = Depends(get_crypto_pattern_service),
    agent_service: CryptoAgentService = Depends(get_crypto_agent_service),
) -> StreamingResponse:
    ticker_upper = ticker.upper()

    signal = await scoring_service.score_one(ticker_upper)
    signal_data: dict[str, Any] = {}
    patterns: list[str] = []
    if signal is not None:
        signal_data = {
            "signal": signal.signal,
            "score": signal.score,
            "rsi_14": signal.rsi_14,
            "macd_signal": signal.macd_signal,
            "fear_greed_value": signal.fear_greed_value,
        }
        patterns = signal.detected_patterns
    else:
        # Kein Live-Signal verfügbar (z.B. yfinance down) — Pattern-Detection
        # läuft trotzdem separat, damit der Agent nicht komplett leer dasteht.
        from backend.domain.entities.crypto_asset import SUPPORTED_CRYPTOS

        yf_ticker = next((c[1] for c in SUPPORTED_CRYPTOS if c[1].startswith(ticker_upper)), None)
        if yf_ticker:
            patterns, _ = await pattern_service.detect(yf_ticker)

    async def event_stream() -> AsyncIterator[str]:
        async for chunk in agent_service.stream_analysis(ticker_upper, signal_data, patterns):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
