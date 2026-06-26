"""Smoke-Test für backend/scripts/crypto_daily_snapshot.py — alle externen
I/O-Punkte (yfinance, CoinGecko, Fear&Greed, Anthropic, DB) sind gemockt.
Kein echter Netzwerk-/LLM-Call — verifiziert nur die Orchestrierung.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from backend.application.services.crypto_agent_service import CryptoAgentService
from backend.application.services.crypto_pattern_service import CryptoPatternService
from backend.application.services.crypto_scoring_service import CryptoScoringService
from backend.domain.value_objects.crypto_signal import CryptoSignal
from backend.infrastructure.persistence.repositories.crypto_signal_repository import (
    SQLACryptoSignalRepository,
)

_MODULE = "backend.scripts.crypto_daily_snapshot"


def _fake_signal(ticker: str = "BTC") -> CryptoSignal:
    return CryptoSignal(
        ticker=ticker,
        name="Bitcoin",
        signal="BUY",
        score=72.0,
        score_components={
            "momentum": 20.0,
            "trend": 18.0,
            "sentiment": 14.0,
            "markt": 8.0,
            "risiko": 5.0,
        },
        signal_reason_de="Test.",
        fear_greed_value=30,
        fear_greed_label="Fear",
        rsi_14=40.0,
        macd_signal="bullish",
        volatility_30d_pct=45.0,
        correlation_smi_1y=0.1,
        has_six_etp=True,
        price_chf=90000.0,
        market_cap_chf=1e12,
        price_change_24h_pct=1.0,
        price_change_7d_pct=5.0,
        ath_change_pct=-20.0,
        market_cap_rank=1,
        timestamp=datetime.now(tz=UTC),
        detected_patterns=["GOLDEN_CROSS"],
        pattern_score=2.5,
    )


async def test_main_saves_one_record_per_signal() -> None:
    import backend.scripts.crypto_daily_snapshot as mod

    fake_session = AsyncMock()
    fake_session.__aenter__.return_value = fake_session
    fake_session.__aexit__.return_value = None

    saved_records: list[Any] = []

    async def _fake_save(record: Any) -> None:
        saved_records.append(record)

    mock_cron_repo = AsyncMock()
    mock_cron_repo.start_run.return_value = "mock-run-id"

    with (
        patch(f"{_MODULE}.get_anthropic_client", return_value=AsyncMock()),
        patch(f"{_MODULE}.SQLACostLogRepository", return_value=AsyncMock()),
        patch("backend.application.services.cost_tracker.CostTracker") as MockCostTracker,
        patch(f"{_MODULE}.SQLACronRunRepository", return_value=mock_cron_repo),
        patch.object(
            CryptoScoringService,
            "score_all",
            AsyncMock(return_value=[_fake_signal("BTC"), _fake_signal("ETH")]),
        ),
        patch.object(
            CryptoPatternService,
            "detect",
            AsyncMock(return_value=(["GOLDEN_CROSS"], 2.5)),
        ),
        patch.object(CryptoAgentService, "analyze_brief", AsyncMock(return_value="Kurzanalyse.")),
        patch(f"{_MODULE}.get_session_factory", return_value=lambda: fake_session),
        patch.object(SQLACryptoSignalRepository, "save", AsyncMock(side_effect=_fake_save)),
    ):
        MockCostTracker.return_value = AsyncMock()
        await mod.main()

    assert len(saved_records) == 2
    assert {r.ticker for r in saved_records} == {"BTC", "ETH"}
    assert saved_records[0].agent_analysis == "Kurzanalyse."
    fake_session.commit.assert_awaited_once()


async def test_main_continues_after_one_ticker_fails() -> None:
    import backend.scripts.crypto_daily_snapshot as mod

    fake_session = AsyncMock()
    fake_session.__aenter__.return_value = fake_session
    fake_session.__aexit__.return_value = None

    call_count = {"n": 0}

    async def _flaky_save(record: Any) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("DB hiccup")

    mock_cron_repo = AsyncMock()
    mock_cron_repo.start_run.return_value = "mock-run-id"

    with (
        patch(f"{_MODULE}.get_anthropic_client", return_value=AsyncMock()),
        patch(f"{_MODULE}.SQLACostLogRepository", return_value=AsyncMock()),
        patch("backend.application.services.cost_tracker.CostTracker") as MockCostTracker,
        patch(f"{_MODULE}.SQLACronRunRepository", return_value=mock_cron_repo),
        patch.object(
            CryptoScoringService,
            "score_all",
            AsyncMock(return_value=[_fake_signal("BTC"), _fake_signal("ETH")]),
        ),
        patch.object(CryptoPatternService, "detect", AsyncMock(return_value=([], 0.0))),
        patch.object(CryptoAgentService, "analyze_brief", AsyncMock(return_value="")),
        patch(f"{_MODULE}.get_session_factory", return_value=lambda: fake_session),
        patch.object(SQLACryptoSignalRepository, "save", AsyncMock(side_effect=_flaky_save)),
    ):
        MockCostTracker.return_value = AsyncMock()
        await mod.main()  # must not raise

    assert call_count["n"] == 2
