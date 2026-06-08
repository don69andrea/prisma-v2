"""Tests für SwissQuantScorer — Swiss-kalibrierte Scoring-Logik."""

from decimal import Decimal

import pytest

from backend.domain.services.swiss_quant_scorer import SwissQuantScorer
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals
from backend.domain.value_objects.swiss_quant_score import SwissQuantScore

pytestmark = pytest.mark.unit

_scorer = SwissQuantScorer()


def _fund(pe=None, pb=None, div=None, eps=None) -> SwissFundamentals:
    return SwissFundamentals(
        market_cap_chf=Decimal("100000000000"),
        pe_ratio=pe,
        pb_ratio=pb,
        dividend_yield=div,
        eps_chf=eps,
    )


def test_score_returns_swiss_quant_score_instance() -> None:
    result = _scorer.score("NESN", _fund(pe=18.0, pb=3.0, div=0.027, eps=5.0))
    assert isinstance(result, SwissQuantScore)
    assert result.ticker == "NESN"


def test_cheap_stock_gets_buy_signal() -> None:
    # P/E 12 → score 100, P/B 1.5 → 100, div 3.5% → 100, eps positive → 100
    result = _scorer.score("NESN", _fund(pe=12.0, pb=1.5, div=0.035, eps=8.0))
    assert result.signal == "BUY"
    assert result.composite >= 70


def test_expensive_stock_gets_watch_signal() -> None:
    # P/E 30 → score 25, P/B 8 → 25, div 0.5% → 25, eps negative → 0
    result = _scorer.score("SOME", _fund(pe=30.0, pb=8.0, div=0.005, eps=-1.0))
    assert result.signal == "WATCH"
    assert result.composite < 40


def test_medium_stock_gets_hold_signal() -> None:
    # P/E 22 → 50, P/B 4.5 → 50, div 1.5% → 50, eps positive → 100
    result = _scorer.score("ABBN", _fund(pe=22.0, pb=4.5, div=0.015, eps=2.0))
    assert result.signal == "HOLD"
    assert 40 <= result.composite < 70


def test_none_fundamentals_get_neutral_scores() -> None:
    result = _scorer.score("UNKN", _fund())
    assert result.value_score == 50.0
    assert result.income_score == 50.0
    assert result.quality_score == 50.0


def test_pe_bands_score_correctly() -> None:
    assert (
        _scorer.score("A", _fund(pe=10.0)).value_score
        > _scorer.score("B", _fund(pe=28.0)).value_score
    )


def test_dividend_yield_bands_score_correctly() -> None:
    high_div = _scorer.score("A", _fund(div=0.04))
    low_div = _scorer.score("B", _fund(div=0.005))
    assert high_div.income_score > low_div.income_score


def test_negative_eps_scores_zero_quality() -> None:
    result = _scorer.score("BAD", _fund(eps=-2.0))
    assert result.quality_score == 0.0
