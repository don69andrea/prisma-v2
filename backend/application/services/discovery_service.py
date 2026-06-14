"""DiscoveryService — Personalisierte Titelauswahl basierend auf InvestorProfile.

Regelbasierter Filter ohne LLM: Sektor-Affinität, Risk-Profile, Quant-Score-Schwelle.

Performance-Optimierung (fix/discovery-use-db-scores):
  Quant-Scores werden primär aus `ml_features` (Feature Store, eine DB-Abfrage)
  geladen, statt für jeden Titel einzeln yfinance aufzurufen. yfinance dient nur
  noch als Fallback für Ticker ohne DB-Eintrag. Fehlen sowohl DB- als auch
  yfinance-Daten, wird ein neutraler Score (50.0) verwendet, damit der Titel nicht
  komplett gedroppt wird.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.investor_profile import InvestorProfile
from backend.domain.entities.swiss_stock import SwissStock
from backend.domain.ports.swiss_market_data_provider import SwissMarketDataProvider
from backend.domain.repositories.swiss_stock_repository import SwissStockRepository
from backend.domain.services.eligibility_filter import EligibilityFilter
from backend.domain.services.swiss_quant_scorer import SwissQuantScorer
from backend.infrastructure.persistence.models.ml_features import MLFeatureORM

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

# Neutraler Score wenn weder DB- noch yfinance-Daten verfügbar sind.
# Verhindert, dass Titel komplett gedroppt werden — conservative (floor=70) filtert sie trotzdem.
_NEUTRAL_SCORE = 50.0


class DiscoveryService:
    """Gibt ein personalisiertes Aktienuniversum für ein InvestorProfile zurück.

    Filter-Reihenfolge (AND-verknüpft, kein LLM):
    1. Sektor: sector_affinity (leer → alle)
    2. Quant-Score: composite >= risk_floor  (Quelle: ml_features DB → yfinance → neutral 50)
    3. Bekannte Titel nach oben priorisieren (known_tickers)
    """

    def __init__(
        self,
        swiss_stock_repo: SwissStockRepository,
        market_data: SwissMarketDataProvider,
        db_session: AsyncSession | None = None,
    ) -> None:
        self._repo = swiss_stock_repo
        self._market_data = market_data
        self._db_session = db_session
        self._scorer = SwissQuantScorer()
        self._eligibility = EligibilityFilter()

    # ------------------------------------------------------------------
    # Interne Hilfsmethoden
    # ------------------------------------------------------------------

    async def _load_db_scores(self, tickers: list[str]) -> dict[str, float]:
        """Lädt die neuesten quant_scores aus ml_features in einer einzigen DB-Abfrage.

        Gibt ein Dict {ticker: quant_score} zurück. Ticker ohne DB-Eintrag fehlen im Dict.
        Wenn keine DB-Session verfügbar ist oder die Abfrage fehlschlägt, wird {} zurückgegeben.
        """
        if self._db_session is None or not tickers:
            return {}

        try:
            # Subquery: neuestes snapshot_date für jeden Ticker (statt globales MAX,
            # damit Ticker mit unterschiedlichen Snapshot-Daten korrekt behandelt werden)
            latest_date_subq = (
                select(
                    MLFeatureORM.ticker,
                    func.max(MLFeatureORM.snapshot_date).label("max_date"),
                )
                .where(MLFeatureORM.ticker.in_(tickers))
                .group_by(MLFeatureORM.ticker)
                .subquery()
            )

            stmt = select(MLFeatureORM.ticker, MLFeatureORM.quant_score).join(
                latest_date_subq,
                (MLFeatureORM.ticker == latest_date_subq.c.ticker)
                & (MLFeatureORM.snapshot_date == latest_date_subq.c.max_date),
            )

            rows = await self._db_session.execute(stmt)
            result = {row.ticker: row.quant_score for row in rows}
            _logger.debug(
                "ml_features: %d/%d Ticker mit DB-Score geladen",
                len(result),
                len(tickers),
            )
            return result
        except Exception as exc:
            _logger.warning(
                "ml_features DB-Abfrage fehlgeschlagen — yfinance-Fallback für alle Ticker: %s",
                exc,
                exc_info=True,
            )
            return {}

    async def _get_quant_score_from_yfinance(self, stock: SwissStock) -> float | None:
        """Ruft quant_score via yfinance ab. Gibt None bei Fehler zurück."""
        try:
            fundamentals = await self._market_data.get_fundamentals(stock.ticker)
            quant_score = self._scorer.score(stock.ticker, fundamentals)
            return quant_score.composite
        except Exception as exc:
            _logger.warning(
                "yfinance-Fallback für %s fehlgeschlagen: %s",
                stock.ticker,
                exc,
            )
            return None

    async def _get_dividend_yield_from_yfinance(self, stock: SwissStock) -> float:
        """Holt dividend_yield via yfinance für Income-Bonus. Gibt 0.0 bei Fehler zurück."""
        try:
            fundamentals = await self._market_data.get_fundamentals(stock.ticker)
            return (fundamentals.dividend_yield or 0.0) if fundamentals else 0.0
        except Exception:
            return 0.0

    async def _score_stock_with_db(
        self,
        stock: SwissStock,
        profile: InvestorProfile,
        risk_floor: float,
        db_scores: dict[str, float],
    ) -> tuple[SwissStock, float] | None:
        """Bewertet einen Titel mit DB-Score (primär) oder yfinance (Fallback).

        Ablauf:
          1. ESG-Filter (sektorbasierter Proxy)
          2. Quant-Score aus db_scores → yfinance → neutral 50.0
          3. Risk-Floor-Filter
          4. Income-Bonus (nur wenn DB-Score vorhanden; andernfalls yfinance für dividend_yield)
        """
        # 1. ESG-Filter
        if (
            profile.esg_preference == "yes"
            and stock.sector is not None
            and stock.sector.lower() in _NON_ESG_SECTORS
        ):
            _logger.debug("ESG-Filter: %s (Sektor '%s') ausgeschlossen", stock.ticker, stock.sector)
            return None

        # 2. Quant-Score bestimmen
        composite: float
        dividend_yield: float = 0.0

        if stock.ticker in db_scores:
            composite = db_scores[stock.ticker]
            _logger.debug("DB-Score für %s: %.1f", stock.ticker, composite)
            # Income-Bonus: dividend_yield aus yfinance nur wenn wirklich benötigt
            # (Income-Präferenz gesetzt und Titel hat DB-Score)
            if profile.income_preference in ("dividends", "growth"):
                dividend_yield = await self._get_dividend_yield_from_yfinance(stock)
        else:
            # yfinance-Fallback für Ticker ohne DB-Eintrag
            yf_score = await self._get_quant_score_from_yfinance(stock)
            if yf_score is None:
                # Weder DB noch yfinance — neutraler Score, damit Titel nicht komplett fällt
                _logger.info(
                    "%s: Kein DB- und kein yfinance-Score — neutraler Score %.1f wird verwendet",
                    stock.ticker,
                    _NEUTRAL_SCORE,
                )
                composite = _NEUTRAL_SCORE
            else:
                composite = yf_score
                _logger.debug("yfinance-Score für %s: %.1f", stock.ticker, composite)
                # dividend_yield aus yfinance bereits latent via get_fundamentals geholt;
                # wir machen einen zweiten Call nur wenn Income-Präferenz aktiv ist.
                if profile.income_preference in ("dividends", "growth"):
                    dividend_yield = await self._get_dividend_yield_from_yfinance(stock)

        # 3. Risk-Floor-Filter
        if composite < risk_floor:
            return None

        # 4. Income-Bonus
        adjusted = composite
        if profile.income_preference == "dividends" and dividend_yield >= _DIVIDEND_YIELD_THRESHOLD:
            adjusted = min(adjusted + 10.0, 100.0)
        elif profile.income_preference == "growth" and dividend_yield < _DIVIDEND_YIELD_THRESHOLD:
            adjusted = min(adjusted + 5.0, 100.0)

        return (stock, adjusted)

    # ------------------------------------------------------------------
    # Legacy-Hilfsmethode (yfinance-only, weiterhin für Rückwärtskompatibilität)
    # ------------------------------------------------------------------

    async def _score_stock(
        self, stock: SwissStock, profile: InvestorProfile, risk_floor: float
    ) -> tuple[SwissStock, float] | None:
        """Berechnet Quant-Score für einen Titel inkl. ESG-Filter und Income-Bonus.

        Gibt None zurück wenn der Titel nicht verfügbar, unter dem Risk-Floor liegt
        oder via esg_preference ausgeschlossen wird.

        Hinweis: Diese Methode wird nur noch verwendet wenn _db_session=None und
        ml_features komplett leer ist (Fallback-Pfad für frische DBs ohne Feature-Store).
        """
        # ESG-Filter (sektorbasierter Proxy — kein dediziertes ESG-Rating vorhanden)
        if (
            profile.esg_preference == "yes"
            and stock.sector is not None
            and stock.sector.lower() in _NON_ESG_SECTORS
        ):
            _logger.debug(
                "ESG-Filter: %s (Sektor '%s') ausgeschlossen",
                stock.ticker,
                stock.sector,
            )
            return None

        try:
            fundamentals = await self._market_data.get_fundamentals(stock.ticker)
            quant_score = self._scorer.score(stock.ticker, fundamentals)
        except Exception as exc:
            _logger.warning(
                "Quant-Score für %s nicht verfügbar — übersprungen: %s",
                stock.ticker,
                exc,
                exc_info=True,
            )
            return None

        if quant_score.composite < risk_floor:
            return None

        # Income-Präferenz: Bonus-Score basierend auf Dividendenrendite
        adjusted = quant_score.composite
        dividend_yield = (fundamentals.dividend_yield or 0.0) if fundamentals else 0.0
        pref = profile.income_preference
        if pref == "dividends" and dividend_yield >= _DIVIDEND_YIELD_THRESHOLD:
            adjusted = min(adjusted + 10.0, 100.0)
        elif pref == "growth" and dividend_yield < _DIVIDEND_YIELD_THRESHOLD:
            adjusted = min(adjusted + 5.0, 100.0)

        return (stock, adjusted)

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

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

        # 2. Quant-Score-Filter + ESG/Income
        #    Primärpfad: DB-Scores aus ml_features (eine Abfrage für alle Kandidaten)
        #    Fallback:   yfinance per Titel → neutraler Score 50.0
        candidate_tickers = [s.ticker for s in candidates]
        db_scores = await self._load_db_scores(candidate_tickers)

        if db_scores:
            _logger.info(
                "Discovery: %d/%d Kandidaten mit DB-Scores aus ml_features",
                len(db_scores),
                len(candidates),
            )
            raw = await asyncio.gather(
                *[
                    self._score_stock_with_db(stock, profile, risk_floor, db_scores)
                    for stock in candidates
                ],
                return_exceptions=True,
            )
        else:
            # Keine DB-Session oder ml_features leer (frische DB) → klassischer yfinance-Pfad
            _logger.info(
                "Discovery: Keine DB-Scores verfügbar — yfinance-Fallback für %d Kandidaten",
                len(candidates),
            )
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
        result = [stock for stock, _ in scored[:limit]]

        # Fallback: wenn yfinance alle Titel gefiltert hat (Timeout / Rate-Limit auf Render),
        # geben wir bekannte Titel + Top-Titel nach market_cap zurück anstatt leer.
        if not result:
            _logger.warning(
                "Discovery: Alle %d Kandidaten gefiltert (risk=%s, esg=%s, risk_floor=%.1f) "
                "— Fallback auf bekannte Titel + market_cap-Ranking",
                len(candidates),
                profile.risk_profile,
                profile.esg_preference,
                risk_floor,
            )
            pool = candidates if candidates else all_stocks
            known_first = sorted(
                pool,
                key=lambda s: (0 if s.ticker in known else 1, -(s.market_cap_chf or 0)),
            )
            result = known_first[:limit]

        return result
