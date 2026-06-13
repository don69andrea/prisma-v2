"""DiscoveryService — Personalisierte Titelauswahl basierend auf InvestorProfile.

Regelbasierter Filter ohne LLM: Sektor-Affinität, Risk-Profile, Quant-Score-Schwelle.
"""

from __future__ import annotations

import asyncio
import logging

from backend.domain.entities.investor_profile import InvestorProfile
from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.ports.swiss_market_data_provider import SwissMarketDataProvider
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.domain.services.eligibility_filter import EligibilityFilter
from backend.domain.services.swiss_quant_scorer import SwissQuantScorer

_logger = logging.getLogger(__name__)

# Risk-Profile → Mindest-Composite-Score
_RISK_MIN_COMPOSITE: dict[str, float] = {
    "conservative": 70.0,  # nur BUY-Signal
    "moderate": 40.0,  # BUY + HOLD
    "aggressive": 0.0,  # alle Signale
}

# financial_knowledge → maximale Titelanzahl im Discovery-Ergebnis
# Mehr Wissen → breiteres Universum, da der User mit Komplexität umgehen kann
_KNOWLEDGE_RESULT_LIMIT: dict[str, int] = {
    "low": 10,
    "medium": 20,
    "high": 30,
}

# Sektoren die bei esg_preference="yes" herausgefiltert werden.
# Proxy-Ansatz: kein ESG-Rating auf SwissStock → sektorbasierte Annäherung.
_NON_ESG_SECTORS: frozenset[str] = frozenset(
    {
        "energy",
        "coal",
        "oil & gas",
        "defense",
        "gambling",
        "tobacco",
        "weapons",
    }
)

# Mindest-Dividendenrendite (%) für Income-Bonus
_DIVIDEND_YIELD_THRESHOLD = 0.02  # 2 %


class DiscoveryService:
    """Gibt ein personalisiertes Aktienuniversum für ein InvestorProfile zurück.

    Filter-Reihenfolge (AND-verknüpft, kein LLM):
    1. Sektor: sector_affinity (leer → alle)
    2. Quant-Score: composite >= risk_floor
    3. Bekannte Titel nach oben priorisieren (known_tickers)
    """

    def __init__(
        self,
        swiss_stock_repo: SwissStockRepository,
        market_data: SwissMarketDataProvider,
    ) -> None:
        self._repo = swiss_stock_repo
        self._market_data = market_data
        self._scorer = SwissQuantScorer()
        self._eligibility = EligibilityFilter()

    async def _score_stock(
        self, stock: SwissStock, profile: InvestorProfile, risk_floor: float
    ) -> tuple[SwissStock, float] | None:
        """Berechnet Quant-Score für einen Titel inkl. ESG-Filter und Income-Bonus.

        Gibt None zurück wenn der Titel nicht verfügbar, unter dem Risk-Floor liegt
        oder via esg_preference ausgeschlossen wird.
        """
        # ESG-Filter (sektorbasierter Proxy — kein dediziertes ESG-Rating vorhanden)
        if (
            profile.esg_preference == "yes"
            and stock.sector is not None
            and stock.sector.lower() in _NON_ESG_SECTORS
        ):
            _logger.debug("ESG-Filter: %s (Sektor '%s') ausgeschlossen", stock.ticker, stock.sector)
            return None

        try:
            fundamentals = await self._market_data.get_fundamentals(stock.ticker)
            quant_score = self._scorer.score(stock.ticker, fundamentals)
        except Exception:
            _logger.debug("Quant-Score für %s nicht verfügbar — übersprungen", stock.ticker)
            return None

        if quant_score.composite < risk_floor:
            return None

        # Income-Präferenz: Bonus-Score basierend auf Dividendenrendite
        adjusted = quant_score.composite
        dividend_yield = (fundamentals.dividend_yield or 0.0) if fundamentals else 0.0
        if profile.income_preference == "dividends" and dividend_yield >= _DIVIDEND_YIELD_THRESHOLD:
            adjusted = min(adjusted + 10.0, 100.0)
        elif profile.income_preference == "growth" and dividend_yield < _DIVIDEND_YIELD_THRESHOLD:
            adjusted = min(adjusted + 5.0, 100.0)

        return (stock, adjusted)

    async def get_personalized_universe(self, profile: InvestorProfile) -> list[SwissStock]:
        """Gibt die gefilterte Titelliste für das übergebene Profil zurück."""
        all_stocks = await self._repo.list_by_exchange(exchange="XSWX", limit=200)

        # 1. Sektor-Filter (sector_affinity leer → alle Sektoren)
        if profile.sector_affinity:
            sector_set = {s.lower() for s in profile.sector_affinity}
            candidates = [
                s for s in all_stocks if s.sector is not None and s.sector.lower() in sector_set
            ]
        else:
            candidates = all_stocks

        risk_floor = _RISK_MIN_COMPOSITE.get(profile.risk_profile, 0.0)

        # 2. Quant-Score-Filter + ESG/Income — alle Titel parallel bewerten
        raw = await asyncio.gather(
            *[self._score_stock(stock, profile, risk_floor) for stock in candidates],
            return_exceptions=True,
        )
        scored: list[tuple[SwissStock, float]] = [r for r in raw if isinstance(r, tuple)]

        # 3. Bekannte Titel zuerst, dann nach Composite-Score absteigend
        known = {t.upper() for t in profile.known_tickers}
        scored.sort(key=lambda t: (0 if t[0].ticker in known else 1, -t[1]))

        # 4. Ergebnis-Limit basierend auf financial_knowledge
        # Einsteiger sehen weniger Titel um nicht überwältigt zu werden
        limit = _KNOWLEDGE_RESULT_LIMIT.get(profile.financial_knowledge, 20)
        return [stock for stock, _ in scored[:limit]]
