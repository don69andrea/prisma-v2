"""CryptoScoringService — orchestriert alle Datenquellen und berechnet CryptoSignals."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import pandas as pd

from backend.application.services.crypto_pattern_service import CryptoPatternService
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
        pattern_service: CryptoPatternService | None = None,
    ) -> None:
        self._cg = cg_adapter
        self._yf = yf_adapter
        self._fg = fg_adapter
        self._scorer = scorer
        self._pattern_svc = pattern_service or CryptoPatternService()
        # PERF-03: Request-Level-Cache verhindert parallele API-Stampede.
        # asyncio.Lock serialisiert gleichzeitige score_all()-Aufrufe, so dass
        # nur ein CoinGecko-Roundtrip pro Request-Burst stattfindet.
        self._cache_lock = asyncio.Lock()
        self._cache_result: list[CryptoSignal] | None = None

    async def score_all(self) -> list[CryptoSignal]:
        """Berechnet Scores für alle 10 unterstützten Kryptos parallel.

        PERF-03: asyncio.Lock verhindert parallele API-Stampede — mehrere
        gleichzeitige score_all()-Aufrufe lösen nur einen CoinGecko-Batch aus.
        """
        async with self._cache_lock:
            if self._cache_result is not None:
                return self._cache_result
            result = await self._score_all_uncached()
            self._cache_result = result
            return result

    async def _score_all_uncached(self) -> list[CryptoSignal]:
        """Interner Kern ohne Cache-Logik."""
        fear_greed = await self._fg.get_current()
        fg_value = fear_greed["value"]
        fg_label = fear_greed["label"]

        coin_ids = [c[0] for c in SUPPORTED_CRYPTOS]
        market_data = await self._cg.get_market_data(coin_ids)
        market_map = {d["id"]: d for d in market_data}

        tech_tasks = [self._yf.get_technicals(c[1]) for c in SUPPORTED_CRYPTOS]
        corr_tasks = [self._yf.get_smi_correlation(c[1]) for c in SUPPORTED_CRYPTOS]
        pattern_tasks = [self._pattern_svc.detect(c[1]) for c in SUPPORTED_CRYPTOS]

        all_tech = await asyncio.gather(*tech_tasks, return_exceptions=True)
        all_corr = await asyncio.gather(*corr_tasks, return_exceptions=True)
        all_patterns = await asyncio.gather(*pattern_tasks, return_exceptions=True)

        results: list[CryptoSignal] = []
        for i, (cg_id, yf_ticker, name, kategorie, has_etp) in enumerate(SUPPORTED_CRYPTOS):
            _raw_tech = all_tech[i]
            tech: pd.DataFrame = (
                _raw_tech if isinstance(_raw_tech, pd.DataFrame) else pd.DataFrame()
            )
            _raw_corr = all_corr[i]
            corr: float = float(_raw_corr) if not isinstance(_raw_corr, Exception) else 0.0  # type: ignore[arg-type]
            _raw_pattern = all_patterns[i]
            if isinstance(_raw_pattern, Exception):
                patterns, pattern_modifier = [], 0.0
            else:
                patterns, pattern_modifier = _raw_pattern  # type: ignore[misc]
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
                asset,
                tech,
                fg_value,
                correlation_smi_1y=float(corr),
                pattern_modifier=pattern_modifier,
            )
            signal = _score_to_signal(score)

            rsi = float(tech["RSI_14"].iloc[-1]) if "RSI_14" in tech.columns else 50.0
            macd_val = (
                float(tech["MACD_12_26_9"].iloc[-1]) if "MACD_12_26_9" in tech.columns else 0.0
            )
            macd_sig_val = (
                float(tech["MACDs_12_26_9"].iloc[-1]) if "MACDs_12_26_9" in tech.columns else 0.0
            )
            returns = tech["Close"].pct_change().dropna()
            vol_30d = (
                float(returns.rolling(30).std().iloc[-1] * (365**0.5) * 100)
                if len(returns) >= 30
                else 0.0
            )

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
                    correlation_smi_1y=round(float(corr), 3),
                    has_six_etp=has_etp,
                    price_chf=asset.price_chf,
                    market_cap_chf=asset.market_cap_chf,
                    price_change_24h_pct=asset.price_change_24h_pct,
                    price_change_7d_pct=asset.price_change_7d_pct,
                    ath_change_pct=asset.ath_change_pct,
                    market_cap_rank=asset.market_cap_rank,
                    timestamp=datetime.now(tz=UTC),
                    detected_patterns=patterns,
                    pattern_score=pattern_modifier,
                )
            )

        return sorted(results, key=lambda x: x.score, reverse=True)

    async def score_one(self, ticker_symbol: str) -> CryptoSignal | None:
        """Einzelsignal für einen Ticker (z.B. 'BTC', 'ETH').

        FIX-05: Standalone-Implementierung — ruft NICHT score_all() auf.
        Früher: score_one() → score_all() → 10× yfinance + 10× CoinGecko
        Jetzt:  score_one() → 1× yfinance + CoinGecko-Batch (für Marktdaten)
        """
        symbol_upper = ticker_symbol.upper()

        # Finde die Krypto-Config für diesen Ticker
        entry = next(
            (c for c in SUPPORTED_CRYPTOS if c[1].split("-")[0] == symbol_upper),
            None,
        )
        if entry is None:
            return None

        cg_id, yf_ticker, name, kategorie, has_etp = entry

        fear_greed, market_data_list, tech, corr, pattern_result = await asyncio.gather(
            self._fg.get_current(),
            self._cg.get_market_data([cg_id]),
            self._yf.get_technicals(yf_ticker),
            self._yf.get_smi_correlation(yf_ticker),
            self._pattern_svc.detect(yf_ticker),
            return_exceptions=True,
        )

        if isinstance(tech, Exception) or (isinstance(tech, pd.DataFrame) and tech.empty):
            _logger.warning("Keine Technikaldaten für %s — score_one() gibt None zurück", yf_ticker)
            return None

        fg_value = fear_greed["value"] if not isinstance(fear_greed, Exception) else 50
        fg_label = fear_greed["label"] if not isinstance(fear_greed, Exception) else "Neutral"

        market_list = market_data_list if not isinstance(market_data_list, Exception) else []
        mkt = market_list[0] if market_list else {}

        corr_val = float(corr) if not isinstance(corr, Exception) else 0.0
        if isinstance(pattern_result, Exception):
            patterns, pattern_modifier = [], 0.0
        else:
            patterns, pattern_modifier = pattern_result

        asset = CryptoAsset(
            ticker_cg=cg_id,
            ticker_yf=yf_ticker,
            name=name,
            symbol=symbol_upper,
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

        assert isinstance(tech, pd.DataFrame)
        score, components = self._scorer.score(
            asset,
            tech,
            fg_value,
            correlation_smi_1y=corr_val,
            pattern_modifier=pattern_modifier,
        )
        signal = _score_to_signal(score)

        rsi = float(tech["RSI_14"].iloc[-1]) if "RSI_14" in tech.columns else 50.0
        macd_val = float(tech["MACD_12_26_9"].iloc[-1]) if "MACD_12_26_9" in tech.columns else 0.0
        macd_sig_val = (
            float(tech["MACDs_12_26_9"].iloc[-1]) if "MACDs_12_26_9" in tech.columns else 0.0
        )
        returns = tech["Close"].pct_change().dropna()
        vol_30d = (
            float(returns.rolling(30).std().iloc[-1] * (365**0.5) * 100)
            if len(returns) >= 30
            else 0.0
        )

        reason = generate_signal_reason(
            signal=signal,
            asset_name=name,
            score=score,
            rsi=rsi,
            fear_greed=fg_value,
            change_7d=asset.price_change_7d_pct or 0.0,
        )

        return CryptoSignal(
            ticker=symbol_upper,
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
            correlation_smi_1y=round(corr_val, 3),
            has_six_etp=has_etp,
            price_chf=asset.price_chf,
            market_cap_chf=asset.market_cap_chf,
            price_change_24h_pct=asset.price_change_24h_pct,
            price_change_7d_pct=asset.price_change_7d_pct,
            ath_change_pct=asset.ath_change_pct,
            market_cap_rank=asset.market_cap_rank,
            timestamp=datetime.now(tz=UTC),
            detected_patterns=patterns,
            pattern_score=pattern_modifier,
        )


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
