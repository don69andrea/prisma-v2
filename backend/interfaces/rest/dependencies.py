"""FastAPI Dependency-Injection-Kette: Session → Repository → Service."""

import hmac
import logging
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

import anthropic
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.cost_tracker import CostTracker
from backend.application.services.crypto_agent_service import CryptoAgentService
from backend.application.services.crypto_pattern_service import CryptoPatternService
from backend.application.services.crypto_scoring_service import CryptoScoringService
from backend.application.services.factsheet_service import FactsheetService
from backend.application.services.narrative_service import NarrativeService
from backend.application.services.ranking_run_service import RankingRunService
from backend.application.services.retrieval_service import RetrievalService
from backend.application.services.stock_service import StockService
from backend.application.services.swiss_market_service import SwissMarketService
from backend.application.services.universe_service import UniverseService
from backend.application.services.universe_suggestion_service import UniverseSuggestionService
from backend.config import Settings, get_settings
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.ports.swiss_market_data_provider import SwissMarketDataProvider
from backend.domain.repositories.cost_log_repository import CostLogRepository
from backend.domain.repositories.crypto_signal_repository import CryptoSignalRepository
from backend.domain.repositories.memo_batch_job_repository import MemoBatchJobRepository
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.research_memo_repository import ResearchMemoRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.domain.services.crypto_scorer import CryptoScorer
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.infrastructure.adapters.yfinance_crypto import YFinanceCryptoAdapter
from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.pricing import PRICING  # Single-Source-of-Truth via DI an LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader
from backend.infrastructure.persistence.repositories.cost_log_repository import (
    SQLACostLogRepository,
)
from backend.infrastructure.persistence.repositories.crypto_signal_repository import (
    SQLACryptoSignalRepository,
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
from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
    SQLASwissStockRepository,
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

_logger = logging.getLogger(__name__)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Liefert eine AsyncSession für den aktuellen Request-Scope.

    ACHTUNG: Der `async for`-Wrapper ist kein Versehen. Er durchreicht die
    Generator-Cleanup-Semantik von get_async_session() (commit bei normalem
    Exit, rollback bei Exception) an FastAPIs Dependency-Teardown. Den
    Wrapper NICHT auf `async with` umstellen und kein Exception-Handling
    hinzufügen, das Exceptions schluckt — sonst kein Rollback mehr.
    """
    async for session in get_async_session():
        yield session


async def get_stock_repository(
    session: AsyncSession = Depends(get_session),
) -> StockRepository:
    """Instanziiert den SQLAlchemy-Adapter mit der aktuellen Session."""
    return SQLAStockRepository(session=session)


async def get_fundamentals_provider(
    settings: Settings = Depends(get_settings),
) -> FundamentalsProvider:
    if settings.environment == "production":
        _logger.warning(
            "StubFundamentalsProvider active in production — serving synthetic data. "
            "Wire a real FundamentalsProvider before going live (Issue #41)."
        )
    return StubFundamentalsProvider()


async def get_market_data_provider(
    settings: Settings = Depends(get_settings),
) -> MarketDataProvider:
    if settings.environment == "production":
        _logger.warning(
            "StubMarketDataProvider active in production — serving synthetic data. "
            "Wire a real MarketDataProvider before going live (Issue #41)."
        )
    return StubMarketDataProvider()


async def get_stock_service(
    repository: StockRepository = Depends(get_stock_repository),
    market_data_provider: MarketDataProvider = Depends(get_market_data_provider),
) -> StockService:
    """Erstellt einen StockService mit dem injizierten Repository und MarketDataProvider."""
    return StockService(repository=repository, market_data_provider=market_data_provider)


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


async def get_crypto_signal_repository(
    session: AsyncSession = Depends(get_session),
) -> CryptoSignalRepository:
    return SQLACryptoSignalRepository(session=session)


async def get_universe_service(
    repository: UniverseRepository = Depends(get_universe_repository),
    fundamentals_provider: FundamentalsProvider = Depends(get_fundamentals_provider),
    market_data_provider: MarketDataProvider = Depends(get_market_data_provider),
) -> UniverseService:
    return UniverseService(
        repository=repository,
        fundamentals_provider=fundamentals_provider,
        market_data_provider=market_data_provider,
    )


async def get_ranking_run_repository(
    session: AsyncSession = Depends(get_session),
) -> RankingRunRepository:
    return SQLARankingRunRepository(session=session)


async def get_factsheet_service(
    stock_repo: StockRepository = Depends(get_stock_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
) -> FactsheetService:
    return FactsheetService(stock_repo=stock_repo, run_repo=run_repo)


async def get_ranking_run_service(
    universe_repo: UniverseRepository = Depends(get_universe_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    fundamentals_provider: FundamentalsProvider = Depends(get_fundamentals_provider),
    market_data_provider: MarketDataProvider = Depends(get_market_data_provider),
    stock_service: StockService = Depends(get_stock_service),
) -> RankingRunService:
    return RankingRunService(
        universe_repo=universe_repo,
        run_repo=run_repo,
        fundamentals_provider=fundamentals_provider,
        market_data_provider=market_data_provider,
        stock_service=stock_service,
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
        # In production, a missing key is a misconfiguration — block all requests.
        # In test/dev, no key means auth is not configured → bypass so tests run
        # without needing API_KEY set in CI. Admin tests that want to verify 401
        # behaviour inject their own Settings(api_key=...) via dependency_overrides.
        if settings.environment == "production":
            raise HTTPException(status_code=401, detail="Invalid API key")
        return
    if x_api_key is None or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Opt-in X-API-Key-Guard für MCP-Tool-Endpoints (z.B. POST /api/v1/runs).

    Wenn tool_api_key leer ist (default), kein Enforcement — bestehende Aufrufer
    ohne Header werden nicht gebrochen. Sobald TOOL_API_KEY gesetzt ist,
    muss der Header exakt übereinstimmen.

    In Production (ENVIRONMENT=production) wird bei fehlendem Key ein 503
    zurückgegeben statt den Endpoint ohne Auth durchzulassen.
    """
    if not settings.tool_api_key:
        if settings.environment == "production":
            _logger.error(
                "require_api_key: TOOL_API_KEY ist nicht konfiguriert, "
                "Endpoint in Production ohne Auth aufgerufen — Zugriff verweigert."
            )
            raise HTTPException(
                status_code=503,
                detail="Dienst nicht verfügbar: API-Key-Konfiguration fehlt.",
            )
        _logger.warning(
            "require_api_key: TOOL_API_KEY ist nicht gesetzt — Auth-Enforcement deaktiviert. "
            "Setze TOOL_API_KEY in Production."
        )
        return
    if x_api_key is None or not hmac.compare_digest(x_api_key, settings.tool_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------------
# NarrativeService DI-Chain
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_prompt_loader() -> PromptTemplateLoader:
    """Singleton — Templates werden einmal beim ersten Aufruf geladen."""
    return PromptTemplateLoader()


@lru_cache(maxsize=1)
def get_anthropic_client() -> Any:
    """Singleton — AsyncAnthropic öffnet einen httpx-Connection-Pool.

    Pro-Request-Instanziierung würde bei jeder API-Anfrage einen frischen Pool
    aufbauen und sofort verwerfen (Issue #68 / PR #64 W4). lru_cache analog
    get_prompt_loader(). Spec §7: timeout=30s, max_retries=3.
    """
    settings = get_settings()
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=30.0,
        max_retries=3,
    )


async def get_llm_client(
    cost_tracker: CostTracker = Depends(get_cost_tracker),
) -> LLMClient:
    """Erstellt den LLMClient-Wrapper. Voyage-Client ist None — wird nur für embed() benötigt,
    das von der Narrative-Engine nicht verwendet wird."""
    return LLMClient(
        anthropic=get_anthropic_client(),
        voyage=None,
        cost_tracker=cost_tracker,
        pricing=PRICING,
    )


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


async def get_backtest_service(
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    universe_repo: UniverseRepository = Depends(get_universe_repository),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    session: AsyncSession = Depends(get_session),
) -> Any:
    from backend.application.services.backtest_service import BacktestService
    from backend.infrastructure.persistence.repositories.backtest_result_repository import (
        SQLABacktestResultRepository,
    )

    return BacktestService(
        run_repo=run_repo,
        universe_repo=universe_repo,
        market_data=market_data,
        result_repo=SQLABacktestResultRepository(session=session),
    )


async def get_embedding_repository() -> Any:
    from backend.infrastructure.persistence.repositories.embedding_repository import (
        SQLAEmbeddingRepository,
    )

    return SQLAEmbeddingRepository(session_factory=get_session_factory())


@lru_cache(maxsize=1)
def get_voyage_client() -> Any:
    """Singleton-Voyage-Client analog get_anthropic_client().

    Sync + lru_cache verhindert, dass im Memo-Batch (N Stocks) N neue
    Client-Instanzen gebaut werden.
    """
    settings = get_settings()
    if not settings.voyage_api_key:
        return None
    import voyageai

    return voyageai.Client(api_key=settings.voyage_api_key)  # type: ignore[attr-defined]


async def get_retrieval_service(
    embedding_repo: Any = Depends(get_embedding_repository),
    cost_tracker: CostTracker = Depends(get_cost_tracker),
) -> RetrievalService:
    voyage = get_voyage_client()
    llm = LLMClient(
        anthropic=get_anthropic_client(),
        voyage=voyage,
        cost_tracker=cost_tracker,
        pricing=PRICING,
    )
    return RetrievalService(embedding_repo=embedding_repo, llm_client=llm)


async def get_narrative_service(
    memo_repo: ResearchMemoRepository = Depends(get_research_memo_repository),
    run_repo: RankingRunRepository = Depends(get_ranking_run_repository),
    stock_repo: StockRepository = Depends(get_stock_repository),
    batch_repo: MemoBatchJobRepository = Depends(get_memo_batch_job_repository),
    llm: LLMClient = Depends(get_llm_client),
    prompt_loader: PromptTemplateLoader = Depends(get_prompt_loader),
    cost_tracker: CostTracker = Depends(get_cost_tracker),
    retrieval: RetrievalService = Depends(get_retrieval_service),
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
        retrieval_service=retrieval,
        session_factory=get_session_factory(),
        # Factories fuer Background-Worker-Repos: keine konkreten Infrastructure-
        # Klassen im Application-Layer (Hexagonal — PR #70 W4-Fix).
        stock_repo_factory=lambda s: SQLAStockRepository(session=s),
        run_repo_factory=lambda s: SQLARankingRunRepository(session=s),
        max_concurrent_batch_workers=settings.max_concurrent_batch_workers,
        stale_batch_timeout_seconds=settings.stale_batch_timeout_seconds,
    )


async def get_universe_suggestion_service(
    llm: LLMClient = Depends(get_llm_client),
    stock_service: StockService = Depends(get_stock_service),
) -> UniverseSuggestionService:
    """Erstellt den UniverseSuggestionService mit LLMClient und StockService."""
    return UniverseSuggestionService(llm_client=llm, stock_service=stock_service)


# ---------------------------------------------------------------------------
# SwissMarketService DI-Chain
# ---------------------------------------------------------------------------


async def get_swiss_stock_repository(
    session: AsyncSession = Depends(get_session),
) -> SwissStockRepository:
    """Instanziiert den SQLAlchemy-Adapter für Swiss Stocks mit der aktuellen Session."""
    return SQLASwissStockRepository(session=session)


_yfinance_adapter: YFinanceSwissAdapter | None = None


def _get_yfinance_adapter_singleton() -> YFinanceSwissAdapter:
    global _yfinance_adapter
    if _yfinance_adapter is None:
        _yfinance_adapter = YFinanceSwissAdapter()
    return _yfinance_adapter


async def get_swiss_market_data_provider() -> SwissMarketDataProvider:
    """Liefert den prozess-weiten YFinanceSwissAdapter (Singleton)."""
    return _get_yfinance_adapter_singleton()


async def get_yfinance_adapter() -> YFinanceSwissAdapter:
    """Liefert den prozess-weiten YFinanceSwissAdapter (Singleton)."""
    return _get_yfinance_adapter_singleton()


async def get_swiss_market_service(
    repo: SwissStockRepository = Depends(get_swiss_stock_repository),
    market_data: SwissMarketDataProvider = Depends(get_swiss_market_data_provider),
) -> SwissMarketService:
    """Erstellt den SwissMarketService mit Repository + YFinanceSwissAdapter."""
    return SwissMarketService(repo=repo, market_data=market_data)


# ---------------------------------------------------------------------------
# SteuerAgent DI-Chain
# ---------------------------------------------------------------------------


async def get_steuer_agent(
    cost_tracker: CostTracker = Depends(get_cost_tracker),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> Any:
    from backend.application.agents.steuer_agent import SteuerAgent

    return SteuerAgent(
        llm_client=LLMClient(
            anthropic=get_anthropic_client(),
            voyage=get_voyage_client(),
            cost_tracker=cost_tracker,
            pricing=PRICING,
        ),
        retrieval_service=retrieval,
        prompt_loader=get_prompt_loader(),
    )


# ---------------------------------------------------------------------------
# News-RAG DI-Chain
# ---------------------------------------------------------------------------


async def get_news_repository() -> Any:
    from backend.infrastructure.persistence.repositories.news_repository import (
        SQLANewsRepository,
    )

    return SQLANewsRepository(session_factory=get_session_factory())


async def get_news_ingestion_service(
    cost_tracker: CostTracker = Depends(get_cost_tracker),
) -> Any:
    from backend.application.services.news_ingestion_service import NewsIngestionService
    from backend.infrastructure.adapters.rss_news_adapter import RssNewsAdapter
    from backend.infrastructure.adapters.ticker_ner import SWISS_TICKERS, TickerNer
    from backend.infrastructure.persistence.repositories.news_repository import (
        SQLANewsRepository,
    )

    repo = SQLANewsRepository(session_factory=get_session_factory())
    voyage = get_voyage_client()
    llm = LLMClient(
        anthropic=get_anthropic_client(),
        voyage=voyage,
        cost_tracker=cost_tracker,
        pricing=PRICING,
    )
    return NewsIngestionService(
        news_repo=repo,
        rss_adapter=RssNewsAdapter(),
        ticker_ner=TickerNer(SWISS_TICKERS),
        llm_client=llm,
    )


async def get_news_retrieval_service(
    cost_tracker: CostTracker = Depends(get_cost_tracker),
) -> Any:
    from backend.application.services.news_retrieval_service import NewsRetrievalService
    from backend.infrastructure.persistence.repositories.news_repository import (
        SQLANewsRepository,
    )

    repo = SQLANewsRepository(session_factory=get_session_factory())
    voyage = get_voyage_client()
    llm = LLMClient(
        anthropic=get_anthropic_client(),
        voyage=voyage,
        cost_tracker=cost_tracker,
        pricing=PRICING,
    )
    return NewsRetrievalService(news_repo=repo, llm_client=llm)


# ---------------------------------------------------------------------------
# Swiss RAG (SIX Filings) DI-Chain
# ---------------------------------------------------------------------------


async def get_swiss_filing_repository() -> Any:
    from backend.infrastructure.persistence.repositories.swiss_filing_repository import (
        SQLASwissFilingRepository,
    )

    return SQLASwissFilingRepository(session_factory=get_session_factory())


async def get_swiss_filing_retrieval_service(
    repo: Any = Depends(get_swiss_filing_repository),
) -> Any:
    from backend.application.services.swiss_filing_retrieval_service import (
        SwissFilingRetrievalService,
    )

    voyage = get_voyage_client()
    return SwissFilingRetrievalService(repository=repo, voyage_client=voyage)


# ---------------------------------------------------------------------------
# Crypto Module DI-Chain
# ---------------------------------------------------------------------------

_fear_greed_adapter: FearGreedAdapter | None = None
_coingecko_adapter: CoinGeckoAdapter | None = None
_yfinance_crypto_adapter: YFinanceCryptoAdapter | None = None


def _get_fear_greed_singleton() -> FearGreedAdapter:
    global _fear_greed_adapter
    if _fear_greed_adapter is None:
        _fear_greed_adapter = FearGreedAdapter()
    return _fear_greed_adapter


def _get_coingecko_singleton() -> CoinGeckoAdapter:
    global _coingecko_adapter
    if _coingecko_adapter is None:
        from backend.config import get_settings

        _coingecko_adapter = CoinGeckoAdapter(api_key=get_settings().coingecko_api_key)
    return _coingecko_adapter


def _get_yfinance_crypto_singleton() -> YFinanceCryptoAdapter:
    global _yfinance_crypto_adapter
    if _yfinance_crypto_adapter is None:
        _yfinance_crypto_adapter = YFinanceCryptoAdapter()
    return _yfinance_crypto_adapter


async def get_fear_greed_adapter() -> FearGreedAdapter:
    return _get_fear_greed_singleton()


async def get_coingecko_adapter() -> CoinGeckoAdapter:
    return _get_coingecko_singleton()


async def get_yfinance_crypto_adapter() -> YFinanceCryptoAdapter:
    return _get_yfinance_crypto_singleton()


_crypto_pattern_service: CryptoPatternService | None = None


def _get_crypto_pattern_singleton() -> CryptoPatternService:
    global _crypto_pattern_service
    if _crypto_pattern_service is None:
        _crypto_pattern_service = CryptoPatternService()
    return _crypto_pattern_service


async def get_crypto_pattern_service() -> CryptoPatternService:
    return _get_crypto_pattern_singleton()


async def get_crypto_agent_service(
    llm_client: LLMClient = Depends(get_llm_client),
) -> CryptoAgentService:
    return CryptoAgentService(llm_client=llm_client)


async def get_crypto_scoring_service() -> CryptoScoringService:
    return CryptoScoringService(
        cg_adapter=_get_coingecko_singleton(),
        yf_adapter=_get_yfinance_crypto_singleton(),
        fg_adapter=_get_fear_greed_singleton(),
        scorer=CryptoScorer(),
        pattern_service=_get_crypto_pattern_singleton(),
    )
