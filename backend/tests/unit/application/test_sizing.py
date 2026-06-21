"""Unit-Tests für sizing.py — Vol-Targeting + Drawdown-Brake.

Test-IDs:
  A7.5 — Monotonicity: höhere pred_vol → kleinerer size_factor
  A7.8 — SELL-Aktion → size_factor = 0.0 immer
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ── A7.5: Vol-Target Monotonizität ────────────────────────────────────────────


def test_vol_target_size_monotone() -> None:
    """A7.5 — höhere pred_vol → kleinerer size_factor (mind. 5 Wertpaare)."""
    from backend.application.signals.sizing import vol_target_size

    pred_vols = [0.10, 0.20, 0.40, 0.80, 1.20]
    sizes = [vol_target_size(v) for v in pred_vols]

    # Jeder Nachfolgewert muss kleiner oder gleich dem Vorgänger sein
    for i in range(len(sizes) - 1):
        assert sizes[i] >= sizes[i + 1], (
            f"Monotonizität verletzt bei pred_vol={pred_vols[i]} -> {sizes[i]:.4f} "
            f"vs pred_vol={pred_vols[i+1]} -> {sizes[i+1]:.4f}"
        )
    # Mindestens eine strikte Verringerung muss auftreten
    assert sizes[0] > sizes[-1], "Erster und letzter Wert müssen sich unterscheiden"


def test_vol_target_size_strictly_monotone_at_key_points() -> None:
    """Strikte Monotonizität: je doppelte Vol → halb so grosser Size."""
    from backend.application.signals.sizing import vol_target_size

    # target=0.60, pred_vol=0.30 → size = 0.60/0.30 = 2.0 (aber cap=1.5)
    # pred_vol=0.60 → size = 1.0
    # pred_vol=1.20 → size = 0.5
    s1 = vol_target_size(0.30, target_vol=0.60, cap=2.0)
    s2 = vol_target_size(0.60, target_vol=0.60, cap=2.0)
    s3 = vol_target_size(1.20, target_vol=0.60, cap=2.0)
    assert s1 > s2 > s3, f"Nicht strikt monoton: {s1}, {s2}, {s3}"


# ── Bounds-Tests ──────────────────────────────────────────────────────────────


def test_vol_target_size_bounds() -> None:
    """size_factor immer ∈ [0.0, cap] für pred_vol ∈ [0.05, 2.0]."""
    from backend.application.signals.sizing import vol_target_size

    import numpy as np

    cap = 1.5
    for pred_vol in np.linspace(0.05, 2.0, 40):
        size = vol_target_size(float(pred_vol), cap=cap)
        assert 0.0 <= size <= cap, (
            f"size={size:.4f} ausserhalb [0, {cap}] bei pred_vol={pred_vol:.4f}"
        )


def test_vol_target_size_low_vol_capped() -> None:
    """Sehr kleine pred_vol → size wird auf cap begrenzt (nicht über cap)."""
    from backend.application.signals.sizing import vol_target_size

    size = vol_target_size(0.001, target_vol=0.60, cap=1.5)
    assert size == pytest.approx(1.5, abs=1e-9), f"Erwartet 1.5 (cap), erhalten {size}"


def test_vol_target_size_zero_vol_capped() -> None:
    """pred_vol = 0.0 → Safety-Fallback: size = cap."""
    from backend.application.signals.sizing import vol_target_size

    size = vol_target_size(0.0, target_vol=0.60, cap=1.5)
    assert size == pytest.approx(1.5, abs=1e-9), f"Erwartet cap=1.5, erhalten {size}"


def test_vol_target_size_equal_vol_target() -> None:
    """pred_vol = target_vol → size = 1.0."""
    from backend.application.signals.sizing import vol_target_size

    size = vol_target_size(0.60, target_vol=0.60, cap=1.5)
    assert size == pytest.approx(1.0, abs=1e-9), f"Erwartet 1.0, erhalten {size}"


# ── A7.8: SELL-Aktion → 0.0 ──────────────────────────────────────────────────


def test_sell_action_zero_size() -> None:
    """A7.8 — SELL-Aktion → size_factor = 0.0 unabhängig von pred_vol."""
    from backend.application.signals.sizing import apply_sizing

    test_cases = [0.05, 0.10, 0.30, 0.60, 1.00, 1.50, 2.00]
    for pred_vol in test_cases:
        size = apply_sizing("SELL", pred_vol)
        assert size == 0.0, (
            f"SELL mit pred_vol={pred_vol} → size={size}, erwartet 0.0"
        )


def test_sell_action_never_negative() -> None:
    """SELL darf nie einen negativen size_factor produzieren (kein Short)."""
    from backend.application.signals.sizing import apply_sizing

    size = apply_sizing("SELL", 100.0)  # extreme pred_vol
    assert size >= 0.0, f"Negative Size: {size}"


# ── Drawdown-Brake Tests ──────────────────────────────────────────────────────


def test_drawdown_brake_halves_exposure() -> None:
    """current_dd=-0.25 mit threshold=-0.20 → Size wird halbiert."""
    from backend.application.signals.sizing import drawdown_brake

    original_size = 1.0
    result = drawdown_brake(original_size, current_dd=-0.25, threshold=-0.20)
    assert result == pytest.approx(0.5, abs=1e-9), (
        f"Drawdown-Brake: erwartet 0.5, erhalten {result}"
    )


def test_drawdown_brake_no_effect_above_threshold() -> None:
    """current_dd=-0.10 (über threshold=-0.20) → Size unverändert."""
    from backend.application.signals.sizing import drawdown_brake

    original_size = 1.2
    result = drawdown_brake(original_size, current_dd=-0.10, threshold=-0.20)
    assert result == pytest.approx(1.2, abs=1e-9), (
        f"Drawdown-Brake soll inaktiv sein: erwartet 1.2, erhalten {result}"
    )


def test_drawdown_brake_at_threshold_no_effect() -> None:
    """current_dd = threshold (Grenzfall) → kein Brake (< threshold triggert)."""
    from backend.application.signals.sizing import drawdown_brake

    original_size = 0.8
    result = drawdown_brake(original_size, current_dd=-0.20, threshold=-0.20)
    assert result == pytest.approx(0.8, abs=1e-9), (
        f"Brake bei exakt threshold: erwartet 0.8 (kein Brake), erhalten {result}"
    )


def test_drawdown_brake_large_drawdown() -> None:
    """Sehr starker Drawdown → Size immer noch >= 0."""
    from backend.application.signals.sizing import drawdown_brake

    result = drawdown_brake(1.5, current_dd=-0.80, threshold=-0.20)
    assert result >= 0.0, f"Negative Size nach Drawdown-Brake: {result}"
    assert result == pytest.approx(0.75, abs=1e-9)


# ── apply_sizing Integrations-Tests ──────────────────────────────────────────


def test_apply_sizing_buy_no_drawdown() -> None:
    """BUY ohne Drawdown → normale Vol-Target-Size."""
    from backend.application.signals.sizing import apply_sizing, vol_target_size

    expected = vol_target_size(0.60, target_vol=0.60, cap=1.5)
    result = apply_sizing("BUY", 0.60, current_dd=0.0)
    assert result == pytest.approx(expected, abs=1e-9)


def test_apply_sizing_hold_with_drawdown() -> None:
    """HOLD mit Drawdown → Vol-Target-Size halbiert."""
    from backend.application.signals.sizing import apply_sizing

    # pred_vol=0.60 → vol_target_size = 1.0, dann halbiert → 0.5
    result = apply_sizing("HOLD", 0.60, current_dd=-0.25, target_vol=0.60, cap=1.5)
    assert result == pytest.approx(0.5, abs=1e-9)


def test_apply_sizing_returns_float() -> None:
    """apply_sizing gibt immer einen float zurück."""
    from backend.application.signals.sizing import apply_sizing

    result = apply_sizing("BUY", 0.50)
    assert isinstance(result, float), f"Erwartet float, erhalten {type(result)}"
