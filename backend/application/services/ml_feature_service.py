"""Application Service: ML Feature Engineering für Swiss Quant ML-Layer.

Berechnet Feature-Vektoren für Training (build_dataset) und Inferenz (build_features).
Features: 5 Quant-Scores, 12M/6M/3M-Return, Vol(30d/90d), RSI(14),
          Price-to-52W-High, Volume-Trend, SNB-Rate, CHF/EUR.
"""

from __future__ import annotations

import asyncio
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

# Datum der letzten manuellen Aktualisierung der Makro-Daten.
# Wenn dieser Wert >7 Tage in der Vergangenheit liegt, wird beim Start eine Warnung geloggt.
# BITTE bei jeder Aktualisierung der Listen unten dieses Datum anpassen.
_MACRO_DATA_LAST_UPDATED = date(2025, 6, 13)
_MACRO_STALENESS_THRESHOLD_DAYS = 7


def _check_macro_staleness() -> None:
    """Warnt, wenn die hartcodierten Makro-Daten zu alt sind."""
    days_old = (date.today() - _MACRO_DATA_LAST_UPDATED).days
    if days_old > _MACRO_STALENESS_THRESHOLD_DAYS:
        _logger.warning(
            "ACHTUNG: Makro-Daten (SNB/ECB/FED Zinsen, FX-Kurse) sind %d Tage alt "
            "(zuletzt aktualisiert: %s). Bitte ml_feature_service.py manuell aktualisieren "
            "oder eine API-Integration einrichten.",
            days_old,
            _MACRO_DATA_LAST_UPDATED.isoformat(),
        )


# SNB Leitzins-History (näherungsweise, quartalsweise)
# ACHTUNG: Manuell gepflegt — zuletzt aktualisiert: 2025-06-13
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
    # Zinssätze per 2026-06-13 — manuell aktualisieren wenn neue Sitzungen stattfinden
    (date(2025, 9, 18), 0.0),
    (date(2025, 12, 11), 0.0),
    (date(2026, 3, 19), 0.0),
]
_SNB_RATE_BEFORE_2022 = -0.75

# ECB Einlagenzins-History (Deposit Facility Rate)
_ECB_RATE_HISTORY: list[tuple[date, float]] = [
    (date(2022, 7, 27), 0.00),
    (date(2022, 9, 14), 0.75),
    (date(2022, 10, 27), 1.50),
    (date(2022, 12, 15), 2.00),
    (date(2023, 2, 2), 2.50),
    (date(2023, 3, 22), 3.00),
    (date(2023, 5, 10), 3.25),
    (date(2023, 6, 21), 3.50),
    (date(2023, 7, 27), 3.75),
    (date(2024, 6, 12), 3.50),
    (date(2024, 9, 18), 3.25),
    (date(2024, 10, 23), 3.00),
    (date(2024, 12, 18), 2.75),
    (date(2025, 1, 30), 2.50),
    (date(2025, 3, 6), 2.25),
    (date(2025, 4, 17), 2.00),
    (date(2025, 6, 5), 1.75),
    # Zinssätze per 2026-06-13 — manuell aktualisieren wenn neue Sitzungen stattfinden
    (date(2025, 9, 12), 1.50),
    (date(2025, 10, 30), 1.25),
    (date(2026, 1, 30), 1.00),
    (date(2026, 3, 6), 0.75),
]
_ECB_RATE_BEFORE_2022 = -0.50
# ACHTUNG: Manuell gepflegt — zuletzt aktualisiert: 2025-06-13


def _ecb_rate_on(target: date) -> float:
    """Gibt den ECB Einlagenzins zum Stichtag zurück."""
    rate = _ECB_RATE_BEFORE_2022
    for effective_date, r in _ECB_RATE_HISTORY:
        if target >= effective_date:
            rate = r
    return rate


