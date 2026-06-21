"""Unit-Tests für Layer 1 Signal-Faktoren: cross_sectional_momentum + onchain_health_score."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ── Lazy import — schlägt fehl (RED) bis Implementierung existiert ──────────
def _import() -> tuple:  # type: ignore[type-arg]
    from backend.application.signals.factors import (  # noqa: PLC0415
        cross_sectional_momentum,
        onchain_health_score,
    )

    return cross_sectional_momentum, onchain_health_score


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_prices(n_days: int = 120) -> pd.DataFrame:
    """3-Coin-Preisreihe: BTC hat den höchsten Return, DOGE den niedrigsten."""
    idx = pd.date_range("2023-01-01", periods=n_days, freq="D")
    rng = np.random.default_rng(42)
    base = pd.DataFrame(
        {
            "BTC": 100.0 * np.cumprod(1 + rng.normal(0.002, 0.02, n_days)),
            "ETH": 100.0 * np.cumprod(1 + rng.normal(0.001, 0.02, n_days)),
            "DOGE": 100.0 * np.cumprod(1 + rng.normal(-0.001, 0.03, n_days)),
        },
        index=idx,
    )
    return base


def _make_onchain(n: int = 60) -> pd.DataFrame:
    """Synthetischer On-Chain-DataFrame für 3 Coins."""
    rows = []
    rng = np.random.default_rng(7)
    for coin in ["BTC", "ETH", "DOGE"]:
        for i in range(n):
            rows.append(
                {
                    "coin_id": coin,
                    "date": pd.Timestamp("2023-01-01") + pd.Timedelta(days=i),
                    "mvrv_z": float(rng.normal(1.5, 1.0)),
                    "active_addresses": float(rng.uniform(5_000, 50_000)),
                }
            )
    return pd.DataFrame(rows)


# ── Tests: cross_sectional_momentum ──────────────────────────────────────────


def test_cross_sectional_momentum_ranking_deterministic():
    """Ranking muss deterministisch und vollständig (1/2/3) sein."""
    cross_sectional_momentum, _ = _import()
    prices = _make_prices(n_days=120)
    result = cross_sectional_momentum(prices)

    assert isinstance(result, pd.DataFrame)
    assert "momentum_rank_30d" in result.columns
    assert "momentum_rank_90d" in result.columns
    assert "composite_rank" in result.columns

    # Genau 3 Coins im Ergebnis
    assert len(result) == 3

    # Ränge vollständig (1/2/3 vorhanden)
    ranks_30d = set(result["momentum_rank_30d"].astype(int).tolist())
    assert ranks_30d == {1, 2, 3}


def test_cross_sectional_momentum_higher_return_better_rank():
    """Coin mit höchstem Return erhält Rang 1."""
    cross_sectional_momentum, _ = _import()
    n = 120
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    # Konstruiere garantierten Return: BTC +20%, ETH +10%, DOGE -5%
    prices = pd.DataFrame(
        {
            "BTC": np.linspace(100, 120, n),
            "ETH": np.linspace(100, 110, n),
            "DOGE": np.linspace(100, 95, n),
        },
        index=idx,
    )
    result = cross_sectional_momentum(prices, windows=[30, 90])
    assert result.loc["BTC", "momentum_rank_30d"] == 1
    assert result.loc["DOGE", "momentum_rank_30d"] == 3


def test_cross_sectional_momentum_no_nan_with_sufficient_history():
    """Genug History (≥90 Tage) → kein NaN in Rankings."""
    cross_sectional_momentum, _ = _import()
    prices = _make_prices(n_days=120)
    result = cross_sectional_momentum(prices)
    assert not result["momentum_rank_30d"].isna().any()
    assert not result["momentum_rank_90d"].isna().any()
    assert not result["composite_rank"].isna().any()


def test_cross_sectional_momentum_composite_is_mean_of_window_ranks():
    """composite_rank = Mittelwert der Fenster-Ränge (per Spec)."""
    cross_sectional_momentum, _ = _import()
    prices = _make_prices(n_days=120)
    result = cross_sectional_momentum(prices, windows=[30, 90])
    expected = (result["momentum_rank_30d"] + result["momentum_rank_90d"]) / 2
    pd.testing.assert_series_equal(
        result["composite_rank"],
        expected,
        check_names=False,
        atol=1e-9,
    )


# ── Tests: onchain_health_score ───────────────────────────────────────────────


def test_onchain_health_score_range():
    """Ausgabe muss für valide Inputs ∈ [0, 1] liegen."""
    _, onchain_health_score = _import()
    df = _make_onchain()
    result = onchain_health_score(df)

    assert isinstance(result, pd.Series)
    assert len(result) == 3
    assert (result >= 0.0).all(), f"Wert unter 0: {result[result < 0]}"
    assert (result <= 1.0).all(), f"Wert über 1: {result[result > 1]}"


def test_onchain_health_score_nan_mvrv_fallback():
    """NULL mvrv_z → Score basiert nur auf active_addresses-Komponente."""
    _, onchain_health_score = _import()
    df = _make_onchain()
    # BTC: mvrv_z auf NaN setzen
    df.loc[df["coin_id"] == "BTC", "mvrv_z"] = float("nan")
    result = onchain_health_score(df)

    # Score für BTC muss trotzdem eine valide Zahl ∈ [0,1] sein
    assert not np.isnan(result["BTC"])
    assert 0.0 <= result["BTC"] <= 1.0


def test_onchain_health_score_nan_addr_fallback():
    """NULL active_addresses → Score basiert nur auf mvrv_z-Komponente."""
    _, onchain_health_score = _import()
    df = _make_onchain()
    df.loc[df["coin_id"] == "ETH", "active_addresses"] = float("nan")
    result = onchain_health_score(df)

    assert not np.isnan(result["ETH"])
    assert 0.0 <= result["ETH"] <= 1.0


def test_onchain_health_score_all_nan_returns_midpoint():
    """Beide NaN → neutrale Mitte (0.5) oder NaN, aber kein Absturz."""
    _, onchain_health_score = _import()
    df = _make_onchain()
    df.loc[df["coin_id"] == "DOGE", ["mvrv_z", "active_addresses"]] = float("nan")
    # Darf nicht abstürzen
    result = onchain_health_score(df)
    assert "DOGE" in result.index
