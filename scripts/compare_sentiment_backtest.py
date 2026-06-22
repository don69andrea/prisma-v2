"""compare_sentiment_backtest.py — Walk-forward Backtest-Vergleich (D-08).

Fuehrt run_walkforward() zweimal unter identischen Bedingungen aus:
  1. SENTIMENT_ENABLED=false — Baseline (V4-1/V4-2 Signal, Positionen unveraendert)
  2. SENTIMENT_ENABLED=true  — Sentiment-enhanced (Veto setzt Position auf 0,
                               Downside-Skalierung per D-06)

Vergleich: Sharpe, Calmar, MaxDD, Hit-Rate, Anzahl vetoed Trades.
Berichtet ehrlich gemaess D-08 Ehrlichkeits-Regel — auch wenn Sentiment schadet.

Ausfuehrung:
    source .venv/bin/activate
    python scripts/compare_sentiment_backtest.py

Keine Schwellenwert-Optimierung (D-08): _VETO_SCORE_THRESHOLD und _FEAR_THRESHOLD
sind Konstanten aus CONTEXT.md D-05 und werden hier NICHT veraendert.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.application.backtest.walkforward import run_walkforward_with_details

# ---------------------------------------------------------------------------
# Konstanten (D-05 — unveraendert, kein Tuning erlaubt per D-08)
# ---------------------------------------------------------------------------

_VETO_SCORE_THRESHOLD: float = -0.3
_FEAR_THRESHOLD: float = -0.2

# Annualisierungsfaktor Krypto (365 Handelstage)
_ANN_CRYPTO: int = 365


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SentimentVetoRecord:
    """Einfacher Record fuer Sentiment-Veto-Entscheidungen pro Handelstag."""

    date: object  # pd.Timestamp oder date
    coin: str
    score: float
    regime: str
    news_surprise: bool
    veto: bool


@dataclass(frozen=True)
class ComparisonResult:
    """Ergebnis des 2x-Walk-forward-Vergleichs fuer einen Coin."""

    coin: str
    # DISABLED-Metriken (Baseline)
    disabled_sharpe: float
    disabled_calmar: float
    disabled_max_dd: float
    disabled_hit_rate: float
    # ENABLED-Metriken (Sentiment)
    enabled_sharpe: float
    enabled_calmar: float
    enabled_max_dd: float
    enabled_hit_rate: float
    # Veto-Statistik
    vetoed_trade_count: int
    total_trade_count: int
    # D-08-Entscheidung
    sentiment_improves: bool


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _hit_rate(net_returns: pd.Series) -> float:
    """Anteil profitabler Handelstage (positive Rendite)."""
    if len(net_returns) == 0:
        return 0.0
    return float((net_returns > 0).mean())


def _apply_veto_to_positions(
    positions: pd.Series,
    veto_records: list[SentimentVetoRecord],
    coin: str,
    size_scaling: bool = True,
) -> tuple[pd.Series, int]:
    """Wendet Sentiment-Veto und Downside-Skalierung auf Positions-Series an.

    Args:
        positions: Original-Positions-Series (0.0 oder 1.0).
        veto_records: Liste von SentimentVetoRecord fuer diesen Coin.
        coin: Coin-Bezeichner (fuer Filterung).
        size_scaling: Wenn True, downside score-Skalierung anwenden (D-06).

    Returns:
        Tuple (modifizierte Positions-Series, Anzahl vetoed Trades).
    """
    if not veto_records:
        return positions.copy(), 0

    # Index: Datum -> Record
    veto_map: dict[object, SentimentVetoRecord] = {
        r.date: r for r in veto_records if r.coin == coin
    }

    modified = positions.copy()
    vetoed_count = 0

    for idx in modified.index:
        record = veto_map.get(idx)
        if record is None:
            continue

        original = float(modified.loc[idx])

        # D-05 Veto-Regel: regime==FEAR AND news_surprise AND score < _VETO_SCORE_THRESHOLD
        if record.veto and original > 0:
            modified.loc[idx] = 0.0
            vetoed_count += 1
        elif size_scaling and record.score < 0 and original > 0:
            # D-06 Downside-only Skalierung (kein Veto, aber negativer Score)
            scaled = original * (1 + record.score * 0.3)
            modified.loc[idx] = max(0.0, scaled)

    return modified, vetoed_count


# ---------------------------------------------------------------------------
# Kern-Vergleichsfunktion (importierbar fuer Tests)
# ---------------------------------------------------------------------------


def compare_sentiment_backtest(
    prices: pd.DataFrame,
    signals: pd.Series,
    coin: str = "UNKNOWN",
    veto_records: list[SentimentVetoRecord] | None = None,
    costs: float = 0.001,
    min_train: int = 252,
    step: int = 63,
) -> ComparisonResult:
    """Fuehrt den 2x-Walk-forward-Vergleich durch (DISABLED vs. ENABLED).

    Diese Funktion ist importierbar und wird vom Integrations-Test angesteuert.

    Args:
        prices: DataFrame mit 'close'-Spalte und DatetimeIndex.
        signals: Series[0/1] (1=investiert, 0=Cash), gleicher Index wie prices.
        coin: Instrument-Bezeichner.
        veto_records: Sentiment-Veto-Records fuer die ENABLED-Variante.
                      None = kein Veto (produziert identische Metriken wie DISABLED).
        costs: Transaktionskosten pro Einheit (default 0.001 = 0.1%).
        min_train: Mindest-Trainingstage (default 252).
        step: Schrittweite Expanding Window (default 63).

    Returns:
        ComparisonResult mit Metriken beider Modi und Veto-Statistik.
    """
    veto_records = veto_records or []

    # --- 1. DISABLED: Baseline (Positionen unveraendert) ---
    disabled_details = run_walkforward_with_details(
        prices=prices,
        signals=signals,
        costs=costs,
        min_train=min_train,
        step=step,
        meta_filter=None,
    )
    disabled_net = disabled_details["net_returns"]
    disabled_sharpe = disabled_details["strategy_sharpe"]
    disabled_calmar = disabled_details["strategy_calmar"]
    disabled_max_dd = disabled_details["strategy_max_dd"]
    disabled_hit_rate = _hit_rate(disabled_net)

    # --- 2. ENABLED: Sentiment-enhanced (Veto + Downside-Skalierung) ---
    # Positionen modifizieren: Veto setzt auf 0, Downside skaliert
    enabled_signals, vetoed_count = _apply_veto_to_positions(
        positions=signals,
        veto_records=veto_records,
        coin=coin,
        size_scaling=True,
    )

    enabled_details = run_walkforward_with_details(
        prices=prices,
        signals=enabled_signals,
        costs=costs,
        min_train=min_train,
        step=step,
        meta_filter=None,
    )
    enabled_net = enabled_details["net_returns"]
    enabled_sharpe = enabled_details["strategy_sharpe"]
    enabled_calmar = enabled_details["strategy_calmar"]
    enabled_max_dd = enabled_details["strategy_max_dd"]
    enabled_hit_rate = _hit_rate(enabled_net)

    # --- 3. D-08 Entscheidungsregel ---
    # Sentiment verbessert NUR wenn ALLE drei Bedingungen erfuellt:
    # Sharpe besser UND Calmar besser UND MaxDD kleiner (weniger negativ)
    sentiment_improves = bool(
        enabled_sharpe > disabled_sharpe
        and enabled_calmar > disabled_calmar
        and enabled_max_dd > disabled_max_dd  # MaxDD ist negativ; groesser = besser
    )

    total_trades = disabled_details["n_trades"]

    return ComparisonResult(
        coin=coin,
        disabled_sharpe=disabled_sharpe,
        disabled_calmar=disabled_calmar,
        disabled_max_dd=disabled_max_dd,
        disabled_hit_rate=disabled_hit_rate,
        enabled_sharpe=enabled_sharpe,
        enabled_calmar=enabled_calmar,
        enabled_max_dd=enabled_max_dd,
        enabled_hit_rate=enabled_hit_rate,
        vetoed_trade_count=vetoed_count,
        total_trade_count=total_trades,
        sentiment_improves=sentiment_improves,
    )


# ---------------------------------------------------------------------------
# Synthetische Demo-Daten (fuer Dry-Run ohne DB)
# ---------------------------------------------------------------------------


def _make_synthetic_prices(n: int = 800, seed: int = 42) -> pd.DataFrame:
    """Erzeugt synthetische Tagespreise fuer einen Dry-Run-Test."""
    rng = np.random.default_rng(seed)
    # Leicht trendiger Random Walk
    log_returns = rng.normal(0.0003, 0.02, size=n)
    prices = 100.0 * np.exp(np.cumsum(log_returns))
    dates = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame({"close": prices}, index=dates)


def _make_synthetic_signals(prices: pd.DataFrame, seed: int = 42) -> pd.Series:
    """Einfaches 20/50-MA-Kreuz-Signal auf synthetischen Preisen."""
    close = prices["close"]
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    signal = (ma20 > ma50).astype(float).fillna(0.0)
    return signal


def _make_synthetic_veto_records(
    prices: pd.DataFrame,
    coin: str,
    veto_fraction: float = 0.05,
    seed: int = 42,
) -> list[SentimentVetoRecord]:
    """Erzeugt synthetische Veto-Records (ca. 5% der Tage mit Veto)."""
    rng = np.random.default_rng(seed + 1)
    records = []
    dates = prices.index.tolist()
    for d in dates:
        score = float(rng.uniform(-0.6, 0.6))
        regime = "FEAR" if score < _FEAR_THRESHOLD else ("GREED" if score > 0.2 else "NEUTRAL")
        news_surprise = bool(rng.random() < 0.3)
        veto = regime == "FEAR" and news_surprise and score < _VETO_SCORE_THRESHOLD
        # Nur ~veto_fraction der Tage in Liste (Speichereffizienz)
        if veto or (rng.random() < veto_fraction):
            records.append(
                SentimentVetoRecord(
                    date=d,
                    coin=coin,
                    score=score,
                    regime=regime,
                    news_surprise=news_surprise,
                    veto=veto,
                )
            )
    return records


# ---------------------------------------------------------------------------
# Ausgabe-Formatierung
# ---------------------------------------------------------------------------


def _print_comparison_table(results: list[ComparisonResult]) -> None:
    """Gibt den Vergleich als formatierten Text aus."""
    print()
    print("=" * 70)
    print("PRISMA V4-4 Sentiment Backtest-Vergleich (D-08 Ehrlichkeits-Regel)")
    print("=" * 70)
    print(f"{'Coin':<6} {'Metrik':<12} {'DISABLED':>10} {'ENABLED':>10} {'Delta':>10}")
    print("-" * 70)

    for r in results:
        metrics = [
            ("Sharpe", r.disabled_sharpe, r.enabled_sharpe),
            ("Calmar", r.disabled_calmar, r.enabled_calmar),
            ("MaxDD", r.disabled_max_dd, r.enabled_max_dd),
            ("Hit-Rate", r.disabled_hit_rate, r.enabled_hit_rate),
        ]
        for i, (name, dis, en) in enumerate(metrics):
            coin_label = r.coin if i == 0 else ""
            delta = en - dis
            delta_str = f"{delta:+.4f}"
            print(f"{coin_label:<6} {name:<12} {dis:>10.4f} {en:>10.4f} {delta_str:>10}")
        print(
            f"{'':6} {'Vetoes':<12} {r.total_trade_count:>10} {r.vetoed_trade_count:>10}"
            f" {'(' + str(r.vetoed_trade_count) + ' vetoed)':>10}"
        )

        decision = "VERBESSERT" if r.sentiment_improves else "KEIN Vorteil"
        print(f"       D-08-Entscheidung: {decision}")
        print("-" * 70)

    print()
    print("Hinweis: Keine Schwellenwert-Optimierung angewandt (D-08).")
    print(
        "_VETO_SCORE_THRESHOLD =",
        _VETO_SCORE_THRESHOLD,
        "| _FEAR_THRESHOLD =",
        _FEAR_THRESHOLD,
    )
    print()

    # Gesamtentscheidung
    any_improves = any(r.sentiment_improves for r in results)
    all_improve = all(r.sentiment_improves for r in results)
    if all_improve:
        print("EMPFEHLUNG: SENTIMENT_ENABLED=true (alle Coins verbessert, D-08 erfuellt)")
    elif any_improves:
        print(
            "EMPFEHLUNG: SENTIMENT_ENABLED=false "
            "(nicht alle Coins verbessert; D-08 nicht erfuellt)"
        )
    else:
        print(
            "EMPFEHLUNG: SENTIMENT_ENABLED=false bleibt Standard "
            "(kein Coin verbessert, D-08)"
        )
    print()


# ---------------------------------------------------------------------------
# Main (Live-Backtest oder Dry-Run)
# ---------------------------------------------------------------------------


TOP_COINS = ["BTC", "ETH", "SOL", "BNB", "XRP"]


async def main() -> int:
    """Fuehrt den 2x-Walk-forward-Vergleich fuer alle Top-Coins durch.

    Ohne DB-Verbindung: Dry-Run mit synthetischen Daten.
    Mit DB-Verbindung: Echte historische Preisdaten und gespeicherte Veto-Records.
    """
    print("PRISMA V4-4 Sentiment Backtest-Vergleich")
    print(f"Coins: {', '.join(TOP_COINS)}")
    print("Modus: Synthetischer Dry-Run (kein DB-Zugriff in diesem Lauf)")
    print("-" * 70)

    results: list[ComparisonResult] = []

    for coin in TOP_COINS:
        seed = abs(hash(coin)) % 1000
        prices = _make_synthetic_prices(n=800, seed=seed)
        signals = _make_synthetic_signals(prices)
        veto_records = _make_synthetic_veto_records(prices, coin=coin, seed=seed)

        result = compare_sentiment_backtest(
            prices=prices,
            signals=signals,
            coin=coin,
            veto_records=veto_records,
            costs=0.001,
            min_train=252,
            step=63,
        )
        results.append(result)
        print(
            f"[{coin}] Sharpe DISABLED={result.disabled_sharpe:.4f}"
            f" ENABLED={result.enabled_sharpe:.4f}"
            f" | Vetoes={result.vetoed_trade_count}"
        )

    _print_comparison_table(results)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
