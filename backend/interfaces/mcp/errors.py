"""MCP-Error-Mapping — übersetzt HTTP-Statuscodes in MCP-Fehlertypen."""

from typing import Any

import httpx


class MCPError(Exception):
    """Basis-Exception für MCP-Tool-Fehler. FastMCP fängt und serialisiert."""

    def __init__(self, code: str, **fields: Any) -> None:
        self.code = code
        self.fields = fields
        super().__init__(f"{code}: {fields}")


def raise_for_response(response: httpx.Response) -> None:
    """Wirft MCPError wenn der Response kein 2xx-Status hat."""
    if response.is_success:
        return
    try:
        detail = response.json().get("detail", "")
    except Exception:
        detail = ""

    status = response.status_code
    if status == 401:
        raise MCPError("AUTH_FAILED", hint="Check PRISMA_API_KEY env var")
    if status == 404:
        raise MCPError("NOT_FOUND", detail=detail)
    if status == 422:
        raise MCPError("INVALID_INPUT", detail=str(detail))
    raise MCPError("INTERNAL", upstream_status=status, detail=detail)


def wrap_network_error(exc: httpx.RequestError) -> MCPError:
    return MCPError("UPSTREAM_UNAVAILABLE", reason=str(exc))
