"""Unit-Tests für MLFeatureService."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.application.services.ml_feature_service import (
    MLFeatureService,
    _compute_rsi,
    _score_wachstum,
    _snb_rate_on,
)
from backend.domain.value_objects.ml_feature_vector import MLFeatureVector
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals
from backend.domain.value_objects.swiss_quant_score import SwissQuantScore

# ---------------------------------------------------------------------------
# SNB Rate Lookup
# ---------------------------------------------------------------------------


def test_snb_rate_before_2022() -> None:
    assert _snb_rate_on(date(2021, 6, 1)) == -0.75


def test_snb_rate_first_hike() -> None:
    assert _snb_rate_on(date(2022, 10, 1)) == 0.5


def test_snb_rate_peak() -> None:
    # Nach Juni 2023: 1.75%
    assert _snb_rate_on(date(2023, 8, 1)) == 1.75


def test_snb_rate_zero_2025() -> None:
    assert _snb_rate_on(date(2025, 7, 1)) == 0.0


# ---------------------------------------------------------------------------
# RSI Berechnung
# ---------------------------------------------------------------------------


def test_compute_rsi_uptrend() -> None:
    """RSI bei steigendem Markt sollte > 50 sein."""
    prices = pd.Series(list(range(50, 80)))
    rsi = _compute_rsi(prices)
    assert 60.0 < rsi <= 100.0


def test_compute_rsi_downtrend() -> None:
    """RSI bei fallendem Markt sollte < 50 sein."""
    prices = pd.Series(list(range(80, 50, -1)))
    rsi = _compute_rsi(prices)
    assert 0.0 <= rsi < 45.0


def test_compute_rsi_flat_returns_50() -> None:
    """Flache Preisserie → kein avg_loss → Fallback 50."""
    prices = pd.Series([100.0] * 30)
    rsi = _compute_rsi(prices)
    assert rsi == 50.0


def test_compute_rsi_too_short_returns_50() -> None:
    prices = pd.Series([100.0, 101.0, 99.0])
    rsi = _compute_rsi(prices, window=14)
    assert rsi == 50.0


# ---------------------------------------------------------------------------
# score_wachstum
# ---------------------------------------------------------------------------


def test_score_wachstum_no_eps_none() -> None:
    f = SwissFundamentals(market_cap_chf=None, pe_ratio=15.0, pb_ratio=None, dividend_yield=None, eps_chf=None)
    assert _score_wachstum(f) == 50.0


def test_score_wachstum_negative_eps() -> None:
    f = SwissFundamentals(market_cap_chf=None, pe_ratio=None, pb_ratio=None, dividend_yield=None, eps_chf=-1.0)
    assert _score_wachstum(f) == 10.0


def test_score_wachstum_value_stock() -> None:
    f = SwissFundamentals(market_cap_chf=None, pe_ratio=12.0, pb_ratio=None, dividend_yield=None, eps_chf=5.0)
    assert _score_wachstum(f) == 70.0


def test_score_wachstum_expensive() -> None:
    f = SwissFundamentals(market_cap_chf=None, pe_ratio=45.0, pb_ratio=None, dividend_yield=None, eps_chf=2.0)
    assert _score_wachstum(f) == 40.0


# ---------------------------------------------------------------------------
# build_features (async, mit Mocks)
# ---------------------------------------------------------------------------


def _make_score() -> SwissQuantScore:
    return SwissQuantScore(
        ticker="NESN",
        value_score=60.0,
        income_score=55.0,
        quality_score=70.0,
        composite=61.7,
        signal="HOLD",
    )


def _make_prices() -> pd.DataFrame:
    idx = pd.date_range(end=date.today(), periods=400, freq="B")
    prices = 100.0 + np.cumsum(np.random.randn(400))
    return pd.DataFrame({"Close": prices, "Volume": 1_000_000}, index=idx)


@pytest.mark.asyncio
async def test_build_features_happy_path() -> None:
    """build_features gibt MLFeatureVector zurück bei korrekten Mocks."""
    fundamentals = SwissFundamentals(
        market_cap_chf=Decimal("50000000000"),
        pe_ratio=18.0,
        pb_ratio=2.5,
        dividend_yield=0.025,
        eps_chf=8.0,
    )
    adapter_mock = AsyncMock()
    adapter_mock.get_fundamentals.return_value = fundamentals
    adapter_mock.get_price_history.return_value = _make_prices()

    scorer_mock = MagicMock()
    scorer_mock.score.return_value = _make_score()

    with patch("backend.application.services.ml_feature_service._current_chf_eur", return_value=0.93):
        service = MLFeatureService(yfinance_adapter=adapter_mock, scorer=scorer_mock)
        result = await service.build_features("NESN")

    assert isinstance(result, MLFeatureVector)
    assert result.ticker == "NESN"
    assert result.quant_score == 61.7
    assert result.score_rendite == 55.0
    assert result.score_sicherheit == 70.0
    assert result.score_substanz == 60.0
    assert result.score_wachstum == 60.0  # pe=18 → bracket <25
    assert result.chf_eur == 0.93
    assert result.target_class is None
    assert result.forward_return_12m is None


@pytest.mark.asyncio
async def test_build_features_returns_none_on_adapter_error() -> None:
    adapter_mock = AsyncMock()
    adapter_mock.get_fundamentals.side_effect = RuntimeError("network error")

    service = MLFeatureService(yfinance_adapter=adapter_mock)
    result = await service.build_features("FAIL")
    assert result is None


@pytest.mark.asyncio
async def test_build_features_returns_none_on_empty_prices() -> None:
    fundamentals = SwissFundamentals(
        market_cap_chf=None, pe_ratio=None, pb_ratio=None, dividend_yield=None, eps_chf=None
    )
    adapter_mock = AsyncMock()
    adapter_mock.get_fundamentals.return_value = fundamentals
    adapter_mock.get_price_history.return_value = pd.DataFrame()  # leer

    scorer_mock = MagicMock()
    scorer_mock.score.return_value = _make_score()

    service = MLFeatureService(yfinance_adapter=adapter_mock, scorer=scorer_mock)
    result = await service.build_features("EMPTY")
    assert result is None


# ---------------------------------------------------------------------------
# MLFeatureVector: to_feature_dict
# ---------------------------------------------------------------------------


def test_feature_vector_to_feature_dict() -> None:
    fv = MLFeatureVector(
        ticker="NESN",
        snapshot_date=date(2024, 1, 15),
        quant_score=65.0,
        score_rendite=55.0,
        score_sicherheit=70.0,
        score_wachstum=60.0,
        score_substanz=60.0,
        return_12m=0.12,
        vol_30d=0.18,
        rsi_14=55.0,
        snb_rate=1.0,
        chf_eur=0.93,
        forward_return_12m=None,
        target_class=None,
    )
    d = fv.to_feature_dict()
    assert set(d.keys()) == set(MLFeatureVector.FEATURE_NAMES)
    assert d["quant_score"] == 65.0
    assert "ticker" not in d
    assert "target_class" not in d
    assert "forward_return_12m" not in d