# Fed Funds Rate (Upper Bound) History
# ACHTUNG: Manuell gepflegt — zuletzt aktualisiert: 2025-06-13
_FED_RATE_HISTORY: list[tuple[date, float]] = [
    (date(2018, 3, 22), 1.75),
    (date(2018, 6, 14), 2.00),
    (date(2018, 9, 27), 2.25),
    (date(2018, 12, 20), 2.50),
    (date(2019, 8, 1), 2.25),
    (date(2019, 9, 19), 2.00),
    (date(2019, 10, 31), 1.75),
    (date(2020, 3, 4), 1.25),
    (date(2020, 3, 16), 0.25),
    (date(2022, 3, 17), 0.50),
    (date(2022, 5, 5), 1.00),
    (date(2022, 6, 16), 1.75),
    (date(2022, 7, 28), 2.50),
    (date(2022, 9, 22), 3.25),
    (date(2022, 11, 3), 4.00),
    (date(2022, 12, 15), 4.50),
    (date(2023, 2, 2), 4.75),
    (date(2023, 3, 23), 5.00),
    (date(2023, 5, 4), 5.25),
    (date(2023, 7, 27), 5.50),
    (date(2024, 9, 19), 5.00),
    (date(2024, 11, 8), 4.75),
    (date(2024, 12, 19), 4.50),
    (date(2025, 3, 20), 4.25),
    # Zinssätze per 2026-06-13 — manuell aktualisieren wenn neue Sitzungen stattfinden
    (date(2025, 6, 18), 4.25),
    (date(2025, 9, 17), 4.00),
    (date(2025, 12, 10), 3.75),
    (date(2026, 3, 18), 3.50),
]
_FED_RATE_BEFORE_2018 = 1.25


def _fed_rate_on(target: date) -> float:
    """Gibt den Fed Funds Rate (Upper Bound) zum Stichtag zurück."""
    rate = _FED_RATE_BEFORE_2018
    for effective_date, r in _FED_RATE_HISTORY:
        if target >= effective_date:
            rate = r
    return rate


# Exchange suffix → yfinance suffix mapping for non-Swiss stocks
_EU_YF_SUFFIX: dict[str, str] = {
    ".DE": ".DE",  # Xetra (Deutschland)
    ".PA": ".PA",  # Euronext Paris
    ".AS": ".AS",  # Euronext Amsterdam
    ".MC": ".MC",  # Bolsa Madrid
    ".MI": ".MI",  # Borsa Italiana
    ".L": ".L",  # London Stock Exchange (GBP)
    ".ST": ".ST",  # Nasdaq Stockholm (SEK)
    ".VI": ".VI",  # Wiener Börse (EUR)
    ".BR": ".BR",  # Euronext Brüssel (EUR)
}


def _ticker_to_yf(ticker: str) -> str:
    """Konvertiert internen Ticker zu yfinance-Format."""
    overrides = {"ROG": "RO.SW"}
    if ticker in overrides:
        return overrides[ticker]
    if "." in ticker:
        return ticker  # EU-Ticker haben bereits Börsen-Suffix
    return f"{ticker}.SW"  # Swiss default


def _is_eu_ticker(ticker: str) -> bool:
    """True wenn es sich um einen EU-Ticker (nicht Swiss) handelt."""
    if "." not in ticker:
        return False
    suffix = "." + ticker.rsplit(".", 1)[-1].upper()
    return suffix in _EU_YF_SUFFIX


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


def _compute_macd_hist(close: pd.Series) -> float:
    """MACD histogram (EMA12-EMA26 - EMA9 signal), price-normalized."""
    if len(close) < 35:
        return 0.0
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = float(macd_line.iloc[-1] - signal_line.iloc[-1])
    price = float(close.iloc[-1])
    if price <= 0:
        return 0.0
    return hist / price


def _compute_bb_position(close: pd.Series, window: int = 20) -> float:
    """Position in Bollinger Bands (0 = lower band, 1 = upper band)."""
    if len(close) < window:
        return 0.5
    tail = close.tail(window)
    sma = float(tail.mean())
    std = float(tail.std())
    if std <= 0:
        return 0.5
    upper = sma + 2 * std
    lower = sma - 2 * std
    band_range = upper - lower
    if band_range <= 0:
        return 0.5
    pos = (float(close.iloc[-1]) - lower) / band_range
    return max(-0.5, min(1.5, pos))


