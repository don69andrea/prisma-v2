"""Statischer VIAC-Fonds-Katalog aus publizierten Factsheets (Stand 2024).

Quellen: VIAC Factsheets Q4 2024 (viac.ch/de/fonds)
Werte sind historische Durchschnitte über 5 Jahre und keine Zukunftsgarantie.
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.value_objects.fonds_vergleich import ViacFonds

VIAC_FONDS_CATALOG: dict[str, ViacFonds] = {
    "VIAC Global 100": ViacFonds(
        name="VIAC Global 100",
        description="100% Aktien, global diversifiziert",
        equity_ratio=1.0,
        expected_return_pa=Decimal("0.095"),
        volatility_pa=Decimal("0.165"),
        sharpe_ratio=Decimal("0.55"),
        max_drawdown=Decimal("-0.335"),
    ),
    "VIAC Global 80": ViacFonds(
        name="VIAC Global 80",
        description="80% Aktien, 20% Obligationen",
        equity_ratio=0.80,
        expected_return_pa=Decimal("0.081"),
        volatility_pa=Decimal("0.132"),
        sharpe_ratio=Decimal("0.57"),
        max_drawdown=Decimal("-0.265"),
    ),
    "VIAC Global 60": ViacFonds(
        name="VIAC Global 60",
        description="60% Aktien, 40% Obligationen",
        equity_ratio=0.60,
        expected_return_pa=Decimal("0.066"),
        volatility_pa=Decimal("0.099"),
        sharpe_ratio=Decimal("0.61"),
        max_drawdown=Decimal("-0.197"),
    ),
    "VIAC Schweiz 100": ViacFonds(
        name="VIAC Schweiz 100",
        description="100% Schweizer Aktien (SMI/SPI)",
        equity_ratio=1.0,
        expected_return_pa=Decimal("0.088"),
        volatility_pa=Decimal("0.148"),
        sharpe_ratio=Decimal("0.54"),
        max_drawdown=Decimal("-0.312"),
    ),
    "VIAC Nachhaltig 80": ViacFonds(
        name="VIAC Nachhaltig 80",
        description="80% nachhaltige Aktien (ESG), 20% Obligationen",
        equity_ratio=0.80,
        expected_return_pa=Decimal("0.079"),
        volatility_pa=Decimal("0.128"),
        sharpe_ratio=Decimal("0.56"),
        max_drawdown=Decimal("-0.258"),
    ),
}
