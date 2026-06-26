"""Unit-Tests für backend.application.backtest.guards (A7.2 — Look-Ahead-Guard).

RED-Phase: Tests müssen fehlschlagen, bis guards.py implementiert ist.
"""

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit


@pytest.fixture()
def price_series() -> pd.Series:
    """Synthetische Close-Preisserie mit 300 Datenpunkten."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 300)
    prices = 100.0 * (1 + returns).cumprod()
    idx = pd.date_range("2020-01-01", periods=300, freq="D")
    return pd.Series(prices, index=idx, name="close")


@pytest.fixture()
def df_with_close(price_series: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"close": price_series})


class TestLookAheadGuardPasses:
    def test_guard_passes_on_shifted_feature(self, df_with_close: pd.DataFrame) -> None:
        """Korrekt verschobenes Feature (shift(1)) soll keinen Fehler auslösen."""
        from backend.application.backtest.guards import assert_no_lookahead

        df = df_with_close.copy()
        df["ma_20"] = df["close"].rolling(20).mean().shift(1)
        df = df.dropna()

        # Kein Fehler erwartet
        assert_no_lookahead(df, feature_cols=["ma_20"], price_col="close")

    def test_guard_ignores_first_row_nan(self, df_with_close: pd.DataFrame) -> None:
        """NaN in Zeile 0 durch shift(1) ist normal und kein Look-Ahead."""
        from backend.application.backtest.guards import assert_no_lookahead

        df = df_with_close.copy()
        df["feature"] = df["close"].shift(1)  # NaN in row 0

        # Sollte nur die nicht-NaN-Zeilen prüfen — kein Fehler
        assert_no_lookahead(df, feature_cols=["feature"], price_col="close")

    def test_guard_passes_multiple_shifted_columns(self, df_with_close: pd.DataFrame) -> None:
        """Mehrere korrekt verschobene Spalten passieren alle ohne Fehler."""
        from backend.application.backtest.guards import assert_no_lookahead

        df = df_with_close.copy()
        df["f1"] = df["close"].shift(1)
        df["f2"] = df["close"].rolling(5).mean().shift(1)
        df["f3"] = df["close"].rolling(20).mean().shift(1)
        df = df.dropna()

        assert_no_lookahead(df, feature_cols=["f1", "f2", "f3"], price_col="close")


class TestLookAheadGuardRaises:
    def test_guard_raises_on_unshifted_feature(self, df_with_close: pd.DataFrame) -> None:
        """Direkte Verwendung von close (kein shift) muss LookAheadError auslösen."""
        from backend.application.backtest.guards import LookAheadError, assert_no_lookahead

        df = df_with_close.copy()
        df["feature"] = df["close"]  # identisch mit close -> Look-Ahead!

        with pytest.raises(LookAheadError):
            assert_no_lookahead(df, feature_cols=["feature"], price_col="close")

    def test_guard_names_bad_column_in_error(self, df_with_close: pd.DataFrame) -> None:
        """Fehlermeldung muss den Namen der problematischen Spalte enthalten."""
        from backend.application.backtest.guards import LookAheadError, assert_no_lookahead

        df = df_with_close.copy()
        df["bad_feature"] = df["close"]  # Look-Ahead

        with pytest.raises(LookAheadError, match="bad_feature"):
            assert_no_lookahead(df, feature_cols=["bad_feature"], price_col="close")

    def test_guard_checks_multiple_columns_names_bad_one(self, df_with_close: pd.DataFrame) -> None:
        """Bei 3 Spalten (1 unshifted) muss der Guard die fehlerhafte Spalte benennen."""
        from backend.application.backtest.guards import LookAheadError, assert_no_lookahead

        df = df_with_close.copy()
        df["ok1"] = df["close"].shift(1)
        df["bad_col"] = df["close"]  # Look-Ahead!
        df["ok2"] = df["close"].rolling(5).mean().shift(1)
        df = df.dropna()

        with pytest.raises(LookAheadError, match="bad_col"):
            assert_no_lookahead(df, feature_cols=["ok1", "bad_col", "ok2"], price_col="close")

    def test_lookahad_error_is_value_error_subclass(self, df_with_close: pd.DataFrame) -> None:
        """LookAheadError muss von ValueError erben (Abwärtskompatibilität)."""
        from backend.application.backtest.guards import LookAheadError

        assert issubclass(LookAheadError, ValueError)
