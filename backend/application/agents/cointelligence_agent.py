"""CointelligenceAgent — On-Chain Intelligence für BTC/ETH via Claude Tool-Use."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from backend.domain.schemas.multiagent_schemas import CointelligenceReport

_logger = logging.getLogger(__name__)
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024
_MAX_ITERATIONS = 6
_DISCLAIMER = (
    "Kryptowährungen sind hochspekulative Anlagen mit erheblichem Verlustrisiko. "
    "Diese Analyse ist keine Anlageberatung. Nie mehr als 5–10% des freien Vermögens."
)

_COIN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_coin_data",
        "description": "Aktueller Preis (USD + CHF), Market Cap, 24h-Veränderung für BTC oder ETH.",
        "input_schema": {
            "type": "object",
            "properties": {"coin": {"type": "string", "enum": ["bitcoin", "ethereum"]}},
            "required": ["coin"],
        },
    },
    {
        "name": "get_mvrv_z_score",
        "description": "Bitcoin MVRV-Z-Score. Nur für BTC.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fear_greed_index",
        "description": "Crypto Fear & Greed Index (0=extreme Angst, 100=extreme Gier).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_sharpe_comparison",
        "description": "Vergleicht Sharpe Ratio von BTC oder ETH vs. SMI über 365 Tage.",
        "input_schema": {
            "type": "object",
            "properties": {"coin": {"type": "string", "enum": ["BTC-USD", "ETH-USD"]}},
            "required": ["coin"],
        },
    },
    {
        "name": "get_chf_usd_rate",
        "description": "Aktueller CHF/USD-Kurs.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

_SYSTEM = """Du bist ein nüchterner Krypto-Analyst für Schweizer Privatanleger (freie Mittel, NICHT 3a).
Nutze alle verfügbaren Tools um ein vollständiges Bild zu bekommen.

Antworte NUR mit JSON (kein Markdown):
{
  "price_chf": float,
  "mvrv_zone": "UNDERBOUGHT|FAIR|EXPENSIVE|EXTREME|UNKNOWN",
  "fear_greed": int,
  "sharpe_crypto": float,
  "sharpe_smi": float,
  "chf_usd_impact": "GÜNSTIG|NEUTRAL|UNGÜNSTIG",
  "regime_signal": "ACCUMULATE|HOLD|CAUTION|AVOID",
  "max_allocation_pct": float,
  "reasoning": "max 3 Sätze",
  "disclaimer": "Kryptowährungen sind hochspekulative Anlagen..."
}

