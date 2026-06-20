"""CryptoScorer — technisch-sentimentaler Score für Kryptowährungen (0–100)."""

from __future__ import annotations

import pandas as pd

from backend.domain.entities.crypto_asset import CryptoAsset


class CryptoScorer:
    """Bewertet Kryptowährungen auf einer Skala von 0–100.

    Signal-Schwellen:
      STRONG_BUY  >= 75
      BUY         >= 60
      HOLD        >= 40
      SELL        >= 25
      STRONG_SELL  < 25
    """

    STRONG_BUY_THRESHOLD = 75
    BUY_THRESHOLD = 60
    HOLD_THRESHOLD = 40
    SELL_THRESHOLD = 25

    def score(
        self,
        asset: CryptoAsset,
        technicals: pd.DataFrame,
        fear_greed: int,
        correlation_smi_1y: float = 0.0,
        pattern_modifier: float | None = None,
    ) -> tuple[float, dict[str, float]]:
        """Berechnet den Gesamtscore und gibt (score, components) zurück.

        `pattern_modifier` (optional, -7.5..+7.5) kommt aus CryptoPatternService
        und wird additiv auf die Summe der 5 Kern-Dimensionen angewendet, bevor
        auf [0, 100] geclampt wird. Bewusst kein 6. hartes Dimension-Cap, damit
        die bestehenden Signal-Schwellen (75/60/40/25) unverändert gültig bleiben.
        """
        components: dict[str, float] = {}

        # ── 1. MOMENTUM (max 30 Pt) ──────────────────────────────
        rsi = float(technicals["RSI_14"].iloc[-1])
        rsi_score = self._rsi_score(rsi)

        macd_val = float(technicals["MACD_12_26_9"].iloc[-1])
        macd_sig = float(technicals["MACDs_12_26_9"].iloc[-1])
        macd_score = 5.0 if macd_val > macd_sig else 0.0

        mom_7d = asset.price_change_7d_pct or 0.0
        momentum_score = self._momentum_score(mom_7d)

        components["momentum"] = rsi_score + macd_score + momentum_score

        # ── 2. TREND (max 25 Pt) ─────────────────────────────────
        close = technicals["Close"]
        last_close = float(close.iloc[-1])
        ema20 = float(technicals["EMA_20"].iloc[-1])
        ema50 = float(technicals["EMA_50"].iloc[-1])
        ema200 = float(close.ewm(span=200).mean().iloc[-1])

        trend_score = 0.0
        if last_close > ema20:
            trend_score += 5.0
        if last_close > ema50:
            trend_score += 7.0
        if last_close > ema200:
            trend_score += 8.0
        if ema20 > ema50:
            trend_score += 5.0

        bb_upper = float(technicals["BBU_20_2.0"].iloc[-1])
        bb_lower = float(technicals["BBL_20_2.0"].iloc[-1])
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_position = (last_close - bb_lower) / bb_range
            trend_score = min(25.0, trend_score + round(bb_position * 5))

        components["trend"] = min(25.0, trend_score)

        # ── 3. SENTIMENT (max 20 Pt) ─────────────────────────────
        fg_score = self._fear_greed_score(fear_greed)
        vol_trend = self._volume_trend_score(technicals)
        components["sentiment"] = fg_score + vol_trend

        # ── 4. MARKT (max 15 Pt) ─────────────────────────────────
        rank = asset.market_cap_rank or 50
        rank_score = float(max(0, 10 - max(0, rank - 10) // 5))
        ath_pct = abs(asset.ath_change_pct or -50.0)
        ath_score = max(0.0, 5 - int(ath_pct // 20))
        components["markt"] = rank_score + ath_score

        # ── 5. RISIKO (max 10 Pt) ────────────────────────────────
        returns = close.pct_change().dropna()
        vol_30d = float(returns.rolling(30).std().iloc[-1] * (365**0.5) * 100)
        vol_score = float(max(0.0, 5.0 - int(vol_30d // 20)))

        # Niedrige Korrelation zum SMI = Diversifikationsbonus (0–5 Pt)
        corr_abs = abs(correlation_smi_1y)
        corr_score = float(max(0.0, 5.0 * (1.0 - corr_abs)))
        components["risiko"] = vol_score + round(corr_score, 1)

        if pattern_modifier is not None:
            components["pattern"] = round(pattern_modifier, 1)

        total = float(sum(components.values()))
        return min(100.0, max(0.0, total)), components

    def _rsi_score(self, rsi: float) -> float:
        """RSI: Oversold (< 30) = 10 Pt, Overbought (> 70) = 0 Pt."""
        if rsi < 30:
            return 10.0
        if rsi < 45:
            return 8.0
        if rsi < 55:
            return 5.0
        if rsi < 70:
            return 3.0
        return 0.0

    def _fear_greed_score(self, fg: int) -> float:
        """Contrarian: Extreme Fear (Einstiegsgelegenheit) = höchster Score."""
        if fg <= 25:
            return 12.0
        if fg <= 40:
            return 9.0
        if fg <= 60:
            return 6.0
        if fg <= 75:
            return 3.0
        return 0.0

    def _momentum_score(self, change_7d_pct: float) -> float:
        """7-Tage-Preismomentum (0–15 Pt)."""
        if change_7d_pct > 20:
            return 15.0
        if change_7d_pct > 10:
            return 12.0
        if change_7d_pct > 5:
            return 9.0
        if change_7d_pct > 0:
            return 6.0
        if change_7d_pct > -5:
            return 3.0
        return 0.0

    def _volume_trend_score(self, technicals: pd.DataFrame) -> float:
        """Volumen-Trend: Steigendes Volumen bei steigendem Preis = 8 Pt."""
        if "Volume" not in technicals.columns or len(technicals) < 14:
            return 4.0
        close = technicals["Close"]
        volume = technicals["Volume"]
        vol_recent = float(volume.iloc[-7:].mean())
        vol_prior = float(volume.iloc[-14:-7].mean())
        price_up = float(close.iloc[-1]) > float(close.iloc[-7])
        vol_up = vol_recent > vol_prior * 1.05
        if vol_up and price_up:
            return 8.0
        if not vol_up and not price_up:
            return 2.0
        return 4.0


def generate_signal_reason(
    signal: str,
    asset_name: str,
    score: float,
    rsi: float,
    fear_greed: int,
    change_7d: float,
) -> str:
    """Generiert einen 1-Satz deutschen Signalgrund ohne LLM."""
    fg_text = (
        "Extreme Angst am Markt"
        if fear_greed < 25
        else "Angststimmung"
        if fear_greed < 40
        else "neutrale Stimmung"
        if fear_greed < 60
        else "Gier am Markt"
    )

    if signal in ("STRONG_BUY", "BUY"):
        if rsi < 35:
            return f"{asset_name} ist technisch überverkauft (RSI {rsi:.0f}) — historisch ein Einstiegssignal."
        if fear_greed < 30:
            return f"Extreme Angst am Markt schafft Einstiegsgelegenheit für {asset_name}."
        return f"{asset_name} zeigt starkes 7-Tage-Momentum (+{change_7d:.1f}%) bei Score {score:.0f}/100."

    if signal == "HOLD":
        return f"{asset_name} in neutralem Bereich (Score {score:.0f}/100) — {fg_text}, kein klarer Trigger."

    if rsi > 70:
        return f"{asset_name} ist technisch überkauft (RSI {rsi:.0f}) — Vorsicht bei neuem Kapital."
    return f"{asset_name} zeigt schwaches Momentum bei {fg_text} — Rücksetzer möglich."
