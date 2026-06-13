"""Fonds-Vergleich-Service — VIAC-Fonds vs. Custom-Portfolio."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from backend.domain.value_objects.fonds_vergleich import (
    FondsVergleich,
    PortfolioCompareMetrics,
)
from backend.infrastructure.seeds.viac_fonds_catalog import VIAC_FONDS_CATALOG

_logger = logging.getLogger(__name__)
# Fallback-Wert wenn SNB-Rate nicht verfügbar.
# Wird in __init__ durch aktuellen SNB-Leitzins überschrieben.
_RISK_FREE_RATE_FALLBACK = 0.01


class FondsNotFound(Exception):
    pass


class FondsVergleichService:
    """Vergleicht VIAC-Fonds-Metriken mit einem benutzerdefinierten Portfolio.

    yfinance_adapter ist optional (Any | None) damit der Service
    ohne MarketData-Anbindung lauffähig bleibt.
    """

    def __init__(self, yfinance_adapter: Any | None = None, risk_free_rate: float | None = None) -> None:
        self._yf = yfinance_adapter
        if risk_free_rate is not None:
            self._risk_free_rate = risk_free_rate
        else:
            # Aktuellen SNB-Leitzins als Risk-Free Rate verwenden
            try:
                from datetime import date
                from backend.application.services.ml_feature_service import _snb_rate_on
                snb_rate = _snb_rate_on(date.today())
                self._risk_free_rate = snb_rate / 100.0  # Prozent → Dezimal
            except Exception as exc:
                _logger.warning("SNB-Rate nicht verfügbar (%s) — Fallback auf %.2f%%", exc, _RISK_FREE_RATE_FALLBACK * 100)
                self._risk_free_rate = _RISK_FREE_RATE_FALLBACK

    def list_fonds(self) -> list[dict[str, str | float]]:
        return [
            {
                "name": f.name,
                "description": f.description,
                "equity_ratio": f.equity_ratio,
            }
            for f in VIAC_FONDS_CATALOG.values()
        ]

    async def compare(
        self,
        fonds_name: str,
        positions: list[dict[str, object]],
        lookback_years: int = 3,
    ) -> FondsVergleich:
        """Vergleicht VIAC-Fonds mit Custom-Portfolio.

        positions: [{"ticker": "NESN", "weight": 0.4}, ...]
        Gewichte werden normalisiert (müssen nicht exakt 1.0 ergeben).
        """
        fonds = VIAC_FONDS_CATALOG.get(fonds_name)
        if fonds is None:
            raise FondsNotFound(f"Fonds '{fonds_name}' nicht im Katalog.")

        fonds_metrics = PortfolioCompareMetrics(
            expected_return_pa=fonds.expected_return_pa,
            volatility_pa=fonds.volatility_pa,
            sharpe_ratio=fonds.sharpe_ratio,
            max_drawdown=fonds.max_drawdown,
        )

        custom_metrics = await self._compute_custom_metrics(positions, lookback_years)

        return FondsVergleich(
            fonds_name=fonds_name,
            fonds_metrics=fonds_metrics,
            custom_metrics=custom_metrics,
            snapshot_date=datetime.now(tz=UTC).date(),
        )

    async def _compute_custom_metrics(
        self,
        positions: list[dict[str, object]],
        lookback_years: int,
    ) -> PortfolioCompareMetrics:
        import numpy as np

        if not positions or self._yf is None:
            return PortfolioCompareMetrics(
                expected_return_pa=Decimal("0"),
                volatility_pa=Decimal("0"),
                sharpe_ratio=None,
                max_drawdown=Decimal("0"),
            )

        # Gewichte normalisieren
        raw_weights = {str(p["ticker"]): float(str(p.get("weight", 1.0))) for p in positions}
        total = sum(raw_weights.values())
        if total <= 0:
            total = 1.0
        weights = {t: w / total for t, w in raw_weights.items()}

        # Preishistorie laden
        all_returns: list[Any] = []
        all_w: list[float] = []
        for ticker, weight in weights.items():
            try:
                prices = await self._yf.get_price_history(ticker, years=lookback_years)
                if prices is None or len(prices) < 20:
                    continue
                import pandas as pd

                price_series = pd.Series(prices) if not hasattr(prices, "pct_change") else prices
                ret = price_series.pct_change().dropna().values
                all_returns.append(ret)
                all_w.append(weight)
            except Exception:
                _logger.warning("Preishistorie nicht verfügbar für %s", ticker)

        if not all_returns:
            return PortfolioCompareMetrics(
                expected_return_pa=Decimal("0"),
                volatility_pa=Decimal("0"),
                sharpe_ratio=None,
                max_drawdown=Decimal("0"),
            )

        # Portfolio-Rendite als gewichtetes Mittel
        w_arr = np.array(all_w)
        w_arr = w_arr / w_arr.sum()
        min_len = min(len(r) for r in all_returns)
        stacked = np.column_stack([r[:min_len] for r in all_returns])
        portfolio_returns = stacked @ w_arr

        ann_factor = 252
        ann_return = float(np.mean(portfolio_returns)) * ann_factor
        ann_vol = float(np.std(portfolio_returns, ddof=1)) * math.sqrt(ann_factor)
        sharpe: float | None = (ann_return - self._risk_free_rate) / ann_vol if ann_vol > 1e-9 else None
        cum = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cum)
        drawdowns = (cum - running_max) / running_max
        max_dd = float(np.min(drawdowns))

        return PortfolioCompareMetrics(
            expected_return_pa=Decimal(str(round(ann_return, 4))),
            volatility_pa=Decimal(str(round(ann_vol, 4))),
            sharpe_ratio=Decimal(str(round(sharpe, 4))) if sharpe is not None else None,
            max_drawdown=Decimal(str(round(max_dd, 4))),
        )
