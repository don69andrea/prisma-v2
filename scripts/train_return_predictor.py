"""Issue #13 — XGBoost/LightGBM Return Predictor Training Script.

Walk-Forward-Validierung: Modell wird auf N-1 Jahren trainiert, auf letzten
12 Monaten validiert. Bestes Modell (XGBoost vs. LightGBM nach Val-Accuracy)
wird als joblib-Artifact in models/ gespeichert.

Usage:
    python scripts/train_return_predictor.py
    python scripts/train_return_predictor.py --tickers NESN NOVN ROG --years 4
    python scripts/train_return_predictor.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

# Projekt-Root zum sys.path hinzufügen
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.application.services.ml_feature_service import MLFeatureService  # noqa: E402
from backend.domain.value_objects.ml_feature_vector import MLFeatureVector  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_logger = logging.getLogger(__name__)

MODELS_DIR = ROOT / "models"

# SMI-Univers (20 Blue Chips + 10 Mid Caps für genug Trainingssamples)
DEFAULT_TICKERS = [
    "NESN",
    "NOVN",
    "ROG",
    "ABBN",
    "ZURN",
    "UHR",
    "GIVN",
    "SIKA",
    "LONN",
    "AMS",
    "BAER",
    "SLHN",
    "SCMN",
    "GEBN",
    "CSGN",
    "UBSG",
    "CFR",
    "CLTN",
    "DUFN",
    "KNIN",
]

FEATURE_NAMES = list(MLFeatureVector.FEATURE_NAMES)


# ---------------------------------------------------------------------------
# Walk-Forward Split
# ---------------------------------------------------------------------------


def walk_forward_split(
    df: pd.DataFrame,
    val_months: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Teilt DataFrame in Trainings- und Validierungsset (Walk-Forward).

    Die letzten `val_months` Snapshot-Monate dienen als Validierungsset.
    """
    df = df.copy()
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    cutoff = df["snapshot_date"].max() - pd.DateOffset(months=val_months)
    train = df[df["snapshot_date"] <= cutoff]
    val = df[df["snapshot_date"] > cutoff]
    return train, val


# ---------------------------------------------------------------------------
# Metriken
# ---------------------------------------------------------------------------


def top_quartile_accuracy(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    top_class: int = 2,
) -> float:
    """Anteil korrekt identifizierter Top-Quartil-Aktien."""
    mask = y_true == top_class
    if mask.sum() == 0:
        return 0.0
    return float((y_pred[mask] == top_class).mean())


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float((y_true == y_pred).mean())


# ---------------------------------------------------------------------------
# Modelltraining
# ---------------------------------------------------------------------------


def train_xgboost(x_train: np.ndarray, y_train: np.ndarray) -> Any:
    """Trainiert XGBoost-Klassifikator (3 Klassen)."""
    from xgboost import XGBClassifier

    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        objective="multi:softmax",
        num_class=3,
        random_state=42,
        eval_metric="mlogloss",
        verbosity=0,
    )
    model.fit(x_train, y_train)
    return model


def train_lightgbm(x_train: np.ndarray, y_train: np.ndarray) -> Any:
    """Trainiert LightGBM-Klassifikator (3 Klassen)."""
    import lightgbm as lgb

    model = lgb.LGBMClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=10,
        num_leaves=15,
        objective="multiclass",
        num_class=3,
        random_state=42,
        verbosity=-1,
    )
    model.fit(x_train, y_train)
    return model


# ---------------------------------------------------------------------------
# Feature Importance Report
# ---------------------------------------------------------------------------


