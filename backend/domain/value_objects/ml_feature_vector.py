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

    # Makro-Features
    snb_rate: float  # SNB Leitzins (%)
    chf_eur: float  # CHF/EUR Wechselkurs (CHF pro EUR)

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
            "snb_rate": self.snb_rate,
            "chf_eur": self.chf_eur,
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
        "snb_rate",
        "chf_eur",
    )
