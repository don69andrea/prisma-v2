"""CryptoScoringService — orchestriert alle Datenquellen und berechnet CryptoSignals."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import pandas as pd

from backend.domain.entities.crypto_asset import SUPPORTED_CRYPTOS, CryptoAsset
from backend.domain.services.crypto_scorer import CryptoScorer, generate_signal_reason
from backend.domain.value_objects.crypto_signal import CryptoSignal
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.infrastructure.adapters.yfinance_crypto import YFinanceCryptoAdapter

_logger = logging.getLogger(__name__)


class CryptoScoringService:
    """Orchestriert CoinGecko, yFinance und Fear&Greed für alle 10 Kryptos."""

    def __init__(
        self,
        cg_adapter: CoinGeckoAdapter,
        yf_adapter: YFinanceCryptoAdapter,
        fg_adapter: FearGreedAdapter,
        scorer: CryptoScorer,
    ) -> None:
        self._cg = cg_adapter
        self._yf = yf_adapter
        self._fg = fg_adapter
        self._scorer = scorer

    async def score_all(self) -> list[CryptoSignal]:
        """Berechnet Scores für alle 10 unterstützten Kryptos parallel."""
        fear_greed = await self._fg.get_current()
        fg_value = fear_greed["value"]
        fg_label = fear_greed["label"]

        coin_ids = [c[0] for c in SUPPORTED_CRYPTOS]
        market_data = await self._cg.get_market_data(coin_ids)
        market_map = {d["id"]: d for d in market_data}

        tech_tasks = [self._yf.get_technicals(c[1]) for c in SUPPORTED_CRYPTOS]
        corr_tasks = [self._yf.get_smi_correlation(c[1]) for c in SUPPORTED_CRYPTOS]

        all_tech = await asyncio.gather(*tech_tasks, return_exceptions=True)
        all_corr = await asyncio.gather(*corr_tasks, return_exceptions=True)

        results: list[CryptoSignal] = []
        for i, (cg_id, yf_ticker, name, kategorie, has_etp) in enumerate(SUPPORTED_CRYPTOS):
            tech = all_tech[i] if not isinstance(all_tech[i], Exception) else pd.DataFrame()
            corr = all_corr[i] if not isinstance(all_corr[i], Exception) else 0.0
            if isinstance(tech, pd.DataFrame) and tech.empty:
                _logger.warning("Keine Technikaldaten für %s — übersprungen", yf_ticker)
                continue

            mkt = market_map.get(cg_id, {})
            asset = CryptoAsset(
                ticker_cg=cg_id,
                ticker_yf=yf_ticker,
                name=name,
                symbol=yf_ticker.split("-")[0],
                kategorie=kategorie,
                has_six_etp=has_etp,
                price_chf=mkt.get("current_price"),
                market_cap_chf=mkt.get("market_cap"),
                volume_24h_chf=mkt.get("total_volume"),
                price_change_24h_pct=mkt.get("price_change_percentage_24h"),
                price_change_7d_pct=mkt.get("price_change_percentage_7d_in_currency"),
                ath_change_pct=mkt.get("ath_change_percentage"),
                market_cap_rank=mkt.get("market_cap_rank"),
            )

            score, components = self._scorer.score(
                asset, tech, fg_value, correlation_smi_1y=float(corr)  # type: ignore[arg-type]
            )
            signal = _score_to_signal(score)

            rsi = float(tech["RSI_14"].iloc[-1]) if "RSI_14" in tech.columns else 50.0
            macd_val = float(tech["MACD_12_26_9"].iloc[-1]) if "MACD_12_26_9" in tech.columns else 0.0
            macd_sig_val = float(tech["MACDs_12_26_9"].iloc[-1]) if "MACDs_12_26_9" in tech.columns else 0.0
            returns = tech["Close"].pct_change().dropna()
            vol_30d = float(returns.rolling(30).std().iloc[-1] * (365**0.5) * 100) if len(returns) >= 30 else 0.0

            reason = generate_signal_reason(
                signal=signal,
                asset_name=name,
                score=score,
                rsi=rsi,
                fear_greed=fg_value,
                change_7d=asset.price_change_7d_pct or 0.0,
            )

            results.append(
                CryptoSignal(
                    ticker=yf_ticker.split("-")[0],
                    name=name,
                    signal=signal,  # type: ignore[arg-type]
                    score=round(score, 1),
                    score_components={k: round(v, 1) for k, v in components.items()},
                    signal_reason_de=reason,
                    fear_greed_value=fg_value,
                    fear_greed_label=fg_label,
                    rsi_14=round(rsi, 1),
                    macd_signal="bullish" if macd_val > macd_sig_val else "bearish",
                    volatility_30d_pct=round(vol_30d, 1),
                    correlation_smi_1y=round(float(corr), 3),  # type: ignore[arg-type]
                    has_six_etp=has_etp,
                    price_chf=asset.price_chf,
                    market_cap_chf=asset.market_cap_chf,
                    price_change_24h_pct=asset.price_change_24h_pct,
                    price_change_7d_pct=asset.price_change_7d_pct,
                    ath_change_pct=asset.ath_change_pct,
                    market_cap_rank=asset.market_cap_rank,
                    timestamp=datetime.now(tz=UTC),
                )
            )

        return sorted(results, key=lambda x: x.score, reverse=True)

    async def score_one(self, ticker_symbol: str) -> CryptoSignal | None:
        """Einzelsignal für einen Ticker (z.B. 'BTC', 'ETH')."""
        all_signals = await self.score_all()
        return next((s for s in all_signals if s.ticker == ticker_symbol.upper()), None)


def _score_to_signal(score: float) -> str:
    if score >= CryptoScorer.STRONG_BUY_THRESHOLD:
        return "STRONG_BUY"
    if score >= CryptoScorer.BUY_THRESHOLD:
        return "BUY"
    if score >= CryptoScorer.HOLD_THRESHOLD:
        return "HOLD"
    if score >= CryptoScorer.SELL_THRESHOLD:
        return "SELL"
    return "STRONG_SELL"
