"""Tests für run_ranking Tool-Handler."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.interfaces.mcp.errors import MCPError
from backend.interfaces.mcp.tools.run_ranking import run_ranking

_UNIVERSE_ID = "550e8400-e29b-41d4-a716-446655440000"
_RUN_RESPONSE = {"id": "run-abc-123", "status": "completed", "universe_id": _UNIVERSE_ID}
_RANKINGS = [
    {
        "ticker": "AAPL",
        "total_rank": 1,
        "weighted_avg": 0.9,
        "is_sweet_spot": True,
        "per_model_ranks": {},
    },
    {
        "ticker": "MSFT",
        "total_rank": 2,
        "weighted_avg": 0.8,
        "is_sweet_spot": False,
        "per_model_ranks": {},
    },
    {
        "ticker": "NVDA",
        "total_rank": 3,
        "weighted_avg": 0.7,
        "is_sweet_spot": False,
        "per_model_ranks": {},
    },
]


def _mock_client(
    run_resp: dict[str, Any] = _RUN_RESPONSE,
    rankings: list[dict[str, Any]] = _RANKINGS,
) -> AsyncMock:
    client = AsyncMock()
    client.post = AsyncMock(return_value=run_resp)
    client.get = AsyncMock(return_value=rankings)
    return client


@pytest.mark.asyncio
async def test_happy_path_returns_top_10() -> None:
    client = _mock_client()
    result = await run_ranking(client, universe_id=_UNIVERSE_ID)

    assert result["model_run_id"] == "run-abc-123"
    assert result["n_stocks"] == 3
    assert result["top_10_summary"][0]["ticker"] == "AAPL"
    assert result["top_10_summary"][0]["sweet_spot"] is True


@pytest.mark.asyncio
async def test_passes_weight_config_to_backend() -> None:
    client = _mock_client()
    weights = {"quality_classic": 0.5, "alpha": 0.5}
    await run_ranking(client, universe_id=_UNIVERSE_ID, weights=weights)

    call_args = client.post.call_args
    assert call_args.kwargs["json"]["weight_config"] == weights


@pytest.mark.asyncio
async def test_no_weights_omits_weight_config() -> None:
    client = _mock_client()
    await run_ranking(client, universe_id=_UNIVERSE_ID)

    call_args = client.post.call_args
    assert "weight_config" not in call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_invalid_weights_forwarded_to_backend() -> None:
    """Gewicht-Validierung delegiert ans Backend — payload wird ohne lokalen Check gesendet."""
    client = _mock_client()
    await run_ranking(client, universe_id=_UNIVERSE_ID, weights={"quality_classic": 0.5})
    call_args = client.post.call_args
    assert call_args.kwargs["json"]["weight_config"] == {"quality_classic": 0.5}


@pytest.mark.asyncio
async def test_backend_order_preserved_in_top10() -> None:
    """Backend liefert Rankings sortiert — MCP-Tool übernimmt diese Reihenfolge."""
    pre_sorted: list[dict[str, Any]] = [
        {
            "ticker": "AAPL",
            "total_rank": 1,
            "weighted_avg": 0.9,
            "is_sweet_spot": True,
            "per_model_ranks": {},
        },
        {
            "ticker": "X",
            "total_rank": None,
            "weighted_avg": None,
            "is_sweet_spot": False,
            "per_model_ranks": {},
        },
    ]
    client = _mock_client(rankings=pre_sorted)
    result = await run_ranking(client, universe_id=_UNIVERSE_ID)

    assert result["top_10_summary"][0]["ticker"] == "AAPL"
    assert result["top_10_summary"][1]["ticker"] == "X"


@pytest.mark.asyncio
async def test_mcp_error_propagates() -> None:
    client = AsyncMock()
    client.post = AsyncMock(side_effect=MCPError("NOT_FOUND", detail="Universe not found"))
    with pytest.raises(MCPError) as exc_info:
        await run_ranking(client, universe_id=_UNIVERSE_ID)
    assert exc_info.value.code == "NOT_FOUND"
