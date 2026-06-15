"""SignalValidationService — berechnet historische Trefferquote von PRISMA-Signalen."""

from __future__ import annotations

import logging

import numpy as np

_logger = logging.getLogger(__name__)
_BUY_THRESHOLD = 70.0
_LOOKBACK_DAYS = 3 * 365


class SignalValidationResult:
    def __init__(self, ticker, return_pct, buy_and_hold_pct, win_rate_pct, label):
        self.ticker = ticker
        self.return_pct = return_pct
        self.buy_and_hold_pct = buy_and_hold_pct
        self.win_rate_pct = win_rate_pct
        self.label = label


class SignalValidationService:
    def __init__(self, market_data_provider) -> None:
        self._market = market_data_provider

    async def validate(self, ticker: str) -> SignalValidationResult | None:
        try:
            df = await self._market.get_price_history(ticker, days=_LOOKBACK_DAYS)
        except Exception as exc:
            _logger.warning("signal_validation: no data for %s: %s", ticker, exc)
            return None

        if df is None or df.empty or len(df) < 60:
            return None

        # Preisserie
        if "Close" in df.columns:
            prices = df["Close"].dropna()
        elif "close" in df.columns:
            prices = df["close"].dropna()
        else:
            prices = df.iloc[:, 0].dropna()

        if len(prices) < 60:
            return None

        prices = prices.sort_index()

        # Momentum-basierter Proxy für PRISMA Score
        momentum_20d = prices.pct_change(20)
        returns_20d = prices.pct_change(20).shift(-20)  # forward return

        def momentum_to_score(mom: float) -> float:
            if np.isnan(mom):
                return 50.0
            clipped = max(-0.30, min(0.30, mom))
            return 50.0 + (clipped / 0.30) * 50.0

        signals = momentum_20d.apply(momentum_to_score)
        buy_signals = signals >= _BUY_THRESHOLD
        forward_returns = returns_20d[buy_signals].dropna()

        if len(forward_returns) < 3:
            return None

        prisma_return = float((1 + forward_returns).prod() - 1) * 100
        bah_return = float((prices.iloc[-1] / prices.iloc[0]) - 1) * 100
        win_rate = float((forward_returns > 0).mean()) * 100

        label = _generate_label(ticker, prisma_return, bah_return, win_rate)

        return SignalValidationResult(
            ticker=ticker,
            return_pct=round(prisma_return, 1),
            buy_and_hold_pct=round(bah_return, 1),
            win_rate_pct=round(win_rate, 1),
            label=label,
        )


def _generate_label(ticker, prisma, bah, win_rate):
    diff = prisma - bah
    if win_rate >= 60 and diff > 5:
        return f"PRISMA hat bei {ticker} historisch gut funktioniert."
    if win_rate >= 50 and diff > 0:
        return f"PRISMA-Signale für {ticker} lagen öfter richtig als falsch."
    if win_rate < 50:
        return f"Bei {ticker} war Buy & Hold in diesem Zeitraum stärker als aktive Signale."
    return f"PRISMA-Signale für {ticker} zeigten gemischte Ergebnisse."
