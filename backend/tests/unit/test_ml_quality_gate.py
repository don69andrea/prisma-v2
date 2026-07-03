"""Unit-Tests: Hartes ML-Quality-Gate (Audit-Befund W2-C-02).

Prüft die reinen Gate-Entscheidungsfunktionen beider Trainings-Scripts OHNE
echtes Training, Modell oder Netzwerk. Metriken unter der Baseline müssen vom
Gate abgelehnt, Metriken über der Baseline akzeptiert werden.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit


def _import_return_gate() -> tuple[Callable[..., Any], float, float]:
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.train_return_predictor import (
        GATE_MIN_MARGIN,
        RANDOM_TOP_QUARTILE_RECALL,
        _passes_quality_gate,
    )

    return _passes_quality_gate, RANDOM_TOP_QUARTILE_RECALL, GATE_MIN_MARGIN


def _import_quantile_gate() -> Callable[..., Any]:
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.train_quantile_model import _passes_quality_gate

    return _passes_quality_gate


# ---------------------------------------------------------------------------
# Return-Predictor: Top-Quartil-Recall gegen Zufalls-Baseline (0.25) + Champion
# ---------------------------------------------------------------------------


class TestReturnPredictorGate:
    def test_below_random_baseline_rejected(self):
        """Der aktuelle Champion (0.4223) liegt unter Zufall+Marge → abgelehnt."""
        gate, baseline, margin = _import_return_gate()
        # 0.4223 val_accuracy — aber Top-Quartil-Recall knapp über Baseline?
        # Explizit: ein Recall unter Baseline+Marge muss durchfallen.
        assert gate(0.20) is False
        assert gate(baseline) is False  # exakt Baseline reicht nicht
        assert gate(baseline + margin - 0.001) is False

    def test_above_baseline_accepted(self):
        gate, baseline, margin = _import_return_gate()
        assert gate(baseline + margin) is True
        assert gate(0.55) is True

    def test_must_beat_current_champion(self):
        gate, _baseline, _margin = _import_return_gate()
        # Über Baseline, aber nicht besser als Champion → abgelehnt.
        assert gate(0.50, champion_recall=0.50) is False
        assert gate(0.49, champion_recall=0.50) is False
        # Schlägt Champion → akzeptiert.
        assert gate(0.51, champion_recall=0.50) is True

    def test_no_champion_falls_back_to_baseline(self):
        gate, baseline, margin = _import_return_gate()
        assert gate(baseline + margin, champion_recall=None) is True
        assert gate(0.10, champion_recall=None) is False

    def test_weak_champion_still_needs_baseline(self):
        """Auch wenn der Champion schwach ist, muss die Baseline geschlagen werden."""
        gate, baseline, _margin = _import_return_gate()
        # Unter Baseline, aber besser als ein noch schlechterer Champion → trotzdem abgelehnt.
        assert gate(0.20, champion_recall=0.10) is False


# ---------------------------------------------------------------------------
# Quantil-Modell: Pinball-Loss aller Quantile gegen konstante Baseline
# ---------------------------------------------------------------------------


class TestQuantileGate:
    def test_all_quantiles_beat_baseline_accepted(self):
        gate = _import_quantile_gate()
        cv = {"q10": [0.010, 0.012], "q50": [0.020, 0.021], "q90": [0.011, 0.013]}
        bl = {"q10": [0.015, 0.016], "q50": [0.030, 0.031], "q90": [0.018, 0.019]}
        assert gate(cv, bl) is True

    def test_one_quantile_worse_rejected(self):
        gate = _import_quantile_gate()
        cv = {"q10": [0.010], "q50": [0.040], "q90": [0.011]}  # q50 schlechter
        bl = {"q10": [0.015], "q50": [0.030], "q90": [0.018]}
        assert gate(cv, bl) is False

    def test_equal_loss_rejected(self):
        gate = _import_quantile_gate()
        cv = {"q10": [0.015], "q50": [0.030], "q90": [0.018]}
        bl = {"q10": [0.015], "q50": [0.030], "q90": [0.018]}
        assert gate(cv, bl) is False

    def test_empty_folds_rejected(self):
        gate = _import_quantile_gate()
        assert gate({}, {}) is False
        assert gate({"q10": []}, {"q10": []}) is False

    def test_min_margin_enforced(self):
        gate = _import_quantile_gate()
        # Modell nur minimal besser (1 %) — bei 5 % Marge abgelehnt.
        cv = {"q10": [0.0099], "q50": [0.0099], "q90": [0.0099]}
        bl = {"q10": [0.0100], "q50": [0.0100], "q90": [0.0100]}
        assert gate(cv, bl, min_margin=0.05) is False
        # Ohne Marge (nur strikt besser) akzeptiert.
        assert gate(cv, bl, min_margin=0.0) is True
