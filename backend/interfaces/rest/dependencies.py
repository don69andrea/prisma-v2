"""FastAPI Dependency-Injection-Kette: Session → Repository → Service."""

import hmac
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

import anthropic
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.cost_tracker import CostTracker
from backend.application.services.narrative_service import NarrativeService
from backend.application.services.ranking_run_service import RankingRunService
from backend.application.services.stock_service import StockService
from backend.config import Settings, get_settings
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.cost_log_repository import CostLogRepository
from backend.domain.repositories.memo_batch_job_repository import MemoBatchJobRepository
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.pricing import PRICING
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
from backend.infrastructure.persistence.repositories.cost_log_repository import (
    SQLACostLogRepository,
)
from backend.infrastructure.persistence.repositories.memo_batch_job_repository import (
    SQLAMemoBatchJobRepository,
)
from backend.infrastructure.persistence.repositories.ranking_run_repository import (
    SQLARankingRunRepository,
)
from backend.infrastructure.persistence.repositories.research_memo_repository import (
    SQLAResearchMemoRepository,
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
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider


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
        pricing=PRICING,
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


async def get_market_data_provider() -> MarketDataProvider:
    return StubMarketDataProvider()


async def get_ranking_run_service(
    universe_repo: UniverseRepository = Depends(get_universe_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    fundamentals_provider: FundamentalsProvider = Depends(get_fundamentals_provider),
    market_data_provider: MarketDataProvider = Depends(get_market_data_provider),
) -> RankingRunService:
    return RankingRunService(
        universe_repo=universe_repo,
        run_repo=run_repo,
        fundamentals_provider=fundamentals_provider,
        market_data_provider=market_data_provider,
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


# ---------------------------------------------------------------------------
# NarrativeService DI-Chain
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_prompt_loader() -> PromptTemplateLoader:
    """Singleton — Templates werden einmal beim ersten Aufruf geladen."""
    return PromptTemplateLoader()


async def get_anthropic_client(
    settings: Settings = Depends(get_settings),
) -> Any:
    """Instanziiert den Anthropic AsyncAnthropic-Client mit Spec-konformen Timeouts.

    Spec §7 (Single-Memo-Slice): `timeout=30.0`, `max_retries=3`. SDK-Defaults
    sind 10-Minuten-Timeout / 2 Retries — bei langsam-antwortender API blockiert
    ein FastAPI-Worker sonst 10 Minuten pro Call.
    """
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=30.0,
        max_retries=3,
    )


async def get_llm_client(
    anthropic_client: Any = Depends(get_anthropic_client),
    cost_tracker: CostTracker = Depends(get_cost_tracker),
) -> LLMClient:
    """Erstellt den LLMClient-Wrapper. Voyage-Client ist None — wird nur für embed() benötigt,
    das von der Narrative-Engine nicht verwendet wird."""
    return LLMClient(anthropic=anthropic_client, voyage=None, cost_tracker=cost_tracker)


async def get_research_memo_repository() -> ResearchMemoRepository:
    """Instanziiert den SQLAlchemy-Adapter fuer ResearchMemo.

    SQLAResearchMemoRepository verwaltet seine eigene Session-Factory
    (wie SQLACostLogRepository), daher kein Depends(get_session) noetig.
    """
    return SQLAResearchMemoRepository(session_factory=get_session_factory())


async def get_memo_batch_job_repository() -> MemoBatchJobRepository:
    """Instanziiert den SQLAlchemy-Adapter fuer MemoBatchJob.

    Eigene Session-Factory analog SQLAResearchMemoRepository — Background-
    Worker persistieren ausserhalb des Request-Scopes.
    """
    return SQLAMemoBatchJobRepository(session_factory=get_session_factory())


async def get_narrative_service(
    memo_repo: ResearchMemoRepository = Depends(get_research_memo_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    stock_repo: StockRepository = Depends(get_stock_repository),
    batch_repo: MemoBatchJobRepository = Depends(get_memo_batch_job_repository),
    llm: LLMClient = Depends(get_llm_client),
    prompt_loader: PromptTemplateLoader = Depends(get_prompt_loader),
    cost_tracker: CostTracker = Depends(get_cost_tracker),
    settings: Settings = Depends(get_settings),
) -> NarrativeService:
    """Erstellt den NarrativeService mit vollstaendiger DI-Chain."""
    return NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        batch_repository=batch_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
        cost_tracker=cost_tracker,
        session_factory=get_session_factory(),
        # Factories fuer Background-Worker-Repos: keine konkreten Infrastructure-
        # Klassen im Application-Layer (Hexagonal — PR #70 W4-Fix).
        stock_repo_factory=lambda s: SQLAStockRepository(session=s),
        run_repo_factory=lambda s: SQLARankingRunRepository(session=s),
        max_concurrent_batch_workers=settings.max_concurrent_batch_workers,
        stale_batch_timeout_seconds=settings.stale_batch_timeout_seconds,
    )
