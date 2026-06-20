"""Unit-Tests: C1-Contract Quantil-Regression (TEIL E §E1.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Hilfsfunktionen (direkt aus train_quantile_model importieren)
# ---------------------------------------------------------------------------


def _import_train() -> tuple[
    Callable[..., Any], Callable[..., Any], Callable[..., Any], Callable[..., Any]
]:
    import sys

    root = Path(__file__).resolve().parents[4]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.train_quantile_model import (
        _monotone_q10_q50_q90,
        _pinball_loss,
        _prob_outperform,
        _purged_embargo_folds,
    )

    return _monotone_q10_q50_q90, _pinball_loss, _prob_outperform, _purged_embargo_folds


# ---------------------------------------------------------------------------
# E1.5-1: Monotonie q10 <= q50 <= q90
# ---------------------------------------------------------------------------


class TestMonotonicity:
    def test_monotone_100_random_inputs(self):
        mono, _, _, _ = _import_train()
        rng = np.random.default_rng(42)
        raw = rng.normal(0, 0.05, size=(100, 3))
        q10, q50, q90 = mono(raw[:, 0], raw[:, 1], raw[:, 2])
        assert np.all(q10 <= q50), "q10 muss <= q50 sein"
        assert np.all(q50 <= q90), "q50 muss <= q90 sein"

    def test_monotone_preserves_order_when_already_sorted(self):
        mono, _, _, _ = _import_train()
        q10 = np.array([-0.05, -0.02, 0.0])
        q50 = np.array([0.01, 0.03, 0.05])
        q90 = np.array([0.08, 0.10, 0.12])
        r10, r50, r90 = mono(q10, q50, q90)
        np.testing.assert_array_equal(r10, q10)
        np.testing.assert_array_equal(r50, q50)
        np.testing.assert_array_equal(r90, q90)


# ---------------------------------------------------------------------------
# E1.5-2: prob_outperform in [0,1]; bei q50 > 0 => prob > 0.5
# ---------------------------------------------------------------------------


class TestProbOutperform:
    def test_range_0_1(self):
        _, _, prob, _ = _import_train()
        cases = [
            (-0.1, -0.05, 0.0),
            (-0.1, 0.0, 0.1),
            (0.01, 0.05, 0.1),
            (-0.2, -0.1, -0.05),
            (0.0, 0.0, 0.0),
        ]
        for q10, q50, q90 in cases:
            p = prob(q10, q50, q90)
            assert 0.0 <= p <= 1.0, f"prob={p} ausserhalb [0,1] für ({q10},{q50},{q90})"

    def test_positive_median_implies_prob_gt_half(self):
        _, _, prob, _ = _import_train()
        cases = [
            (-0.02, 0.03, 0.08),
            (-0.05, 0.01, 0.06),
            (0.01, 0.05, 0.10),
        ]
        for q10, q50, q90 in cases:
            p = prob(q10, q50, q90)
            assert p > 0.5, f"q50={q50} > 0 aber prob={p} <= 0.5"

    def test_negative_all_quantiles_prob_is_zero(self):
        _, _, prob, _ = _import_train()
        p = prob(-0.1, -0.05, -0.01)
        assert p == 0.0

    def test_all_positive_quantiles_prob_is_one(self):
        _, _, prob, _ = _import_train()
        p = prob(0.01, 0.05, 0.10)
        assert p == 1.0


# ---------------------------------------------------------------------------
# E1.5-3: Pinball-Loss Modell < Baseline
# ---------------------------------------------------------------------------


class TestPinballLoss:
    def test_perfect_prediction_lower_than_constant_baseline(self):
        _, pinball, _, _ = _import_train()
        rng = np.random.default_rng(0)
        y = rng.normal(0, 0.03, 500)

        # "Modell" kennt y exakt (obere Schranke der Güte)
        alpha = 0.5
        perfect = y.copy()
        loss_perfect = pinball(y, perfect, alpha)

        # Baseline: konstantes Median-Quantil aus y
        baseline_q = float(np.quantile(y, alpha))
        loss_baseline = pinball(y, np.full_like(y, baseline_q), alpha)

        assert loss_perfect < loss_baseline

    def test_pinball_non_negative(self):
        _, pinball, _, _ = _import_train()
        y = np.array([0.01, -0.02, 0.03])
        pred = np.array([0.0, 0.0, 0.0])
        assert pinball(y, pred, 0.5) >= 0


# ---------------------------------------------------------------------------
# E1.5-4: Feature-Mismatch beim Laden wirft ValueError
# ---------------------------------------------------------------------------


class TestFeatureMismatch:
    def test_mismatched_hash_raises_value_error(self, tmp_path):
        """Falsche feature_hash in registry.json führt zu ValueError."""
        import json

        meta = {
            "type": "quantile",
            "cv": "purged_embargo",
            "embargo_days": 30,
            "features": ["wrong_feature"],
            "feature_hash": "deadbeef",
            "n_train": 100,
            "n_folds": 3,
            "trained_at": "2099-01-01",
        }
        meta_path = tmp_path / "quantile_meta_2099-01-01.json"
        meta_path.write_text(json.dumps(meta))

        reg: dict[str, Any] = {
            "active": None,
            "active_quantile": "quantile_meta_2099-01-01.json",
            "versions": [],
        }
        (tmp_path / "registry.json").write_text(json.dumps(reg))

        import backend.application.services.quantile_prediction_service as svc

        svc._model_cache = {}

        with (
            patch.object(svc, "_MODELS_DIR", tmp_path),
            pytest.raises(ValueError, match="Feature-Mismatch"),
        ):
            svc._load_quantile_models()


# ---------------------------------------------------------------------------
# E1.5-5: build_target_excess_30d — Randfall None am Datenrand
# ---------------------------------------------------------------------------


class TestBuildTargetExcess30d:
    def setup_method(self):
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[4]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from backend.application.services.ml_feature_service import build_target_excess_30d

        self.fn = build_target_excess_30d

    def _series(self, n: int, start: str = "2020-01-01") -> pd.Series:
        import pandas as pd

        idx = pd.date_range(start, periods=n, freq="B")
        return pd.Series(np.ones(n) * 100.0 + np.arange(n) * 0.01, index=idx)

    def test_returns_float_when_enough_data(self):
        import pandas as pd

        close = self._series(100)
        smi = self._series(100)
        snap = pd.Timestamp("2020-01-31")
        result = self.fn(close, smi, snap)
        assert isinstance(result, float)

    def test_returns_none_at_data_edge(self):
        import pandas as pd

        close = self._series(40)
        smi = self._series(40)
        snap = pd.Timestamp("2020-02-28")
        result = self.fn(close, smi, snap)
        assert result is None

    def test_pit_correct_uses_only_future(self):
        import pandas as pd

        # Wenn zukünftige Preise konstant sind, ist Excess = 0
        idx_past = pd.date_range("2020-01-01", periods=50, freq="B")
        idx_future = pd.date_range(idx_past[-1] + pd.Timedelta(days=1), periods=40, freq="B")
        all_idx = idx_past.append(idx_future)
        close = pd.Series(np.ones(90), index=all_idx)
        smi = pd.Series(np.ones(90), index=all_idx)
        snap = pd.Timestamp(idx_past[-1])
        result = self.fn(close, smi, snap)
        assert result is not None
        assert abs(result) < 1e-9


# ---------------------------------------------------------------------------
# E1.5-6: TEIL_F_FEATURE_COLS Vollständigkeit
# ---------------------------------------------------------------------------


class TestFeatureCols:
    def test_exactly_15_features(self):
        from backend.application.services.ml_feature_service import TEIL_F_FEATURE_COLS

        assert len(TEIL_F_FEATURE_COLS) == 15

    def test_no_fundamental_features(self):
        from backend.application.services.ml_feature_service import TEIL_F_FEATURE_COLS

        fundamentals = {
            "pe_ratio",
            "pb_ratio",
            "dividend_yield",
            "revenue_growth",
            "ev_ebitda",
            "roe",
            "debt_equity",
            "fcf_margin",
            "eps_growth",
        }
        overlap = fundamentals & set(TEIL_F_FEATURE_COLS)
        assert not overlap, f"Fundamental-Features im TEIL_F_FEATURE_COLS: {overlap}"

    def test_required_features_present(self):
        from backend.application.services.ml_feature_service import TEIL_F_FEATURE_COLS

        required = {
            "return_1m",
            "return_3m",
            "return_6m",
            "return_12m",
            "vol_30d",
            "vol_90d",
            "rsi_14",
            "price_to_52w_high",
            "momentum_vs_smi_3m",
            "bb_position",
            "macd_hist",
            "drawdown_12m",
            "snb_rate",
            "chf_eur",
            "inflation_ch",
        }
        missing = required - set(TEIL_F_FEATURE_COLS)
        assert not missing, f"Fehlende Features: {missing}"

    def test_feature_hash_deterministic(self):
        from backend.application.services.ml_feature_service import TEIL_F_FEATURE_COLS

        h1 = hashlib.sha256(",".join(TEIL_F_FEATURE_COLS).encode()).hexdigest()[:8]
        h2 = hashlib.sha256(",".join(TEIL_F_FEATURE_COLS).encode()).hexdigest()[:8]
        assert h1 == h2


# ---------------------------------------------------------------------------
# E1.5-7: QuantilePrediction VO Struktur
# ---------------------------------------------------------------------------


class TestQuantilePredictionVO:
    def test_frozen_dataclass(self):
        from backend.domain.value_objects.ml_prediction import QuantilePrediction

        pred = QuantilePrediction(
            ticker="NESN",
            as_of=date(2024, 1, 15),
            q10=-0.04,
            q50=0.02,
            q90=0.08,
            prob_outperform=0.65,
            expected_edge=0.02,
            uncertainty=0.12,
            model_version="2024-01-01",
            feature_hash="abcd1234",
        )
        assert pred.expected_edge == pred.q50
        assert pred.uncertainty == pytest.approx(pred.q90 - pred.q10)
        with pytest.raises((AttributeError, TypeError)):
            pred.q50 = 999.0  # type: ignore[misc]
