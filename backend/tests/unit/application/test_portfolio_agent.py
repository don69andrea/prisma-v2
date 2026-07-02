"""Unit-Tests für PortfolioAgent."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from backend.application.agents.portfolio_agent import (
    _PRICE_DAYS_MEAN_VARIANCE,
    PortfolioAgent,
    _mean_variance,
    _normalize_weights,
    _risk_parity,
    _score_weighted,
)
from backend.domain.entities.swiss_stock import SwissStock


def _mock_rankings(
    tickers: list[str], scores: list[float] | None = None
) -> list[dict[str, object]]:
    scores = scores or [80.0, 70.0, 60.0, 55.0, 50.0]
    return [
        {"ticker": t, "total_rank": i + 1, "weighted_avg": scores[i] if i < len(scores) else 50.0}
        for i, t in enumerate(tickers)
    ]


def _mock_swiss_stock(ticker: str, market_cap: int = 200_000_000) -> SwissStock:
    return SwissStock(
        id=uuid4(),
        ticker=ticker,
        isin="CH0012221716",
        name=ticker,
        exchange="XSWX",
        sector=None,
        market_cap_chf=Decimal(market_cap),
    )


def _price_df(n: int = 35) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n)
    closes = 100 + np.cumsum(np.random.randn(n))
    return pd.DataFrame({"Close": closes}, index=dates)


# --- _normalize_weights ---


def test_normalize_weights_sums_to_one() -> None:
    raw = {"A": 3.0, "B": 1.0, "C": 1.0}
    result = _normalize_weights(raw)
    assert abs(sum(result.values()) - 1.0) < 1e-6


def test_normalize_weights_clamps_max() -> None:
    raw = {"A": 100.0, "B": 1.0, "C": 1.0}
    result = _normalize_weights(raw)
    assert result["A"] <= 0.40 + 1e-6
    assert abs(sum(result.values()) - 1.0) < 1e-6


def test_normalize_weights_clamps_min() -> None:
    raw = {"A": 0.001, "B": 100.0}
    result = _normalize_weights(raw)
    assert result["A"] >= 0.05 - 1e-6


def test_normalize_weights_empty() -> None:
    assert _normalize_weights({}) == {}


# --- _score_weighted ---


def test_score_weighted_higher_score_higher_weight() -> None:
    picks = [
        {"ticker": "NESN", "quant_score": 80.0},
        {"ticker": "NOVN", "quant_score": 40.0},
        {"ticker": "ROG", "quant_score": 30.0},
    ]
    result = _score_weighted(picks)
    assert result["NESN"] > result["NOVN"]
    assert result["NOVN"] > result["ROG"]
    assert abs(sum(result.values()) - 1.0) < 1e-6


# --- _risk_parity ---


def test_risk_parity_low_vol_higher_weight() -> None:
    low_vol = pd.DataFrame({"Close": [100.0 + i * 0.01 for i in range(35)]})
    high_vol = pd.DataFrame({"Close": [100.0 + (i % 3 - 1) * 5.0 for i in range(35)]})
    mid_vol = pd.DataFrame({"Close": [100.0 + (i % 2) * 1.0 for i in range(35)]})
    picks = [
        {"ticker": "A", "quant_score": 60.0},
        {"ticker": "B", "quant_score": 60.0},
        {"ticker": "C", "quant_score": 60.0},
    ]
    result = _risk_parity(picks, {"A": low_vol, "B": high_vol, "C": mid_vol})
    assert result["A"] > result["B"]
    assert abs(sum(result.values()) - 1.0) < 1e-6


def test_risk_parity_missing_history_uses_fallback() -> None:
    picks = [{"ticker": "A", "quant_score": 60.0}, {"ticker": "B", "quant_score": 60.0}]
    result = _risk_parity(picks, {})
    assert abs(sum(result.values()) - 1.0) < 1e-6


# --- PortfolioAgent.allocate ---


@pytest.mark.asyncio
async def test_allocate_score_weighted_returns_allocation() -> None:
    tickers = ["NESN", "NOVN", "ROG"]
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(tickers)
    repo = AsyncMock()
    repo.get_by_ticker.return_value = _mock_swiss_stock("NESN")

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        llm_client=None,
    )
    result = await agent.allocate(run_id=uuid4(), top_n=3, method="score_weighted")

    assert len(result.positions) == 3
    assert result.method == "score_weighted"
    total = sum(p.weight for p in result.positions)
    assert abs(total - 1.0) < 1e-4
    assert result.positions[0].weight >= result.positions[-1].weight


@pytest.mark.asyncio
async def test_allocate_eligible_only_filters() -> None:
    tickers = ["NESN", "NOVN", "TINY"]
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(tickers)

    repo = AsyncMock()

    async def _get(ticker: str) -> SwissStock | None:
        if ticker == "TINY":
            return _mock_swiss_stock("TINY", market_cap=50_000_000)
        return _mock_swiss_stock(ticker)

    repo.get_by_ticker.side_effect = _get

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        llm_client=None,
    )
    result = await agent.allocate(run_id=uuid4(), top_n=3, eligible_only=True)

    tickers_in_result = {p.ticker for p in result.positions}
    assert "TINY" not in tickers_in_result


@pytest.mark.asyncio
async def test_allocate_risk_parity_uses_yfinance() -> None:
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(["NESN", "NOVN"])
    repo = AsyncMock()
    repo.get_by_ticker.return_value = _mock_swiss_stock("NESN")
    yf = AsyncMock()
    yf.get_price_history.return_value = _price_df()

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        yfinance_adapter=yf,
        llm_client=None,
    )
    result = await agent.allocate(run_id=uuid4(), top_n=2, method="risk_parity")

    assert result.method == "risk_parity"
    assert len(result.positions) == 2
    assert abs(sum(p.weight for p in result.positions) - 1.0) < 1e-4


def _price_df_full(n: int = 300, seed: int = 0, vol: float = 0.01) -> pd.DataFrame:
    """Preishistorie mit genügend Handelstagen für Mean-Variance (>= 30)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-01", periods=n)
    returns = rng.normal(0.0005, vol, size=n)
    closes = 100.0 * np.cumprod(1.0 + returns)
    return pd.DataFrame({"Close": closes}, index=dates)


