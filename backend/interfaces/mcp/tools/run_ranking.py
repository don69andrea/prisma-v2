"""MCP-Tool-Handler für `run_ranking`."""

from backend.interfaces.mcp.rest_client import RESTClient


async def run_ranking(
    client: RESTClient,
    *,
    universe_id: str,
    weights: dict[str, float] | None = None,
) -> dict:  # type: ignore[type-arg]
    """Löst einen neuen Ranking-Run aus und gibt Top-10 zurück.

    Args:
        universe_id: UUID des Universums als String.
        weights: Optionale Modell-Gewichte (müssen auf 1.0 summieren).

    Returns:
        {"model_run_id": str, "n_stocks": int,
         "top_10_summary": [{"ticker": str, "total_rank": int|None, "sweet_spot": bool}]}
    """
    payload: dict = {"universe_id": universe_id}  # type: ignore[type-arg]
    if weights is not None:
        payload["weight_config"] = weights

    # Validierung (UUID-Format, Gewicht-Summe) delegiert an Backend — 422 bei Fehler.
    run = await client.post("/api/v1/runs", json=payload)
    run_id = run["id"]

    rankings = await client.get(f"/api/v1/runs/{run_id}/rankings")

    top_10 = [
        {
            "ticker": r["ticker"],
            "total_rank": r["total_rank"],
            "sweet_spot": r["is_sweet_spot"],
        }
        for r in rankings[:10]
    ]

    return {
        "model_run_id": run_id,
        "n_stocks": len(rankings),
        "top_10_summary": top_10,
    }
