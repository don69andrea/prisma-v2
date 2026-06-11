"""DiscoveryService — Personalisierte Titelauswahl basierend auf InvestorProfile.

Regelbasierter Filter ohne LLM: Sektor-Affinität, Risk-Profile, Quant-Score-Schwelle.
"""

from __future__ import annotations

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
    "moderate": 40.0,      # BUY + HOLD
    "aggressive": 0.0,     # alle Signale
}


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

        scored: list[tuple[SwissStock, float]] = []
        for stock in candidates:
            # 2. Quant-Score-Filter
            try:
                fundamentals = await self._market_data.get_fundamentals(stock.ticker)
                quant_score = self._scorer.score(stock.ticker, fundamentals)
            except Exception:
                _logger.debug("Quant-Score für %s nicht verfügbar — übersprungen", stock.ticker)
                continue

            if quant_score.composite < risk_floor:
                continue

            scored.append((stock, quant_score.composite))

        # 3. Bekannte Titel zuerst, dann nach Composite-Score absteigend
        known = {t.upper() for t in profile.known_tickers}
        scored.sort(key=lambda t: (0 if t[0].ticker in known else 1, -t[1]))

        return [stock for stock, _ in scored]
