"""Tests für MCP-Error-Mapping (alle 5 Typen aus Master-Spec §8)."""

import httpx
import pytest

from backend.interfaces.mcp.errors import MCPError, raise_for_response, wrap_network_error


def _mock_response(status_code: int, json_body: dict | None = None) -> httpx.Response:  # type: ignore[type-arg]
    content = b"{}" if json_body is None else __import__("json").dumps(json_body).encode()
    return httpx.Response(status_code, content=content)


def test_2xx_does_not_raise() -> None:
    raise_for_response(_mock_response(200))
    raise_for_response(_mock_response(201))


def test_401_raises_auth_failed() -> None:
    with pytest.raises(MCPError) as exc_info:
        raise_for_response(_mock_response(401))
    assert exc_info.value.code == "AUTH_FAILED"


def test_404_raises_not_found() -> None:
    with pytest.raises(MCPError) as exc_info:
        raise_for_response(_mock_response(404, {"detail": "Universe not found"}))
    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.fields["detail"] == "Universe not found"


def test_422_raises_invalid_input() -> None:
    with pytest.raises(MCPError) as exc_info:
        raise_for_response(_mock_response(422, {"detail": "field required"}))
    assert exc_info.value.code == "INVALID_INPUT"


def test_5xx_raises_internal() -> None:
    with pytest.raises(MCPError) as exc_info:
        raise_for_response(_mock_response(500))
    assert exc_info.value.code == "INTERNAL"
    assert exc_info.value.fields["upstream_status"] == 500


def test_unexpected_4xx_raises_internal() -> None:
    with pytest.raises(MCPError) as exc_info:
        raise_for_response(_mock_response(409))
    assert exc_info.value.code == "INTERNAL"


def test_wrap_network_error() -> None:
    exc = httpx.ConnectError("connection refused")
    mcp_err = wrap_network_error(exc)
    assert mcp_err.code == "UPSTREAM_UNAVAILABLE"
    assert "connection refused" in mcp_err.fields["reason"]
