"""Async httpx-Client mit X-API-Key-Header und MCP-Error-Mapping."""

import os

import httpx

from backend.interfaces.mcp.errors import raise_for_response, wrap_network_error


class RESTClient:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
        )

    @classmethod
    def from_env(cls) -> "RESTClient":
        return cls(
            base_url=os.environ.get("PRISMA_API_URL", "http://localhost:8000"),
            api_key=os.environ.get("PRISMA_API_KEY", ""),
        )

    async def post(self, path: str, json: dict) -> dict:  # type: ignore[type-arg]
        try:
            response = await self._client.post(path, json=json)
        except httpx.RequestError as exc:
            raise wrap_network_error(exc) from exc
        raise_for_response(response)
        return response.json()  # type: ignore[no-any-return]

    async def get(self, path: str) -> dict:  # type: ignore[type-arg]
        try:
            response = await self._client.get(path)
        except httpx.RequestError as exc:
            raise wrap_network_error(exc) from exc
        raise_for_response(response)
        return response.json()  # type: ignore[no-any-return]

    async def close(self) -> None:
        await self._client.aclose()
