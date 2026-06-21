"""Look-Ahead-Guard (A7.2).

Verhindert, dass Features im Backtest Daten aus der Zukunft verwenden.
Ein Feature darf an Tag t nur Daten bis einschliesslich Tag t-1 verwenden.

Verwendung:
    assert_no_lookahead(df, feature_cols=["ma_20", "rsi"], price_col="close")
    # Wirft LookAheadError, wenn eine Spalte zu stark mit dem aktuellen Preis korreliert.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["LookAheadError", "assert_no_lookahead"]

# Korrelations-Schwellenwert für Look-Ahead-Erkennung.
# Wenn |corr(feature, close)| > THRESHOLD → Look-Ahead-Verdacht.
_LOOKAHEAD_CORR_THRESHOLD = 0.999


class LookAheadError(ValueError):
    """Wird ausgelöst, wenn ein Feature-Vektor Daten aus der Zukunft verwendet.

    Erbt von ValueError für Abwärtskompatibilität mit bestehendem Exception-Handling.
    """


def assert_no_lookahead(
    df: pd.DataFrame,
    feature_cols: list[str],
    price_col: str = "close",
) -> None:
    """Prüft, ob feature_cols keinen Look-Ahead auf price_col enthalten.

    Methodik (deterministisch):
    Für jede feature_col wird die Pearson-Korrelation mit dem aktuellen Preis (lag=0)
    berechnet. Ist |corr| > 0.999 (d.h. Feature ist nahezu identisch mit Close),
    wird LookAheadError ausgelöst.

    Ein korrekt verschobenes Feature (close.shift(1)) hat corr < 1.0 mit dem
    aktuellen Close, da Shift eine 1-Perioden-Verzögerung einführt.

    NaN-Zeilen (z. B. erste Zeile nach shift(1)) werden ignoriert.

    Args:
        df: DataFrame mit mindestens price_col und allen feature_cols.
        feature_cols: Liste der zu prüfenden Feature-Spaltennamen.
        price_col: Referenzspalte für den aktuellen Preis (default: "close").

    Raises:
        LookAheadError: Wenn eine Feature-Spalte zu stark mit dem aktuellen Preis
                        korreliert und damit einen Look-Ahead indiziert.
        KeyError: Wenn price_col oder eine feature_col nicht in df vorhanden ist.
    """
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' nicht in DataFrame-Spalten: {list(df.columns)}")

    price = df[price_col]

    for col in feature_cols:
        if col not in df.columns:
            raise KeyError(f"feature_col '{col}' nicht in DataFrame-Spalten: {list(df.columns)}")

        feature = df[col]

        # Nur Zeilen ohne NaN in beiden Spalten für die Korrelationsberechnung
        mask = feature.notna() & price.notna()
        feat_clean = feature[mask]
        price_clean = price[mask]

        if len(feat_clean) < 2:
            # Zu wenige Datenpunkte — Korrelation nicht aussagekräftig, überspringen
            continue

        corr = feat_clean.corr(price_clean)

        if abs(corr) > _LOOKAHEAD_CORR_THRESHOLD:
            raise LookAheadError(
                f"Look-Ahead detected in column '{col}': "
                f"|corr(feature, {price_col})| = {abs(corr):.6f} > {_LOOKAHEAD_CORR_THRESHOLD}. "
                f"Feature muss um mindestens 1 Periode verschoben sein (z. B. {col} = close.shift(1))."
            )