# --- W3-C-03: Mean-Variance läuft wirklich, degradiert nicht still ---


def test_mean_variance_runs_markowitz_with_enough_data() -> None:
    """Mit >= 30 Handelstagen nutzt mean_variance echt Markowitz (kein Fallback)."""
    picks = [
        {"ticker": "A", "quant_score": 60.0},
        {"ticker": "B", "quant_score": 60.0},
        {"ticker": "C", "quant_score": 60.0},
    ]
    histories = {
        "A": _price_df_full(n=300, seed=1, vol=0.005),  # low vol
        "B": _price_df_full(n=300, seed=2, vol=0.03),  # high vol
        "C": _price_df_full(n=300, seed=3, vol=0.015),  # mid vol
    }

    # Wenn _mean_variance still auf Risk-Parity zurückfiele, würde dieser Mock
    # aufgerufen und der Test bräche mit AssertionError -> beweist echten Pfad.
    def _fail_risk_parity(*_args: object, **_kwargs: object) -> dict[str, float]:
        raise AssertionError("mean_variance ist unerwartet auf Risk-Parity zurückgefallen")

    with patch(
        "backend.application.agents.portfolio_agent._risk_parity",
        side_effect=_fail_risk_parity,
    ):
        result = _mean_variance(picks, histories)

    assert set(result) == {"A", "B", "C"}
    assert abs(sum(result.values()) - 1.0) < 1e-6
    for w in result.values():
        assert 0.05 - 1e-6 <= w <= 0.40 + 1e-6