def _compute_drawdown_12m(close: pd.Series) -> float:
    """Max drawdown over last 252 trading days (0 to -1)."""
    if len(close) < 2:
        return 0.0
    lookback = min(len(close), 252)
    window = close.tail(lookback)
    rolling_max = window.cummax()
    # W-11: replace zero rolling_max with NaN to avoid division-by-zero
    # (can occur for delisted tickers with zero prices)
    safe_max = rolling_max.replace(0, float("nan"))
    drawdowns = (window - safe_max) / safe_max
    result = drawdowns.min()
    return 0.0 if pd.isna(result) else float(result)


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
        _check_macro_staleness()

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
        chf_eur = await asyncio.to_thread(_current_chf_eur)  # K-11: offload blocking yfinance call

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
            macd_hist=_compute_macd_hist(close),
            bb_position=_compute_bb_position(close),
            return_1m=_return_nm_from_series(close, 21),
            drawdown_12m=_compute_drawdown_12m(close),
            snb_rate=_snb_rate_on(today),
            chf_eur=chf_eur,
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
        simfin_adapter: object | None = None,
        ticker_markets: dict[str, str] | None = None,
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
            t = ticker.upper()
            _market = (ticker_markets or {}).get(ticker, None) or (
                "eu" if _is_eu_ticker(t) else "ch"
            )
            # US-Ticker brauchen kein Exchange-Suffix in yfinance
            yf_ticker = t if _market == "us" else _ticker_to_yf(t)
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

            # Fundamentals: SimFin (historisch) wenn verfügbar, sonst aktueller Stub
            _use_simfin = simfin_adapter is not None
            if not _use_simfin:
                fund = _stub_fundamentals(ticker, _market)
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

                # Per-Snapshot Fundamentals wenn SimFin verfügbar (behebt Point-in-Time Bias)
                if _use_simfin:
                    _sf_fund = simfin_adapter.get_fundamentals_on_date(  # type: ignore[union-attr]
                        ticker, snap_date, _market
                    )
                    fund = _sf_fund if _sf_fund is not None else _stub_fundamentals(ticker, _market)
                    score = self._scorer.score(ticker.upper(), fund)
                    s_wachstum = _score_wachstum(fund)

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
                        "macd_hist": _compute_macd_hist(past_prices),
                        "bb_position": _compute_bb_position(past_prices),
                        "return_1m": _return_nm_from_series(past_prices, 21),
                        "drawdown_12m": _compute_drawdown_12m(past_prices),
                        "snb_rate": (
                            _fed_rate_on(snap_date)
                            if _market == "us"
                            else _ecb_rate_on(snap_date)
                            if _market == "eu"
                            else _snb_rate_on(snap_date)
                        ),
                        "chf_eur": _fx_rate_on(ticker, snap, _market),
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


def _usd_chf_on(year: int) -> float:
    """Approximierter USD/CHF Kurs (CHF pro USD) per Jahr."""
    _rates = {
        2015: 0.99,
        2016: 0.99,
        2017: 0.97,
        2018: 0.99,
        2019: 1.00,
        2020: 0.94,
        2021: 0.92,
        2022: 0.96,
        2023: 0.89,
        2024: 0.89,
        2025: 0.88,
    }
    return _rates.get(year, 0.93)


def _gbp_chf_on(year: int) -> float:
    """Approximierter GBP/CHF Kurs (CHF pro GBP) per Jahr."""
    _rates = {
        2015: 1.48,
        2016: 1.27,
        2017: 1.27,
        2018: 1.31,
        2019: 1.26,
        2020: 1.19,
        2021: 1.26,
        2022: 1.18,
        2023: 1.12,
        2024: 1.13,
        2025: 1.15,
    }
    return _rates.get(year, 1.15)


def _fx_rate_on(ticker: str, snap: pd.Timestamp, market: str) -> float:
    """CHF-relative FX-Rate für historische Snapshots (Training)."""
    if market == "us":
        return _usd_chf_on(snap.year)
    if market == "ch":
        return _chf_eur_on(snap)
    # EU markets: dispatch by suffix
    suffix = ("." + ticker.rsplit(".", 1)[-1].upper()) if "." in ticker else ""
    if suffix == ".L":
        return _gbp_chf_on(snap.year)
    if suffix == ".ST":
        return 0.094  # SEK/CHF näherungsweise stabil
    return 1.0  # EUR-denominierte Märkte (DE, FR, NL, ES, IT, BE, AT)


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


def _stub_fundamentals(ticker: str, market: str = "ch") -> SwissFundamentals:
    """Aktuelle Fundamentals als Proxy für historische Snapshots (Point-in-Time Bias).

    Fallback wenn SimFin keine Daten liefert. Markt-Parameter steuert
    das yfinance-Ticker-Format (CH: NESN.SW, EU: SAP.DE, US: AAPL).
    """
    from decimal import Decimal

    try:
        import yfinance as yf

        yf_sym = ticker.upper() if market in ("eu", "us") else _ticker_to_yf(ticker.upper())
        info = yf.Ticker(yf_sym).info
        # W-12: Decimal("0") is falsy, so `Decimal(...) or None` incorrectly returns None
        # for a valid zero market cap. Use explicit None-check instead.
        _mc = info.get("marketCap")
        return SwissFundamentals(
            market_cap_chf=Decimal(str(_mc)) if _mc is not None else None,
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
