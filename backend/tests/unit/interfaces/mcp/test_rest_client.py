"""Tests für RESTClient — httpx-Mock, X-API-Key-Header, Error-Mapping."""

import json

import httpx
import pytest

from backend.interfaces.mcp.errors import MCPError
from backend.interfaces.mcp.rest_client import RESTClient


class _MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = iter(responses)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        resp = next(self._responses)
        resp.request = request
        return resp


def _make_client(responses: list[httpx.Response], *, api_key: str = "test-key") -> RESTClient:
    client = RESTClient(base_url="http://test", api_key=api_key)
    client._client = httpx.AsyncClient(
        base_url="http://test",
        transport=_MockTransport(responses),
        headers={"X-API-Key": api_key} if api_key else {},
    )
    return client


def _ok(body: dict | list) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(200, content=json.dumps(body).encode())


def _created(body: dict) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(201, content=json.dumps(body).encode())


@pytest.mark.asyncio
async def test_post_sends_api_key_header() -> None:
    captured: list[httpx.Request] = []

    class CapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _created({"id": "abc"})

    client = RESTClient(base_url="http://test", api_key="my-secret")
    client._client = httpx.AsyncClient(
        base_url="http://test",
        transport=CapturingTransport(),
        headers={"X-API-Key": "my-secret"},
    )
    await client.post("/api/v1/runs", json={"universe_id": "x"})
    assert captured[0].headers.get("x-api-key") == "my-secret"


@pytest.mark.asyncio
async def test_post_returns_json_on_success() -> None:
    client = _make_client([_created({"id": "run-1", "status": "completed"})])
    result = await client.post("/api/v1/runs", json={})
    assert result["id"] == "run-1"


@pytest.mark.asyncio
async def test_get_returns_json_on_success() -> None:
    client = _make_client([_ok([{"ticker": "AAPL"}])])
    result = await client.get("/api/v1/runs/1/rankings")
    assert result[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_post_raises_mcp_error_on_401() -> None:
    client = _make_client([httpx.Response(401)])
    with pytest.raises(MCPError) as exc_info:
        await client.post("/api/v1/runs", json={})
    assert exc_info.value.code == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_post_raises_upstream_unavailable_on_network_error() -> None:
    class FailingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

    client = RESTClient(base_url="http://test", api_key="k")
    client._client = httpx.AsyncClient(base_url="http://test", transport=FailingTransport())
    with pytest.raises(MCPError) as exc_info:
        await client.post("/api/v1/runs", json={})
    assert exc_info.value.code == "UPSTREAM_UNAVAILABLE"
