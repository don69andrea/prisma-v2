"""Portfolio Intelligence Agent — Score-Weighted, Risk-Parity und Mean-Variance Allokation."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.domain.services.eligibility_filter import EligibilityFilter
from backend.domain.value_objects.portfolio_allocation import PortfolioAllocation, PortfolioPosition

_logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5"
_MAX_TOKENS = 400
_MIN_WEIGHT = 0.05
_MAX_WEIGHT = 0.40
_PRICE_DAYS = 40  # 30d Daten + Puffer für Wochenenden


class _NarrativeOutput(BaseModel):
    overall: str = Field(..., min_length=20, max_length=600)
    positions: dict[str, str] = Field(default_factory=dict)


def _normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    """Normalisiert Gewichte: Summe = 1.0, jedes in [MIN_WEIGHT, MAX_WEIGHT]."""
    if not raw:
        return {}
    tickers = list(raw.keys())
    values = np.array([raw[t] for t in tickers], dtype=float)

    # Iterative Clamp-Normalisierung (geometrische Konvergenz, max 50 Schritte)
    for _ in range(50):
        total = values.sum()
        if total <= 0:
            values = np.ones(len(tickers))
            total = float(len(tickers))
        values = values / total
        values = np.clip(values, _MIN_WEIGHT, _MAX_WEIGHT)
        total = values.sum()
        if abs(total - 1.0) < 1e-6:
            break
        values = values / total

    return {t: float(v) for t, v in zip(tickers, values, strict=True)}


def _score_weighted(picks: list[dict[str, Any]]) -> dict[str, float]:
    """Gewichtung proportional zum quant_score."""
    raw = {p["ticker"]: max(float(p.get("quant_score", 1.0)), 1.0) for p in picks}
    return _normalize_weights(raw)


def _risk_parity(
    picks: list[dict[str, Any]],
    price_histories: dict[str, pd.DataFrame],
) -> dict[str, float]:
    """Gewichtung umgekehrt proportional zur annualisierten 30d-Volatilität."""
    raw: dict[str, float] = {}
    for p in picks:
        ticker = p["ticker"]
        hist = price_histories.get(ticker)
        if hist is None or hist.empty or len(hist) < 5:
            raw[ticker] = 1.0 / max(float(p.get("quant_score", 50.0)), 1.0)
            continue
        returns = hist["Close"].pct_change().dropna()
        vol = float(returns.std()) * (252**0.5)
        raw[ticker] = 1.0 / max(vol, 0.05)
    return _normalize_weights(raw)


def _mean_variance(
    picks: list[dict[str, Any]],
    price_histories: dict[str, pd.DataFrame],
    target_return: float | None = None,
) -> dict[str, float]:
    """Markowitz Mean-Variance Optimierung mit Ledoit-Wolf Kovarianzschätzung.

    Maximiert Sharpe Ratio (risk-free rate = SNB Leitzins, ca. 0%).
    Ledoit-Wolf Shrinkage für stabile Kovarianzmatrix bei kleinen Stichproben.
    Fallback auf _risk_parity() bei zu wenig Daten, singulärer Matrix oder
    fehlenden Abhängigkeiten (sklearn / scipy).
    """
    tickers = [p["ticker"] for p in picks]

    # Datenpunkte sammeln
    returns_list: list[pd.Series] = []
    for ticker in tickers:
        hist = price_histories.get(ticker)
        if hist is None or hist.empty:
            _logger.warning("Keine Preishistorie für %s — Fallback auf Risk-Parity", ticker)
            return _risk_parity(picks, price_histories)
        ret = hist["Close"].pct_change().dropna()
        returns_list.append(ret.rename(ticker))

    # Gemeinsamer Index (inner join), mindestens 30 Beobachtungen
    returns_df = pd.concat(returns_list, axis=1).dropna()
    if len(returns_df) < 30:
        _logger.warning(
            "Zu wenig Datenpunkte (%d) für Mean-Variance — Fallback auf Risk-Parity",
            len(returns_df),
        )
        return _risk_parity(picks, price_histories)

    try:
        from scipy.optimize import minimize  # noqa: PLC0415
        from sklearn.covariance import LedoitWolf  # noqa: PLC0415
    except ImportError:
        _logger.warning("sklearn/scipy nicht verfügbar — Fallback auf Risk-Parity")
        return _risk_parity(picks, price_histories)

    try:
        returns_matrix = returns_df.values  # shape: (T, N)
        n_assets = returns_matrix.shape[1]

        # Annualisierte expected Returns (mu)
        mu = returns_matrix.mean(axis=0) * 252  # shape: (N,)

        # Kovarianzmatrix mit Ledoit-Wolf Shrinkage, annualisiert
        lw = LedoitWolf()
        lw.fit(returns_matrix)
        cov_matrix = lw.covariance_ * 252  # shape: (N, N)

        # Sharpe-Ratio-Maximierung via SLSQP
        # Wir minimieren den negativen Sharpe Ratio: -mu^T w / sqrt(w^T Σ w)
        def neg_sharpe(weights: np.ndarray) -> float:
            port_return = float(mu @ weights)
            port_vol = float(np.sqrt(weights @ cov_matrix @ weights))
            if port_vol < 1e-10:
                return 0.0
            return -port_return / port_vol

        # Gradient (analytisch) für schnellere Konvergenz
        def neg_sharpe_grad(weights: np.ndarray) -> np.ndarray:
            port_return = float(mu @ weights)
            port_var = float(weights @ cov_matrix @ weights)
            port_vol = float(np.sqrt(max(port_var, 1e-20)))
            grad_return = mu
            grad_vol = (cov_matrix @ weights) / port_vol
            sharpe = port_return / port_vol
            return np.asarray(-(grad_return / port_vol - sharpe * grad_vol / port_vol))

        w0 = np.full(n_assets, 1.0 / n_assets)
        bounds = [(float(_MIN_WEIGHT), float(_MAX_WEIGHT))] * n_assets
        constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]

        result = minimize(
            neg_sharpe,
            w0,
            jac=neg_sharpe_grad,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-9},
        )

        if not result.success:
            _logger.warning(
                "SLSQP-Optimierung nicht konvergiert (%s) — Fallback auf Risk-Parity",
                result.message,
            )
            return _risk_parity(picks, price_histories)

        optimized = {ticker: float(w) for ticker, w in zip(tickers, result.x, strict=True)}
        return _normalize_weights(optimized)

    except (np.linalg.LinAlgError, ValueError) as exc:
        _logger.warning("Singuläre Matrix oder numerischer Fehler (%s) — Fallback", exc)
        return _risk_parity(picks, price_histories)


class PortfolioAgent:
    """Agent: berechnet Portfolio-Allokation aus Top-N-Ranking-Picks."""

    def __init__(
        self,
        ranking_run_service: Any,
        swiss_stock_repo: SwissStockRepository,
        yfinance_adapter: Any | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self._runs = ranking_run_service
        self._repo = swiss_stock_repo
        self._yf = yfinance_adapter
        self._llm = llm_client
        self._eligibility = EligibilityFilter()

    async def allocate(
        self,
        run_id: UUID,
        top_n: int = 10,
        eligible_only: bool = False,
        method: str = "score_weighted",
    ) -> PortfolioAllocation:
        rankings = await self._runs.get_rankings(run_id)
        ranked = sorted(
            [r for r in rankings if r.get("total_rank") is not None],
            key=lambda r: r["total_rank"],
        )

        # 3a-Filter
        picks: list[dict[str, Any]] = []
        for r in ranked:
            if len(picks) >= top_n:
                break
            ticker = r["ticker"]
            quant_score = float(r.get("weighted_avg") or 50.0)
            is_eligible = await self._check_eligible(ticker)
            if eligible_only and not is_eligible:
                continue
            picks.append(
                {"ticker": ticker, "quant_score": quant_score, "is_3a_eligible": is_eligible}
            )

        if not picks:
            picks = [
                {"ticker": r["ticker"], "quant_score": 50.0, "is_3a_eligible": False}
                for r in ranked[:top_n]
            ]

        # Gewichtungsberechnung
        weights: dict[str, float]
        if method in ("risk_parity", "mean_variance") and self._yf is not None:
            histories = await self._fetch_histories([p["ticker"] for p in picks])
            if method == "mean_variance":
                weights = _mean_variance(picks, histories)
            else:
                weights = _risk_parity(picks, histories)
        else:
            weights = _score_weighted(picks)

        # Narrative
        overall_de, pos_rationales = await self._generate_narrative(picks, weights, method)

        positions = tuple(
            sorted(
                [
                    PortfolioPosition(
                        ticker=p["ticker"],
                        weight=round(weights.get(p["ticker"], 1.0 / len(picks)), 4),
                        quant_score=p["quant_score"],
                        is_3a_eligible=p["is_3a_eligible"],
                        rationale_de=pos_rationales.get(p["ticker"], ""),
                    )
                    for p in picks
                ],
                key=lambda pos: pos.weight,
                reverse=True,
            )
        )

        return PortfolioAllocation(
            run_id=run_id,
            method=method,
            positions=positions,
            overall_rationale_de=overall_de,
            computed_at=datetime.now(tz=UTC),
            eligible_only=eligible_only,
        )

    async def _check_eligible(self, ticker: str) -> bool:
        stock = await self._repo.get_by_ticker(ticker.upper())
        if stock is None:
            return False
        return self._eligibility.check(stock).eligible

    async def _fetch_histories(self, tickers: list[str]) -> dict[str, pd.DataFrame]:
        histories: dict[str, pd.DataFrame] = {}
        if self._yf is None:
            return histories
        for ticker in tickers:
            try:
                df = await self._yf.get_price_history(ticker, days=_PRICE_DAYS)
                histories[ticker] = df
            except Exception:
                _logger.warning("Preishistorie nicht verfügbar für %s", ticker)
        return histories

    async def _generate_narrative(
        self,
        picks: list[dict[str, Any]],
        weights: dict[str, float],
        method: str,
    ) -> tuple[str, dict[str, str]]:
        if self._llm is None:
            return self._fallback_narrative(picks, weights, method)

        top3 = sorted(picks, key=lambda p: weights.get(p["ticker"], 0), reverse=True)[:3]
        prompt = (
            f"Methode: {method}. "
            f"Top-3-Positionen: "
            + ", ".join(
                f"{p['ticker']} ({weights.get(p['ticker'], 0):.1%}, Score {p['quant_score']:.0f})"
                for p in top3
            )
            + ". Erstelle eine kurze sachliche Portfolio-Begründung auf Deutsch "
            "für Schweizer Aktien-Investoren (freie Mittel). "
            'Antworte NUR mit JSON: {"overall": "...", "positions": {"TICKER": "kurze Begründung", ...}}'
        )
        system = (
            "Du bist ein präziser Schweizer Portfolio-Analyst. "
            "Antworte NUR mit validem JSON ohne Markdown. "
            'Schema: {"overall": "<max 3 Sätze>", "positions": {"<TICKER>": "<max 1 Satz>"}}'
        )
        try:
            response = await self._llm.messages_create(
                model=_HAIKU,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=_MAX_TOKENS,
                feature="portfolio_narrative",
            )
            raw = response.content[0].text.strip()
            parsed = _NarrativeOutput.model_validate(json.loads(raw))
            return parsed.overall, parsed.positions
        except (ValidationError, Exception):
            _logger.warning("Portfolio-Narrative LLM fehlgeschlagen — Fallback", exc_info=True)
            return self._fallback_narrative(picks, weights, method)

    @staticmethod
    def _fallback_narrative(
        picks: list[dict[str, Any]],
        weights: dict[str, float],
        method: str,
    ) -> tuple[str, dict[str, str]]:
        method_label = (
            "Score-Gewichtung"
            if method == "score_weighted"
            else "Mean-Variance (Markowitz)"
            if method == "mean_variance"
            else "Risk-Parity"
        )
        sorted_picks = sorted(picks, key=lambda p: weights.get(p["ticker"], 0), reverse=True)
        top = sorted_picks[0] if sorted_picks else None
        top_weight_pct = f"{weights.get(top['ticker'], 0) * 100:.1f}%" if top else "—"

        overall_parts = [
            f"Portfolio mit {len(picks)} Positionen nach {method_label}.",
        ]
        if top:
            overall_parts.append(
                f"Grösste Position: {top['ticker']} ({top_weight_pct}, Quant-Score {top['quant_score']:.0f})."
            )
        avg_score = sum(p["quant_score"] for p in picks) / len(picks) if picks else 0
        overall_parts.append(f"Durchschnittlicher Quant-Score: {avg_score:.0f}/100.")
        overall = " ".join(overall_parts)

        pos = {
            p["ticker"]: (
                f"{weights.get(p['ticker'], 0) * 100:.1f}% Gewicht, "
                f"Quant-Score {p['quant_score']:.0f}"
                + (f", Signal: {p.get('signal', '—')}" if p.get("signal") else "")
                + "."
            )
            for p in sorted_picks
        }
        return overall, pos
