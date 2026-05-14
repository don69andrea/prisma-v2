"""Integrationstests für /api/v1/universes gegen die Test-App mit InMemory-Repository."""

import uuid
from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.domain.entities.universe import Universe
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_universe_repository

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# In-Memory-Implementierung für Tests ohne Datenbankverbindung
# ---------------------------------------------------------------------------


class InMemoryUniverseRepository(UniverseRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, Universe] = {}

    async def get(self, universe_id: UUID) -> Universe | None:
        return self._store.get(universe_id)

    async def list(self) -> list[Universe]:
        return sorted(self._store.values(), key=lambda u: u.name)

    async def save(self, universe: Universe) -> None:
        self._store[universe.id] = universe


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SMI_ID = uuid.uuid4()
_SP500_ID = uuid.uuid4()


def _make_sample_universes() -> list[Universe]:
    return [
        Universe(id=_SMI_ID, name="SMI", region="CH", tickers=("NESN", "NOVN", "ROG")),
        Universe(id=_SP500_ID, name="S&P 500 Subset", region="US", tickers=("AAPL", "MSFT")),
    ]


@pytest.fixture
def in_memory_universe_repo() -> InMemoryUniverseRepository:
    repo = InMemoryUniverseRepository()
    for u in _make_sample_universes():
        repo._store[u.id] = u
    return repo


@pytest_asyncio.fixture
async def http_client(
    in_memory_universe_repo: InMemoryUniverseRepository,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    app.dependency_overrides[get_universe_repository] = lambda: in_memory_universe_repo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/universes
# ---------------------------------------------------------------------------


async def test_list_universes_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.get("/api/v1/universes")
    assert response.status_code == 200


async def test_list_universes_response_shape(http_client: AsyncClient) -> None:
    body = (await http_client.get("/api/v1/universes")).json()
    assert "items" in body
    assert "total" in body


async def test_list_universes_returns_two_sample_entries(http_client: AsyncClient) -> None:
    body = (await http_client.get("/api/v1/universes")).json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_list_universes_item_has_expected_fields(http_client: AsyncClient) -> None:
    item = (await http_client.get("/api/v1/universes")).json()["items"][0]
    assert "id" in item
    assert "name" in item
    assert "region" in item
    assert "tickers" in item


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/universes
# ---------------------------------------------------------------------------


async def test_create_universe_returns_201(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/universes",
        json={"name": "DAX", "region": "DE", "tickers": ["SAP", "BMW"]},
    )
    assert response.status_code == 201


async def test_create_universe_response_has_id(http_client: AsyncClient) -> None:
    body = (
        await http_client.post(
            "/api/v1/universes",
            json={"name": "DAX", "region": "DE", "tickers": ["SAP"]},
        )
    ).json()
    assert "id" in body
    uuid.UUID(body["id"])  # must be valid UUID


async def test_create_universe_tickers_uppercased(http_client: AsyncClient) -> None:
    body = (
        await http_client.post(
            "/api/v1/universes",
            json={"name": "Test", "region": "US", "tickers": ["aapl", "msft"]},
        )
    ).json()
    assert body["tickers"] == ["AAPL", "MSFT"]


async def test_create_universe_empty_name_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/universes",
        json={"name": "", "region": "CH", "tickers": ["NESN"]},
    )
    assert response.status_code == 422


async def test_create_universe_missing_field_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/universes",
        json={"name": "Test"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/universes/{id}
# ---------------------------------------------------------------------------


async def test_get_universe_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.get(f"/api/v1/universes/{_SMI_ID}")
    assert response.status_code == 200


async def test_get_universe_returns_correct_name(http_client: AsyncClient) -> None:
    body = (await http_client.get(f"/api/v1/universes/{_SMI_ID}")).json()
    assert body["name"] == "SMI"


async def test_get_universe_unknown_id_returns_404(http_client: AsyncClient) -> None:
    unknown = uuid.uuid4()
    response = await http_client.get(f"/api/v1/universes/{unknown}")
    assert response.status_code == 404


async def test_create_universe_blank_region_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/universes",
        json={"name": "Test", "region": "   ", "tickers": ["AAPL"]},
    )
    assert response.status_code == 422


async def test_create_universe_blank_tickers_returns_422(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/api/v1/universes",
        json={"name": "Test", "region": "US", "tickers": ["  ", ""]},
    )
    assert response.status_code == 422
