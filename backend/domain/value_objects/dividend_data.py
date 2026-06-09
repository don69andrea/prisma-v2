"""Dividendendaten für einen Swiss Stock — immutabler Value Object."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DividendEntry:
    """Einzelne Dividendenausschüttung."""

    date: str
    amount_chf: float


@dataclass(frozen=True)
class DividendData:
    """Dividendendaten aus yfinance für einen SIX-kotierten Titel.

    Alle Felder können None sein wenn yfinance keine Daten liefert.
    Währung: CHF (SIX-kotierte Titel sind CHF-denominiert).
    """

    ticker: str
    last_dividend_chf: float | None
    ex_date: str | None
    dividend_yield_pct: float | None
    history: tuple[DividendEntry, ...]
    disclaimer: str
