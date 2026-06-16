"""Domain Value Object: ML Feature Vector für Swiss Quant ML-Layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MLFeatureVector:
    """Feature-Vektor für einen (ticker, snapshot_date)-Datenpunkt.

    Alle numerischen Features sind auf den jeweiligen Ticker bezogen und
    basieren auf öffentlich verfügbaren Daten (yfinance + SNB).
    """

    ticker: str
    snapshot_date: date

    # SwissQuantScorer-Komponenten (0–10)
    quant_score: float
    score_rendite: float
    score_sicherheit: float
    score_wachstum: float
    score_substanz: float

    # Technische Indikatoren (Preis-basiert)
    return_12m: float  # annualisierte 12-Monats-Rendite
    return_6m: float  # 6-Monats-Rendite (Momentum)
    return_3m: float  # 3-Monats-Rendite (Kurzzeit-Momentum)
    vol_30d: float  # 30-Tage-Volatilität (annualisiert)
    vol_90d: float  # 90-Tage-Volatilität (annualisiert)
    rsi_14: float  # RSI über 14 Tage (0–100)
    price_to_52w_high: float  # Preis / 52-Wochen-Hoch (0–1)
    vol_trend: float  # Avg-Volumen 20d / Avg-Volumen 60d (Volume-Momentum)
    macd_hist: float  # MACD histogram price-normalized (EMA12-EMA26 minus EMA9 signal line)
    bb_position: float  # position in Bollinger Bands: (price - lower) / (upper - lower), 0-1
    return_1m: float  # 1-month return (21 trading days)
    drawdown_12m: float  # max drawdown last 12 months (0 to -1, e.g. -0.25 = 25%)

    # Makro-Features
    snb_rate: float  # SNB Leitzins (%)
    chf_eur: float  # CHF/EUR Wechselkurs (CHF pro EUR)

    # Fundamental-Features (yfinance / SimFin; 0.0 wenn nicht verfügbar)
    pe_ratio: float  # Kurs-Gewinn-Verhältnis (trailing)
    pb_ratio: float  # Kurs-Buchwert-Verhältnis
    dividend_yield: float  # Dividendenrendite (z.B. 0.03 = 3%)
    revenue_growth: float  # Umsatzwachstum YoY (z.B. 0.10 = +10%)

    # Trainingslabel (None für aktuelle Inferenz)
    forward_return_12m: float | None  # 12-Monats-Vorwärtsrendite
    target_class: int | None  # 0=Bottom, 1=Mid, 2=Top Quartil

    def to_feature_dict(self) -> dict[str, float]:
        """Gibt nur numerische Features zurück (kein Label, kein Ticker/Datum)."""
        return {
            "quant_score": self.quant_score,
            "score_rendite": self.score_rendite,
            "score_sicherheit": self.score_sicherheit,
            "score_wachstum": self.score_wachstum,
            "score_substanz": self.score_substanz,
            "return_12m": self.return_12m,
            "return_6m": self.return_6m,
            "return_3m": self.return_3m,
            "vol_30d": self.vol_30d,
            "vol_90d": self.vol_90d,
            "rsi_14": self.rsi_14,
            "price_to_52w_high": self.price_to_52w_high,
            "vol_trend": self.vol_trend,
            "macd_hist": self.macd_hist,
            "bb_position": self.bb_position,
            "return_1m": self.return_1m,
            "drawdown_12m": self.drawdown_12m,
            "snb_rate": self.snb_rate,
            "chf_eur": self.chf_eur,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "dividend_yield": self.dividend_yield,
            "revenue_growth": self.revenue_growth,
        }

    FEATURE_NAMES: tuple[str, ...] = (
        "quant_score",
        "score_rendite",
        "score_sicherheit",
        "score_wachstum",
        "score_substanz",
        "return_12m",
        "return_6m",
        "return_3m",
        "vol_30d",
        "vol_90d",
        "rsi_14",
        "price_to_52w_high",
        "vol_trend",
        "macd_hist",
        "bb_position",
        "return_1m",
        "drawdown_12m",
        "snb_rate",
        "chf_eur",
        "pe_ratio",
        "pb_ratio",
        "dividend_yield",
        "revenue_growth",
    )
