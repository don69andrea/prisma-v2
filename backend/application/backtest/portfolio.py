"""Portfolio allocator for the V4-4b multi-coin portfolio layer.

Design:
- Vol-based weighting: raw_weight_i = target_vol / vol_i × size_factor_i
- Per-coin cap: weight_i ≤ max_weight (default 40 %)
- Global exposure: Σ weights ≤ max_exposure (default 80 %)
- SELL signal → weight = 0 (no short exposure)
- Eligibility filter: coins not in eligible_coins are excluded
- Drawdown brake: if portfolio_dd < dd_brake_threshold, halve all weights

Constants are fixed and must NOT be tuned for backtest results.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PortfolioWeights", "allocate_portfolio"]

# Fixed constants — do NOT optimise for better backtest numbers
_TARGET_VOL: float = 0.20  # 20 % annual portfolio vol target
_MAX_WEIGHT: float = 0.40  # max 40 % per coin
_MAX_EXPOSURE: float = 0.80  # max 80 % total invested
_DD_BRAKE_THRESHOLD: float = -0.15  # halve exposure at -15 % portfolio drawdown
_DD_BRAKE_FACTOR: float = 0.50


@dataclass(frozen=True)
class PortfolioWeights:
    """Immutable portfolio weight vector for one time step.

    Attributes:
        weights: Mapping of coin → weight ∈ [0, max_weight].
        total_exposure: Sum of all weights ∈ [0, max_exposure].
    """

    weights: dict[str, float]
    total_exposure: float


def allocate_portfolio(
    signals: dict[str, tuple[str, float]],
    realized_vols: dict[str, float],
    eligible_coins: frozenset[str],
    portfolio_dd: float = 0.0,
    target_vol: float = _TARGET_VOL,
    max_weight: float = _MAX_WEIGHT,
    max_exposure: float = _MAX_EXPOSURE,
    dd_brake_threshold: float = _DD_BRAKE_THRESHOLD,
    dd_brake_factor: float = _DD_BRAKE_FACTOR,
) -> PortfolioWeights:
    """Compute portfolio weights from per-coin signals and volatilities.

    Algorithm:
        1. Filter to BUY signals on eligible coins.
        2. Compute raw vol-target weight: w_i = target_vol / max(vol_i, 1e-8) × size_i.
        3. Cap each weight at max_weight.
        4. Normalise so Σ weights ≤ max_exposure.
        5. Apply drawdown brake (multiply all by dd_brake_factor) if needed.

    Args:
        signals:       {coin: (action, size_factor)} — action ∈ {"BUY","HOLD","SELL"}.
        realized_vols: {coin: annualised_vol} — must be positive; defaults to 1.0 if missing.
        eligible_coins: Frozenset of coins eligible at this date (PIT universe).
        portfolio_dd:  Current portfolio drawdown as a negative float (e.g. -0.18 = -18%).
        target_vol:    Target annualised portfolio vol (constant).
        max_weight:    Per-coin weight cap (constant).
        max_exposure:  Maximum total portfolio exposure (constant).
        dd_brake_threshold: Drawdown level that triggers the brake (constant).
        dd_brake_factor:    Factor applied to all weights when brake fires (constant).

    Returns:
        PortfolioWeights (frozen dataclass).
    """
    if not signals or not eligible_coins:
        return PortfolioWeights(weights={}, total_exposure=0.0)

    # Step 1: raw vol-target weights for BUY signals on eligible coins
    raw_weights: dict[str, float] = {}
    for coin, (action, size_factor) in signals.items():
        if coin not in eligible_coins:
            continue
        if action != "BUY":
            continue
        vol = max(realized_vols.get(coin, 1.0), 1e-8)
        raw = (target_vol / vol) * size_factor
        raw_weights[coin] = raw

    if not raw_weights:
        return PortfolioWeights(weights={}, total_exposure=0.0)

    # Step 2: cap per-coin
    capped: dict[str, float] = {coin: min(w, max_weight) for coin, w in raw_weights.items()}

    # Step 3: scale so total ≤ max_exposure
    total_raw = sum(capped.values())
    if total_raw > max_exposure:
        scale = max_exposure / total_raw
        scaled = {coin: w * scale for coin, w in capped.items()}
    else:
        scaled = dict(capped)

    # Step 4: drawdown brake
    if portfolio_dd < dd_brake_threshold:
        scaled = {coin: w * dd_brake_factor for coin, w in scaled.items()}

    total_exposure = sum(scaled.values())
    return PortfolioWeights(weights=scaled, total_exposure=total_exposure)
