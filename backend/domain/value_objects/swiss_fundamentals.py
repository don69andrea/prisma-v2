"""Fundamentaldaten für einen Swiss Stock — immutabler Value Object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SwissFundamentals:
    """Fundamentaldaten aus yfinance für einen SIX-kotierten Titel.

    Alle Felder können None sein wenn yfinance keine Daten liefert.
    Währung: CHF (SIX-kotierte Titel sind CHF-denominiert).
    """

    market_cap_chf: Decimal | None
    pe_ratio: float | None
    pb_ratio: float | None
    dividend_yield: float | None
    eps_chf: float | None
