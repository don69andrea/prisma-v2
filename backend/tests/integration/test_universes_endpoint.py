"""Integrationstests für /api/v1/universes gegen die Test-App mit InMemory-Repository."""

import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager as AsyncContextManager
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.domain.entities.universe import Universe
from backend.domain.repositories.universe_repository import (
    DuplicateUniverseNameError,
    UniverseRepository,
)
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
        for existing in self._store.values():
            if existing.id != universe.id and existing.name == universe.name:
                raise DuplicateUniverseNameError(universe.name)
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


async def test_create_universe_duplicate_name_returns_409(http_client: AsyncClient) -> None:
    """Regression K-4/F-BTCR-3: Namens-Duplikat darf nicht als 500 durchschlagen."""
    first = await http_client.post(
        "/api/v1/universes",
        json={"name": "Duplicate-Name", "region": "CH", "tickers": ["NESN"]},
    )
    assert first.status_code == 201

    second = await http_client.post(
        "/api/v1/universes",
        json={"name": "Duplicate-Name", "region": "US", "tickers": ["AAPL"]},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Ein Universe mit diesem Namen existiert bereits."


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


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/universes/{id}/sync
# ---------------------------------------------------------------------------


async def test_sync_universe_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.post(f"/api/v1/universes/{_SMI_ID}/sync")
    assert response.status_code == 200


async def test_sync_universe_response_has_expected_fields(http_client: AsyncClient) -> None:
    body = (await http_client.post(f"/api/v1/universes/{_SP500_ID}/sync")).json()
    assert "universe_id" in body
    assert "synced_count" in body
    assert "failed_tickers" in body


async def test_sync_universe_returns_correct_universe_id(http_client: AsyncClient) -> None:
    body = (await http_client.post(f"/api/v1/universes/{_SMI_ID}/sync")).json()
    assert body["universe_id"] == str(_SMI_ID)


async def test_sync_universe_unknown_id_returns_404(http_client: AsyncClient) -> None:
    response = await http_client.post(f"/api/v1/universes/{uuid.uuid4()}/sync")
    assert response.status_code == 404


async def test_sync_universe_sp500_synced_count_is_positive(http_client: AsyncClient) -> None:
    """S&P-500-Subset (AAPL, MSFT) liegen im StubFundamentalsProvider — synced_count > 0."""
    body = (await http_client.post(f"/api/v1/universes/{_SP500_ID}/sync")).json()
    assert body["synced_count"] > 0
    assert body["synced_count"] + len(body["failed_tickers"]) == 2  # SP500 hat 2 Tickers


async def test_sync_universe_smi_tickers_now_in_stub_land_synced(
    http_client: AsyncClient,
) -> None:
    """SMI-Tickers (NESN/NOVN/ROG) sind im StubFundamentalsProvider — alle synced."""
    body = (await http_client.post(f"/api/v1/universes/{_SMI_ID}/sync")).json()
    assert body["synced_count"] == 3
    assert body["failed_tickers"] == []


async def test_sync_universe_ticker_count_invariant(http_client: AsyncClient) -> None:
    """synced_count + len(failed_tickers) == Anzahl Tickers im Universum (immer)."""
    body = (await http_client.post(f"/api/v1/universes/{_SMI_ID}/sync")).json()
    assert body["synced_count"] + len(body["failed_tickers"]) == 3  # SMI hat 3 Tickers


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/universes/suggest
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

from backend.application.services.universe_suggestion_service import (  # noqa: E402
    EmptySuggestion,
    UniverseSuggestion,
    UniverseSuggestionService,
)
from backend.interfaces.rest.dependencies import get_universe_suggestion_service  # noqa: E402


@pytest_asyncio.fixture
async def make_client_with_suggest(
    in_memory_universe_repo: InMemoryUniverseRepository,
) -> Callable[[object], AsyncContextManager[AsyncClient]]:
    """Factory-Fixture: nimm einen fake suggestion service, gibt client zurück."""

    @asynccontextmanager
    async def _make(fake_service: object) -> AsyncGenerator[AsyncClient, None]:
        app = create_app()
        app.dependency_overrides[get_universe_repository] = lambda: in_memory_universe_repo
        app.dependency_overrides[get_universe_suggestion_service] = lambda: fake_service
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client

    return _make


async def test_suggest_returns_200_with_valid_suggestion(
    make_client_with_suggest: Callable[[object], AsyncContextManager[AsyncClient]],
) -> None:
    """Mit Mock-LLM gibt der Endpoint einen Vorschlag zurück."""
    fake_service = MagicMock(spec=UniverseSuggestionService)
    fake_service.suggest = AsyncMock(
        return_value=UniverseSuggestion(
            name="Mock-Universe",
            region="US",
            tickers=["AAPL", "MSFT"],
            reasoning="Test-Vorschlag mit zwei Tickern.",
            available_tickers=["AAPL", "MSFT", "GOOGL"],
        )
    )

    async with make_client_with_suggest(fake_service) as client:
        response = await client.post(
            "/api/v1/universes/suggest",
            json={"description": "Tech-Heavy"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Mock-Universe"
    assert body["tickers"] == ["AAPL", "MSFT"]
    assert body["available_tickers"] == ["AAPL", "MSFT", "GOOGL"]


async def test_suggest_returns_422_for_short_description(
    make_client_with_suggest: Callable[[object], AsyncContextManager[AsyncClient]],
) -> None:
    """Description < 3 chars wird abgelehnt."""
    fake_service = MagicMock(spec=UniverseSuggestionService)
    fake_service.suggest = AsyncMock(side_effect=AssertionError("Should not be called"))

    async with make_client_with_suggest(fake_service) as client:
        response = await client.post(
            "/api/v1/universes/suggest",
            json={"description": "x"},
        )

    assert response.status_code == 422


async def test_suggest_returns_422_when_service_raises_empty(
    make_client_with_suggest: Callable[[object], AsyncContextManager[AsyncClient]],
) -> None:
    """Wenn Service EmptySuggestion wirft → 422."""
    fake_service = MagicMock(spec=UniverseSuggestionService)
    fake_service.suggest = AsyncMock(side_effect=EmptySuggestion("Keine validen Tickers"))

    async with make_client_with_suggest(fake_service) as client:
        response = await client.post(
            "/api/v1/universes/suggest",
            json={"description": "irgendwas"},
        )

    assert response.status_code == 422
    assert "Keine validen Tickers" in response.json()["detail"]
