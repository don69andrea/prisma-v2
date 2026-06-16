"""SimFin Adapter — Point-in-Time Fundamentaldaten für ML-Training (nur offline).

Free-Tier-Strategie (Stand 2026-06):
  • derived/quarterly (P/E, P/B fertig berechnet) → Premium-only, nicht verfügbar
  • Stattdessen: P/E, P/B, EPS, Dividendenrendite aus Rohdaten selbst berechnet:
      income/quarterly + balance/quarterly + shareprices/daily (alle kostenfrei für US)
  • Für CH/EU: SimFin Free Tier hat keine brauchbare Coverage → None → Stub-Fallback

Point-in-Time Korrektheit:
  Jeder historische Trainings-Snapshot verwendet ausschliesslich Daten,
  die zum Snapshot-Datum bereits öffentlich publiziert waren (Publish Date ≤ snap_date).
  Report Date != Publish Date: ein Q3-Bericht mit Report Date 30-Sep wird oft erst
  6–8 Wochen später publiziert. Nur Publish Date ist point-in-time-korrekt.

Berechnungen:
  P/E  = Adj. Close / EPS_TTM
         EPS_TTM = Σ(Net Income letzter 4 Quartale) / Shares (Diluted)
  P/B  = Adj. Close / Buchwert pro Aktie
         Buchwert = Total Equity / Shares (Diluted)
  Div% = Σ(Dividenden letzte 12 Monate) / Adj. Close
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

_logger = logging.getLogger(__name__)


def ticker_to_simfin_market(ticker: str) -> str:
    """Leitet SimFin-Markt aus Ticker-Suffix ab (SAP.DE → 'de', NESN → 'ch')."""
    if "." in ticker:
        _SUFFIX_MAP = {"sw": "ch", "de": "de", "pa": "fr", "as": "nl", "mc": "es", "mi": "it"}
        suffix = ticker.rsplit(".", 1)[-1].lower()
        return _SUFFIX_MAP.get(suffix, "de")
    return "ch"


def ticker_clean(ticker: str) -> str:
    """Entfernt Börsen-Suffix für SimFin-Lookup (NESN.SW → NESN, SAP.DE → SAP)."""
    return ticker.split(".")[0].upper()


class SimFinAdapter:
    """Historische Point-in-Time Fundamentaldaten aus SimFin-Rohdaten.

    Für US-Ticker (market='us') werden P/E, P/B, EPS und Dividendenrendite aus
    income/quarterly, balance/quarterly und shareprices/daily berechnet.
    Für alle anderen Märkte gibt get_fundamentals_on_date() None zurück —
    der Aufrufer (build_dataset) fällt dann auf _stub_fundamentals() zurück.

    Alle Markt-Bulk-Downloads werden beim ersten Zugriff einmalig geladen und
    danach als Dict {ticker → DataFrame} im Speicher gehalten (kein Re-Download).
    """

    def __init__(self, api_key: str, data_dir: Path | None = None) -> None:
        try:
            import simfin as sf
        except ImportError as exc:
            raise ImportError("pip install simfin") from exc

        self._sf = sf
        self._data_dir = data_dir or Path.home() / ".simfin_cache"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        sf.set_api_key(api_key)
        sf.set_data_dir(str(self._data_dir))

        # Lazy-loaded after first US call
        self._us_loaded = False
        self._income_us: dict[str, pd.DataFrame] = {}  # ticker → rows sorted by Publish Date
        self._balance_us: dict[str, pd.DataFrame] = {}
        self._prices_us: dict[str, pd.DataFrame] = {}  # ticker → rows sorted by Date

        _logger.info("SimFinAdapter initialisiert (data_dir=%s)", self._data_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_fundamentals_on_date(
        self,
        ticker: str,
        snap_date: date,
        market: str = "ch",
    ) -> SwissFundamentals | None:
        """Point-in-Time Fundamentaldaten für (ticker, snap_date).

        Gibt None zurück wenn:
        - Markt != 'us' (kein brauchbares SimFin Free-Tier Coverage)
        - Ticker nicht in SimFin-Daten vorhanden
        - Zu wenig historische Daten vor snap_date

        In allen None-Fällen greift build_dataset() auf _stub_fundamentals() zurück.
        """
        if market != "us":
            return None

        self._ensure_us_loaded()

        clean = ticker_clean(ticker)
        snap_ts = pd.Timestamp(snap_date)

        price = self._price_on(clean, snap_ts)
        if price is None or price <= 0:
            return None

        pe = self._compute_pe(clean, snap_ts, price)
        pb = self._compute_pb(clean, snap_ts, price)
        eps = self._compute_eps_ttm(clean, snap_ts)
        div_yield = self._compute_div_yield(clean, snap_ts, price)

        if pe is None and pb is None and eps is None:
            return None  # Keine nutzbaren Daten → Stub-Fallback

        return SwissFundamentals(
            market_cap_chf=None,
            pe_ratio=pe,
            pb_ratio=pb,
            dividend_yield=div_yield,
            eps_chf=eps,  # in USD für US-Ticker — Vorzeichen/Grössenordnung ist korrekt
        )

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def _ensure_us_loaded(self) -> None:
        if self._us_loaded:
            return
        self._us_loaded = True
        self._income_us = self._load_income("us")
        self._balance_us = self._load_balance("us")
        self._prices_us = self._load_prices("us")
        _logger.info(
            "SimFin US geladen: %d Income-Ticker, %d Balance-Ticker, %d Preis-Ticker",
            len(self._income_us),
            len(self._balance_us),
            len(self._prices_us),
        )

    def _load_income(self, market: str) -> dict[str, pd.DataFrame]:
        try:
            df = self._sf.load(dataset="income", variant="quarterly", market=market)
            if df is None or df.empty:
                return {}
            df = df.copy()
            df["Publish Date"] = pd.to_datetime(df["Publish Date"])
            df = df.sort_values("Publish Date")
            return {t: g.reset_index(drop=True) for t, g in df.groupby("Ticker")}
        except Exception as exc:
            _logger.warning("SimFin income/%s Ladefehler: %s", market, exc)
            return {}

    def _load_balance(self, market: str) -> dict[str, pd.DataFrame]:
        try:
            df = self._sf.load(dataset="balance", variant="quarterly", market=market)
            if df is None or df.empty:
                return {}
            df = df.copy()
            df["Publish Date"] = pd.to_datetime(df["Publish Date"])
            df = df.sort_values("Publish Date")
            return {t: g.reset_index(drop=True) for t, g in df.groupby("Ticker")}
        except Exception as exc:
            _logger.warning("SimFin balance/%s Ladefehler: %s", market, exc)
            return {}

    def _load_prices(self, market: str) -> dict[str, pd.DataFrame]:
        try:
            df = self._sf.load(dataset="shareprices", variant="daily", market=market)
            if df is None or df.empty:
                return {}
            df = df.copy()
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")
            # Nur benötigte Spalten behalten — spart ~60% Speicher
            df = df[["Ticker", "Date", "Adj. Close", "Dividend"]]
            return {t: g.reset_index(drop=True) for t, g in df.groupby("Ticker")}
        except Exception as exc:
            _logger.warning("SimFin shareprices/%s Ladefehler: %s", market, exc)
            return {}

    # ------------------------------------------------------------------
    # Berechnungen
    # ------------------------------------------------------------------

    def _price_on(self, ticker: str, snap_ts: pd.Timestamp) -> float | None:
        """Bereinigter Schlusskurs am oder direkt vor snap_ts."""
        df = self._prices_us.get(ticker)
        if df is None:
            return None
        hist = df[df["Date"] <= snap_ts]
        if hist.empty:
            return None
        val = hist.iloc[-1]["Adj. Close"]
        return float(val) if pd.notna(val) and val > 0 else None

    def _compute_eps_ttm(self, ticker: str, snap_ts: pd.Timestamp) -> float | None:
        """EPS (Trailing 12 Monate) aus Summe der letzten 4 publizierten Quartale."""
        df = self._income_us.get(ticker)
        if df is None:
            return None
        published = df[df["Publish Date"] <= snap_ts]
        if len(published) < 1:
            return None
        last_4 = published.tail(4)
        net_income = last_4["Net Income (Common)"].sum()
        shares = published.iloc[-1]["Shares (Diluted)"]
        if pd.isna(shares) or shares <= 0:
            return None
        return float(net_income / shares)

    def _compute_pe(self, ticker: str, snap_ts: pd.Timestamp, price: float) -> float | None:
        """Trailing P/E = Preis / EPS_TTM. None wenn EPS ≤ 0 (Verlust)."""
        eps = self._compute_eps_ttm(ticker, snap_ts)
        if eps is None or eps <= 0:
            return None
        pe = price / eps
        # Plausibilitätsfilter: P/E > 500 ist Datenfehler oder Ausreisser
        return float(pe) if 0 < pe < 500 else None

    def _compute_pb(self, ticker: str, snap_ts: pd.Timestamp, price: float) -> float | None:
        """P/B = Preis / Buchwert pro Aktie (Total Equity / Shares Diluted)."""
        df = self._balance_us.get(ticker)
        if df is None:
            return None
        published = df[df["Publish Date"] <= snap_ts]
        if published.empty:
            return None
        row = published.iloc[-1]
        equity = row.get("Total Equity")
        shares = row.get("Shares (Diluted)")
        if pd.isna(equity) or pd.isna(shares) or shares <= 0:
            return None
        bvps = float(equity) / float(shares)
        if bvps <= 0:
            return None
        pb = price / bvps
        return float(pb) if 0 < pb < 100 else None

    def _compute_div_yield(self, ticker: str, snap_ts: pd.Timestamp, price: float) -> float | None:
        """Dividendenrendite = Summe Dividenden letzte 12 Monate / Preis."""
        df = self._prices_us.get(ticker)
        if df is None:
            return None
        one_year_ago = snap_ts - pd.DateOffset(years=1)
        window = df[(df["Date"] > one_year_ago) & (df["Date"] <= snap_ts)]
        if window.empty:
            return None
        div_ttm = float(window["Dividend"].fillna(0).sum())
        if div_ttm <= 0:
            return 0.0  # Keine Dividende — valider Wert (kein None)
        return div_ttm / price
