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

# Datum der letzten manuellen Aktualisierung der Makro-Daten.
# Wenn dieser Wert >7 Tage in der Vergangenheit liegt, wird beim Start eine Warnung geloggt.
# BITTE bei jeder Aktualisierung der Listen unten dieses Datum anpassen.
_MACRO_DATA_LAST_UPDATED = date(2026, 6, 14)
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
    (date(2026, 6, 14), 0.0),
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
    (date(2026, 6, 14), 0.75),
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
    (date(2026, 6, 14), 3.50),
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
    """SNB-Leitzins zum Stichtag — Fallback wenn macro_rates-Tabelle leer."""
    rate = _SNB_RATE_BEFORE_2022
    for effective_date, r in _SNB_RATE_HISTORY:
        if target >= effective_date:
            rate = r
    return rate


async def _snb_rate_from_db(target: date) -> float | None:
    """Liest SNB-Leitzins aus macro_rates-Tabelle; None wenn keine Daten."""
    from sqlalchemy import text

    from backend.infrastructure.persistence.session import get_session_factory

    try:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                text(
                    "SELECT rate_pct FROM macro_rates "
                    "WHERE rate_type = 'snb_policy' AND effective_date <= :d "
                    "ORDER BY effective_date DESC LIMIT 1"
                ),
                {"d": target},
            )
            row = result.fetchone()
            return float(row[0]) if row else None
    except Exception as exc:
        _logger.debug("macro_rates nicht erreichbar (%s) — nutze Fallback", exc)
        return None


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


def _empty_fundamentals() -> SwissFundamentals:
    """Leerer Fundamentals-Stub (Null-Werte) für den Pfad ohne SimFin."""
    from decimal import Decimal

    return SwissFundamentals(
        market_cap_chf=Decimal(0),
        pe_ratio=None,
        pb_ratio=None,
        dividend_yield=None,
        eps_chf=None,
        revenue_growth=None,
    )


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
        # ECB statt yfinance — funktioniert von Render-IPs, kein Rate-Limit
        from backend.infrastructure.adapters.ecb_fx_adapter import fetch_chf_eur as _ecb_chf_eur

        chf_eur = await _ecb_chf_eur()
        snb_rate = await _snb_rate_from_db(today) or _snb_rate_on(today)

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
            snb_rate=snb_rate,
            chf_eur=chf_eur,
            pe_ratio=fundamentals.pe_ratio or 0.0,
            pb_ratio=fundamentals.pb_ratio or 0.0,
            dividend_yield=fundamentals.dividend_yield or 0.0,
            revenue_growth=fundamentals.revenue_growth or 0.0,
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

            # Fundamentals: SimFin (historisch) wenn verfügbar, sonst leerer Stub
            _use_simfin = simfin_adapter is not None
            if not _use_simfin:
                fund = _empty_fundamentals()
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
                    fund = _sf_fund if _sf_fund is not None else _empty_fundamentals()
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
                        "snb_rate": _snb_rate_on(snap_date),
                        "chf_eur": _chf_eur_on(snap),
                        "pe_ratio": fund.pe_ratio or 0.0,
                        "pb_ratio": fund.pb_ratio or 0.0,
                        "dividend_yield": fund.dividend_yield or 0.0,
                        "revenue_growth": fund.revenue_growth or 0.0,
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
    # Vereinfachung: statischer Näherungswert pro Quartal
    year = snap_dt.year
    if year <= 2022:
        return 0.92
    if year == 2023:
        return 0.94
    if year == 2024:
        return 0.95
    return 0.93


# ---------------------------------------------------------------------------
# TEIL F §F2/§F3 — Feature-Set (nur Preis/Technik + Makro, KEINE Fundamentals)
# ---------------------------------------------------------------------------

TEIL_F_FEATURE_COLS: tuple[str, ...] = (
    "return_1m",
    "return_3m",
    "return_6m",
    "return_12m",
    "vol_30d",
    "vol_90d",
    "rsi_14",
    "price_to_52w_high",
    "momentum_vs_smi_3m",
    "bb_position",
    "macd_hist",
    "drawdown_12m",
    "snb_rate",
    "chf_eur",
    "inflation_ch",
)


def build_target_excess_30d(
    close: pd.Series,
    smi_close: pd.Series,
    snap: pd.Timestamp,
) -> float | None:
    """30-Handelstage-Forward-Excess-Return des Titels vs. SMI.

    PIT: nutzt ausschliesslich Daten nach snap+1.
    Gibt None zurück wenn < 30 Handelstage Zukunft vorhanden (Datenrand).
    Überlappung der 30d-Fenster ist dokumentiert → Purged/Embargoed CV Pflicht (Kap. 16).
    """
    future_stock = close[close.index > snap].head(30)
    future_smi = smi_close[smi_close.index > snap].head(30)
    if len(future_stock) < 30 or len(future_smi) < 30:
        return None
    stock_ret = float(future_stock.iloc[-1] / future_stock.iloc[0]) - 1
    smi_ret = float(future_smi.iloc[-1] / future_smi.iloc[0]) - 1
    return stock_ret - smi_ret


