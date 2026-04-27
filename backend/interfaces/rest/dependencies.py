"""FastAPI Dependency-Injection-Kette: Session → Repository → Service."""

import hmac
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.cost_tracker import CostTracker
from backend.application.services.ranking_run_service import RankingRunService
from backend.application.services.stock_service import StockService
from backend.config import Settings, get_settings
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.repositories.cost_log_repository import CostLogRepository
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.infrastructure.persistence.repositories.cost_log_repository import (
    SQLACostLogRepository,
)
from backend.infrastructure.persistence.repositories.ranking_run_repository import (
    SQLARankingRunRepository,
)
from backend.infrastructure.persistence.repositories.stock_repository import (
    SQLAStockRepository,
)
from backend.infrastructure.persistence.repositories.universe_repository import (
    SQLAUniverseRepository,
)
from backend.infrastructure.persistence.session import (
    get_async_session,
    get_session_factory,
)
from backend.infrastructure.providers.stub_fundamentals import StubFundamentalsProvider


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Liefert eine AsyncSession für den aktuellen Request-Scope."""
    async for session in get_async_session():
        yield session


async def get_stock_repository(
    session: AsyncSession = Depends(get_session),
) -> StockRepository:
    """Instanziiert den SQLAlchemy-Adapter mit der aktuellen Session."""
    return SQLAStockRepository(session=session)


async def get_stock_service(
    repository: StockRepository = Depends(get_stock_repository),
) -> StockService:
    """Erstellt einen StockService mit dem injizierten Repository."""
    return StockService(repository=repository)


async def get_cost_log_repository() -> CostLogRepository:
    """Liefert den CostLogRepository-Adapter.

    Im Gegensatz zu StockRepository bekommt der Cost-Adapter eine
    Session-Factory injiziert, weil jede Operation (insbesondere `record()`)
    in einer eigenen Transaktion laufen muss — sonst würden Audit-Inserts
    laufende Business-Operationen mit-committen.
    """
    return SQLACostLogRepository(session_factory=get_session_factory())


async def get_cost_tracker(
    repository: CostLogRepository = Depends(get_cost_log_repository),
    settings: Settings = Depends(get_settings),
) -> CostTracker:
    """Konstruiert einen CostTracker mit Settings-gespeisten Cap-Werten."""
    return CostTracker(
        repository=repository,
        cap_usd=settings.budget_cap_usd,
        threshold=settings.budget_cap_threshold,
    )


async def get_universe_repository(
    session: AsyncSession = Depends(get_session),
) -> UniverseRepository:
    return SQLAUniverseRepository(session=session)


async def get_ranking_run_repository(
    session: AsyncSession = Depends(get_session),
) -> RankingRunRepository:
    return SQLARankingRunRepository(session=session)


async def get_fundamentals_provider() -> FundamentalsProvider:
    return StubFundamentalsProvider()


async def get_ranking_run_service(
    universe_repo: UniverseRepository = Depends(get_universe_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    fundamentals_provider: FundamentalsProvider = Depends(get_fundamentals_provider),
) -> RankingRunService:
    return RankingRunService(
        universe_repo=universe_repo,
        run_repo=run_repo,
        fundamentals_provider=fundamentals_provider,
    )


async def require_admin_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Vergleicht den eingehenden X-API-Key konstant-zeitsicher mit Settings.api_key.

    Settings via Depends → Tests können `app.dependency_overrides[get_settings]`
    nutzen, statt am Production-Default zu hängen.

    Fehlendes oder falsches Header liefert 401 (nicht 422), damit kein
    Information-Leak über die erwartete Header-Struktur entsteht. Ein leerer
    `settings.api_key` wird ebenfalls als 401 behandelt — kein gültiger Key
    kann leer sein.
    """
    if not settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if x_api_key is None or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
