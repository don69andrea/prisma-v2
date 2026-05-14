"""PRISMA MCP-Server Entry-Point — STDIO via FastMCP."""

import logging

from mcp.server.fastmcp import FastMCP

from backend.interfaces.mcp.rest_client import RESTClient
from backend.interfaces.mcp.tools.run_ranking import run_ranking as _run_ranking_impl

logger = logging.getLogger(__name__)

mcp = FastMCP("PRISMA")
_client = RESTClient.from_env()


@mcp.tool()
async def run_ranking(
    universe_id: str,
    weights: dict[str, float] | None = None,
) -> dict:  # type: ignore[type-arg]
    """Löst einen neuen Ranking-Run für das angegebene Universum aus.

    Args:
        universe_id: UUID des zu rankenden Universums.
        weights: Optionale Modell-Gewichte (Dict mit Modell-Namen → Gewicht,
                 müssen auf 1.0 summieren). Wenn None: gleichgewichtet.

    Returns:
        model_run_id, n_stocks und Top-10-Summary mit ticker, total_rank, sweet_spot.
    """
    logger.info("run_ranking called: universe_id=%s", universe_id)
    return await _run_ranking_impl(_client, universe_id=universe_id, weights=weights)


if __name__ == "__main__":
    mcp.run()
