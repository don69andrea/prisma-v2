"""SwissStock-Entity — Schweizer Aktie mit CH-ISIN und SIX-Exchange-Attributen."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from uuid import UUID

from backend.domain.validators.isin import validate_ch_isin


@dataclass(frozen=True)
class SwissStock:
    """Repräsentiert eine an der SIX Swiss Exchange kotierte Aktie.

    Alle Felder sind immutable. ISIN wird in __post_init__ gegen den
    CH-Luhn-Validator geprüft; ungültige ISINs werfen ValueError.
    """

    id: UUID
    ticker: str
    isin: str
    name: str
    exchange: Literal["XSWX"]
    sector: str | None
    market_cap_chf: Decimal | None
    currency: Literal["CHF"] = field(default="CHF")

    def __post_init__(self) -> None:
        if not validate_ch_isin(self.isin):
            raise ValueError(f"Ungültiges CH-ISIN: {self.isin!r}")
        object.__setattr__(self, "ticker", self.ticker.upper())
