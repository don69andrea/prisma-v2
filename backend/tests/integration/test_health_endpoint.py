"""Integrationstest für den Health-Check-Endpunkt."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_health_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.get("/health")
    assert response.status_code == 200


async def test_health_returns_ok_body(http_client: AsyncClient) -> None:
    response = await http_client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_health_content_type_is_json(http_client: AsyncClient) -> None:
    response = await http_client.get("/health")
    assert "application/json" in response.headers["content-type"]
