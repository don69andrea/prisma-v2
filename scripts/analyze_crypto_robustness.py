"""Robustheits-Analyse: Konstant-35%-Exposure vs Vol-Targeting vs Modell.

Kein Retraining. Lädt Preisdaten aus DB, berechnet drei Baseline-Varianten
auf dem OOS-Zeitraum des Modells und ergänzt docs/ml_eval_crypto_v2.md.

Kernfrage: Ist der Drawdown-Schutz des Modells echter Timing-Skill
oder nur ein Artefakt der niedrigen durchschnittlichen Investitionsquote?

Aufruf: uv run python scripts/analyze_crypto_robustness.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("robustness")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

COINS = ["BTC", "ETH", "SOL", "ADA", "BNB", "XRP"]

# Modell-Kennzahlen aus ml_eval_crypto_v2.md (fix, kein Retraining nötig)
MODEL_SIGNAL_RATE = 0.351
MODEL_SHARPE = 0.91
MODEL_MAX_DD = -0.368
MODEL_ANN_RETURN = 0.665
MODEL_CALMAR = 1.81
MODEL_2022_MAX_DD = -0.270
MODEL_2022_TOTAL = -0.090

# OOS-Periode aus den Fold-Grenzen
OOS_START = date(2019, 5, 9)
OOS_END = date(2026, 5, 1)
BEAR_START = date(2022, 1, 1)
BEAR_END = date(2022, 12, 31)

TRANSACTION_COST_RT = 0.003  # 0.3 % Round-Trip
VOL_TARGET_ANN = 0.35  # Ziel-Vola für vol-getargetete Variante (35 % p.a.)
COST_THRESHOLD = 0.05  # Position-Änderung >5 % löst TC aus


# ---------------------------------------------------------------------------
# DB-Datenladen
# ---------------------------------------------------------------------------


async def _load_closes() -> dict[str, pd.Series]:
    from sqlalchemy import text

    from backend.infrastructure.persistence.session import get_session_factory

    factory = get_session_factory()
    result: dict[str, pd.Series] = {}
    for coin in COINS:
        async with factory() as sess:
            r = await sess.execute(
                text(
                    "SELECT timestamp::date, close FROM crypto_price_history "
                    "WHERE ticker = :t AND interval = '1d' ORDER BY timestamp ASC"
                ),
                {"t": coin},
            )
            rows = r.fetchall()
        if rows:
            idx = pd.to_datetime([row[0] for row in rows])
            result[coin] = pd.Series([float(row[1]) for row in rows], index=idx)
            log.info(
                "%s: %d Tage (%s → %s)",
                coin,
                len(result[coin]),
                result[coin].index[0].date(),
                result[coin].index[-1].date(),
            )
    return result


# ---------------------------------------------------------------------------
# Monatliche Portfolio-Returns (Equal-Weight, nur verfügbare Coins)
# ---------------------------------------------------------------------------


def _build_monthly_portfolio_returns(
    closes: dict[str, pd.Series],
    start: date,
    end: date,
) -> pd.Series:
    """Monatliche Equal-Weight-Portfolio-Returns aus täglichen Close-Preisen.

    Für jeden Kalendermonat: prozentualer Return des Portfolios.
    Coins ohne Daten am Monatsanfang werden ausgelassen (PIT-korrekt).
    """
    df_list: list[pd.Series] = []
    for coin, close in closes.items():
        monthly = close.resample("MS").first()
        monthly_ret = monthly.pct_change()
        df_list.append(monthly_ret.rename(coin))

    df = pd.concat(df_list, axis=1)
    df = df[(df.index.date >= start) & (df.index.date <= end)]

    # Portf.-Return = Mittel aller Coins mit Daten (kein NaN)
    port = df.mean(axis=1, skipna=True)
    return port


# ---------------------------------------------------------------------------
# Strategien
# ---------------------------------------------------------------------------


def _strategy_full_bah(port_ret: pd.Series) -> npt.NDArray[Any]:
    """100 % Long, keine Transaktionskosten."""
    return port_ret.to_numpy(dtype=np.float64)


def _strategy_scaled_bah(port_ret: pd.Series, scale: float = MODEL_SIGNAL_RATE) -> npt.NDArray[Any]:
    """Konstant {scale}-%-Long, kein Ein/Ausstieg → keine TC."""
    return (port_ret * scale).to_numpy(dtype=np.float64)


def _strategy_vol_targeted(
    port_ret: pd.Series,
    vol_target: float = VOL_TARGET_ANN,
) -> npt.NDArray[Any]:
    """Dynamische Positionsgrösse: target_vol / trailing_3m_vol.

    TC fällt an, wenn Positionsgrösse um >COST_THRESHOLD ändert.
    """
    arr = port_ret.to_numpy(dtype=np.float64)
    n = len(arr)
    result = np.zeros(n, dtype=np.float64)
    prev_pos = 0.0

    for i in range(n):
        # Trailing 3-Monats-Vola (annualisiert)
        window = arr[max(0, i - 3) : i] if i > 0 else arr[0:1]
        if len(window) < 2:
            pos = 1.0  # Kein Prior → voll investiert
        else:
            realized_vol_ann = float(np.std(window, ddof=1)) * np.sqrt(12)
            pos = 1.0 if realized_vol_ann < 1e-6 else min(vol_target / realized_vol_ann, 1.0)

        gross = arr[i] * pos
        # TC nur bei merklicher Positionsänderung
        tc = TRANSACTION_COST_RT if abs(pos - prev_pos) > COST_THRESHOLD else 0.0
        result[i] = gross - tc
        prev_pos = pos

    return result


# ---------------------------------------------------------------------------
# Risk Metrics
# ---------------------------------------------------------------------------


def _sharpe(returns: npt.NDArray[Any], periods_per_year: float = 12.0) -> float:
    if len(returns) < 2:
        return 0.0
    std = float(np.std(returns, ddof=1))
    return 0.0 if std < 1e-9 else float(np.mean(returns) / std * np.sqrt(periods_per_year))


def _max_drawdown(returns: npt.NDArray[Any]) -> float:
    equity = np.cumprod(1 + returns)
    peaks = np.maximum.accumulate(equity)
    dd = (equity - peaks) / peaks
    return float(dd.min())


def _ann_return(returns: npt.NDArray[Any], periods_per_year: float = 12.0) -> float:
    mean_r = float(np.mean(returns))
    return float((1 + mean_r) ** periods_per_year - 1)


def _calmar(returns: npt.NDArray[Any], periods_per_year: float = 12.0) -> float:
    mdd = abs(_max_drawdown(returns))
    ann = _ann_return(returns, periods_per_year)
    return ann / mdd if mdd > 1e-6 else 0.0


def _subperiod_metrics(
    port_ret: pd.Series, strategy_returns: npt.NDArray[Any], sub_start: date, sub_end: date
) -> dict[str, float]:
    mask = (port_ret.index.date >= sub_start) & (port_ret.index.date <= sub_end)
    sub = strategy_returns[mask]
    if len(sub) < 2:
        return {"max_drawdown": 0.0, "total_return": 0.0, "n_months": 0}
    equity = np.cumprod(1 + sub)
    return {
        "max_drawdown": _max_drawdown(sub),
        "total_return": float(equity[-1] - 1),
        "n_months": len(sub),
    }


# ---------------------------------------------------------------------------
# Hauptanalyse
# ---------------------------------------------------------------------------


async def run_analysis() -> dict[str, Any]:
    closes = await _load_closes()
    port_ret = _build_monthly_portfolio_returns(closes, start=OOS_START, end=OOS_END)
    log.info("OOS-Periode: %s → %s, %d Monate", OOS_START, OOS_END, len(port_ret))

    strategies: dict[str, npt.NDArray[Any]] = {
        "full_bah": _strategy_full_bah(port_ret),
        "scaled_bah_35pct": _strategy_scaled_bah(port_ret, scale=MODEL_SIGNAL_RATE),
        "vol_targeted": _strategy_vol_targeted(port_ret),
    }

    results: dict[str, dict[str, Any]] = {}
    for name, rets in strategies.items():
        sh = _sharpe(rets)
        mdd = _max_drawdown(rets)
        ann = _ann_return(rets)
        cal = _calmar(rets)
        sub = _subperiod_metrics(port_ret, rets, BEAR_START, BEAR_END)
        results[name] = {
            "sharpe": sh,
            "max_drawdown": mdd,
            "ann_return": ann,
            "calmar": cal,
            "bear_2022": sub,
        }
        log.info(
            "[%s] Sharpe=%.2f | MaxDD=%.1f%% | Ann=%.1f%% | Bear22-MaxDD=%.1f%%",
            name,
            sh,
            mdd * 100,
            ann * 100,
            sub["max_drawdown"] * 100,
        )

    # Sharpe ist skalenunabhängig → mathematische Bestätigung
    sharpe_scale_check = (
        abs(results["full_bah"]["sharpe"] - results["scaled_bah_35pct"]["sharpe"]) < 0.01
    )

    return {
        "strategies": results,
        "port_ret": port_ret,
        "sharpe_scale_invariant_confirmed": sharpe_scale_check,
    }


# ---------------------------------------------------------------------------
# Eval-Doc ergänzen
# ---------------------------------------------------------------------------


def append_robustness_section(analysis: dict[str, Any]) -> None:
    doc_path = ROOT / "docs" / "ml_eval_crypto_v2.md"
    if not doc_path.exists():
        log.error("ml_eval_crypto_v2.md nicht gefunden — Abbruch")
        return

    r = analysis["strategies"]
    scale_inv = analysis["sharpe_scale_invariant_confirmed"]

    # Modell-Werte (aus Training-Run, fix)
    m_sh = MODEL_SHARPE
    m_mdd = MODEL_MAX_DD
    m_ann = MODEL_ANN_RETURN
    m_cal = MODEL_CALMAR
    m_b22_mdd = MODEL_2022_MAX_DD
    m_b22_tot = MODEL_2022_TOTAL

    sb = r["scaled_bah_35pct"]
    vt = r["vol_targeted"]
    fb = r["full_bah"]

    # Timing-Skill: Modell schlägt konstant-35%-BaH beim Drawdown?
    model_beats_scaled_dd = m_mdd > sb["max_drawdown"]  # (beide negativ, > = weniger negativ)
    model_beats_scaled_2022 = m_b22_mdd > sb["bear_2022"]["max_drawdown"]
    model_beats_vt_dd = m_mdd > vt["max_drawdown"]

    lines = [
        "\n\n---\n",
        "## 9 · Robustheitsprüfung: Isolierung des Timing-Skills\n",
        "Kernfrage: Schlägt das Modell auch eine **exposure-gematchte** Buy-and-Hold-Baseline?",
        "Falls ja, ist der Drawdown-Schutz echter Timing-Skill — nicht nur ein Artefakt",
        "der niedrigen Investitionsquote (35.1 % Signal-Rate).\n",
        "### 9.1 · Strategie-Definitionen\n",
        "| Strategie | Investitionsquote | Transaktionskosten | Beschreibung |",
        "|-----------|------------------|--------------------|-------------|",
        "| Modell | ≈35.1 % (dynamisch) | 0.3 % RT wenn Long | Signal-basiertes Timing |",
        "| **Konstant-35 %-BaH** | 35.1 % (fix) | 0 % (statisch) | Gleiche Ø-Exposure, kein Timing |",
        "| Vol-Targeting BaH | dynamisch (Ziel: 35 % p.a.) | 0.3 % RT wenn Pos.-Wechsel >5 % | Risiko-Budgetierung ohne Timing |",
        "| Buy-and-Hold | 100 % (fix) | 0 % | Passives Benchmark |",
        "\n*Note: Sharpe Ratio ist skalenunabhängig (bei Risk-Free=0): "
        f"konstant-35 %-BaH hat per Definition denselben Sharpe wie BaH {'✅ bestätigt' if scale_inv else '⚠ numerisch'} "
        f"({fb['sharpe']:.2f} ≈ {sb['sharpe']:.2f}). Modell (0.91) muss sich daher gegen BaH-Sharpe (0.82) messen.*\n",
        "### 9.2 · Risikoadjustierte Kennzahlen (OOS-Zeitraum 2019–2026)\n",
        "| Strategie | Sharpe | Ann. Return (netto) | Max-Drawdown | Calmar |",
        "|-----------|--------|--------------------|--------------|----|",
        f"| **Modell** | **{m_sh:.2f}** | {m_ann * 100:.1f}% | **{m_mdd * 100:.1f}%** | {m_cal:.2f} |",
        f"| Konstant-35 %-BaH | {sb['sharpe']:.2f} | {sb['ann_return'] * 100:.1f}% | {sb['max_drawdown'] * 100:.1f}% | {sb['calmar']:.2f} |",
        f"| Vol-Targeting BaH | {vt['sharpe']:.2f} | {vt['ann_return'] * 100:.1f}% | {vt['max_drawdown'] * 100:.1f}% | {vt['calmar']:.2f} |",
        f"| Buy-and-Hold (100 %) | {fb['sharpe']:.2f} | {fb['ann_return'] * 100:.1f}% | {fb['max_drawdown'] * 100:.1f}% | {fb['calmar']:.2f} |",
        "",
        f"**Modell MaxDD ({m_mdd * 100:.1f}%) < Konstant-35%-BaH MaxDD ({sb['max_drawdown'] * 100:.1f}%):** "
        f"{'✅ JA — echter Timing-Skill' if model_beats_scaled_dd else '❌ NEIN — nur Unterinvestition'}",
        f"**Modell MaxDD < Vol-Targeting ({vt['max_drawdown'] * 100:.1f}%):** "
        f"{'✅ JA' if model_beats_vt_dd else '❌ NEIN'}",
        "",
        "### 9.3 · Bear-Market-Vergleich 2022 (LUNA + FTX)\n",
        "| Strategie | MaxDD 2022 | Gesamt-Return 2022 |",
        "|-----------|------------|-------------------|",
        f"| **Modell** | **{m_b22_mdd * 100:.1f}%** | {m_b22_tot * 100:.1f}% |",
        f"| Konstant-35 %-BaH | {sb['bear_2022']['max_drawdown'] * 100:.1f}% | {sb['bear_2022']['total_return'] * 100:.1f}% |",
        f"| Vol-Targeting BaH | {vt['bear_2022']['max_drawdown'] * 100:.1f}% | {vt['bear_2022']['total_return'] * 100:.1f}% |",
        f"| Buy-and-Hold (100 %) | {fb['bear_2022']['max_drawdown'] * 100:.1f}% | {fb['bear_2022']['total_return'] * 100:.1f}% |",
        "",
        f"**2022: Modell ({m_b22_mdd * 100:.1f}%) vs Konstant-35%-BaH ({sb['bear_2022']['max_drawdown'] * 100:.1f}%):** "
        f"{'✅ Modell hat echten Timing-Skill — geringerer Drawdown trotz gleicher Ø-Exposure' if model_beats_scaled_2022 else '❌ Kein Timing-Vorteil in 2022 — Drawdown trotz 35 %-Exposure ähnlich'}",
        "",
        "### 9.4 · Schlussfolgerung (ehrlich)\n",
    ]

    if model_beats_scaled_2022 and model_beats_scaled_dd:
        conclusion_lines = [
            "**ML auf Krypto zeigt robuste DRAWDOWN-/REGIME-Vermeidung, aber keine zuverlässige Return-Vorhersage.**\n",
            "Die Robustheitsprüfung bestätigt: Der Drawdown-Schutz ist **echter Timing-Skill**,",
            "nicht nur ein Artefakt der niedrigen Investitionsquote. Eine konstant-35%-Exposure-BaH",
            f"ohne Timing-Signal hätte in 2022 noch {sb['bear_2022']['max_drawdown'] * 100:.1f}% verloren",
            f"— das Modell begrenzte den Verlust auf {m_b22_mdd * 100:.1f}%, also",
            f"{(sb['bear_2022']['max_drawdown'] - m_b22_mdd) * 100:.1f} Prozentpunkte weniger.\n",
            "**Was das Modell kann:**",
            f"- Regime-Erkennung: vermeidet die schlimmsten Bärmarkt-Phasen (2022: {m_b22_mdd * 100:.1f}% vs {sb['bear_2022']['max_drawdown'] * 100:.1f}% Exposure-adj. BaH)",
            f"- Sharpe-Verbesserung: {m_sh:.2f} vs {fb['sharpe']:.2f} (BaH) — risikoadjustiert überlegen",
            f"- Calmar: {m_cal:.2f} vs {fb['calmar']:.2f} (BaH) — besseres Return/Drawdown-Verhältnis\n",
            "**Was das Modell NICHT kann:**",
            "- Returns zuverlässig vorhersagen: F1=0.42 ± 0.06, verliert gegen Momentum-Only im F1",
            "- Buy-and-Hold im rohen Return schlagen: 66.5 % vs 130.2 % p.a. — der Bullenmarkt-Drift",
            "  dominiert bei 65 % Cash-Quote\n",
            "**Empfehlung:**",
            "Das Modell eignet sich als **Risikomanagement-Overlay** (Drawdown-Begrenzung,",
            "Bärmarkt-Erkennung), nicht als Return-Generator. Wert liegt im Kapitalschutz,",
            "nicht in Alpha-Generierung.",
        ]
    else:
        conclusion_lines = [
            "**ML auf Krypto: Drawdown-Schutz primär durch Unterinvestition, nicht durch Timing-Skill.**\n",
            "Die Robustheitsprüfung zeigt: Eine konstant-35%-Exposure-BaH ohne Timing-Signal",
            f"erreicht in 2022 ähnliche Drawdowns ({sb['bear_2022']['max_drawdown'] * 100:.1f}% vs Modell {m_b22_mdd * 100:.1f}%).",
            "Der scheinbare Vorteil erklärt sich fast vollständig durch die niedrige",
            "Investitionsquote (35.1 %), nicht durch echtes Market-Timing.\n",
            "**Was das Modell kann:**",
            f"- Sharpe-Verbesserung vs BaH: {m_sh:.2f} vs {fb['sharpe']:.2f} — aber das ist skalenunabhängig",
            "  und spiegelt die niedrigere Vola bei niedrigerer Exposure wider\n",
            "**Was das Modell NICHT kann:**",
            "- Echter Timing-Skill: Drawdown ähnlich wie exposure-gematchte Baseline",
            "- Returns vorhersagen: F1=0.42 ± 0.06, verliert gegen Momentum-Only\n",
            "**Schlussfolgerung:** Technische Features + Fear&Greed + MVRV liefern keinen",
            "signifikanten Timing-Edge gegenüber simplen Exposure-Baselines.",
            "Falls Drawdown-Reduktion das Ziel ist, ist konstantes Risk-Targeting genauso gut.",
        ]

    lines.extend(conclusion_lines)

    existing = doc_path.read_text()
    # Prüfe ob Abschnitt 9 bereits vorhanden
    if "## 9 ·" in existing:
        # Abschnitt 9 ersetzen
        idx = existing.find("\n\n---\n\n## 9 ·")
        if idx == -1:
            idx = existing.find("## 9 ·")
            if idx > 0:
                # Suche nach dem vorherigen doppelten Newline
                idx = existing.rfind("\n\n", 0, idx)
        if idx > 0:
            existing = existing[:idx]
        doc_path.write_text(existing + "\n".join(lines))
        log.info("Abschnitt 9 ersetzt in ml_eval_crypto_v2.md")
    else:
        doc_path.write_text(existing + "\n".join(lines))
        log.info("Abschnitt 9 angehängt an ml_eval_crypto_v2.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    log.info("=== Robustheits-Analyse: Konstant-35%%-BaH + Vol-Targeting ===")
    analysis = await run_analysis()
    append_robustness_section(analysis)
    log.info("Fertig — docs/ml_eval_crypto_v2.md aktualisiert")


if __name__ == "__main__":
    asyncio.run(main())
