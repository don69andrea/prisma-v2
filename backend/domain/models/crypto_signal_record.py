"""CryptoSignalRecord — persistierter täglicher Signal-Snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CryptoSignalRecord:
    """Ein Snapshot-Eintrag in `crypto_signals` — ein Eintrag pro Ticker pro Tag."""

    ticker: str
    signal: str
    score: float
    components: dict[str, float] = field(default_factory=dict)
    price_chf: float | None = None
    price_change_24h: float | None = None
    fear_greed_value: int | None = None
    rsi_14: float | None = None
    macd_signal: str | None = None
    volatility_30d_pct: float | None = None
    detected_patterns: list[str] = field(default_factory=list)
    pattern_score: float | None = None
    agent_analysis: str | None = None
    created_at: datetime | None = None
    id: str | None = None
