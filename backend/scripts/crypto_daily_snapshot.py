#!/usr/bin/env python3
"""Krypto Daily Snapshot — läuft täglich via Render Cron.

Berechnet alle 10 Krypto-Signale (inkl. Pattern-Erkennung + LLM-Kurzanalyse)
und persistiert sie in `crypto_signals`. Lauffähig per `python -m backend.scripts.crypto_daily_snapshot`.
"""

from __future__ import annotations

import asyncio
import logging

from backend.application.services.crypto_agent_service import CryptoAgentService
from backend.application.services.crypto_pattern_service import CryptoPatternService
from backend.application.services.crypto_scoring_service import CryptoScoringService
from backend.config import get_settings
from backend.domain.entities.crypto_asset import SUPPORTED_CRYPTOS
from backend.domain.models.crypto_signal_record import CryptoSignalRecord
from backend.domain.services.crypto_scorer import CryptoScorer
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.infrastructure.adapters.yfinance_crypto import YFinanceCryptoAdapter
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.pricing import PRICING
from backend.infrastructure.persistence.repositories.cost_log_repository import (
    SQLACostLogRepository,
)
from backend.infrastructure.persistence.repositories.cron_run_repository import (
    SQLACronRunRepository,
)
from backend.infrastructure.persistence.repositories.crypto_signal_repository import (
    SQLACryptoSignalRepository,
)
from backend.infrastructure.persistence.session import get_session_factory
from backend.interfaces.rest.dependencies import get_anthropic_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("crypto_daily_snapshot")


async def main() -> None:
    settings = get_settings()
    from backend.application.services.cost_tracker import CostTracker

    cost_repo = SQLACostLogRepository(session_factory=get_session_factory())
    cost_tracker = CostTracker(
        repository=cost_repo,
        pricing=PRICING,
        cap_usd=settings.budget_cap_usd,
        threshold=settings.budget_cap_threshold,
    )
    llm_client = LLMClient(
        anthropic=get_anthropic_client(),
        voyage=None,
        cost_tracker=cost_tracker,
        pricing=PRICING,
    )

    log.info("=== Krypto Daily Snapshot gestartet ===")

    session_factory = get_session_factory()
    run_id: str | None = None
    async with session_factory() as log_session:
        log_repo = SQLACronRunRepository(log_session)
        run_id = await log_repo.start_run("crypto_daily")

    scoring_svc = CryptoScoringService(
        cg_adapter=CoinGeckoAdapter(api_key=settings.coingecko_api_key),
        yf_adapter=YFinanceCryptoAdapter(),
        fg_adapter=FearGreedAdapter(),
        scorer=CryptoScorer(),
        pattern_service=CryptoPatternService(),
    )
    pattern_svc = CryptoPatternService()
    agent_svc = CryptoAgentService(llm_client=llm_client)

    try:
        results = await scoring_svc.score_all()
    except Exception:
        log.exception("score_all() fehlgeschlagen")
        if run_id is not None:
            async with session_factory() as log_session:
                log_repo = SQLACronRunRepository(log_session)
                await log_repo.finish_run(run_id, "error", error_msg="score_all() fehlgeschlagen")
        return

    yf_ticker_by_symbol = {c[1].split("-")[0]: c[1] for c in SUPPORTED_CRYPTOS}

    saved = 0
    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        for result in results:
            try:
                yf_ticker = yf_ticker_by_symbol.get(result.ticker, result.ticker)
                patterns, _modifier = await pattern_svc.detect(yf_ticker)
                agent_text = await agent_svc.analyze_brief(result.ticker, result, patterns)

                record = CryptoSignalRecord(
                    ticker=result.ticker,
                    signal=result.signal,
                    score=result.score,
                    components=result.score_components,
                    price_chf=result.price_chf,
                    price_change_24h=result.price_change_24h_pct,
                    fear_greed_value=result.fear_greed_value,
                    rsi_14=result.rsi_14,
                    macd_signal=result.macd_signal,
                    volatility_30d_pct=result.volatility_30d_pct,
                    detected_patterns=result.detected_patterns or patterns,
                    pattern_score=result.pattern_score,
                    agent_analysis=agent_text,
                )
                await repo.save(record)
                saved += 1
                log.info("  OK %s: %s (%.1f)", result.ticker, result.signal, result.score)
            except Exception:
                log.exception("  FEHLER bei %s", result.ticker)
        await session.commit()

    log.info("=== Snapshot fertig: %d/%d gespeichert ===", saved, len(results))

    async with session_factory() as log_session:
        log_repo = SQLACronRunRepository(log_session)
        await log_repo.finish_run(run_id, "ok", records_saved=saved)


if __name__ == "__main__":
    asyncio.run(main())
