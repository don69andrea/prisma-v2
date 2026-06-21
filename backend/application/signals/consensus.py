"""2-of-3 consensus voting for WANN signal generation (Layer 2).

The consensus_vote function combines multiple binary signal columns via a
weighted vote.  The default configuration implements the standard 2-of-3
majority rule: at least 2 of {ma_signal, macd_signal, rsi_signal} must be 1
for the consensus to fire (return 1).

Look-ahead guard: input signals must already be shifted by the caller so that
signal@t uses only data <= t-1.
"""
from __future__ import annotations

import pandas as pd

# Default weights for the 3 canonical signal columns
_DEFAULT_CFG: dict[str, float | int] = {
    "ma_signal": 1.0,
    "macd_signal": 1.0,
    "rsi_signal": 1.0,
    "threshold": 0.5,  # >= 2/3 columns active → fires
}


def consensus_vote(df: pd.DataFrame, cfg: dict[str, float | int] | None = None) -> pd.Series:
    """Compute the weighted 2-of-3 consensus signal for each row in *df*.

    Algorithm::

        weights = {col: weight for col, weight in cfg.items() if col != "threshold"}
        present = {col: w for col, w in weights.items() if col in df.columns}
        weighted_sum = sum(df[col] * w for col, w in present.items())
        total_weight = sum(present.values())
        normalised   = weighted_sum / total_weight   (0 when total_weight == 0)
        result       = (normalised >= threshold).astype(int)

    With the default equal-weight configuration the threshold of 0.5 means
    at least 2 out of 3 columns must be active (≥ 2/3 ≈ 0.667 > 0.5).

    Args:
        df: DataFrame containing one or more signal columns (0 or 1 values).
        cfg: Optional configuration dict.  Recognised keys:

            - Any signal column name (str) → float weight (positive).
            - ``"threshold"`` → float in (0, 1], default 0.5.

            Columns in *cfg* that are absent from *df* are silently ignored.
            Columns in *df* that are absent from *cfg* are silently ignored.

    Returns:
        pd.Series[int] with values 0 or 1, aligned to ``df.index``.
    """
    effective_cfg: dict[str, float | int] = {**_DEFAULT_CFG, **(cfg or {})}

    threshold = float(effective_cfg.get("threshold", 0.5))
    weights: dict[str, float] = {
        col: float(w)
        for col, w in effective_cfg.items()
        if col != "threshold" and col in df.columns
    }

    if not weights:
        # No recognised signal columns → return all zeros
        return pd.Series(0, index=df.index, dtype=int)

    total_weight = sum(weights.values())
    weighted_sum = sum(df[col] * w for col, w in weights.items())
    normalised = weighted_sum / total_weight

    return (normalised >= threshold).astype(int)
