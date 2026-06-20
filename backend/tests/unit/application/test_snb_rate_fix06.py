"""Unit-Tests für FIX-06: SNB-Rate aus macro_rates-Tabelle (mit Fallback)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestSnbRateFallback:
    """_snb_rate_on() (Fallback) — Kernlogik muss korrekt sein."""

    def test_rate_before_2022_is_negative(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_on

        assert _snb_rate_on(date(2021, 12, 31)) < 0

    def test_rate_after_first_hike_2022(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_on

        assert _snb_rate_on(date(2022, 10, 1)) == pytest.approx(0.5)

    def test_rate_at_peak_2023(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_on

        assert _snb_rate_on(date(2023, 9, 1)) == pytest.approx(1.75)

    def test_rate_after_cuts_2025(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_on

        assert _snb_rate_on(date(2025, 7, 1)) == pytest.approx(0.0)

    def test_rate_monotone_in_hike_phase(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_on

        r_2022q3 = _snb_rate_on(date(2022, 10, 1))
        r_2023q2 = _snb_rate_on(date(2023, 7, 1))
        assert r_2023q2 > r_2022q3


class TestSnbRateFromDb:
    """_snb_rate_from_db() — liest aus macro_rates, fällt bei leerer DB zurück."""

    @pytest.mark.asyncio
    async def test_returns_none_when_db_unreachable(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_from_db

        with patch(
            "backend.infrastructure.persistence.session.get_session_factory",
            side_effect=Exception("no db"),
        ):
            result = await _snb_rate_from_db(date(2025, 1, 1))
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_rate_from_db_row(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_from_db

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: 1.75

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        with patch(
            "backend.infrastructure.persistence.session.get_session_factory",
            return_value=mock_factory,
        ):
            result = await _snb_rate_from_db(date(2023, 9, 1))

        assert result == pytest.approx(1.75)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_row(self) -> None:
        from backend.application.services.ml_feature_service import _snb_rate_from_db

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        with patch(
            "backend.infrastructure.persistence.session.get_session_factory",
            return_value=mock_factory,
        ):
            result = await _snb_rate_from_db(date(2023, 9, 1))

        assert result is None
