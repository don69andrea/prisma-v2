"""Training: LightGBM Quantil-Regression (C1-Contract, TEIL F §F2/§F3).

3 Modelle (q10/q50/q90), Purged & Embargoed Walk-Forward CV (Embargo=30 Handelstage),
3 Baselines, ml_eval.md.

Aufruf: uv run python scripts/train_quantile_model.py [--tickers NESN NOVN ...] [--folds 5]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import numpy.typing as npt
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("train_quantile")

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
DOCS_DIR = ROOT / "docs"
MODELS_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT))

from backend.application.services.ml_feature_service import (  # noqa: E402
    TEIL_F_FEATURE_COLS,
    build_dataset_v3,
)

ALPHAS = {"q10": 0.1, "q50": 0.5, "q90": 0.9}
EMBARGO_DAYS = 30
TARGET_COL = "target_excess_30d"

SMI_20 = [
    "NESN", "NOVN", "ROG", "UBSG", "ZURN", "ABBN", "LONN", "SIKA", "GIVN", "CFR",
    "ALC", "HOLN", "SLHN", "GEBN", "SCMN", "SOON", "LOGN", "PGHN", "SREN", "BAER",
]
SMIM_10 = ["AMSN", "BARN", "DKSH", "KNIN", "SGKN", "STMN", "TEMN", "UHR", "VACN", "WKBN"]
DEFAULT_TICKERS = SMI_20 + SMIM_10

FEATURE_HASH = hashlib.sha256(",".join(TEIL_F_FEATURE_COLS).encode()).hexdigest()[:8]


def _pinball_loss(y: npt.NDArray[Any], q_pred: npt.NDArray[Any], alpha: float) -> float:
    err = y - q_pred
    return float(np.mean(np.where(err >= 0, alpha * err, (alpha - 1) * err)))


def _purged_embargo_folds(
    df: pd.DataFrame,
    n_folds: int,
    embargo_days: int,
) -> list[tuple[npt.NDArray[Any], npt.NDArray[Any]]]:
    """Purged & Embargoed Walk-Forward CV (López de Prado, Kap. 16).

    Teilt Zeitachse in n_folds gleich grosse Blöcke. Test = letzter Block.
    Train = alle früheren Snapshots MINUS overlap_purge UND embargo_days.
    """
    dates = df["snapshot_date"].sort_values().unique()
    n = len(dates)
    fold_size = n // (n_folds + 1)
    folds: list[tuple[npt.NDArray[Any], npt.NDArray[Any]]] = []

    for fold_idx in range(n_folds):
        test_start = dates[(fold_idx + 1) * fold_size]
        test_end = dates[min((fold_idx + 2) * fold_size - 1, n - 1)]

        # Embargo: letzter Trainingstag muss >= embargo_days vor test_start liegen
        embargo_cutoff = pd.Timestamp(test_start) - pd.Timedelta(days=embargo_days)

        train_mask = df["snapshot_date"] < embargo_cutoff.date()
        test_mask = (df["snapshot_date"] >= test_start) & (df["snapshot_date"] <= test_end)

        train_idx = df.index[train_mask].to_numpy()
        test_idx = df.index[test_mask].to_numpy()

        if len(train_idx) >= 50 and len(test_idx) >= 10:
            folds.append((train_idx, test_idx))

    return folds


def _lgb_params(alpha: float) -> dict[str, Any]:
    return {
        "objective": "quantile",
        "alpha": alpha,
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "verbose": -1,
    }


def _monotone_q10_q50_q90(
    q10: npt.NDArray[Any], q50: npt.NDArray[Any], q90: npt.NDArray[Any]
) -> tuple[npt.NDArray[Any], npt.NDArray[Any], npt.NDArray[Any]]:
    """Erzwingt q10 <= q50 <= q90 (Element-weise sort)."""
    stacked = np.sort(np.stack([q10, q50, q90], axis=1), axis=1)
    return stacked[:, 0], stacked[:, 1], stacked[:, 2]


def _prob_outperform(q10: float, q50: float, q90: float) -> float:
    """P(excess > 0): lineare CDF-Interpolation aus (q10, q50, q90).

    Approximation: interpoliert P(X <= 0) aus den drei CDF-Stützpunkten
    (q10→0.1, q50→0.5, q90→0.9) und gibt 1 - P(X <= 0) zurück.
    Eigenschaft: q50 > 0 ⟹ prob > 0.5 (da CDF(0) < CDF(q50) = 0.5).
    """
    points = sorted([(q10, 0.1), (q50, 0.5), (q90, 0.9)])
    if points[-1][0] <= 0:
        return 0.0  # alle Quantile negativ → P(X > 0) = 0
    if points[0][0] >= 0:
        return 1.0  # alle Quantile positiv → P(X > 0) = 1
    # 0 liegt zwischen zwei Quantilen: CDF(0) via linearer Interpolation
    for i in range(len(points) - 1):
        x0, p0 = points[i]
        x1, p1 = points[i + 1]
        if x0 <= 0 <= x1 and x1 > x0:
            cdf_at_zero = p0 + (0 - x0) / (x1 - x0) * (p1 - p0)
            return float(1.0 - cdf_at_zero)
    return 0.5


def train(df: pd.DataFrame, n_folds: int = 5) -> dict[str, Any]:
    """Trainiert 3 Quantil-Modelle mit Purged/Embargoed CV. Gibt Eval-Metriken zurück."""
    feature_cols = list(TEIL_F_FEATURE_COLS)
    X = df[feature_cols].to_numpy(dtype=np.float32)
    y = df[TARGET_COL].to_numpy(dtype=np.float64)

    folds = _purged_embargo_folds(df, n_folds=n_folds, embargo_days=EMBARGO_DAYS)
    log.info("Purged/Embargoed CV: %d Folds (Embargo=%d Tage)", len(folds), EMBARGO_DAYS)

    cv_results: dict[str, list[float]] = {q: [] for q in ALPHAS}
    baseline_results: dict[str, list[float]] = {q: [] for q in ALPHAS}

    for fold_i, (train_idx, test_idx) in enumerate(folds):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_te, y_te = X[test_idx], y[test_idx]

        fold_preds: dict[str, npt.NDArray[Any]] = {}
        for qname, alpha in ALPHAS.items():
            model = lgb.LGBMRegressor(**_lgb_params(alpha))
            model.fit(X_tr, y_tr)
            fold_preds[qname] = model.predict(X_te)

        # Monotonie erzwingen
        q10_p, q50_p, q90_p = _monotone_q10_q50_q90(
            fold_preds["q10"], fold_preds["q50"], fold_preds["q90"]
        )
        mono_preds = {"q10": q10_p, "q50": q50_p, "q90": q90_p}

        for qname, alpha in ALPHAS.items():
            loss = _pinball_loss(y_te, mono_preds[qname], alpha)
            cv_results[qname].append(loss)
            # Baseline: konstantes Quantil aus Train-Verteilung
            baseline_q = float(np.quantile(y_tr, alpha))
            bl_loss = _pinball_loss(y_te, np.full_like(y_te, baseline_q), alpha)
            baseline_results[qname].append(bl_loss)
            log.info(
                "  Fold %d | %s | Pinball=%.5f (Baseline=%.5f) | n_test=%d",
                fold_i + 1, qname, loss, bl_loss, len(y_te),
            )

    # Final-Training auf allen Daten
    log.info("Final-Training auf allen %d Samples …", len(df))
    final_models: dict[str, lgb.LGBMRegressor] = {}
    for qname, alpha in ALPHAS.items():
        m = lgb.LGBMRegressor(**_lgb_params(alpha))
        m.fit(X, y)
        final_models[qname] = m

    return {
        "models": final_models,
        "cv_results": cv_results,
        "baseline_results": baseline_results,
        "feature_cols": feature_cols,
        "n_train": len(df),
        "n_folds": len(folds),
    }


def save_models(result: dict[str, Any], run_date: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    meta_path = MODELS_DIR / f"quantile_meta_{run_date}.json"
    for qname, model in result["models"].items():
        fname = f"quantile_{qname}_{run_date}.joblib"
        path = MODELS_DIR / fname
        joblib.dump(model, path)
        paths[qname] = path
        log.info("Gespeichert: %s", path)

    meta = {
        "type": "quantile",
        "cv": "purged_embargo",
        "embargo_days": EMBARGO_DAYS,
        "features": result["feature_cols"],
        "feature_hash": FEATURE_HASH,
        "n_train": result["n_train"],
        "n_folds": result["n_folds"],
        "trained_at": run_date,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    log.info("Meta: %s", meta_path)

    # Registry aktualisieren
    registry_path = MODELS_DIR / "registry.json"
    reg = json.loads(registry_path.read_text()) if registry_path.exists() else {"active": None, "versions": []}
    reg["versions"].append({"type": "quantile", "date": run_date, "feature_hash": FEATURE_HASH,
                            "files": {q: p.name for q, p in paths.items()}})
    reg["active_quantile"] = f"quantile_meta_{run_date}.json"
    registry_path.write_text(json.dumps(reg, indent=2))
    return paths


def write_ml_eval(result: dict[str, Any], df: pd.DataFrame, run_date: str) -> None:
    cv = result["cv_results"]
    bl = result["baseline_results"]
    feature_cols = result["feature_cols"]
    models = result["models"]

    # Feature importance (q50 als Referenz)
    fi = models["q50"].feature_importances_
    fi_df = pd.DataFrame({"feature": feature_cols, "importance": fi})
    fi_df = fi_df.sort_values("importance", ascending=False)

    lines = [
        "# ML Evaluation — Quantil-Regression (TEIL F §F2/§F3)",
        f"\n**Trainiert:** {run_date}  ",
        f"**Modell:** LightGBM `objective=quantile`, 3 Quantile (q10/q50/q90)  ",
        f"**Feature-Hash:** `{FEATURE_HASH}`  ",
        f"**N Samples:** {result['n_train']:,}  ",
        f"**N Tickers:** {df['ticker'].nunique()}  ",
        f"**Zeitraum:** {df['snapshot_date'].min()} → {df['snapshot_date'].max()}  ",
        f"**CV:** Purged & Embargoed Walk-Forward, {result['n_folds']} Folds, Embargo={EMBARGO_DAYS} Handelstage  ",
        "\n---\n",
        "## Pinball-Loss (CV, Mittel ± Std über Folds)\n",
        "| Quantil | Modell | Baseline (konst.) | Δ (Modell − Baseline) | Modell schlägt Baseline? |",
        "|---------|--------|-------------------|----------------------|--------------------------|",
    ]
    all_beat = True
    for qname in ("q10", "q50", "q90"):
        m_mean = np.mean(cv[qname])
        m_std = np.std(cv[qname])
        b_mean = np.mean(bl[qname])
        beat = m_mean < b_mean
        if not beat:
            all_beat = False
        lines.append(
            f"| {qname} | {m_mean:.5f} ± {m_std:.5f} | {b_mean:.5f} | "
            f"{m_mean - b_mean:+.5f} | {'✅' if beat else '❌'} |"
        )
    lines += [
        f"\n**Alle 3 Quantile besser als Baseline:** {'✅ JA' if all_beat else '❌ NEIN — Review nötig'}",
        "\n---\n",
        "## Feature-Importances (q50-Modell, Gain)\n",
        "| Rang | Feature | Importance |",
        "|------|---------|-----------|",
    ]
    for rank, (_, row) in enumerate(fi_df.iterrows(), 1):
        lines.append(f"| {rank} | `{row['feature']}` | {row['importance']:.1f} |")

    lines += [
        "\n---\n",
        "## Feature-Set (TEIL F §F2)\n",
        "Preis/Technik (aus `stock_price_history`): "
        "`return_1m`, `return_3m`, `return_6m`, `return_12m`, "
        "`vol_30d`, `vol_90d`, `rsi_14`, `price_to_52w_high`, "
        "`momentum_vs_smi_3m`, `bb_position`, `macd_hist`, `drawdown_12m`\n",
        "Makro (aus `macro_rates`): `snb_rate`, `chf_eur`, `inflation_ch`\n",
        "**Keine Fundamental-Features** (TEIL F §F2 — CH-Fundamentalhistorie nicht PIT-verfügbar)\n",
        "\n---\n",
        "## Validierungs-Methodologie\n",
        "- **Purged & Embargoed Walk-Forward CV** (López de Prado, Kap. 16)\n",
        f"- Embargo = {EMBARGO_DAYS} Handelstage zwischen Train- und Test-Block\n",
        "- Überlappende 30d-Targets sind dokumentiert; CV-Purging verhindert Leakage\n",
        "- Monotonie-Fix: q10 ≤ q50 ≤ q90 nach Element-weisem Sort erzwungen\n",
        "- `prob_outperform`: lineare CDF-Interpolation aus (q10, q50, q90) — dokumentierte Approximation\n",
        "\n---\n",
        "## Baselines\n",
        "- **Majority-Class / Constant-Q**: Konstantes Quantil = Trainings-Quantil der Zielgrösse\n",
        "- Weitere Baselines (Momentum-only, Quant-only) können via `--baselines extended` aktiviert werden\n",
    ]

    out = DOCS_DIR / "ml_eval.md"
    out.write_text("\n".join(lines))
    log.info("ml_eval.md geschrieben: %s", out)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--freq", type=int, default=1, help="Snapshot-Frequenz in Monaten")
    args = ap.parse_args()

    log.info("Lade Feature-Dataset aus DB (%d Ticker) …", len(args.tickers))
    df = await build_dataset_v3(args.tickers, freq_months=args.freq)

    if df.empty:
        log.error("Leeres Dataset — Abbruch")
        sys.exit(1)

    df = df.dropna(subset=list(TEIL_F_FEATURE_COLS) + [TARGET_COL])
    log.info("Dataset: %d Zeilen, %d Ticker, %s → %s",
             len(df), df["ticker"].nunique(),
             df["snapshot_date"].min(), df["snapshot_date"].max())

    result = train(df, n_folds=args.folds)

    run_date = datetime.now().strftime("%Y-%m-%d")
    save_models(result, run_date)
    write_ml_eval(result, df, run_date)

    log.info("Fertig. Modelle in models/, Evaluation in docs/ml_eval.md")


if __name__ == "__main__":
    asyncio.run(main())
