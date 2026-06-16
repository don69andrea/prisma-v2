"""CryptoSignal — Scoring-Ergebnis für eine Kryptowährung."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class CryptoSignal:
    """Immutabler Value Object: Signal + Score + Metriken für ein Krypto-Asset."""

    ticker: str
    name: str
    signal: Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
    score: float
    score_components: dict[str, float]
    signal_reason_de: str
    fear_greed_value: int
    fear_greed_label: str
    rsi_14: float
    macd_signal: Literal["bullish", "bearish"]
    volatility_30d_pct: float
    correlation_smi_1y: float
    has_six_etp: bool
    price_chf: float | None
    market_cap_chf: float | None
    price_change_24h_pct: float | None
    price_change_7d_pct: float | None
    ath_change_pct: float | None
    market_cap_rank: int | None
    timestamp: datetime
    detected_patterns: list[str] = field(default_factory=list)
    pattern_score: float = 0.0