Regeln: max_allocation_pct NIEMALS über 10. Bei MVRV > 5 oder Fear&Greed > 80: CAUTION oder AVOID."""


class CointelligenceAgent:
    def __init__(
        self,
        coingecko: Any,
        fear_greed: Any,
        macro_service: Any,
        llm_client: Any,
        glassnode_api_key: str = "",
    ) -> None:
        self._cg = coingecko
        self._fg = fear_greed
        self._macro = macro_service
        self._llm = llm_client
        self._glassnode_key = glassnode_api_key

    async def analyze(self, coin: Literal["BTC", "ETH"]) -> CointelligenceReport:
        coingecko_id = "bitcoin" if coin == "BTC" else "ethereum"
        yf_ticker = "BTC-USD" if coin == "BTC" else "ETH-USD"

        tool_cache = await self._prefetch(coingecko_id, yf_ticker, coin)

        messages: list[dict[str, Any]] = [{
            "role": "user",
            "content": (
                f"Analysiere {coin} für einen Schweizer Privatanleger (freie Mittel, nicht 3a). "
                "Nutze alle Tools für ein vollständiges Bild."
            ),
        }]

        try:
            for _ in range(_MAX_ITERATIONS):
                response = await self._llm.messages_create(
                    model=_MODEL,
                    system=_SYSTEM,
                    messages=messages,
                    tools=_COIN_TOOLS,
                    max_tokens=_MAX_TOKENS,
                    feature="cointelligence",
                )

                if response.stop_reason == "end_turn":
                    text_block = next(
                        (b for b in response.content if getattr(b, "type", None) == "text"), None
                    )
                    if text_block:
                        return self._parse(coin, text_block.text, tool_cache)
                    break

                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        result = tool_cache.get(block.name, {"error": "Tool nicht gefunden"})
                        if block.name == "get_coin_data":
                            result = tool_cache.get(
                                f"get_coin_data_{block.input.get('coin', 'bitcoin')}", result
                            )
                        elif block.name == "get_sharpe_comparison":
                            result = tool_cache.get(
                                f"get_sharpe_{block.input.get('coin', 'BTC-USD')}", result
                            )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            _logger.error("CointelligenceAgent fehlgeschlagen: %s", exc)

        return self._fallback(coin, tool_cache)

    async def _prefetch(self, coingecko_id: str, yf_ticker: str, coin: str) -> dict[str, Any]:
        cache: dict[str, Any] = {}

        try:
            ctx = await self._macro.get_context()
            chf_usd = round(ctx.chf_eur / 1.08, 4)
        except Exception:
            chf_usd = 0.89

        try:
            market = await self._cg.get_market_data([coingecko_id])
            if market:
                d = market[0]
                price_usd = float(d.get("current_price", 0))
                price_chf = round(price_usd * chf_usd, 2)
                coin_data = {
                    "coin": coingecko_id,
                    "price_usd": price_usd,
                    "price_chf": price_chf,
                    "market_cap_usd": d.get("market_cap", 0),
                    "price_change_24h_pct": d.get("price_change_percentage_24h_in_currency", 0),
                }
                cache[f"get_coin_data_{coingecko_id}"] = coin_data
                cache["get_coin_data"] = coin_data
        except Exception as exc:
            _logger.warning("CoinGecko prefetch fehlgeschlagen: %s", exc)

        try:
            fg = await self._fg.get()
            cache["get_fear_greed_index"] = {"value": fg["value"], "label": fg["label"]}
        except Exception:
            cache["get_fear_greed_index"] = {"value": 50, "label": "Neutral"}

        cache["get_chf_usd_rate"] = {"chf_usd": chf_usd}

        if coin == "BTC" and self._glassnode_key:
            try:
                cache["get_mvrv_z_score"] = await self._fetch_mvrv()
            except Exception:
                cache["get_mvrv_z_score"] = {"mvrv_z": None, "zone": "UNKNOWN"}
        else:
            cache["get_mvrv_z_score"] = {"mvrv_z": None, "zone": "UNKNOWN", "note": "Kein Key"}

        try:
            sharpe = await asyncio.to_thread(self._calc_sharpe_sync, yf_ticker)
            cache[f"get_sharpe_{yf_ticker}"] = sharpe
            cache["get_sharpe_comparison"] = sharpe
        except Exception:
            cache["get_sharpe_comparison"] = {"crypto_sharpe": 0.0, "smi_sharpe": 0.0}

        return cache

    async def _fetch_mvrv(self) -> dict[str, Any]:
        url = "https://api.glassnode.com/v1/metrics/market/mvrv_z_score"
        params = {"a": "BTC", "api_key": self._glassnode_key, "i": "24h", "f": "JSON"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            if r.status_code == 200:
                data = r.json()
                latest = data[-1]["v"] if data else None
                zone = (
                    "EXTREME" if latest and latest > 7
                    else "EXPENSIVE" if latest and latest > 3
                    else "FAIR" if latest and latest > 0
                    else "UNDERBOUGHT" if latest is not None
                    else "UNKNOWN"
                )
                return {"mvrv_z": latest, "zone": zone}
        return {"mvrv_z": None, "zone": "UNKNOWN"}

    @staticmethod
    def _calc_sharpe_sync(yf_ticker: str) -> dict[str, Any]:
        try:
            import yfinance as yf  # noqa: PLC0415

            rf = 0.0025 / 252
            coin_hist = yf.Ticker(yf_ticker).history(period="365d")["Close"].pct_change().dropna()
            smi_hist = yf.Ticker("^SSMI").history(period="365d")["Close"].pct_change().dropna()

            def sharpe(r: Any) -> float:
                std = float(r.std())
                return float((r.mean() - rf) / std * (252**0.5)) if std > 1e-8 else 0.0

            return {"crypto_sharpe": round(sharpe(coin_hist), 3), "smi_sharpe": round(sharpe(smi_hist), 3)}
        except Exception:
            return {"crypto_sharpe": 0.0, "smi_sharpe": 0.0}

    def _parse(self, coin: Literal["BTC", "ETH"], text: str, cache: dict[str, Any]) -> CointelligenceReport:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            data = json.loads(text[start:end])
            sharpe = cache.get("get_sharpe_comparison", {})
            return CointelligenceReport(
                coin=coin,
                price_chf=float(data.get("price_chf", 0)),
                mvrv_zone=data.get("mvrv_zone", "UNKNOWN"),
                fear_greed=int(data.get("fear_greed", 50)),
                sharpe_crypto=float(data.get("sharpe_crypto", sharpe.get("crypto_sharpe", 0.0))),
                sharpe_smi=float(data.get("sharpe_smi", sharpe.get("smi_sharpe", 0.0))),
                chf_usd_impact=data.get("chf_usd_impact", "NEUTRAL"),
                regime_signal=data.get("regime_signal", "HOLD"),
                max_allocation_pct=min(float(data.get("max_allocation_pct", 5.0)), 10.0),
                reasoning=data.get("reasoning", ""),
                disclaimer=data.get("disclaimer", _DISCLAIMER),
            )
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            _logger.warning("CointelligenceAgent parse-Fehler: %s", exc)
            return self._fallback(coin, cache)

    @staticmethod
    def _fallback(coin: Literal["BTC", "ETH"], cache: dict[str, Any]) -> CointelligenceReport:
        fg = cache.get("get_fear_greed_index", {}).get("value", 50)
        coin_data = cache.get("get_coin_data", {})
        price_chf = float(coin_data.get("price_chf", 0))
        regime: Literal["ACCUMULATE", "HOLD", "CAUTION", "AVOID"] = "CAUTION" if fg > 75 else "HOLD"
        return CointelligenceReport(
            coin=coin,
            price_chf=price_chf,
            mvrv_zone="UNKNOWN",
            fear_greed=fg,
            sharpe_crypto=0.0,
            sharpe_smi=0.0,
            chf_usd_impact="NEUTRAL",
            regime_signal=regime,
            max_allocation_pct=5.0,
            reasoning="Analyse nicht verfügbar — Fallback verwendet.",
            disclaimer=_DISCLAIMER,
        )
