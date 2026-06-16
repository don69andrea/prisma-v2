"""Application Service: Monte Carlo 3a Retirement Simulator."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

_logger = logging.getLogger(__name__)
_TARGET_500K = 500_000.0
_TRADING_DAYS_PER_MONTH = 21


class NonFiniteMarketDataError(ValueError):
    """Marktdaten von yfinance enthalten NaN/Inf-Werte.

    Erbt von ValueError, damit bestehende Router-Fehlerbehandlung
    (ValueError -> HTTP 422) diese Exception ohne Änderung abfängt und eine
    verständliche Meldung liefert statt eines generischen
    "cannot convert float NaN to integer"-Fehlers.
    """

    def __init__(self, ticker: str, yf_ticker: str) -> None:
        super().__init__(
            f"Kursdaten für {ticker} ({yf_ticker}) enthalten nicht-endliche "
            "Werte (NaN/Inf) und können nicht für die Simulation verwendet werden."
        )


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
    correlation_degraded: bool = False
    interpretation: str = ""


def build_interpretation(result: MonteCarloResult, initial_value: float, years: int) -> str:
    def fmt(v: float) -> str:
        if v >= 1_000_000:
            return f"CHF {v / 1_000_000:,.2f}M".replace(",", "'")
        return f"CHF {v:,.0f}".replace(",", "'")

    p5_final = result.p5[-1]
    p50_final = result.p50[-1]
    p95_final = result.p95[-1]
    prob_pct = round(result.prob_positive_return * 100)
    invested = initial_value + result.contribution_total

    lines: list[str] = []

    lines.append(
        f"Mit 90% Wahrscheinlichkeit liegt der Portfoliowert nach {years} Jahren "
        f"zwischen {fmt(p5_final)} (5. Perzentil) und {fmt(p95_final)} (95. Perzentil)."
    )

    if invested > 0:
        gain = p50_final - invested
        gain_pct = (gain / invested) * 100
        sign = "+" if gain >= 0 else ""
        lines.append(
            f"Im Median-Szenario wächst das Portfolio auf {fmt(p50_final)} "
            f"({sign}{gain_pct:.0f}% gegenüber den Gesamteinzahlungen von {fmt(invested)})."
        )
    else:
        lines.append(f"Im Median-Szenario erreicht das Portfolio {fmt(p50_final)}.")

    if invested > 0:
        worst_pct = round(((p5_final - invested) / invested) * 100)
        sign_w = "+" if worst_pct >= 0 else ""
        lines.append(
            f"Im schlechtesten Szenario (5. Perzentil): {fmt(p5_final)} ({sign_w}{worst_pct}%)."
        )
    else:
        lines.append(f"Im schlechtesten Szenario (5. Perzentil): {fmt(p5_final)}.")

    lines.append(
        f"Die Wahrscheinlichkeit eines positiven Returns gegenüber den Einzahlungen beträgt {prob_pct}%."
    )

    return " ".join(lines)


class MonteCarloService:
    """Simuliert 3a-Wealth-Paths via Geometric Brownian Motion."""

    def __init__(self, ml_prediction_service: Any | None = None) -> None:
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

        async def _fetch_one(h: HoldingWeight) -> tuple[float, float, np.ndarray]:
            hist_mu, hist_sigma, hist_returns = await _fetch_ticker_params(h.ticker)
            ml_mu = await self._fetch_ml_mu(h.ticker)
            blended_mu = 0.5 * hist_mu + 0.5 * ml_mu
            return blended_mu, hist_sigma, hist_returns

        # F-PORT-2 (W-7): Holdings parallel statt sequenziell abrufen. Jeder
        # Ticker-Fetch macht einen synchronen yfinance-Roundtrip via
        # asyncio.to_thread; nacheinander skalierte die Antwortzeit linear
        # mit der Anzahl Holdings (5 Holdings ~13s). _fetch_ticker_params
        # degradiert bei Fehlern intern auf Default-Werte (allow_fallback=True),
        # wirft also nicht — ein einzelner fehlerhafter Ticker bricht den
        # gesamten Batch daher nicht ab.
        results = await asyncio.gather(*(_fetch_one(h) for h in holdings))
        mu_list = [r[0] for r in results]
        sigma_list = [r[1] for r in results]
        returns_matrix = [r[2] for r in results]

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

            result = await svc.predict(ticker)
            if result is None:
                return 0.0003
            annual_map = {"OUTPERFORM": 0.10, "NEUTRAL": 0.05, "UNDERPERFORM": 0.0}
            annual = annual_map.get(result.signal, 0.05)
            return annual / 252
        except Exception:
            return 0.0003


async def _fetch_ticker_params(
    ticker: str, *, allow_fallback: bool = True
) -> tuple[float, float, np.ndarray]:
    """Lädt historische Kursdaten für `ticker` via yfinance und leitet
    (mu, sigma, daily_returns) ab.

    F-PORT-1 (K-2): PRISMA-Ticker (z.B. "ROG") werden über das bestehende
    Yahoo-Finance-Suffix-Mapping aus YFinanceSwissAdapter in das korrekte
    yfinance-Symbol (z.B. "RO.SW") übersetzt, BEVOR sie an yfinance gesendet
    werden. Ohne dieses Mapping matched yfinance "ROG" auf Rogers Corporation
    (US-Elektronikhersteller, NYQ) statt Roche Holding AG — komplett falsche
    Firma und Daten.
    """
    from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

    yf_ticker = YFinanceSwissAdapter().build_yf_ticker(ticker)

    try:
        import yfinance as yf

        raw = await asyncio.to_thread(
            yf.download, yf_ticker, period="1y", progress=False, auto_adjust=True
        )
        if raw.empty or "Close" not in raw.columns:
            raise ValueError("Keine Daten")
        close = raw["Close"]
        prices_with_nan = close.to_numpy(dtype=float).reshape(-1)
        if not np.all(np.isfinite(prices_with_nan)):
            raise NonFiniteMarketDataError(ticker, yf_ticker)
        prices = close.dropna().values
        if len(prices) < 2:
            raise ValueError("Zu wenige Datenpunkte")
        daily_returns = np.diff(np.log(prices.astype(float)))
        mu = float(np.mean(daily_returns))
        sigma = float(np.std(daily_returns))
        if not (math.isfinite(mu) and math.isfinite(sigma)):
            raise NonFiniteMarketDataError(ticker, yf_ticker)
        return mu, max(sigma, 0.005), daily_returns
    except NonFiniteMarketDataError:
        if allow_fallback:
            _logger.warning(
                "Marktdaten für %s (%s) enthalten NaN/Inf — verwende Defaults",
                ticker,
                yf_ticker,
            )
            rng = np.random.default_rng(42)
            return 0.0003, 0.012, rng.normal(0.0003, 0.012, 252)
        raise
    except Exception:
        if allow_fallback:
            _logger.warning("Keine Marktdaten für %s (%s) — verwende Defaults", ticker, yf_ticker)
            rng = np.random.default_rng(42)
            return 0.0003, 0.012, rng.normal(0.0003, 0.012, 252)
        raise


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
    total_invested = contribution_total + inp.initial_value
    prob_positive = float(np.mean(final > total_invested))
    prob_500k = float(np.mean(final > _TARGET_500K))

    partial_result = MonteCarloResult(
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
    interp = build_interpretation(partial_result, initial_value=inp.initial_value, years=inp.years)
    return MonteCarloResult(
        p5=partial_result.p5,
        p50=partial_result.p50,
        p95=partial_result.p95,
        final_distribution=partial_result.final_distribution,
        prob_positive_return=partial_result.prob_positive_return,
        prob_500k=partial_result.prob_500k,
        contribution_total=partial_result.contribution_total,
        months=partial_result.months,
        correlation_degraded=partial_result.correlation_degraded,
        interpretation=interp,
    )
