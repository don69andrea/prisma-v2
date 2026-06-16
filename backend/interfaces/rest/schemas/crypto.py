"""Pydantic Response-Modelle für /api/v1/crypto/*."""

from __future__ import annotations

from pydantic import BaseModel

from backend.domain.value_objects.crypto_signal import CryptoSignal


class CryptoSignalResponse(BaseModel):
    ticker: str
    name: str
    signal: str
    score: float
    score_components: dict[str, float]
    signal_reason_de: str
    price_chf: float | None
    market_cap_chf: float | None
    price_change_24h_pct: float | None
    price_change_7d_pct: float | None
    ath_change_pct: float | None
    market_cap_rank: int | None
    rsi_14: float
    macd_signal: str
    volatility_30d_pct: float
    correlation_smi_1y: float
    fear_greed_value: int
    fear_greed_label: str
    has_six_etp: bool
    timestamp: str
    detected_patterns: list[str] = []
    pattern_score: float = 0.0
    agent_analysis: str | None = None

    @classmethod
    def from_domain(cls, signal: CryptoSignal) -> CryptoSignalResponse:
        return cls(
            ticker=signal.ticker,
            name=signal.name,
            signal=signal.signal,
            score=signal.score,
            score_components=signal.score_components,
            signal_reason_de=signal.signal_reason_de,
            price_chf=signal.price_chf,
            market_cap_chf=signal.market_cap_chf,
            price_change_24h_pct=signal.price_change_24h_pct,
            price_change_7d_pct=signal.price_change_7d_pct,
            ath_change_pct=signal.ath_change_pct,
            market_cap_rank=signal.market_cap_rank,
            rsi_14=signal.rsi_14,
            macd_signal=signal.macd_signal,
            volatility_30d_pct=signal.volatility_30d_pct,
            correlation_smi_1y=signal.correlation_smi_1y,
            fear_greed_value=signal.fear_greed_value,
            fear_greed_label=signal.fear_greed_label,
            has_six_etp=signal.has_six_etp,
            timestamp=signal.timestamp.isoformat(),
        )