def feature_importance_report(model: Any, feature_names: list[str]) -> dict[str, float]:
    """Gibt Feature-Importances als geordnetes Dict zurück."""
    try:
        importances: np.ndarray = model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]
        return {feature_names[i]: float(importances[i]) for i in sorted_idx}
    except AttributeError:
        return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PRISMA Return Predictor")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Swiss tickers to include (default: SMI-20)",
    )
    parser.add_argument("--years", type=int, default=3, help="Years of history (default: 3)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build dataset only, skip training",
    )
    args = parser.parse_args()

    tickers: list[str] = args.tickers
    years: int = args.years

    _logger.info("Starte ML-Feature-Engineering für %d Tickers, %d Jahre", len(tickers), years)

    service = MLFeatureService()
    df = service.build_dataset(tickers=tickers, years=years)

    if df.empty:
        _logger.error("Kein Trainings-Dataset erzeugt — alle Ticker fehlgeschlagen?")
        sys.exit(1)

    _logger.info(
        "Dataset: %d Zeilen, %d Tickers, %d Snapshot-Dates",
        len(df),
        df["ticker"].nunique(),
        df["snapshot_date"].nunique(),
    )

    target_dist = df["target_class"].value_counts().sort_index().to_dict()
    _logger.info("Klassen-Verteilung: %s", target_dist)

    if args.dry_run:
        _logger.info("--dry-run: Kein Modell trainiert.")
        csv_path = MODELS_DIR / "dataset_preview.csv"
        MODELS_DIR.mkdir(exist_ok=True)
        df.head(100).to_csv(csv_path, index=False)
        _logger.info("Erste 100 Zeilen gespeichert: %s", csv_path)
        return

    # Walk-Forward Split
    train_df, val_df = walk_forward_split(df, val_months=12)
    _logger.info("Train: %d Zeilen | Val: %d Zeilen", len(train_df), len(val_df))

    if len(train_df) < 50:
        _logger.error("Zu wenig Trainingsdaten (%d Zeilen). Abbruch.", len(train_df))
        sys.exit(1)

    x_train = train_df[FEATURE_NAMES].values.astype(np.float32)
    y_train = train_df["target_class"].values.astype(int)
    x_val = val_df[FEATURE_NAMES].values.astype(np.float32)
    y_val = val_df["target_class"].values.astype(int)

    # XGBoost
    _logger.info("Trainiere XGBoost …")
    xgb_model = train_xgboost(x_train, y_train)
    xgb_pred = xgb_model.predict(x_val)
    xgb_acc = accuracy(y_val, xgb_pred)
    xgb_top = top_quartile_accuracy(y_val, xgb_pred)
    _logger.info("XGBoost — Accuracy: %.3f | Top-Quartil-Recall: %.3f", xgb_acc, xgb_top)

    # LightGBM
    _logger.info("Trainiere LightGBM …")
    lgb_model = train_lightgbm(x_train, y_train)
    lgb_pred = lgb_model.predict(x_val)
    lgb_acc = accuracy(y_val, lgb_pred)
    lgb_top = top_quartile_accuracy(y_val, lgb_pred)
    _logger.info("LightGBM — Accuracy: %.3f | Top-Quartil-Recall: %.3f", lgb_acc, lgb_top)

    # Bestes Modell nach Top-Quartil-Recall (wichtiger als Overall-Accuracy für Stock Picking)
    if xgb_top >= lgb_top:
        best_model = xgb_model
        best_name = "xgboost"
        best_acc = xgb_acc
        best_top = xgb_top
    else:
        best_model = lgb_model
        best_name = "lightgbm"
        best_acc = lgb_acc
        best_top = lgb_top

    _logger.info("Bestes Modell: %s (Top-Quartil-Recall=%.3f)", best_name, best_top)

    # Feature Importance
    importance = feature_importance_report(best_model, FEATURE_NAMES)
    if importance:
        top5 = list(importance.items())[:5]
        _logger.info("Top-5 Features: %s", top5)

    # Artifact speichern
    MODELS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = MODELS_DIR / f"return_predictor_{best_name}_{ts}.joblib"
    meta_path = MODELS_DIR / "return_predictor_latest.json"

    joblib.dump(best_model, model_path)
    _logger.info("Modell gespeichert: %s", model_path)

    meta = {
        "model_path": str(model_path),
        "model_type": best_name,
        "trained_at": ts,
        "tickers": tickers,
        "years": years,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "val_accuracy": round(best_acc, 4),
        "val_top_quartile_recall": round(best_top, 4),
        "feature_names": FEATURE_NAMES,
        "feature_importance": {k: round(v, 4) for k, v in importance.items()},
        "class_distribution": {str(k): int(v) for k, v in target_dist.items()},
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    _logger.info("Modell-Metadaten: %s", meta_path)

    # Auch als latest-Link speichern
    latest_path = MODELS_DIR / "return_predictor_latest.joblib"
    joblib.dump(best_model, latest_path)
    _logger.info("Latest-Link gespeichert: %s", latest_path)


if __name__ == "__main__":
    main()
