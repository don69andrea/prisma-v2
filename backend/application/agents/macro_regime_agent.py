"""MacroRegimeAgent — NEW crypto-focused macro regime LLM agent (D-03).

§0 Iron Rule: LLM interprets tool data, NEVER invents numbers.
All numeric values from tool stubs (V4-4 replaces stubs with real FRED/DXY feeds).

This is a COMPLETELY NEW agent for crypto macro regime detection.
It is separate from the existing SMI macro agent in macro_agent.py.
Both agents coexist independently without any code sharing or imports.

Cache: 1h TTL (macro regime doesn't change intraday).
Model: claude-haiku-4-5-20251001 (fast, cheap — regime is stable).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend.domain.schemas.agent_schemas import MacroRegime
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

_MAX_TOKENS = 512
_CACHE_TTL_SECONDS = 3600  # 1 hour

# Module-level cache: stores (timestamp, MacroRegime) or None
_REGIME_CACHE: dict[str, tuple[float, MacroRegime]] = {}
_CACHE_KEY = "macro_regime"


# ---------------------------------------------------------------------------
# Tool stubs (V4-4 replaces with real API calls to FRED, DXY, Glassnode)
# ---------------------------------------------------------------------------


def get_us_realrate() -> dict[str, Any]:
    """Stub: US Federal Funds Rate - CPI (real rate).

    V4-4 replaces with FRED API: `FEDFUNDS` - `CPIAUCSL`.
    Returns normalized values for LLM context.
    """
    return {
        "ffr": 5.33,              # Federal Funds Rate %
        "cpi": 3.1,               # CPI YoY %
        "real_rate": 2.23,        # FFR - CPI
        "trend_90d": "falling",   # direction
    }


def get_dxy() -> dict[str, Any]:
    """Stub: US Dollar Index (DXY) — measures USD strength vs. basket.

    V4-4 replaces with live market data feed.
    """
    return {
        "index": 104.2,
        "trend_30d": "weakening",  # or "strengthening", "stable"
        "change_pct_30d": -1.8,
    }


def get_btc_risk_correlation() -> dict[str, Any]:
    """Stub: BTC-SPY 30-day rolling correlation.

    V4-4 replaces with live returns data.
    corr_spy_30d > 0.7 → risk-off dominates (correlated sell-off risk)
    corr_spy_30d < 0.3 → BTC decoupled → potentially risk-on for crypto
    """
    return {
        "corr_spy_30d": 0.42,
        "risk_on_regime": True,   # True if BTC shows crypto-specific upside
        "computed_at": "2026-06-21",
    }


def get_fear_greed() -> dict[str, Any]:
    """Stub: Crypto Fear & Greed Index from alternative.me.

    V4-4 replaces with live API call.
    """
    return {
        "value": 62,
        "classification": "Greed",
        "trend_7d": "rising",
    }


class MacroRegimeAgent:
    """Crypto-focused macro regime agent with 1h TTL cache.

    Constructor injection: LLMClient + PromptTemplateLoader.
    Uses Haiku model — fast and cheap; regime changes slowly.
    Falls back to NEUTRAL on any Exception (no 500s).
    Cache is module-level (shared within process) with 1h TTL.

    NOTE: This is a NEW agent, completely separate from the SMI macro agent
    in macro_agent.py. Do NOT import or modify the existing SMI macro agent.
    """

    _MODEL = "claude-haiku-4-5-20251001"

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_loader: PromptTemplateLoader,
    ) -> None:
        self._llm = llm_client
        self._prompts = prompt_loader

    async def get_regime(self) -> MacroRegime:
        """Return current macro regime, cached for 1h TTL.

        Returns:
            MacroRegime — always, even on LLM failure (deterministic fallback).
        """
        # Check cache
        now = time.monotonic()
        cached = _REGIME_CACHE.get(_CACHE_KEY)
        if cached is not None:
            cached_time, cached_regime = cached
            if now - cached_time < _CACHE_TTL_SECONDS:
                _logger.debug("MacroRegimeAgent cache hit (age=%.1fs)", now - cached_time)
                return cached_regime

        # Cache miss — call LLM
        regime = await self._fetch_regime()

        # Store in cache
        _REGIME_CACHE[_CACHE_KEY] = (now, regime)
        return regime

    async def _fetch_regime(self) -> MacroRegime:
        """Fetch regime from LLM using tool data. Falls back on any Exception."""
        # Collect tool data
        realrate = get_us_realrate()
        dxy = get_dxy()
        btc_corr = get_btc_risk_correlation()
        fear_greed = get_fear_greed()

        system_prompt = self._prompts.render(
            "macro_regime.de.md.j2",
            {
                "realrate": realrate,
                "dxy": dxy,
                "btc_corr": btc_corr,
                "fear_greed": fear_greed,
            },
        )
        user_prompt = (
            "Bestimme das aktuelle Makro-Regime basierend auf den Tool-Daten im System-Prompt. "
            "Antworte als JSON."
        )

        try:
            response = await self._llm.messages_create(
                model=self._MODEL,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=_MAX_TOKENS,
                feature="macro_regime",
                system=system_prompt,
            )
            raw_text: str = response.content[0].text
            data = json.loads(raw_text)
            return MacroRegime.model_validate(data)
        except Exception as exc:
            _logger.error("MacroRegimeAgent LLM/validation failed: %s", exc)
            return self._fallback()

    @staticmethod
    def _fallback() -> MacroRegime:
        """Deterministic fallback — NEUTRAL regime with lowered confidence."""
        return MacroRegime(
            regime="NEUTRAL",
            drivers=["Fallback: LLM-Analyse nicht verfügbar"],
            confidence=0.4,  # lowered — fallback path
            reasoning=(
                "Fallback-Regime: LLM-Analyse konnte nicht ausgeführt werden. "
                "NEUTRAL als sichere Standardannahme gewählt."
            ),
        )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear module-level regime cache. Used for testing."""
        _REGIME_CACHE.clear()
