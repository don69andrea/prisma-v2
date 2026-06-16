"""Issue #13 — XGBoost/LightGBM Return Predictor Training Script.

Walk-Forward-Validierung: Modell wird auf N-1 Jahren trainiert, auf letzten
12 Monaten validiert. Bestes Modell (XGBoost vs. LightGBM nach Val-Accuracy)
wird als joblib-Artifact in models/ gespeichert.

Usage:
    python scripts/train_return_predictor.py
    python scripts/train_return_predictor.py --tickers NESN NOVN ROG --years 4
    python scripts/train_return_predictor.py --market all --years 8
    python scripts/train_return_predictor.py --market all --simfin-key YOUR_KEY --tune
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

# SMI-Univers (SMI-20 Blue Chips + SMIM Mid Caps)
DEFAULT_TICKERS = [
    # SMI-20 Blue Chips
    "NESN", "NOVN", "ROG", "ABBN", "ZURN", "UHR", "GIVN", "SIKA",
    "LONN", "BAER", "SLHN", "SCMN", "GEBN", "UBSG", "CFR", "KNIN",
    "PGHN", "HOLN", "SREN", "SGKN",
    # SMIM Mid Caps (HELN/DUFN/SOFN/CSGN/MBTN delisted — entfernt 2026-06-12)
    "VACN", "TEMN", "COTN", "STMN", "DKSH", "EMMN", "BARN",
    "CLTN", "LISP", "BUCN", "AMS", "CMBN",
    "BCVN", "ORON", "SPSN",
]

# DAX-40 Hauptwerte (Xetra, yfinance-Format mit .DE Suffix)
EU_TICKERS_DE = [
    "SAP.DE", "SIE.DE", "ALV.DE", "MUV2.DE", "DTE.DE",
    "BAYN.DE", "IFX.DE", "BMW.DE", "MBG.DE", "DB1.DE",
    "BAS.DE", "EOAN.DE", "RWE.DE", "ADS.DE", "HNR1.DE",
    "BEI.DE", "HEN3.DE", "MRK.DE", "SHL.DE", "VOW3.DE",
]

# CAC-40 Hauptwerte (Euronext Paris, .PA Suffix)
EU_TICKERS_FR = [
    "OR.PA", "MC.PA", "TTE.PA", "SAN.PA", "BNP.PA",
    "AI.PA", "AIR.PA", "DG.PA", "SU.PA", "CS.PA",
    "ACA.PA", "GLE.PA", "KER.PA", "RI.PA", "CAP.PA",
]

# AEX Hauptwerte (Amsterdam, .AS Suffix) — ING.AS/DSM.AS keine yfinance-Daten
EU_TICKERS_NL = [
    "ASML.AS", "HEIA.AS", "PHIA.AS", "AD.AS",
    "NN.AS", "RAND.AS",
]

# FTSE-100 Hauptwerte (London, .L Suffix, GBP-denominiert)
EU_TICKERS_UK = [
    "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L", "RIO.L",
    "BP.L", "GSK.L", "LSEG.L", "DGE.L", "BHP.L",
    "NWG.L", "LLOY.L", "VOD.L", "REL.L", "IMB.L",
]

# IBEX-35 Hauptwerte (Madrid, .MC Suffix)
EU_TICKERS_ES = [
    "SAN.MC", "ITX.MC", "IBE.MC", "REP.MC", "BBVA.MC",
    "TEF.MC", "ACS.MC", "AENA.MC", "FER.MC", "AMS.MC",
]

# FTSE MIB Hauptwerte (Mailand, .MI Suffix) — STM.MI rate-limited/unzuverlässig
EU_TICKERS_IT = [
    "ENI.MI", "ENEL.MI", "ISP.MI", "UCG.MI",
    "TIT.MI", "PRY.MI", "LDO.MI", "RACE.MI", "G.MI",
]

# OMX Stockholm Hauptwerte (Stockholm, .ST Suffix, SEK-denominiert)
EU_TICKERS_SE = [
    "ERIC-B.ST", "VOLV-B.ST", "SEB-A.ST", "SWED-A.ST",
    "INVE-B.ST", "SAND.ST", "SKF-B.ST", "HM-B.ST",
]

# Alle EU-Ticker zusammen
EU_TICKERS_ALL = (
    EU_TICKERS_DE + EU_TICKERS_FR + EU_TICKERS_NL
    + EU_TICKERS_UK + EU_TICKERS_ES + EU_TICKERS_IT + EU_TICKERS_SE
)

# S&P 500 Mega/Large Caps (kein Börsen-Suffix für yfinance)
US_TICKERS = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA",
    "AVGO", "ORCL", "AMD", "QCOM", "TXN", "AMAT", "MU",
    # Finance
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "V", "MA", "AXP",
    # Healthcare
    "LLY", "UNH", "ABBV", "MRK", "PFE", "TMO", "JNJ",
    # Consumer
    "HD", "MCD", "KO", "PEP", "WMT", "COST", "NKE",
    # Industrial / Energy
    "XOM", "CVX", "CAT", "HON", "GE", "RTX",
    # Other
    "BRK-B", "VZ",
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
    max_date = df["snapshot_date"].max()
    cutoff = (max_date - pd.DateOffset(months=val_months)).to_pydatetime()
    train = df[df["snapshot_date"] <= pd.Timestamp(cutoff)]
    val = df[df["snapshot_date"] > pd.Timestamp(cutoff)]
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
        class_weight="balanced",
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
# Optuna Hyperparameter Tuning
# ---------------------------------------------------------------------------


def tune_lightgbm(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    n_trials: int = 50,
) -> Any:
    """Hyperparameter-Suche für LightGBM via Optuna (minimiert neg. Top-Quartil-Recall)."""
    try:
        import optuna
    except ImportError:
        _logger.warning("optuna nicht installiert — überspringe Tuning. `pip install optuna`")
        return None

    import lightgbm as lgb

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 600),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "num_leaves": trial.suggest_int("num_leaves", 15, 63),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 40),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 1.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 1.0, log=True),
        }
        model = lgb.LGBMClassifier(
            **params,
            objective="multiclass",
            num_class=3,
            random_state=42,
            verbosity=-1,
            class_weight="balanced",
        )
        model.fit(x_train, y_train)
        pred = model.predict(x_val)
        return -top_quartile_accuracy(y_val, pred)

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    _logger.info(
        "Optuna beste Parameter: %s (Top-Quartil-Recall=%.3f)",
        study.best_params,
        -study.best_value,
    )

    best_model = lgb.LGBMClassifier(
        **study.best_params,
        objective="multiclass",
        num_class=3,
        random_state=42,
        verbosity=-1,
        class_weight="balanced",
    )
    best_model.fit(x_train, y_train)
    return best_model


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
    parser.add_argument("--years", type=int, default=8, help="Years of history (default: 8)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build dataset only, skip training",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run Optuna hyperparameter search for LightGBM (50 trials, requires optuna package)",
    )
    parser.add_argument(
        "--market",
        choices=["ch", "eu", "us", "all"],
        default="ch",
        help="Märkte: ch=Schweiz, eu=Europa, us=USA, all=CH+EU+US (default: ch)",
    )
    parser.add_argument(
        "--simfin-key",
        type=str,
        default=None,
        help="SimFin API-Key für historische Fundamentaldaten (kostenlos auf simfin.com)",
    )
    args = parser.parse_args()

    # Ticker-Auswahl nach Markt
    if args.tickers != DEFAULT_TICKERS:
        # explicit --tickers overrides --market; assume CH
        tickers: list[str] = args.tickers
        ticker_markets: dict[str, str] = {t: "ch" for t in tickers}
    else:
        ch = DEFAULT_TICKERS if args.market in ("ch", "all") else []
        eu = EU_TICKERS_ALL if args.market in ("eu", "all") else []
        us = US_TICKERS if args.market in ("us", "all") else []
        tickers = ch + eu + us
        ticker_markets = (
            {t: "ch" for t in ch}
            | {t: "eu" for t in eu}
            | {t: "us" for t in us}
        )

    years: int = args.years

    _logger.info(
        "Starte ML-Feature-Engineering: %d CH + %d EU + %d US Ticker, %d Jahre",
        sum(1 for v in ticker_markets.values() if v == "ch"),
        sum(1 for v in ticker_markets.values() if v == "eu"),
        sum(1 for v in ticker_markets.values() if v == "us"),
        years,
    )

    service = MLFeatureService()

    simfin_adapter = None
    if args.simfin_key:
        try:
            from backend.infrastructure.adapters.simfin_adapter import SimFinAdapter
            simfin_adapter = SimFinAdapter(api_key=args.simfin_key)
            _logger.info("SimFin aktiviert — historische Fundamentaldaten werden genutzt.")
        except ImportError:
            _logger.warning("simfin nicht installiert — `pip install simfin`. Fahre ohne fort.")

    df = service.build_dataset(
        tickers=tickers,
        years=years,
        simfin_adapter=simfin_adapter,
        ticker_markets=ticker_markets,
    )

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

    if args.tune:
        _logger.info("Starte Optuna-Tuning für LightGBM (%d Trials) …", 50)
        tuned_model = tune_lightgbm(x_train, y_train, x_val, y_val, n_trials=50)
        if tuned_model is not None:
            tuned_pred = tuned_model.predict(x_val)
            tuned_acc = accuracy(y_val, tuned_pred)
            tuned_top = top_quartile_accuracy(y_val, tuned_pred)
            _logger.info("Tuned LightGBM — Accuracy: %.3f | Top-Quartil-Recall: %.3f", tuned_acc, tuned_top)
            if tuned_top > lgb_top:
                best_model = tuned_model
                best_name = "lightgbm"
                best_acc = tuned_acc
                best_top = tuned_top
                _logger.info("Tuned Modell ist besser — wird als Best übernommen.")

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
        "tuned": args.tune,
        "market": args.market,
        "simfin_used": simfin_adapter is not None,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    _logger.info("Modell-Metadaten: %s", meta_path)

    # Auch als latest-Link speichern
    latest_path = MODELS_DIR / "return_predictor_latest.joblib"
    joblib.dump(best_model, latest_path)
    _logger.info("Latest-Link gespeichert: %s", latest_path)


if __name__ == "__main__":
    main()
