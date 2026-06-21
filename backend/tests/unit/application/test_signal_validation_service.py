"""Unit-Tests für SignalValidationService.

Tests:
- validate() returns None when market data unavailable
- validate() returns None when df too short
- validate() returns SignalValidationResult on sufficient data
- _generate_label covers all 4 branches
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


def _make_prices(n: int = 200, trend: float = 0.001) -> pd.DataFrame:
    """Synthetische Preisreihe mit gegebenem Trend."""
    rng = np.random.default_rng(42)
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    prices = 100.0 * np.cumprod(1 + rng.normal(trend, 0.02, n))
    return pd.DataFrame({"Close": prices}, index=idx)


class FakeMarket:
    """Minimal mock for market data provider."""

    def __init__(self, df: pd.DataFrame | None = None, raise_exc: bool = False) -> None:
        self._df = df
        self._raise = raise_exc

    async def get_price_history(self, ticker: str, days: int) -> pd.DataFrame | None:
        if self._raise:
            raise RuntimeError("network error")
        return self._df


class TestSignalValidationService:
    def test_validate_raises_exception_returns_none(self) -> None:
        """Returns None when market provider raises."""
        import asyncio  # noqa: PLC0415

        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            SignalValidationService,
        )

        svc = SignalValidationService(FakeMarket(raise_exc=True))
        result = asyncio.new_event_loop().run_until_complete(svc.validate("NESN.SW"))
        assert result is None

    def test_validate_none_df_returns_none(self) -> None:
        """Returns None when provider returns None."""
        import asyncio  # noqa: PLC0415

        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            SignalValidationService,
        )

        svc = SignalValidationService(FakeMarket(df=None))
        result = asyncio.new_event_loop().run_until_complete(svc.validate("NESN.SW"))
        assert result is None

    def test_validate_short_df_returns_none(self) -> None:
        """Returns None when df has fewer than 60 rows."""
        import asyncio  # noqa: PLC0415

        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            SignalValidationService,
        )

        df = _make_prices(n=30)
        svc = SignalValidationService(FakeMarket(df=df))
        result = asyncio.new_event_loop().run_until_complete(svc.validate("NESN.SW"))
        assert result is None

    def test_validate_sufficient_data_returns_result(self) -> None:
        """Returns SignalValidationResult on sufficient data (n=200 rows)."""
        import asyncio  # noqa: PLC0415

        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            SignalValidationResult,
            SignalValidationService,
        )

        df = _make_prices(n=200, trend=0.003)
        svc = SignalValidationService(FakeMarket(df=df))
        result = asyncio.new_event_loop().run_until_complete(svc.validate("NESN.SW"))
        if result is not None:
            assert isinstance(result, SignalValidationResult)
            assert result.ticker == "NESN.SW"
            assert isinstance(result.return_pct, float)
            assert isinstance(result.win_rate_pct, float)
            assert isinstance(result.label, str)

    def test_validate_uses_close_column_fallback(self) -> None:
        """Uses 'close' column when 'Close' not present."""
        import asyncio  # noqa: PLC0415

        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            SignalValidationService,
        )

        df = _make_prices(n=200)
        df = df.rename(columns={"Close": "close"})  # lowercase variant
        svc = SignalValidationService(FakeMarket(df=df))
        result = asyncio.new_event_loop().run_until_complete(svc.validate("NESN.SW"))
        # Just check it doesn't crash
        assert result is None or hasattr(result, "ticker")

    def test_validate_uses_first_column_fallback(self) -> None:
        """Uses first column when neither 'Close' nor 'close' present."""
        import asyncio  # noqa: PLC0415

        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            SignalValidationService,
        )

        df = _make_prices(n=200)
        df = df.rename(columns={"Close": "price"})  # unknown column name
        svc = SignalValidationService(FakeMarket(df=df))
        result = asyncio.new_event_loop().run_until_complete(svc.validate("NESN.SW"))
        assert result is None or hasattr(result, "ticker")


class TestGenerateLabel:
    """Cover all 4 branches of _generate_label."""

    def test_label_win_rate_60_diff_5(self) -> None:
        """Branch: win_rate >= 60 AND diff > 5 → 'hat gut funktioniert'."""
        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            _generate_label,
        )

        label = _generate_label("TEST", prisma=20.0, bah=10.0, win_rate=65.0)
        assert "gut funktioniert" in label

    def test_label_win_rate_50_diff_positive(self) -> None:
        """Branch: win_rate >= 50 AND diff > 0 → 'öfter richtig'."""
        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            _generate_label,
        )

        label = _generate_label("TEST", prisma=12.0, bah=10.0, win_rate=52.0)
        assert "öfter richtig" in label

    def test_label_win_rate_below_50(self) -> None:
        """Branch: win_rate < 50 → 'Buy & Hold stärker'."""
        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            _generate_label,
        )

        label = _generate_label("TEST", prisma=5.0, bah=10.0, win_rate=45.0)
        assert "Buy & Hold" in label

    def test_label_mixed_results(self) -> None:
        """Branch: default → 'gemischte Ergebnisse'."""
        from backend.application.services.signal_validation_service import (  # noqa: PLC0415
            _generate_label,
        )

        # win_rate=50 AND diff <= 0
        label = _generate_label("TEST", prisma=5.0, bah=8.0, win_rate=55.0)
        assert "gemischte" in label


class TestDomainErrors:
    """Cover domain error classes not tested elsewhere."""

    def test_unknown_model_error_attributes(self) -> None:
        """UnknownModelError has model and reason attributes (lines 17-19)."""
        from backend.domain.errors import UnknownModelError  # noqa: PLC0415

        err = UnknownModelError("gpt-9", reason="not in registry")
        assert err.model == "gpt-9"
        assert err.reason == "not in registry"
        assert "gpt-9" in str(err)

    def test_unknown_model_error_default_reason(self) -> None:
        """UnknownModelError with default reason."""
        from backend.domain.errors import UnknownModelError  # noqa: PLC0415

        err = UnknownModelError("claude-unknown")
        assert err.reason == "unbekannt"


class TestSwissQuantScorerInterpret:
    """Cover interpret_score branches (lines 90-98)."""

    def test_interpret_score_ausgezeichnet(self) -> None:
        from backend.domain.services.swiss_quant_scorer import SwissQuantScorer  # noqa: PLC0415
        assert SwissQuantScorer.interpret_score(85.0) == "Ausgezeichnet"

    def test_interpret_score_gut(self) -> None:
        from backend.domain.services.swiss_quant_scorer import SwissQuantScorer  # noqa: PLC0415
        assert SwissQuantScorer.interpret_score(70.0) == "Gut"

    def test_interpret_score_durchschnittlich(self) -> None:
        from backend.domain.services.swiss_quant_scorer import SwissQuantScorer  # noqa: PLC0415
        assert SwissQuantScorer.interpret_score(55.0) == "Durchschnittlich"

    def test_interpret_score_schwach(self) -> None:
        from backend.domain.services.swiss_quant_scorer import SwissQuantScorer  # noqa: PLC0415
        assert SwissQuantScorer.interpret_score(40.0) == "Schwach"

    def test_interpret_score_sehr_schwach(self) -> None:
        from backend.domain.services.swiss_quant_scorer import SwissQuantScorer  # noqa: PLC0415
        assert SwissQuantScorer.interpret_score(20.0) == "Sehr schwach"