@pytest.mark.asyncio
async def test_allocate_mean_variance_no_silent_degradation() -> None:
    """allocate(method='mean_variance') lädt genug Historie und nutzt echt Markowitz."""
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(["NESN", "NOVN", "ROG"])
    repo = AsyncMock()
    repo.get_by_ticker.return_value = _mock_swiss_stock("NESN")

    seeds = iter([11, 22, 33])
    vols = iter([0.006, 0.028, 0.014])
    yf = AsyncMock()

    async def _hist(ticker: str, days: int) -> pd.DataFrame:
        # Beweist, dass genug Kalendertage angefragt werden (>= 250 Handelstage).
        assert days == _PRICE_DAYS_MEAN_VARIANCE
        return _price_df_full(n=300, seed=next(seeds), vol=next(vols))

    yf.get_price_history.side_effect = _hist

    def _fail_risk_parity(*_args: object, **_kwargs: object) -> dict[str, float]:
        raise AssertionError("mean_variance darf nicht still auf Risk-Parity degradieren")

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        yfinance_adapter=yf,
        llm_client=None,
    )

    with patch(
        "backend.application.agents.portfolio_agent._risk_parity",
        side_effect=_fail_risk_parity,
    ):
        result = await agent.allocate(run_id=uuid4(), top_n=3, method="mean_variance")

    assert result.method == "mean_variance"
    assert len(result.positions) == 3
    assert abs(sum(p.weight for p in result.positions) - 1.0) < 1e-4
    # Fenster muss >= 30 Handelstage liefern (Kern des W3-C-03-Bugs).
    assert _PRICE_DAYS_MEAN_VARIANCE >= 365


@pytest.mark.asyncio
async def test_allocate_risk_parity_uses_short_window() -> None:
    """Risk-Parity behält das kurze 30d-Fenster (Fenster an Methode gekoppelt)."""
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(["NESN", "NOVN"])
    repo = AsyncMock()
    repo.get_by_ticker.return_value = _mock_swiss_stock("NESN")

    seen_days: list[int] = []

    async def _hist(ticker: str, days: int) -> pd.DataFrame:
        seen_days.append(days)
        return _price_df()

    yf = AsyncMock()
    yf.get_price_history.side_effect = _hist

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        yfinance_adapter=yf,
        llm_client=None,
    )
    await agent.allocate(run_id=uuid4(), top_n=2, method="risk_parity")

    assert seen_days and all(d < _PRICE_DAYS_MEAN_VARIANCE for d in seen_days)


@pytest.mark.asyncio
async def test_allocate_llm_narrative_parsed() -> None:
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(["NESN", "NOVN"])
    repo = AsyncMock()
    repo.get_by_ticker.return_value = _mock_swiss_stock("NESN")

    llm = AsyncMock()
    llm_resp = MagicMock()
    llm_resp.content = [
        MagicMock(
            text=json.dumps(
                {
                    "overall": "Solide Allokation mit Fokus auf defensive Schweizer Titel.",
                    "positions": {
                        "NESN": "Marktführer Nahrungsmittel.",
                        "NOVN": "Pharma-Exposure.",
                    },
                }
            )
        )
    ]
    llm.messages_create.return_value = llm_resp

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        llm_client=llm,
    )
    result = await agent.allocate(run_id=uuid4(), top_n=2)

    assert "Solide" in result.overall_rationale_de
    assert any("Marktführer" in p.rationale_de for p in result.positions)


@pytest.mark.asyncio
async def test_allocate_llm_failure_uses_fallback() -> None:
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(["NESN"])
    repo = AsyncMock()
    repo.get_by_ticker.return_value = _mock_swiss_stock("NESN")

    llm = AsyncMock()
    llm.messages_create.side_effect = RuntimeError("LLM down")

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        llm_client=llm,
    )
    result = await agent.allocate(run_id=uuid4(), top_n=1)

    assert result.overall_rationale_de != ""
    assert len(result.positions) == 1


@pytest.mark.asyncio
async def test_allocate_top_n_capped_by_available() -> None:
    run_service = AsyncMock()
    run_service.get_rankings.return_value = _mock_rankings(["NESN", "NOVN"])
    repo = AsyncMock()
    repo.get_by_ticker.return_value = _mock_swiss_stock("NESN")

    agent = PortfolioAgent(
        ranking_run_service=run_service,
        swiss_stock_repo=repo,
        llm_client=None,
    )
    result = await agent.allocate(run_id=uuid4(), top_n=10)

    assert len(result.positions) == 2
