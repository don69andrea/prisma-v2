from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_snapshot_saves_one_record_per_signal():
    """main() soll für jedes erfolgreich berechnete Signal ein Record speichern."""
    from backend.domain.value_objects.decision_signal import DecisionSignal

    mock_signal = DecisionSignal(
        ticker="NESN",
        snapshot_date=date(2026, 6, 17),
        signal="BUY",
        confidence=0.72,
        weighted_score=72.0,
        quant_score=68.0,
        ml_score=80.0,
        macro_score=65.0,
        is_3a_eligible=True,
    )

    with (
        patch("backend.scripts.stock_daily_snapshot.SignalAggregationService") as MockSvc,
        patch("backend.scripts.stock_daily_snapshot.get_session_factory") as MockFactory,
        patch("backend.scripts.stock_daily_snapshot.SQLAStockSignalRepository") as MockRepo,
        patch("backend.scripts.stock_daily_snapshot.SQLACronRunRepository") as MockCronRepo,
    ):
        mock_svc = AsyncMock()
        mock_svc.get_signals = AsyncMock(return_value=[mock_signal])
        MockSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        MockFactory.return_value = MagicMock(return_value=mock_session)

        mock_repo = AsyncMock()
        mock_repo.save = AsyncMock()
        MockRepo.return_value = mock_repo

        mock_cron_repo = AsyncMock()
        mock_cron_repo.start_run = AsyncMock(return_value="run-123")
        mock_cron_repo.finish_run = AsyncMock()
        MockCronRepo.return_value = mock_cron_repo

        from backend.scripts.stock_daily_snapshot import main

        await main()

        mock_repo.save.assert_awaited_once()
        mock_cron_repo.start_run.assert_awaited_once()
        mock_cron_repo.finish_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_snapshot_continues_after_one_ticker_fails():
    """Ein fehlgeschlagener Ticker darf den ganzen Snapshot nicht abbrechen."""
    from backend.domain.value_objects.decision_signal import DecisionSignal

    mock_signals = [
        DecisionSignal("NESN", date(2026, 6, 17), "BUY", 0.72, 72.0, 68.0, 80.0, 65.0, True),
        DecisionSignal("NOVN", date(2026, 6, 17), "HOLD", 0.50, 50.0, 52.0, 48.0, 50.0, False),
    ]

    with (
        patch("backend.scripts.stock_daily_snapshot.SignalAggregationService") as MockSvc,
        patch("backend.scripts.stock_daily_snapshot.get_session_factory") as MockFactory,
        patch("backend.scripts.stock_daily_snapshot.SQLAStockSignalRepository") as MockRepo,
        patch("backend.scripts.stock_daily_snapshot.SQLACronRunRepository") as MockCronRepo,
    ):
        mock_svc = AsyncMock()
        mock_svc.get_signals = AsyncMock(return_value=mock_signals)
        MockSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        MockFactory.return_value = MagicMock(return_value=mock_session)

        mock_repo = AsyncMock()
        mock_repo.save = AsyncMock(side_effect=[Exception("DB-Fehler"), None])
        MockRepo.return_value = mock_repo

        mock_cron_repo = AsyncMock()
        mock_cron_repo.start_run = AsyncMock(return_value="run-456")
        mock_cron_repo.finish_run = AsyncMock()
        MockCronRepo.return_value = mock_cron_repo

        from backend.scripts.stock_daily_snapshot import main

        await main()

        assert mock_repo.save.await_count == 2
        mock_cron_repo.finish_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_snapshot_aborts_gracefully_when_get_signals_fails():
    """Wenn get_signals() wirft, soll main() ohne Exception beenden."""
    with (
        patch("backend.scripts.stock_daily_snapshot.SignalAggregationService") as MockSvc,
        patch("backend.scripts.stock_daily_snapshot.get_session_factory") as MockFactory,
        patch("backend.scripts.stock_daily_snapshot.SQLACronRunRepository") as MockCronRepo,
    ):
        mock_svc = AsyncMock()
        mock_svc.get_signals = AsyncMock(side_effect=RuntimeError("yFinance down"))
        MockSvc.return_value = mock_svc

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        MockFactory.return_value = MagicMock(return_value=mock_session)

        mock_cron_repo = AsyncMock()
        mock_cron_repo.start_run = AsyncMock(return_value="run-789")
        mock_cron_repo.finish_run = AsyncMock()
        MockCronRepo.return_value = mock_cron_repo

        from backend.scripts.stock_daily_snapshot import main

        # Should not raise
        await main()

        # Should call finish_run with error status
        mock_cron_repo.finish_run.assert_awaited_once()
