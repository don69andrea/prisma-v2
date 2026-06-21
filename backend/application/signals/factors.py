"""Layer 1 Signal-Faktoren: Cross-Sectional Momentum + On-Chain Health Score.

Beide Funktionen geben eine pandas-Series/DataFrame pro Coin zurück und
enthalten keinerlei Look-Ahead (alle Features basieren auf shift(1) oder
historischen Aggregaten bis einschliesslich des letzten verfügbaren Datenpunkts).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def cross_sectional_momentum(
    prices: pd.DataFrame,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """Berechne Cross-Sectional Momentum-Ranking über alle Coins.

    Parameters
    ----------
    prices:
        DataFrame mit Coins als Spalten und Datum als Index.
        Muss mindestens ``max(windows)`` Zeilen enthalten.
    windows:
        Rendite-Fenster in Tagen. Standard: [30, 90].

    Returns
    -------
    pd.DataFrame
        Index = Coin-Symbole (Spaltennamen der ``prices``-Matrix).
        Spalten: ``momentum_rank_{w}d`` für jedes Fenster,
        ``composite_rank`` (Mittelwert der Fenster-Ränge).
        Rang 1 = höchster Return (bestes Coin).
    """
    if windows is None:
        windows = [30, 90]

    result: dict[str, pd.Series] = {}
    for w in windows:
        col = f"momentum_rank_{w}d"
        # Rendite über w Tage bis zum letzten verfügbaren Datum
        returns = prices.pct_change(w).iloc[-1]
        # Rang 1 = höchster Return (ascending=False → bester bekommt 1)
        ranked = returns.rank(ascending=False, method="min")
        result[col] = ranked

    df = pd.DataFrame(result)
    df.index.name = None
    # composite_rank = Mittelwert der Fenster-Ränge
    rank_cols = [f"momentum_rank_{w}d" for w in windows]
    df["composite_rank"] = df[rank_cols].mean(axis=1)
    return df


def onchain_health_score(df_onchain: pd.DataFrame) -> pd.Series:
    """Berechne On-Chain Health Score für jedes Coin ∈ [0, 1].

    Parameters
    ----------
    df_onchain:
        DataFrame mit Spalten: ``coin_id``, ``date``, ``mvrv_z``,
        ``active_addresses``.

    Returns
    -------
    pd.Series
        Index = coin_id, Werte ∈ [0, 1].
        Fallback: falls eine Komponente komplett NaN ist, wird nur die
        verfügbare Komponente verwendet. Falls beide NaN → 0.5 (neutral).
    """
    scores: dict[str, float] = {}

    for coin_id, group in df_onchain.groupby("coin_id"):
        mvrv = group["mvrv_z"].dropna()
        addr = group["active_addresses"].dropna()

        mvrv_score: float | None = None
        addr_score: float | None = None

        if len(mvrv) >= 2:
            z = (mvrv - mvrv.mean()) / mvrv.std(ddof=1)
            z_clipped = z.clip(-3.0, 3.0)
            # Nehme den aktuellsten Wert (letztes Datum)
            z_last = float(z_clipped.iloc[-1])
            mvrv_score = (z_last + 3.0) / 6.0

        if len(addr) >= 2:
            z = (addr - addr.mean()) / addr.std(ddof=1)
            z_clipped = z.clip(-3.0, 3.0)
            z_last = float(z_clipped.iloc[-1])
            addr_score = (z_last + 3.0) / 6.0

        if mvrv_score is not None and addr_score is not None:
            composite = 0.5 * mvrv_score + 0.5 * addr_score
        elif mvrv_score is not None:
            composite = mvrv_score
        elif addr_score is not None:
            composite = addr_score
        else:
            # Beide Komponenten NaN → neutrale Mitte
            composite = 0.5

        # Sicherheitsclip gegen Floating-Point-Ungenauigkeiten
        scores[str(coin_id)] = float(np.clip(composite, 0.0, 1.0))

    return pd.Series(scores, name="onchain_health_score")
