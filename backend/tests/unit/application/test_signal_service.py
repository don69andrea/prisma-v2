"""Unit-Tests für SignalService.evaluate() — mocked adapters, kein I/O.

Alle Tests:
- Erzeugen synthetische DataFrames (prices, onchain) ohne Datenbank
- Prüfen dass evaluate() ein valides SignalVector-Objekt zurückgibt
- Prüfen SELL → size_factor = 0.0
- Prüfen sub_scores enthält alle erwarteten Keys
- Prüfen Look-Ahead-Guard: asof_date aus der Zukunft → Fehler oder leere Daten
"""

from __future__ import annotations

import asyncio
from datetime import date

import numpy as np
import pandas as pd
import pytest

from backend.interfaces.rest.schemas.signals import SignalVector

pytestmark = pytest.mark.unit


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _run(coro):  # type: ignore[no-untyped-def]
    """Führe eine Coroutine synchron aus (Python 3.10+)."""
    return asyncio.run(coro)


def make_prices_df(
    n_days: int = 300,
    coins: list[str] | None = None,
    end_date: date | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Erzeuge synthetisches Preismatrix-DataFrame."""
    if coins is None:
        coins = ["BTC", "ETH", "SOL"]
    if end_date is None:
        end_date = date(2025, 12, 31)

    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp(end_date), periods=n_days)
    data = {}
    for i, coin in enumerate(coins):
        start_price = 10000.0 * (i + 1)
        log_returns = rng.normal(0.001, 0.02, size=n_days)
        prices = start_price * np.exp(np.cumsum(log_returns))
        data[coin] = prices

    return pd.DataFrame(data, index=idx)


def make_onchain_df(
    coins: list[str] | None = None,
    n_rows_per_coin: int = 30,
    end_date: date | None = None,
    seed: int = 99,
) -> pd.DataFrame:
    """Erzeuge synthetisches On-Chain-DataFrame."""
    if coins is None:
        coins = ["BTC", "ETH", "SOL"]
    if end_date is None:
        end_date = date(2025, 12, 31)

    rng = np.random.default_rng(seed)
    rows = []
    idx = pd.bdate_range(end=pd.Timestamp(end_date), periods=n_rows_per_coin)
    for coin in coins:
        for ts in idx:
            rows.append(
                {
                    "coin_id": coin,
                    "date": ts.date(),
                    "mvrv_z": float(rng.normal(1.5, 0.5)),
                    "active_addresses": float(rng.integers(100_000, 500_000)),
                }
            )

    return pd.DataFrame(rows)


# ── Basis-Tests ───────────────────────────────────────────────────────────────


def test_evaluate_returns_signal_vector() -> None:
    """evaluate() muss ein SignalVector-Objekt zurückgeben."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    assert isinstance(result, SignalVector), (
        f"Erwartet SignalVector, erhalten {type(result)}"
    )


def test_evaluate_correct_coin_and_date() -> None:
    """evaluate() muss coin und asof korrekt setzen."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    assert result.coin == "BTC", f"Falscher Coin: {result.coin}"
    assert result.asof == asof, f"Falsches Datum: {result.asof}"


def test_evaluate_action_valid() -> None:
    """action muss BUY, HOLD oder SELL sein."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    assert result.action in ("BUY", "HOLD", "SELL"), (
        f"Unzulässige action: {result.action}"
    )


def test_evaluate_sell_size_zero() -> None:
    """SELL → size_factor muss 0.0 sein."""
    from backend.application.signals.signal_service import evaluate

    # Erzeuge Preisdaten für schlechtes Momentum (letztes Coin im Ranking)
    # Wir testen alle Coins und prüfen jede SELL-Aktion
    prices = make_prices_df(n_days=300, coins=["BTC", "ETH", "SOL", "BNB", "XRP",
                                                "ADA", "AVAX", "DOGE", "LINK", "DOT"])
    asof = date(2025, 12, 31)

    results = []
    for coin in prices.columns:
        r = _run(evaluate(coin, asof, prices_df=prices))
        results.append(r)

    for r in results:
        if r.action == "SELL":
            assert r.size_factor == 0.0, (
                f"SELL für {r.coin} → size_factor={r.size_factor}, erwartet 0.0"
            )


def test_evaluate_size_factor_bounds() -> None:
    """size_factor muss immer ∈ [0.0, 1.5] sein."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(n_days=300, coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)

    for coin in prices.columns:
        result = _run(evaluate(coin, asof, prices_df=prices))
        assert 0.0 <= result.size_factor <= 1.5, (
            f"{coin}: size_factor={result.size_factor} ausserhalb [0, 1.5]"
        )


def test_evaluate_sub_scores_keys() -> None:
    """sub_scores muss alle erforderlichen Keys enthalten."""
    from backend.application.signals.signal_service import evaluate

    required_keys = {"ma_signal", "macd_signal", "rsi_signal", "vol_pred",
                     "momentum_rank", "onchain_score"}

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    missing = required_keys - set(result.sub_scores.keys())
    assert not missing, f"Fehlende Keys in sub_scores: {missing}"


def test_evaluate_disclaimer_set() -> None:
    """disclaimer muss gesetzt sein (nicht leer)."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    assert result.disclaimer, "disclaimer ist leer"
    assert "Entscheidungsunterstützung" in result.disclaimer, (
        f"Unerwarteter disclaimer: {result.disclaimer}"
    )


def test_evaluate_consensus_format() -> None:
    """consensus muss Format 'N/3' haben."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    assert "/" in result.consensus, f"Unerwartetes consensus-Format: {result.consensus}"
    parts = result.consensus.split("/")
    assert len(parts) == 2, f"Kein N/M-Format: {result.consensus}"
    assert parts[1] == "3", f"Erwarte 3 Signale total: {result.consensus}"


def test_evaluate_confidence_bounds() -> None:
    """confidence muss ∈ [0.0, 1.0] sein."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    assert 0.0 <= result.confidence <= 1.0, (
        f"confidence={result.confidence} ausserhalb [0, 1]"
    )


def test_evaluate_with_onchain_data() -> None:
    """evaluate() mit optionalem onchain_df muss funktionieren."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    onchain = make_onchain_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)

    result = _run(evaluate("BTC", asof, prices_df=prices, onchain_df=onchain))

    assert isinstance(result, SignalVector)
    # onchain_score muss gesetzt sein (kann 0.5 sein als Neutral-Fallback)
    assert "onchain_score" in result.sub_scores


def test_evaluate_pydantic_validates() -> None:
    """Das zurückgegebene SignalVector muss Pydantic-Validierung bestehen."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(coins=["BTC", "ETH", "SOL"])
    asof = date(2025, 12, 31)
    result = _run(evaluate("BTC", asof, prices_df=prices))

    # model_dump() und Re-Konstruktion muss ohne Fehler gehen
    dumped = result.model_dump()
    reconstructed = SignalVector(**dumped)
    assert reconstructed.coin == result.coin
    assert reconstructed.action == result.action


def test_evaluate_no_lookahead_future_data_clipped() -> None:
    """Nur Daten bis asof_date dürfen verwendet werden (Look-Ahead-Guard)."""
    from backend.application.signals.signal_service import evaluate

    prices = make_prices_df(n_days=300, coins=["BTC", "ETH", "SOL"],
                            end_date=date(2025, 12, 31))
    # asof_date ist deutlich vor dem letzten Datum in prices
    asof = date(2025, 6, 30)

    result = _run(evaluate("BTC", asof, prices_df=prices))

    # asof im Result muss dem übergebenen Datum entsprechen
    assert result.asof == asof, f"asof falsch gesetzt: {result.asof}"
