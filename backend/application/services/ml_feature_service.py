"""Application Service: ML Feature Engineering für Swiss Quant ML-Layer.

Berechnet Feature-Vektoren für Training (build_dataset) und Inferenz (build_features).
Features: 5 Quant-Scores, 12M/6M/3M-Return, Vol(30d/90d), RSI(14),
          Price-to-52W-High, Volume-Trend, SNB-Rate, CHF/EUR.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.domain.services.swiss_quant_scorer import SwissQuantScorer
from backend.domain.value_objects.ml_feature_vector import MLFeatureVector
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter

_logger = logging.getLogger(__name__)

# SNB Leitzins-History (näherungsweise, quartalsweise)
_SNB_RATE_HISTORY: list[tuple[date, float]] = [
    (date(2022, 9, 23), 0.5),
    (date(2022, 12, 16), 1.0),
    (date(2023, 3, 23), 1.5),
    (date(2023, 6, 22), 1.75),
    (date(2024, 3, 21), 1.5),
    (date(2024, 6, 20), 1.25),
    (date(2024, 9, 26), 1.0),
    (date(2024, 12, 12), 0.5),
    (date(2025, 3, 20), 0.25),
    (date(2025, 6, 19), 0.0),
]
_SNB_RATE_BEFORE_2022 = -0.75


def _snb_rate_on(target: date) -> float:
    """Gibt den SNB Leitzins zum Stichtag zurück (stufenweise)."""
    rate = _SNB_RATE_BEFORE_2022
    for effective_date, r in _SNB_RATE_HISTORY:
        if target >= effective_date:
            rate = r
    return rate


def _compute_rsi(prices: pd.Series, window: int = 14) -> float:
    """Berechnet den RSI über `window` Perioden (0–100)."""
    delta = prices.diff().dropna()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_gain = gains.rolling(window).mean().iloc[-1]
    avg_loss = losses.rolling(window).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return 50.0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(100.0 - 100.0 / (1.0 + rs))


def _score_wachstum(f: SwissFundamentals) -> float:
    """Wachstums-Score als Proxy aus EPS-Vorzeichen + P/E-Niveau."""
    if f.eps_chf is None or f.eps_chf <= 0:
        return 10.0 if (f.eps_chf is not None and f.eps_chf <= 0) else 50.0
    if f.pe_ratio is None:
        return 50.0
    if f.pe_ratio < 15:
        return 70.0  # Value mit positivem Gewinn
    if f.pe_ratio < 25:
        return 60.0
    if f.pe_ratio < 40:
        return 50.0
    return 40.0  # Sehr teuer, Wachstum schon eingepreist


class MLFeatureService:
    """Berechnet Feature-Vektoren für das Swiss Quant ML-Modell."""

    def __init__(
        self,
        yfinance_adapter: YFinanceSwissAdapter | None = None,
        scorer: SwissQuantScorer | None = None,
    ) -> None:
        self._adapter = yfinance_adapter or YFinanceSwissAdapter()
        self._scorer = scorer or SwissQuantScorer()

    # ------------------------------------------------------------------
    # Inferenz: aktueller Feature-Vektor für einen Ticker
    # ------------------------------------------------------------------

    async def build_features(self, ticker: str) -> MLFeatureVector | None:
        """Berechnet den aktuellen Feature-Vektor (für REST-Inferenz).

        Returns None bei fehlenden Marktdaten.
        """
        ticker_upper = ticker.upper()
        try:
            fundamentals = await self._adapter.get_fundamentals(ticker_upper)
        except Exception as exc:
            _logger.warning("Fundamentals für %s nicht verfügbar: %s", ticker_upper, exc)
            return None

        try:
            prices = await self._adapter.get_price_history(ticker_upper, days=400)
        except Exception as exc:
            _logger.warning("Preishistorie für %s nicht verfügbar: %s", ticker_upper, exc)
            return None

        if prices is None or len(prices) < 30:
            return None

        score = self._scorer.score(ticker_upper, fundamentals)
        today = date.today()
        close = prices["Close"].squeeze()
        volume = prices["Volume"].squeeze() if "Volume" in prices.columns else None

        return MLFeatureVector(
            ticker=ticker_upper,
            snapshot_date=today,
            quant_score=score.composite,
            score_rendite=score.income_score,
            score_sicherheit=score.quality_score,
            score_wachstum=_score_wachstum(fundamentals),
            score_substanz=score.value_score,
            return_12m=_return_12m(prices),
            return_6m=_return_nm_from_series(close, 126),
            return_3m=_return_nm_from_series(close, 63),
            vol_30d=_vol_30d(prices),
            vol_90d=_vol_nd_from_series(close, 90),
            rsi_14=_compute_rsi(close),
            price_to_52w_high=_price_to_52w_high_from_series(close),
            vol_trend=_vol_trend_from_series(volume),
            snb_rate=_snb_rate_on(today),
            chf_eur=_current_chf_eur(),
            forward_return_12m=None,
            target_class=None,
        )

    # ------------------------------------------------------------------
    # Batch: historisches Feature-Dataset für Training
    # ------------------------------------------------------------------

    def build_dataset(
        self,
        tickers: list[str],
        years: int = 3,
    ) -> pd.DataFrame:
        """Baut historisches Feature-Dataset für ML-Training.

        Monatliche Snapshots über `years` Jahre für alle `tickers`.
        Target = 3-Klassen-Label (Bottom/Mid/Top Quartil der 12M-Vorwärtsrendite).

        Returns DataFrame mit Spalten:
          ticker, snapshot_date, quant_score, score_rendite, score_sicherheit,
          score_wachstum, score_substanz, return_12m, vol_30d, rsi_14,
          snb_rate, chf_eur, forward_return_12m, target_class
        """
        import yfinance as yf

        end_date = pd.Timestamp.now().normalize()  # timezone-naive für konsistente Vergleiche
        start_date = end_date - pd.DateOffset(years=years + 1)  # +1 Jahr für Forward-Return

        rows: list[dict[str, Any]] = []

        for ticker in tickers:
            yf_ticker = ticker.upper() + ".SW"
            try:
                hist = yf.download(yf_ticker, start=start_date, end=end_date, progress=False)
                if hist is None or len(hist) < 60:
                    _logger.warning("Zu wenig Daten für %s, überspringe", ticker)
                    continue
                close = hist["Close"].squeeze()
                if close.index.tz is not None:
                    close.index = close.index.tz_convert(None)
            except Exception as exc:
                _logger.warning("yfinance-Download für %s fehlgeschlagen: %s", ticker, exc)
                continue

            # Fundamentals (Punkt-in-Zeit — Vereinfachung für Capstone)
            fund = _stub_fundamentals(ticker)
            score = self._scorer.score(ticker.upper(), fund)
            s_wachstum = _score_wachstum(fund)

            # Monatliche Snapshots
            snapshot_dates = pd.date_range(
                start=start_date + pd.DateOffset(days=252),
                end=end_date - pd.DateOffset(days=252),
                freq="MS",  # Monatsanfang
            )

            for snap_dt in snapshot_dates:
                snap = snap_dt.normalize()
                mask_past = close.index <= snap
                mask_future = close.index > snap

                past_prices = close[mask_past].tail(400)
                future_prices = close[mask_future].head(252)

                if len(past_prices) < 60 or len(future_prices) < 200:
                    continue

                fwd_ret = float((future_prices.iloc[-1] / future_prices.iloc[0]) - 1)
                ret_12m = _return_12m_from_series(past_prices)
                ret_6m = _return_nm_from_series(past_prices, 126)
                ret_3m = _return_nm_from_series(past_prices, 63)
                vol = _vol_30d_from_series(past_prices)
                vol90 = _vol_nd_from_series(past_prices, 90)
                rsi = _compute_rsi(past_prices.tail(30))
                p52wh = _price_to_52w_high_from_series(past_prices)
                # Volume-Trend aus hist["Volume"] wenn vorhanden
                vol_col = hist["Volume"].squeeze() if "Volume" in hist.columns else None
                vol_t = _vol_trend_from_series(
                    vol_col[mask_past].tail(400) if vol_col is not None else None
                )
                snap_date = snap.date()

                rows.append(
                    {
                        "ticker": ticker.upper(),
                        "snapshot_date": snap_date,
                        "quant_score": score.composite,
                        "score_rendite": score.income_score,
                        "score_sicherheit": score.quality_score,
                        "score_wachstum": s_wachstum,
                        "score_substanz": score.value_score,
                        "return_12m": ret_12m,
                        "return_6m": ret_6m,
                        "return_3m": ret_3m,
                        "vol_30d": vol,
                        "vol_90d": vol90,
                        "rsi_14": rsi,
                        "price_to_52w_high": p52wh,
                        "vol_trend": vol_t,
                        "snb_rate": _snb_rate_on(snap_date),
                        "chf_eur": _chf_eur_on(snap),
                        "forward_return_12m": fwd_ret,
                        "target_class": None,  # wird cross-sektional befüllt
                    }
                )

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # Cross-sektionales Quartil-Label pro Snapshot-Datum
        df["target_class"] = df.groupby("snapshot_date")["forward_return_12m"].transform(
            lambda x: pd.qcut(x, q=3, labels=[0, 1, 2], duplicates="drop")
        )
        return df.dropna(subset=["target_class"])


# ------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------


def _return_12m(prices: Any) -> float:
    close = prices["Close"].squeeze() if isinstance(prices, pd.DataFrame) else prices
    if len(close) < 252:
        return 0.0
    return float((close.iloc[-1] / close.iloc[-252]) - 1)


def _return_12m_from_series(close: pd.Series) -> float:
    if len(close) < 252:
        return 0.0
    return float((close.iloc[-1] / close.iloc[-252]) - 1)


def _vol_30d(prices: Any) -> float:
    close = prices["Close"].squeeze() if isinstance(prices, pd.DataFrame) else prices
    if len(close) < 30:
        return 0.0
    ret = close.pct_change().dropna()
    return float(ret.tail(30).std() * np.sqrt(252))


def _vol_30d_from_series(close: pd.Series) -> float:
    if len(close) < 30:
        return 0.0
    ret = close.pct_change().dropna()
    return float(ret.tail(30).std() * np.sqrt(252))


def _current_chf_eur() -> float:
    """Holt aktuellen CHF/EUR aus yfinance (EUR/CHF invertiert)."""
    try:
        import yfinance as yf

        fx = yf.download("EURCHF=X", period="5d", progress=False)
        if fx is not None and len(fx) > 0:
            eur_chf = float(fx["Close"].iloc[-1])
            return round(1 / eur_chf, 6) if eur_chf > 0 else 0.93
    except Exception:
        pass
    return 0.93  # Fallback: ca. CHF 0.93 per EUR


def _return_nm_from_series(close: pd.Series, n_days: int) -> float:
    """N-Tage-Return (z.B. 126 ≈ 6 Monate, 63 ≈ 3 Monate)."""
    if len(close) < n_days:
        return 0.0
    return float((close.iloc[-1] / close.iloc[-n_days]) - 1)


def _vol_nd_from_series(close: pd.Series, n_days: int) -> float:
    """N-Tage-Volatilität annualisiert."""
    if len(close) < n_days:
        return 0.0
    ret = close.pct_change().dropna()
    return float(ret.tail(n_days).std() * np.sqrt(252))


def _price_to_52w_high_from_series(close: pd.Series) -> float:
    """Aktueller Preis / 52-Wochen-Hoch. Gibt 0.0 zurück bei fehlenden Daten."""
    if len(close) < 2:
        return 0.0
    lookback = min(len(close), 252)
    high_52w = close.tail(lookback).max()
    if high_52w <= 0 or pd.isna(high_52w):
        return 0.0
    return float(close.iloc[-1] / high_52w)


def _vol_trend_from_series(volume: pd.Series | None) -> float:
    """Avg-Volumen 20d / Avg-Volumen 60d. Gibt 1.0 (neutral) zurück bei fehlenden Daten."""
    if volume is None or len(volume) < 60:
        return 1.0
    avg_20 = volume.tail(20).mean()
    avg_60 = volume.tail(60).mean()
    if avg_60 <= 0 or pd.isna(avg_60) or pd.isna(avg_20):
        return 1.0
    return float(avg_20 / avg_60)


def _chf_eur_on(snap_dt: pd.Timestamp) -> float:
    """Approximiert CHF/EUR für historische Snapshots (Näherungswert)."""
    # Vereinfachung für Capstone: statischer Wert pro Quartal
    year = snap_dt.year
    if year <= 2022:
        return 0.92
    if year == 2023:
        return 0.94
    if year == 2024:
        return 0.95
    return 0.93


def _stub_fundamentals(ticker: str) -> SwissFundamentals:
    """Approximierte Fundamentals für historische Snapshots.

    Für ein Capstone-Projekt ohne Bloomberg: aktuelle Fundamentals als
    Proxy für die gesamte 3-Jahres-Trainingsperiode. Produziert ein
    starkes Point-in-Time-Bias, aber ausreichend für Demonstrations-Training.
    """
    from decimal import Decimal

    try:
        import yfinance as yf

        info = yf.Ticker(ticker.upper() + ".SW").info
        return SwissFundamentals(
            market_cap_chf=Decimal(str(info.get("marketCap") or 0)) or None,
            pe_ratio=info.get("trailingPE"),
            pb_ratio=info.get("priceToBook"),
            dividend_yield=info.get("dividendYield"),
            eps_chf=info.get("trailingEps"),
        )
    except Exception:
        return SwissFundamentals(
            market_cap_chf=None,
            pe_ratio=None,
            pb_ratio=None,
            dividend_yield=None,
            eps_chf=None,
        )
