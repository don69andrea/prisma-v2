"""Unit tests for ETL pipeline — normalize + validate helpers."""

from __future__ import annotations

import datetime

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


# ── normalize_ohlcv ──────────────────────────────────────────────────────────


def test_normalize_ohlcv_basic():
    from backend.application.pipeline.etl import normalize_ohlcv

    df = pd.DataFrame(
        {"Open": [100.0], "High": [105.0], "Low": [98.0], "Close": [103.0], "Volume": [10000]},
        index=pd.to_datetime(["2024-01-02"]),
    )
    rows = normalize_ohlcv(df, ticker="NESN", source="yfinance", currency="CHF")
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "NESN"
    assert r["currency"] == "CHF"
    assert r["source"] == "yfinance"
    assert r["close"] == 103.0
    assert r["date"] == datetime.date(2024, 1, 2)


def test_normalize_ohlcv_lowercase_columns():
    """Seed DataFrames may already have lowercase columns."""
    from backend.application.pipeline.etl import normalize_ohlcv

    df = pd.DataFrame(
        {"open": [50.0], "high": [52.0], "low": [49.0], "close": [51.0], "volume": [500]},
        index=pd.to_datetime(["2024-03-01"]),
    )
    rows = normalize_ohlcv(df, ticker="NOVN", source="yfinance", currency="CHF")
    assert rows[0]["open"] == 50.0


def test_normalize_ohlcv_missing_volume():
    from backend.application.pipeline.etl import normalize_ohlcv

    df = pd.DataFrame(
        {"Open": [100.0], "High": [101.0], "Low": [99.0], "Close": [100.5]},
        index=pd.to_datetime(["2024-01-02"]),
    )
    rows = normalize_ohlcv(df, ticker="NESN", source="yfinance", currency="CHF")
    assert rows[0]["volume"] is None


# ── validate_ohlcv ───────────────────────────────────────────────────────────


def test_validate_ohlcv_drops_zero_price():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {
            "ticker": "NESN",
            "date": datetime.date(2024, 1, 2),
            "open": 0.0,
            "high": 105.0,
            "low": 0.0,
            "close": 103.0,
        },
        {
            "ticker": "NESN",
            "date": datetime.date(2024, 1, 3),
            "open": 103.0,
            "high": 104.0,
            "low": 102.0,
            "close": 103.5,
        },
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history")
    assert len(clean) == 1
    assert rep.dropped == 1


def test_validate_ohlcv_drops_high_below_low():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {
            "ticker": "NESN",
            "date": datetime.date(2024, 1, 2),
            "open": 100.0,
            "high": 95.0,
            "low": 98.0,
            "close": 99.0,
        },
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history")
    assert len(clean) == 0
    assert rep.dropped == 1


def test_validate_ohlcv_flags_spike():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {
            "ticker": "NESN",
            "date": datetime.date(2024, 1, 2),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
        },
        {
            "ticker": "NESN",
            "date": datetime.date(2024, 1, 3),
            "open": 200.0,
            "high": 201.0,
            "low": 199.0,
            "close": 200.0,
        },
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history", spike_pct=0.25)
    assert len(clean) == 2
    assert len(rep.spikes) == 1


def test_validate_ohlcv_clean_passthrough():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {
            "ticker": "NESN",
            "date": datetime.date(2024, 1, 2),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
        },
        {
            "ticker": "NESN",
            "date": datetime.date(2024, 1, 3),
            "open": 100.5,
            "high": 102.0,
            "low": 100.0,
            "close": 101.0,
        },
    ]
    clean, rep = validate_ohlcv(rows, table="stock_price_history")
    assert rep.ok
    assert rep.dropped == 0
    assert len(clean) == 2


def test_validation_report_ok_false_when_all_dropped():
    from backend.application.pipeline.etl import validate_ohlcv

    rows = [
        {
            "ticker": "X",
            "date": datetime.date(2024, 1, 2),
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
        },
    ]
    _, rep = validate_ohlcv(rows, table="stock_price_history")
    assert not rep.ok
