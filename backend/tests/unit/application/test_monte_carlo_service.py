"""Unit-Tests für MonteCarloService."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.application.services.monte_carlo_service import (
    HoldingWeight,
    MonteCarloInput,
    MonteCarloResult,
    MonteCarloService,
    _fetch_ticker_params,
    build_interpretation,
    run_gbm,
)

pytestmark = pytest.mark.unit


def _make_input(**kwargs: Any) -> MonteCarloInput:
    defaults: dict[str, Any] = dict(
        holdings=[HoldingWeight("NESN.SW", 0.6), HoldingWeight("NOVN.SW", 0.4)],
        monthly_contribution=588.0,
        years=30,
        initial_value=0.0,
        n_simulations=100,
    )
    defaults.update(kwargs)
    return MonteCarloInput(**defaults)


def _mock_params(n: int = 2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.array([0.0005] * n),
        np.array([0.012] * n),
        np.eye(n),
    )


@pytest.mark.asyncio
async def test_simulate_returns_correct_shape() -> None:
    svc = MonteCarloService()
    inp = _make_input(years=5, n_simulations=50)
    with patch.object(
        svc, "_fetch_return_params", new_callable=AsyncMock, return_value=_mock_params(2)
    ):
        result = await svc.simulate(inp)
    assert isinstance(result, MonteCarloResult)
    assert len(result.p5) == 60
    assert len(result.p50) == 60
    assert len(result.p95) == 60
    assert len(result.final_distribution) == 50
    assert result.months == 60
    assert result.contribution_total == pytest.approx(588.0 * 60)


@pytest.mark.asyncio
async def test_p5_le_p50_le_p95() -> None:
    svc = MonteCarloService()
    inp = _make_input(holdings=[HoldingWeight("NESN.SW", 1.0)], years=3, n_simulations=200)
    with patch.object(
        svc, "_fetch_return_params", new_callable=AsyncMock, return_value=_mock_params(1)
    ):
        result = await svc.simulate(inp)
    for p5, p50, p95 in zip(result.p5, result.p50, result.p95, strict=True):
        assert p5 <= p50 <= p95


@pytest.mark.asyncio
async def test_weights_not_summing_to_one_raises() -> None:
    svc = MonteCarloService()
    inp = MonteCarloInput(
        holdings=[HoldingWeight("NESN.SW", 0.6)],
        monthly_contribution=500.0,
        years=5,
        n_simulations=50,
    )
    with pytest.raises(ValueError, match="Gewichte"):
        await svc.simulate(inp)


@pytest.mark.asyncio
async def test_prob_bounds() -> None:
    svc = MonteCarloService()
    inp = _make_input(years=1, n_simulations=100)
    with patch.object(
        svc, "_fetch_return_params", new_callable=AsyncMock, return_value=_mock_params(2)
    ):
        result = await svc.simulate(inp)
    assert 0.0 <= result.prob_positive_return <= 1.0
    assert 0.0 <= result.prob_500k <= 1.0


def test_run_gbm_single_asset() -> None:
    inp = _make_input(holdings=[HoldingWeight("X", 1.0)], years=1, n_simulations=50)
    mu = np.array([0.0003])
    sigma = np.array([0.01])
    corr = np.array([[1.0]])
    result = run_gbm(inp, mu, sigma, corr)
    assert len(result.p50) == 12
    assert all(v > 0 for v in result.p50)


def _make_result(
    p5_final: float = 95_000.0,
    p50_final: float = 285_000.0,
    p95_final: float = 420_000.0,
    initial_value: float = 100_000.0,
    contribution_total: float = 211_680.0,
    months: int = 240,
    prob_positive_return: float = 0.87,
) -> MonteCarloResult:
    return MonteCarloResult(
        p5=[p5_final] * months,
        p50=[p50_final] * months,
        p95=[p95_final] * months,
        final_distribution=[p50_final] * 100,
        prob_positive_return=prob_positive_return,
        prob_500k=0.12,
        contribution_total=contribution_total,
        months=months,
    )


def test_build_interpretation_contains_years() -> None:
    result = _make_result(months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "20 Jahren" in text or "20 Jahre" in text


def test_build_interpretation_contains_p5_and_p95() -> None:
    result = _make_result(p5_final=95_000.0, p95_final=420_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "95" in text or "95'000" in text
    assert "420" in text or "420'000" in text


def test_build_interpretation_contains_probability() -> None:
    result = _make_result(prob_positive_return=0.87, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "80" in text or "87" in text


def test_build_interpretation_contains_median() -> None:
    result = _make_result(p50_final=285_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "285" in text or "285'000" in text


def test_build_interpretation_gain_scenario() -> None:
    result = _make_result(p50_final=285_000.0, contribution_total=211_680.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "+" in text or "Gewinn" in text or "wächst" in text or "%" in text


def test_build_interpretation_worst_case_p5() -> None:
    result = _make_result(p5_final=95_000.0, initial_value=100_000.0, months=240)
    text = build_interpretation(result, initial_value=100_000.0, years=20)
    assert "5" in text
    assert "95" in text or "95'000" in text


def test_build_interpretation_returns_str() -> None:
    result = _make_result(months=60)
    text = build_interpretation(result, initial_value=0.0, years=5)
    assert isinstance(text, str)
    assert len(text) > 50


def test_build_interpretation_zero_initial_value() -> None:
    result = _make_result(
        initial_value=0.0, p5_final=10_000.0, p50_final=80_000.0, p95_final=200_000.0, months=120
    )
    text = build_interpretation(result, initial_value=0.0, years=10)
    assert isinstance(text, str)
    assert len(text) > 20


def _make_price_dataframe(n: int = 30) -> pd.DataFrame:
    closes = 100.0 + np.cumsum(np.random.default_rng(1).normal(0, 1, n))
    return pd.DataFrame({"Close": closes})


@pytest.mark.asyncio
async def test_fetch_ticker_params_uses_swiss_suffix_mapping_for_rog() -> None:
    """F-PORT-1 (K-2): ROG muss als RO.SW an yfinance gesendet werden, nicht als ROG.

    Ohne Suffix-Mapping matched yfinance "ROG" auf Rogers Corporation (US,
    NYQ) statt Roche Holding AG — komplett falsche Firma, falsche Daten.
    """
    captured_symbol: dict[str, str] = {}

    def fake_download(ticker: str, **kwargs: Any) -> pd.DataFrame:
        captured_symbol["symbol"] = ticker
        return _make_price_dataframe()

    with patch("yfinance.download", side_effect=fake_download) as mock_download:
        await _fetch_ticker_params("ROG")

    mock_download.assert_called_once()
    assert captured_symbol["symbol"] == "RO.SW"
    assert captured_symbol["symbol"] != "ROG"


@pytest.mark.asyncio
async def test_fetch_ticker_params_uses_swiss_suffix_mapping_for_plain_ticker() -> None:
    """Normale SIX-Ticker (ohne Override) erhalten das .SW-Suffix, z.B. NESN -> NESN.SW."""
    captured_symbol: dict[str, str] = {}

    def fake_download(ticker: str, **kwargs: Any) -> pd.DataFrame:
        captured_symbol["symbol"] = ticker
        return _make_price_dataframe()

    with patch("yfinance.download", side_effect=fake_download):
        await _fetch_ticker_params("NESN")

    assert captured_symbol["symbol"] == "NESN.SW"


@pytest.mark.asyncio
async def test_fetch_ticker_params_raises_on_nan_prices() -> None:
    """Liefert yfinance NaN-verseuchte Kursdaten, muss eine klare ValueError fliegen
    (statt eines generischen "cannot convert float NaN to integer")."""
    nan_df = pd.DataFrame({"Close": [100.0, np.nan, 102.0, np.nan, 105.0]})

    with (
        patch("yfinance.download", return_value=nan_df),
        pytest.raises(ValueError, match="NaN|nicht-endlich|finite|Inf"),
    ):
        await _fetch_ticker_params("ROG", allow_fallback=False)


@pytest.mark.asyncio
async def test_fetch_ticker_params_falls_back_on_error_by_default() -> None:
    """Standardverhalten (allow_fallback=True, Default für simulate()) bleibt robust:
    bei yfinance-Fehlern wird auf Default-Werte zurückgefallen statt zu crashen."""
    with patch("yfinance.download", side_effect=RuntimeError("network down")):
        mu, sigma, returns = await _fetch_ticker_params("ROG")

    assert isinstance(mu, float)
    assert isinstance(sigma, float)
    assert isinstance(returns, np.ndarray)


@pytest.mark.asyncio
async def test_fetch_return_params_fetches_tickers_in_parallel() -> None:
    """F-PORT-2 (W-7): Ticker-Fetches müssen parallel statt sequenziell laufen.

    Mit 5 Holdings und je 200ms künstlicher Verzögerung pro Ticker-Fetch
    dauert eine sequenzielle for-Schleife ~1s (5 * 200ms). Bei paralleler
    Ausführung via asyncio.gather bleibt die Gesamtzeit nahe an einer
    Einzelverzögerung (~200ms), da alle Fetches gleichzeitig starten.
    """
    delay = 0.2
    n_holdings = 5
    holdings = [HoldingWeight(f"T{i}.SW", 1.0 / n_holdings) for i in range(n_holdings)]
    svc = MonteCarloService()

    async def fake_fetch_ticker_params(ticker: str) -> tuple[float, float, np.ndarray]:
        await asyncio.sleep(delay)
        return 0.0005, 0.012, np.zeros(10)

    async def fake_fetch_ml_mu(ticker: str) -> float:
        return 0.0003

    with (
        patch(
            "backend.application.services.monte_carlo_service._fetch_ticker_params",
            side_effect=fake_fetch_ticker_params,
        ),
        patch.object(svc, "_fetch_ml_mu", side_effect=fake_fetch_ml_mu),
    ):
        start = time.monotonic()
        mu_arr, sigma_arr, corr_matrix = await svc._fetch_return_params(holdings)
        elapsed = time.monotonic() - start

    assert len(mu_arr) == n_holdings
    assert len(sigma_arr) == n_holdings
    # Sequenziell wären es n_holdings * delay (~1.0s). Parallel bleibt es nahe
    # bei einer einzigen Verzögerung. Grosszügige Schwelle für CI-Jitter.
    assert elapsed < delay * n_holdings * 0.6, (
        f"Erwartete parallele Ausführung (<{delay * n_holdings * 0.6:.2f}s), "
        f"aber {elapsed:.2f}s vergangen — Ticker werden vermutlich sequenziell abgerufen."
    )
