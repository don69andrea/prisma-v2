"""Layer 3 Sizing: Vol-Targeting + Drawdown-Brake.

Implementiert:
  vol_target_size(pred_vol, target_vol, cap) → float ∈ [0, cap]
  drawdown_brake(size, current_dd, threshold) → float
  apply_sizing(action, pred_vol, current_dd, target_vol, cap) → float

Design:
- SELL-Aktion → immer 0.0, nie negativ (kein Short-Exposure)
- vol_target_size: target_vol / pred_vol, gecappt auf [0, cap]
- drawdown_brake: halbiert die Size wenn current_dd < threshold
- Keine I/O-Operationen — rein funktional
"""

from __future__ import annotations

__all__ = ["vol_target_size", "drawdown_brake", "apply_sizing"]


def vol_target_size(
    pred_vol: float,
    target_vol: float = 0.60,
    cap: float = 1.5,
) -> float:
    """Berechne den Vol-Targeting Size-Factor.

    Formel: size = target_vol / max(pred_vol, ε), gecappt auf [0, cap].

    Parameters
    ----------
    pred_vol:
        Vorhergesagte annualisierte Volatilität (z. B. 0.60 = 60 % p.a.).
        Werte ≤ 0 werden auf ε=1e-8 gesetzt (Safety-Fallback → cap).
    target_vol:
        Ziel-Volatilität des Portfolios (Standard: 60 % p.a.).
    cap:
        Maximaler Size-Factor (Standard: 1.5 — 150 % Exposure).

    Returns
    -------
    float
        Size-Factor ∈ [0.0, cap].
    """
    safe_vol = max(pred_vol, 1e-8)
    raw_size = target_vol / safe_vol
    return float(min(max(raw_size, 0.0), cap))


def drawdown_brake(
    size: float,
    current_dd: float,
    threshold: float = -0.20,
) -> float:
    """Halbiere die Exposure bei starkem Drawdown.

    Parameters
    ----------
    size:
        Aktueller Size-Factor (Ausgang von vol_target_size oder apply_sizing).
    current_dd:
        Aktueller Drawdown als negativer float (z. B. -0.25 = -25 %).
    threshold:
        Drawdown-Schwelle. Brake feuert wenn current_dd < threshold (Standard: -0.20).

    Returns
    -------
    float
        Reduzierter Size-Factor (Halbierung) oder unveränderter Size-Factor.
    """
    if current_dd < threshold:
        return size * 0.5
    return size


def apply_sizing(
    action: str,
    pred_vol: float,
    current_dd: float = 0.0,
    target_vol: float = 0.60,
    cap: float = 1.5,
) -> float:
    """Vollständige Sizing-Pipeline inkl. Action-Filter.

    Parameters
    ----------
    action:
        Trading-Aktion: "BUY", "HOLD" oder "SELL".
        Bei "SELL" wird immer 0.0 zurückgegeben (kein Short, kein negatives Exposure).
    pred_vol:
        Vorhergesagte annualisierte Volatilität.
    current_dd:
        Aktueller Drawdown als negativer float.
    target_vol:
        Ziel-Volatilität des Portfolios.
    cap:
        Maximaler Size-Factor.

    Returns
    -------
    float
        Size-Factor ∈ [0.0, cap]. SELL → immer 0.0.
    """
    if action == "SELL":
        return 0.0

    size = vol_target_size(pred_vol, target_vol=target_vol, cap=cap)
    return drawdown_brake(size, current_dd=current_dd, threshold=-0.20)