async def _macro_series_from_db(
    rate_type: str,
) -> list[tuple[date, float]]:
    """Lädt eine Makro-Serie aus macro_rates (aufsteigend nach Datum)."""
    from sqlalchemy import text

    from backend.infrastructure.persistence.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                "SELECT effective_date, rate_pct FROM macro_rates "
                "WHERE rate_type = :rt ORDER BY effective_date ASC"
            ),
            {"rt": rate_type},
        )
        return [(row[0], float(row[1])) for row in result.fetchall()]


def _step_value_on(series: list[tuple[date, float]], target: date, default: float) -> float:
    """Step-Funktion: letzter Wert, dessen effective_date <= target."""
    val = default
    for effective_date, rate in series:
        if target >= effective_date:
            val = rate
    return val


async def build_dataset_v3(
    tickers: list[str],
    smi_ticker: str = "^SSMI",
    freq_months: int = 1,
) -> pd.DataFrame:
    """Baut historisches Feature-Dataset nach TEIL F §F2 aus der DB.

    Liest ausschliesslich aus stock_price_history + macro_rates.
    KEINE yfinance-Live-Calls, KEINE Fundamentals.
    Monatliche Snapshots, Target = build_target_excess_30d.
    """
    from sqlalchemy import text

    from backend.infrastructure.persistence.session import get_session_factory

    factory = get_session_factory()

    async def _load_prices(ticker: str) -> pd.Series:
        async with factory() as sess:
            r = await sess.execute(
                text(
                    "SELECT date, close FROM stock_price_history "
                    "WHERE ticker = :t ORDER BY date ASC"
                ),
                {"t": ticker},
            )
            rows = r.fetchall()
        if not rows:
            return pd.Series(dtype=float)
        idx = pd.to_datetime([row[0] for row in rows])
        return pd.Series([float(row[1]) for row in rows], index=idx, name=ticker)

    # Lade Makro-Serien aus DB
    snb_series = await _macro_series_from_db("snb_policy")
    chf_eur_series = await _macro_series_from_db("chf_eur")
    inflation_series = await _macro_series_from_db("inflation_ch")

    smi_close = await _load_prices(smi_ticker)
    if smi_close.empty:
        raise RuntimeError(f"SMI-Index '{smi_ticker}' nicht in stock_price_history")

    records: list[dict[str, object]] = []

    for ticker in tickers:
        close = await _load_prices(ticker)
        if len(close) < 300:
            _logger.warning("%s: zu wenig Daten (%d Zeilen) — übersprungen", ticker, len(close))
            continue

        start = close.index[252]  # mind. 252 Handelstage History vor erstem Snapshot
        end = close.index[-31]  # mind. 30 Handelstage Zukunft nach letztem Snapshot

        snapshot_dates = pd.date_range(start=start, end=end, freq=f"{freq_months}MS")

        for snap in snapshot_dates:
            snap_norm = snap.normalize()
            past = close[close.index <= snap_norm].tail(400)
            if len(past) < 252:
                continue

            target = build_target_excess_30d(close, smi_close, snap_norm)
            if target is None:
                continue

            smi_past = smi_close[smi_close.index <= snap_norm].tail(400)
            smi_63 = _return_nm_from_series(smi_past, 63) if len(smi_past) >= 63 else 0.0
            mom_vs_smi_3m = _return_nm_from_series(past, 63) - smi_63

            snap_date = snap_norm.date()
            records.append(
                {
                    "ticker": ticker,
                    "snapshot_date": snap_date,
                    "return_1m": _return_nm_from_series(past, 21),
                    "return_3m": _return_nm_from_series(past, 63),
                    "return_6m": _return_nm_from_series(past, 126),
                    "return_12m": _return_nm_from_series(past, 252),
                    "vol_30d": _vol_30d_from_series(past),
                    "vol_90d": _vol_nd_from_series(past, 90),
                    "rsi_14": _compute_rsi(past),
                    "price_to_52w_high": _price_to_52w_high_from_series(past),
                    "momentum_vs_smi_3m": mom_vs_smi_3m,
                    "bb_position": _compute_bb_position(past),
                    "macd_hist": _compute_macd_hist(past),
                    "drawdown_12m": _compute_drawdown_12m(past),
                    "snb_rate": _step_value_on(snb_series, snap_date, -0.75),
                    "chf_eur": _step_value_on(chf_eur_series, snap_date, 0.92),
                    "inflation_ch": _step_value_on(inflation_series, snap_date, 0.0),
                    "target_excess_30d": target,
                }
            )

    return pd.DataFrame(records)
