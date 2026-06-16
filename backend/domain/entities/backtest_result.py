"""BacktestResult-Entity — Ergebnis eines quantitativen Portfolio-Backtests."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PortfolioMetrics(BaseModel):
    """Kennzahlen für ein simuliertes Portfolio über den Backtest-Zeitraum."""

    model_config = {"frozen": True}

    total_return: Decimal
    cagr: Decimal
    annual_vol: Decimal
    sharpe: Decimal
    max_drawdown: Decimal


class BacktestSeries(BaseModel):
    """Zeitreihendaten der drei Portfolios (PRISMA, Universum, Benchmark)."""

    model_config = {"frozen": True}

    dates: list[date]
    prisma: list[Decimal]
    universe: list[Decimal]
    benchmark: list[Decimal]


class BacktestResult(BaseModel):
    """Aggregat für einen abgeschlossenen Backtest-Durchlauf."""

    model_config = {"frozen": True}

    id: UUID
    model_run_id: UUID
    start_date: date
    end_date: date
    # Tatsaechlich abgedecktes Fenster der zugrunde liegenden Marktdaten.
    # Der Marktdaten-Provider liefert maximal die letzten 504 Handelstage —
    # bei einem `start_date` weiter in der Vergangenheit wird das Fenster
    # stillschweigend gekuerzt. Diese Felder machen das tatsaechliche
    # Fenster fuer Konsumenten (z.B. Frontend) transparent.
    # Bug: F-BTCR-1 / W-11.
    actual_start_date: date
    actual_end_date: date
    top_n: int
    benchmark_ticker: str
    prisma_metrics: PortfolioMetrics
    universe_metrics: PortfolioMetrics
    benchmark_metrics: PortfolioMetrics
    series: BacktestSeries
    created_at: datetime
