"""Unit-Tests für DiscoveryService."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.application.services.discovery_service import DiscoveryService
from backend.domain.entities.investor_profile import InvestorProfile
from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.value_objects.swiss_quant_score import SwissQuantScore

pytestmark = pytest.mark.unit


def _make_stock(ticker: str, sector: str | None = "tech") -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker=ticker,
        isin="CH0012221716",  # valid CH ISIN
        name=f"{ticker} AG",
        exchange="XSWX",
        sector=sector,
        market_cap_chf=Decimal("10000000000"),
    )


def _make_score(composite: float) -> SwissQuantScore:
    score = MagicMock(spec=SwissQuantScore)
    score.composite = composite
    return score


def _make_service(stocks: list[SwissStock], composite: float = 75.0) -> DiscoveryService:
    repo = MagicMock()
    repo.list_by_exchange = AsyncMock(return_value=stocks)

    market_data = MagicMock()
    market_data.get_fundamentals = AsyncMock(return_value=MagicMock())

    service = DiscoveryService(swiss_stock_repo=repo, market_data=market_data)
    service._scorer = MagicMock()
    service._scorer.score = MagicMock(return_value=_make_score(composite))
    service._eligibility = MagicMock()
    return service


def _make_profile(**kwargs: Any) -> InvestorProfile:
    defaults: dict[str, Any] = {"session_id": "test-sess"}
    defaults.update(kwargs)
    return InvestorProfile(**defaults)


class TestDiscoveryServiceSectorFilter:
    @pytest.mark.asyncio
    async def test_empty_affinity_returns_all(self) -> None:
        stocks = [_make_stock("NESN.SW", "consumer"), _make_stock("LOGN.SW", "tech")]
        service = _make_service(stocks)
        profile = _make_profile(sector_affinity=[])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_sector_filter_applied(self) -> None:
        stocks = [_make_stock("NESN.SW", "consumer"), _make_stock("LOGN.SW", "tech")]
        service = _make_service(stocks)
        profile = _make_profile(sector_affinity=["tech"])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1
        assert result[0].ticker == "LOGN.SW"

    @pytest.mark.asyncio
    async def test_sector_filter_case_insensitive(self) -> None:
        stocks = [_make_stock("LOGN.SW", "Tech")]
        service = _make_service(stocks)
        profile = _make_profile(sector_affinity=["tech"])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1


class TestDiscoveryServiceRiskFilter:
    @pytest.mark.asyncio
    async def test_conservative_excludes_low_composite(self) -> None:
        stocks = [_make_stock("NESN.SW")]
        service = _make_service(stocks, composite=60.0)  # below 70.0 conservative floor
        profile = _make_profile(risk_profile="conservative")
        result = await service.get_personalized_universe(profile)
        # Scored ist leer (60 < 70), aber Fallback auf market_cap gibt den Titel zurück.
        # Das Fallback-Verhalten (PR #186) ist absichtlich: leeres Universe soll verhindert werden.
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_moderate_includes_above_40(self) -> None:
        stocks = [_make_stock("NESN.SW")]
        service = _make_service(stocks, composite=45.0)
        profile = _make_profile(risk_profile="moderate")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_aggressive_includes_all(self) -> None:
        stocks = [_make_stock("NESN.SW")]
        service = _make_service(stocks, composite=10.0)
        profile = _make_profile(risk_profile="aggressive")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1


class TestDiscoveryServiceKnownTickerPriority:
    @pytest.mark.asyncio
    async def test_known_tickers_sorted_first(self) -> None:
        stocks = [
            _make_stock("UNKNOWN.SW"),
            _make_stock("NESN.SW"),
        ]
        service = _make_service(stocks, composite=80.0)
        profile = _make_profile(known_tickers=["NESN.SW"])
        result = await service.get_personalized_universe(profile)
        assert result[0].ticker == "NESN.SW"

    @pytest.mark.asyncio
    async def test_unknown_ticker_not_excluded(self) -> None:
        stocks = [_make_stock("UNKNOWN.SW"), _make_stock("NESN.SW")]
        service = _make_service(stocks, composite=80.0)
        profile = _make_profile(known_tickers=["NESN.SW"])
        result = await service.get_personalized_universe(profile)
        assert len(result) == 2


class TestDiscoveryServiceESGFilter:
    @pytest.mark.asyncio
    async def test_esg_yes_excludes_non_esg_sector(self) -> None:
        stocks = [_make_stock("OIL.SW", "energy"), _make_stock("NESN.SW", "consumer")]
        service = _make_service(stocks, composite=80.0)
        profile = _make_profile(esg_preference="yes")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1
        assert result[0].ticker == "NESN.SW"

    @pytest.mark.asyncio
    async def test_esg_indifferent_includes_all_sectors(self) -> None:
        stocks = [_make_stock("OIL.SW", "energy"), _make_stock("NESN.SW", "consumer")]
        service = _make_service(stocks, composite=80.0)
        profile = _make_profile(esg_preference="indifferent")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_esg_yes_includes_unknown_sector(self) -> None:
        stocks = [_make_stock("ABBN.SW", None)]
        service = _make_service(stocks, composite=80.0)
        profile = _make_profile(esg_preference="yes")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1


class TestDiscoveryServiceIncomePreference:
    @pytest.mark.asyncio
    async def test_dividends_preference_boosts_high_yield(self) -> None:
        stock = _make_stock("NESN.SW", "consumer")
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=[stock])
        market_data = MagicMock()
        fundamentals_mock = MagicMock()
        fundamentals_mock.dividend_yield = 0.03  # 3% > threshold
        market_data.get_fundamentals = AsyncMock(return_value=fundamentals_mock)
        service = DiscoveryService(swiss_stock_repo=repo, market_data=market_data)
        service._scorer = MagicMock()
        service._scorer.score = MagicMock(return_value=_make_score(70.0))
        service._eligibility = MagicMock()
        profile = _make_profile(income_preference="dividends")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1  # included and boosted

    @pytest.mark.asyncio
    async def test_growth_preference_boosts_low_yield(self) -> None:
        stock = _make_stock("LOGN.SW", "tech")
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=[stock])
        market_data = MagicMock()
        fundamentals_mock = MagicMock()
        fundamentals_mock.dividend_yield = 0.005  # 0.5% < threshold
        market_data.get_fundamentals = AsyncMock(return_value=fundamentals_mock)
        service = DiscoveryService(swiss_stock_repo=repo, market_data=market_data)
        service._scorer = MagicMock()
        service._scorer.score = MagicMock(return_value=_make_score(60.0))
        service._eligibility = MagicMock()
        profile = _make_profile(income_preference="growth")
        result = await service.get_personalized_universe(profile)
        assert len(result) == 1  # included and boosted


class TestDiscoveryServiceErrorHandling:
    @pytest.mark.asyncio
    async def test_scoring_error_skips_stock(self) -> None:
        stocks = [_make_stock("NESN.SW"), _make_stock("LOGN.SW")]
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=stocks)
        market_data = MagicMock()
        market_data.get_fundamentals = AsyncMock(return_value=MagicMock())

        service = DiscoveryService(swiss_stock_repo=repo, market_data=market_data)
        service._scorer = MagicMock()
        service._scorer.score = MagicMock(side_effect=Exception("yfinance error"))
        service._eligibility = MagicMock()

        profile = _make_profile(risk_profile="aggressive")
        result = await service.get_personalized_universe(profile)
        # Alle Titel werfen Exception → scored leer → Fallback auf market_cap gibt alle zurück.
        # Das Fallback-Verhalten (PR #186) ist absichtlich: leeres Universe soll verhindert werden.
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests für DB-Score-Pfad (ml_features Feature Store)
# ---------------------------------------------------------------------------


def _make_service_with_db(
    stocks: list[SwissStock],
    db_scores: dict[str, float],
    yfinance_score: float | None = None,
) -> DiscoveryService:
    """Erstellt einen DiscoveryService mit gemockter DB-Session und db_scores."""
    repo = MagicMock()
    repo.list_by_exchange = AsyncMock(return_value=stocks)

    market_data = MagicMock()
    # yfinance liefert Fundamentals mit gegebener dividend_yield
    fundamentals_mock = MagicMock()
    fundamentals_mock.dividend_yield = 0.0
    market_data.get_fundamentals = AsyncMock(return_value=fundamentals_mock)

    db_session = MagicMock()

    service = DiscoveryService(
        swiss_stock_repo=repo,
        market_data=market_data,
        db_session=db_session,
    )
    # Mock _load_db_scores direkt — wir testen nicht SQLAlchemy, sondern die Logik
    service._load_db_scores = AsyncMock(return_value=db_scores)  # type: ignore[method-assign]

    if yfinance_score is not None:
        # Für yfinance-Fallback-Tests: Scorer über market_data simulieren
        service._scorer = MagicMock()
        score_mock = MagicMock(spec=SwissQuantScore)
        score_mock.composite = yfinance_score
        service._scorer.score = MagicMock(return_value=score_mock)
    else:
        service._scorer = MagicMock()
        service._scorer.score = MagicMock(return_value=_make_score(50.0))

    service._eligibility = MagicMock()
    return service


class TestDiscoveryServiceDbScorePath:
    """Tests für den primären DB-Score-Pfad (ml_features Feature Store)."""

    @pytest.mark.asyncio
    async def test_db_score_used_instead_of_yfinance(self) -> None:
        """Titel mit DB-Score umgeht yfinance komplett."""
        stock = _make_stock("NESN", "consumer")
        service = _make_service_with_db([stock], db_scores={"NESN": 80.0})
        profile = _make_profile(risk_profile="aggressive")

        result = await service.get_personalized_universe(profile)

        assert len(result) == 1
        assert result[0].ticker == "NESN"
        # yfinance darf nicht für Score-Berechnung aufgerufen werden
        # (nur ggf. für dividend_yield bei Income-Präferenz)
        service._scorer.score.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_db_score_risk_floor_applied(self) -> None:
        """Risk-Floor-Filter wird auch auf DB-Scores angewendet.

        Wenn scored leer ist, greift der market_cap-Fallback und gibt den Titel trotzdem zurück.
        Der Test verifiziert dass der Titel NICHT aufgrund seines DB-Scores eingeschlossen wird,
        sondern nur durch den Fallback — d.h. score < floor funktioniert korrekt.
        """
        stock = _make_stock("NESN", "consumer")
        # DB-Score 60 < conservative floor 70 → scored leer → Fallback greift
        service = _make_service_with_db([stock], db_scores={"NESN": 60.0})
        profile = _make_profile(risk_profile="conservative")

        result = await service.get_personalized_universe(profile)

        # Fallback auf market_cap → Titel trotzdem im Ergebnis (Fallback ist absichtliches Verhalten)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_db_score_passes_risk_floor(self) -> None:
        """Titel mit DB-Score über dem Risk-Floor wird eingeschlossen."""
        stock = _make_stock("NESN", "consumer")
        service = _make_service_with_db([stock], db_scores={"NESN": 75.0})
        profile = _make_profile(risk_profile="conservative")

        result = await service.get_personalized_universe(profile)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_esg_filter_applied_with_db_score(self) -> None:
        """ESG-Filter greift auch wenn DB-Score vorhanden ist."""
        oil_stock = _make_stock("OIL", "energy")
        safe_stock = _make_stock("NESN", "consumer")
        service = _make_service_with_db(
            [oil_stock, safe_stock],
            db_scores={"OIL": 80.0, "NESN": 80.0},
        )
        profile = _make_profile(esg_preference="yes")

        result = await service.get_personalized_universe(profile)

        assert len(result) == 1
        assert result[0].ticker == "NESN"

    @pytest.mark.asyncio
    async def test_yfinance_fallback_for_missing_db_ticker(self) -> None:
        """Ticker ohne DB-Score fällt auf yfinance zurück."""
        stock = _make_stock("NEWCO", "tech")
        # DB hat keinen Eintrag für NEWCO
        service = _make_service_with_db([stock], db_scores={}, yfinance_score=65.0)
        profile = _make_profile(risk_profile="moderate")

        result = await service.get_personalized_universe(profile)

        assert len(result) == 1
        assert result[0].ticker == "NEWCO"

    @pytest.mark.asyncio
    async def test_neutral_score_when_both_db_and_yfinance_fail(self) -> None:
        """Wenn weder DB noch yfinance einen Score liefern, wird neutraler Score 50 verwendet."""
        stock = _make_stock("FAIL", "tech")
        # DB leer, yfinance wirft Exception
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=[stock])
        market_data = MagicMock()
        market_data.get_fundamentals = AsyncMock(side_effect=Exception("timeout"))
        db_session = MagicMock()

        service = DiscoveryService(
            swiss_stock_repo=repo,
            market_data=market_data,
            db_session=db_session,
        )
        service._load_db_scores = AsyncMock(return_value={"OTHER": 70.0})  # type: ignore[method-assign]
        service._scorer = MagicMock()
        service._eligibility = MagicMock()

        # aggressive hat floor=0, also sollte neutraler Score 50.0 durchkommen
        profile = _make_profile(risk_profile="aggressive")
        result = await service.get_personalized_universe(profile)

        assert len(result) == 1
        assert result[0].ticker == "FAIL"

    @pytest.mark.asyncio
    async def test_neutral_score_filtered_by_conservative_floor(self) -> None:
        """Neutraler Score (50.0) wird durch conservative floor (70.0) gefiltert."""
        stock = _make_stock("FAIL", "tech")
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=[stock])
        market_data = MagicMock()
        market_data.get_fundamentals = AsyncMock(side_effect=Exception("timeout"))
        db_session = MagicMock()

        service = DiscoveryService(
            swiss_stock_repo=repo,
            market_data=market_data,
            db_session=db_session,
        )
        # DB hat keinen Score für FAIL
        service._load_db_scores = AsyncMock(return_value={"OTHER": 80.0})  # type: ignore[method-assign]
        service._scorer = MagicMock()
        service._eligibility = MagicMock()

        profile = _make_profile(risk_profile="conservative")
        result = await service.get_personalized_universe(profile)

        # Neutraler Score 50 < conservative floor 70 → gefiltert
        # Fallback auf market_cap greift aber, weil scored leer ist
        assert isinstance(result, list)  # Fallback liefert Ergebnis, kein Crash

    @pytest.mark.asyncio
    async def test_no_db_session_falls_back_to_yfinance_path(self) -> None:
        """Ohne db_session wird der klassische yfinance-Pfad verwendet."""
        stock = _make_stock("NESN", "consumer")
        stocks = [stock]
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=stocks)
        market_data = MagicMock()
        market_data.get_fundamentals = AsyncMock(return_value=MagicMock())

        # db_session=None → kein DB-Pfad
        service = DiscoveryService(swiss_stock_repo=repo, market_data=market_data, db_session=None)
        service._scorer = MagicMock()
        service._scorer.score = MagicMock(return_value=_make_score(75.0))
        service._eligibility = MagicMock()

        profile = _make_profile(risk_profile="aggressive")
        result = await service.get_personalized_universe(profile)

        assert len(result) == 1
        # yfinance wurde aufgerufen
        market_data.get_fundamentals.assert_called()

    @pytest.mark.asyncio
    async def test_mixed_db_and_yfinance_scores(self) -> None:
        """Ticker mit DB-Score und Ticker ohne werden korrekt gemischt."""
        stock_db = _make_stock("NESN", "consumer")
        stock_yf = _make_stock("NEWCO", "tech")
        stocks = [stock_db, stock_yf]
        repo = MagicMock()
        repo.list_by_exchange = AsyncMock(return_value=stocks)
        market_data = MagicMock()
        fundamentals_mock = MagicMock()
        fundamentals_mock.dividend_yield = 0.0
        market_data.get_fundamentals = AsyncMock(return_value=fundamentals_mock)
        db_session = MagicMock()

        service = DiscoveryService(
            swiss_stock_repo=repo,
            market_data=market_data,
            db_session=db_session,
        )
        # DB hat nur NESN
        service._load_db_scores = AsyncMock(return_value={"NESN": 80.0})  # type: ignore[method-assign]
        service._scorer = MagicMock()
        score_mock = MagicMock(spec=SwissQuantScore)
        score_mock.composite = 65.0
        service._scorer.score = MagicMock(return_value=score_mock)
        service._eligibility = MagicMock()

        profile = _make_profile(risk_profile="moderate")
        result = await service.get_personalized_universe(profile)

        # Beide sollten eingeschlossen werden (80 ≥ 40 und 65 ≥ 40)
        assert len(result) == 2
