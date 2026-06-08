"""Regelbasierter 3a-Eligibility-Filter gemäss BVV2/FINMA.

Referenz: docs/legal/3a-eligibility-rules.md
Alle Regeln sind zustandslos und seiteneffektfrei.
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.value_objects.eligibility_result import EligibilityReason, EligibilityResult

# BVV2 Art. 53 Abs. 1 lit. a: Mindestliquidität — 100M CHF Marktkapitalisierung
_MIN_MARKET_CAP_CHF = Decimal("100_000_000")

# Anerkannte Börsen für Swiss 3a (SIX Swiss Exchange)
_RECOGNIZED_EXCHANGES: frozenset[str] = frozenset({"XSWX"})


class EligibilityFilter:
    """Prüft 3a-Säule-Eignung eines Swiss Stocks nach BVV2/FINMA-Regeln.

    Regeln (in Prüfreihenfolge):
      1. Exchange muss 'XSWX' sein (anerkannte SIX Swiss Exchange)
      2. Marktkapitalisierung >= 100M CHF wenn bekannt (Liquiditätsproxy)
    """

    def check(self, stock: SwissStock) -> EligibilityResult:
        reasons: list[EligibilityReason] = []

        if stock.exchange not in _RECOGNIZED_EXCHANGES:
            reasons.append(EligibilityReason.EXCHANGE_NOT_RECOGNIZED)

        if stock.market_cap_chf is not None and stock.market_cap_chf < _MIN_MARKET_CAP_CHF:
            reasons.append(EligibilityReason.MARKET_CAP_TOO_LOW)

        return EligibilityResult(
            ticker=stock.ticker,
            eligible=len(reasons) == 0,
            reasons=tuple(reasons),
        )
