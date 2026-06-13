"""Application Service: Monte Carlo 3a Retirement Simulator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import numpy as np

_logger = logging.getLogger(__name__)
_TARGET_500K = 500_000.0
_TRADING_DAYS_PER_MONTH = 21


@dataclass(frozen=True)
class HoldingWeight:
    ticker: str
    weight: float


@dataclass(frozen=True)
class MonteCarloInput:
    holdings: list[HoldingWeight]
    monthly_contribution: float
    years: int
    initial_value: float = 0.0
    n_simulations: int = 10_000


@dataclass(frozen=True)
class MonteCarloResult:
    p5: list[float]
    p50: list[float]
    p95: list[float]
    final_distribution: list[float]
    prob_positive_return: float
    prob_500k: float
    contribution_total: float
    months: int
    correlation_degraded: bool = False  # True wenn Cholesky auf Identitätsmatrix zurückgefallen ist


class MonteCarloService:
    """Simuliert 3a-Wealth-Paths via Geometric Brownian Motion."""

    def __init__(self, ml_prediction_service: object | None = None) -> None:
        # MLPredictionService per DI statt inline-Instantiierung
        self._ml_prediction_service = ml_prediction_service

    async def simulate(self, inp: MonteCarloInput) -> MonteCarloResult:
        total_weight = sum(h.weight for h in inp.holdings)
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Gewichte müssen 1.0 ergeben, ist: {total_weight:.3f}")
        mu_arr, sigma_arr, corr_matrix = await self._fetch_return_params(inp.holdings)
        return _run_gbm(inp, mu_arr, sigma_arr, corr_matrix)

    async def _fetch_return_params(
        self, holdings: list[HoldingWeight]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = len(holdings)
        mu_list: list[float] = []
        sigma_list: list[float] = []
        returns_matrix: list[np.ndarray] = []

        for h in holdings:
            hist_mu, hist_sigma, hist_returns = await _fetch_ticker_params(h.ticker)
            ml_mu = await self._fetch_ml_mu(h.ticker)
            blended_mu = 0.5 * hist_mu + 0.5 * ml_mu
            mu_list.append(blended_mu)
            sigma_list.append(hist_sigma)
            returns_matrix.append(hist_returns)

        if n > 1:
            min_len = min(len(r) for r in returns_matrix)
            trimmed = np.column_stack([r[-min_len:] for r in returns_matrix])
            corr_matrix = np.corrcoef(trimmed, rowvar=False)
        else:
            corr_matrix = np.array([[1.0]])

        return np.array(mu_list), np.array(sigma_list), corr_matrix

    async def _fetch_ml_mu(self, ticker: str) -> float:
        try:
            if self._ml_prediction_service is not None:
                svc = self._ml_prediction_service
            else:
                from backend.application.services.ml_prediction_service import MLPredictionService
                svc = MLPredictionService()

            result = await svc.predict(ticker)  # type: ignore[union-attr]
            if result is None:
                return 0.0003
            annual_map = {"OUTPERFORM": 0.10, "NEUTRAL": 0.05, "UNDERPERFORM": 0.0}
            annual = annual_map.get(result.signal, 0.05)
            return annual / 252
        except Exception:
            return 0.0003


async def _fetch_ticker_params(ticker: str) -> tuple[float, float, np.ndarray]:
    try:
        import yfinance as yf

        raw = await asyncio.to_thread(
            yf.download, ticker, period="1y", progress=False, auto_adjust=True
        )
        if raw.empty or "Close" not in raw.columns:
            raise ValueError("Keine Daten")
        prices = raw["Close"].dropna().values
        if len(prices) < 2:
            raise ValueError("Zu wenige Datenpunkte")
        daily_returns = np.diff(np.log(prices.astype(float)))
        mu = float(np.mean(daily_returns))
        sigma = float(np.std(daily_returns))
        return mu, max(sigma, 0.005), daily_returns
    except Exception:
        _logger.warning("Keine Marktdaten für %s — verwende Defaults", ticker)
        rng = np.random.default_rng(42)
        return 0.0003, 0.012, rng.normal(0.0003, 0.012, 252)


def _run_gbm(
    inp: MonteCarloInput,
    mu_arr: np.ndarray,
    sigma_arr: np.ndarray,
    corr_matrix: np.ndarray,
) -> MonteCarloResult:
    n_assets = len(inp.holdings)
    n_months = inp.years * 12
    n_sim = inp.n_simulations
    weights = np.array([h.weight for h in inp.holdings])
    dt = _TRADING_DAYS_PER_MONTH

    correlation_degraded = False
    try:
        L = np.linalg.cholesky(corr_matrix)
    except np.linalg.LinAlgError:
        _logger.warning(
            "Korrelationsmatrix ist nicht positiv-definit — Simulation läuft ohne Titelkorrelationen. "
            "Ergebnisse können die tatsächliche Portfolio-Diversifikation über- oder unterschätzen."
        )
        L = np.eye(n_assets)
        correlation_degraded = True

    mu_m = mu_arr * dt
    sigma_m = sigma_arr * np.sqrt(dt)

    rng = np.random.default_rng()
    z_raw = rng.standard_normal((n_sim, n_months, n_assets))
    z_corr = z_raw @ L.T

    log_ret = (mu_m - 0.5 * sigma_m**2) + sigma_m * z_corr

    portfolio = np.zeros((n_sim, n_months))
    current_value = np.full(n_sim, inp.initial_value)

    for t in range(n_months):
        asset_factor = np.exp(log_ret[:, t, :])
        portfolio_return = asset_factor @ weights
        current_value = current_value * portfolio_return + inp.monthly_contribution
        portfolio[:, t] = current_value

    p5 = np.percentile(portfolio, 5, axis=0).tolist()
    p50 = np.percentile(portfolio, 50, axis=0).tolist()
    p95 = np.percentile(portfolio, 95, axis=0).tolist()
    final = portfolio[:, -1]

    contribution_total = inp.monthly_contribution * n_months
    prob_positive = float(np.mean(final > contribution_total))
    prob_500k = float(np.mean(final > _TARGET_500K))

    return MonteCarloResult(
        p5=[round(v, 2) for v in p5],
        p50=[round(v, 2) for v in p50],
        p95=[round(v, 2) for v in p95],
        final_distribution=[round(float(v), 2) for v in final],
        prob_positive_return=round(prob_positive, 4),
        prob_500k=round(prob_500k, 4),
        contribution_total=round(contribution_total, 2),
        months=n_months,
        correlation_degraded=correlation_degraded,
    )
