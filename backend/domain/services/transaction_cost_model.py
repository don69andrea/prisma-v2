"""TransactionCostModel — Kap. 17 / CHALLENGE 03.

CH-Aktien: Stempelabgabe 0.15%/Seite + Courtage 0.20%/Seite + Spread 0.10%/Seite
Krypto:    Exchange-Fee 0.15%/Seite + Slippage 0.10%/Seite

All costs per-side → round_trip = 2 × per_side.
net_return = gross_return − round_trip_cost.
"""

from __future__ import annotations

from enum import StrEnum


class AssetClass(StrEnum):
    CH_STOCK = "ch_stock"
    CRYPTO = "crypto"


class TransactionCostModel:
    # CH-Aktien (per side, fraction of notional)
    CH_STAMP_PER_SIDE: float = 0.0015   # Stempelabgabe 0.15%
    CH_BROKERAGE_PER_SIDE: float = 0.0020  # Courtage 0.20%
    CH_SPREAD_PER_SIDE: float = 0.0010  # Spread/Slippage 0.10%

    # Krypto (per side)
    CRYPTO_FEE_PER_SIDE: float = 0.0015    # Exchange fee 0.15%
    CRYPTO_SLIPPAGE_PER_SIDE: float = 0.0010  # Slippage 0.10%

    def round_trip_cost(self, asset_class: AssetClass) -> float:
        """Gesamtkosten Ein- + Ausstieg als Bruchteil des Nominals."""
        if asset_class == AssetClass.CH_STOCK:
            per_side = self.CH_STAMP_PER_SIDE + self.CH_BROKERAGE_PER_SIDE + self.CH_SPREAD_PER_SIDE
        else:
            per_side = self.CRYPTO_FEE_PER_SIDE + self.CRYPTO_SLIPPAGE_PER_SIDE
        return 2.0 * per_side

    def net_return(self, gross_return: float, asset_class: AssetClass) -> float:
        """Netto-Return nach Transaktionskosten (round-trip einmalig pro Halteperiode)."""
        return gross_return - self.round_trip_cost(asset_class)

    def ch_stock_round_trip(self) -> float:
        return self.round_trip_cost(AssetClass.CH_STOCK)

    def crypto_round_trip(self) -> float:
        return self.round_trip_cost(AssetClass.CRYPTO)
