"""Integration-Tests für SQLACryptoSignalRepository gegen Live-Postgres."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.domain.models.crypto_signal_record import CryptoSignalRecord
from backend.infrastructure.persistence.repositories.crypto_signal_repository import (
    SQLACryptoSignalRepository,
)

pytestmark = [pytest.mark.integration]


@pytest_asyncio.fixture
async def truncate_crypto_signals(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    async with session_factory() as session:
        await session.execute(text("TRUNCATE crypto_signals"))
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(text("TRUNCATE crypto_signals"))
        await session.commit()


def _record(**overrides: Any) -> CryptoSignalRecord:
    defaults = dict(
        ticker="BTC",
        signal="BUY",
        score=72.5,
        components={"momentum": 22.0, "trend": 18.0},
        price_chf=95000.0,
        fear_greed_value=30,
        rsi_14=42.0,
        detected_patterns=["GOLDEN_CROSS"],
        pattern_score=2.5,
    )
    return CryptoSignalRecord(**{**defaults, **overrides})


async def test_save_then_get_history_returns_record(
    session_factory: async_sessionmaker[AsyncSession],
    truncate_crypto_signals: None,
) -> None:
    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        await repo.save(_record())
        await session.commit()

    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        history = await repo.get_history("BTC", days=7)

    assert len(history) == 1
    assert history[0].ticker == "BTC"
    assert history[0].signal == "BUY"
    assert history[0].detected_patterns == ["GOLDEN_CROSS"]


async def test_save_twice_same_day_upserts_instead_of_duplicating(
    session_factory: async_sessionmaker[AsyncSession],
    truncate_crypto_signals: None,
) -> None:
    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        await repo.save(_record(score=50.0))
        await session.commit()

    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        await repo.save(_record(score=80.0, signal="STRONG_BUY"))
        await session.commit()

    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        history = await repo.get_history("BTC", days=7)

    assert len(history) == 1
    assert history[0].score == 80.0
    assert history[0].signal == "STRONG_BUY"


async def test_get_latest_all_returns_one_per_ticker(
    session_factory: async_sessionmaker[AsyncSession],
    truncate_crypto_signals: None,
) -> None:
    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        await repo.save(_record(ticker="BTC"))
        await repo.save(_record(ticker="ETH", signal="HOLD", score=55.0))
        await session.commit()

    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        latest = await repo.get_latest_all()

    tickers = {r.ticker for r in latest}
    assert tickers == {"BTC", "ETH"}


async def test_get_history_respects_days_window(
    session_factory: async_sessionmaker[AsyncSession],
    truncate_crypto_signals: None,
) -> None:
    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        await repo.save(_record(ticker="SOL"))
        await session.commit()

    async with session_factory() as session:
        repo = SQLACryptoSignalRepository(session)
        history = await repo.get_history("SOL", days=30)
        empty_for_other_ticker = await repo.get_history("ADA", days=30)

    assert len(history) == 1
    assert empty_for_other_ticker == []
