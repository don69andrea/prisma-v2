"""Unit-Tests für LangfristScoreCalculator."""

from decimal import Decimal

import pytest

from backend.domain.services.langfrist_score_calculator import LangfristScoreCalculator
from backend.domain.value_objects.swiss_fundamentals import SwissFundamentals

pytestmark = pytest.mark.unit

_calc = LangfristScoreCalculator()


def _fundamentals(
    market_cap_chf: Decimal | None = Decimal("50_000_000_000"),
    pe_ratio: float | None = 15.0,
    pb_ratio: float | None = 2.5,
    dividend_yield: float | None = 0.035,
    eps_chf: float | None = 5.0,
) -> SwissFundamentals:
    return SwissFundamentals(
        market_cap_chf=market_cap_chf,
        pe_ratio=pe_ratio,
        pb_ratio=pb_ratio,
        dividend_yield=dividend_yield,
        eps_chf=eps_chf,
    )


class TestLangfristScoreCalculator:
    def test_ideal_stock_scores_high(self) -> None:
        score = _calc.calculate("NESN", _fundamentals(), annualized_volatility=0.10)
        assert score.value >= 8.0
        assert score.ticker == "NESN"

    def test_weak_stock_scores_low(self) -> None:
        score = _calc.calculate(
            "WEAK",
            _fundamentals(
                market_cap_chf=Decimal("50_000_000"),
                dividend_yield=0.0,
                eps_chf=-1.0,
            ),
            annualized_volatility=0.50,
        )
        assert score.value <= 4.0

    def test_components_present(self) -> None:
        score = _calc.calculate("TEST", _fundamentals())
        assert "dividende" in score.components
        assert "bilanz" in score.components
        assert "stabilitaet" in score.components
        assert "marktkapita" in score.components

    def test_all_none_fundamentals_returns_neutral(self) -> None:
        score = _calc.calculate(
            "TEST",
            SwissFundamentals(
                market_cap_chf=None,
                pe_ratio=None,
                pb_ratio=None,
                dividend_yield=None,
                eps_chf=None,
            ),
            annualized_volatility=None,
        )
        assert 3.0 <= score.value <= 7.0

    def test_value_clamped_to_0_10(self) -> None:
        score = _calc.calculate("X", _fundamentals(), annualized_volatility=0.05)
        assert 0.0 <= score.value <= 10.0

    def test_high_dividend_increases_score(self) -> None:
        low = _calc.calculate("A", _fundamentals(dividend_yield=0.005), annualized_volatility=0.20)
        high = _calc.calculate("B", _fundamentals(dividend_yield=0.05), annualized_volatility=0.20)
        assert high.value > low.value

    def test_high_volatility_decreases_score(self) -> None:
        stable = _calc.calculate("A", _fundamentals(), annualized_volatility=0.10)
        volatile = _calc.calculate("B", _fundamentals(), annualized_volatility=0.50)
        assert stable.value > volatile.value

    def test_explanation_not_empty(self) -> None:
        score = _calc.calculate("NESN", _fundamentals(), annualized_volatility=0.10)
        assert len(score.explanation) > 0

    def test_langfrist_score_value_invalid_raises(self) -> None:
        from backend.domain.value_objects.langfrist_score import LangfristScore

        with pytest.raises(ValueError, match="zwischen 0 und 10"):
            LangfristScore(ticker="X", value=11.5, components={}, explanation="")
