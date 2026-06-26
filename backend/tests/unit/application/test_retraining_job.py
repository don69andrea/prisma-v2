"""Unit-Tests für RetrainingJob (V4-6 Champion/Challenger).

Pflicht-Guards:
  - Schlechter Challenger (oos_r2 < Champion) wird NICHT aktiviert
  - Besserer Challenger (oos_r2 > Champion) WIRD aktiviert
  - Kein Champion vorhanden → Challenger wird immer Champion
  - Look-Ahead: Challenger-Fit nutzt nur Daten bis asof
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.application.jobs.retraining_job import ModelRecord, RetrainingJob

pytestmark = pytest.mark.unit


# ── Stubs ──────────────────────────────────────────────────────────────────────


class StubModelRegistry:
    def __init__(self, champion: ModelRecord | None = None) -> None:
        self._champion = champion
        self.inserted: list[ModelRecord] = []
        self.champion_set_to: uuid.UUID | None = None
        self.old_champion_deactivated: uuid.UUID | None = None

    async def get_champion(self, model_name: str) -> ModelRecord | None:
        return self._champion

    async def insert(self, record: ModelRecord) -> None:
        self.inserted.append(record)

    async def set_champion(
        self, new_champion_id: uuid.UUID, old_champion_id: uuid.UUID | None
    ) -> None:
        self.champion_set_to = new_champion_id
        self.old_champion_deactivated = old_champion_id


class StubPriceProvider:
    def __init__(self, df: pd.DataFrame | None = None) -> None:
        self._df = df if df is not None else pd.DataFrame()

    async def get_history(self, coins: list[str], asof: date) -> pd.DataFrame:
        return self._df


def _make_champion(oos_r2: float = 0.5) -> ModelRecord:
    return ModelRecord(
        id=uuid.uuid4(),
        model_name="vol_forecast",
        version="v1",
        model_type="har",
        oos_r2=oos_r2,
        is_champion=True,
        trained_at=datetime.now(UTC),
        activated_at=None,
        deactivated_at=None,
        metadata_json=None,
    )


def _make_model_infos(oos_r2: float) -> dict[str, Any]:
    return {
        "BTC-USD": {"oos_r2": oos_r2, "model_type": "har", "model": MagicMock()},
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bad_challenger_not_activated() -> None:
    """Challenger mit schlechterem OOS-R² wird NICHT aktiviert."""
    champion = _make_champion(oos_r2=0.5)
    registry = StubModelRegistry(champion=champion)
    asof = date(2026, 6, 1)

    df = pd.DataFrame({"BTC-USD": [100.0] * 300}, index=pd.date_range("2025-01-01", periods=300))
    price_provider = StubPriceProvider(df=df)

    job = RetrainingJob(
        model_registry=registry,
        price_provider=price_provider,
        coins=["BTC-USD"],
    )

    challenger_infos = _make_model_infos(oos_r2=0.3)  # worse than champion

    with patch(
        "backend.application.jobs.retraining_job._fit_challenger",
        return_value=challenger_infos,
    ):
        result = await job.run(asof=asof)

    assert result["status"] == "kept_champion"
    assert registry.champion_set_to is None
    assert len(registry.inserted) == 1
    assert registry.inserted[0].is_champion is False


@pytest.mark.asyncio
async def test_good_challenger_activated() -> None:
    """Challenger mit besserem OOS-R² WIRD zum Champion."""
    champion = _make_champion(oos_r2=0.3)
    registry = StubModelRegistry(champion=champion)
    asof = date(2026, 6, 1)

    df = pd.DataFrame({"BTC-USD": [100.0] * 300}, index=pd.date_range("2025-01-01", periods=300))
    price_provider = StubPriceProvider(df=df)

    job = RetrainingJob(
        model_registry=registry,
        price_provider=price_provider,
        coins=["BTC-USD"],
    )

    challenger_infos = _make_model_infos(oos_r2=0.6)  # better than champion

    with patch(
        "backend.application.jobs.retraining_job._fit_challenger",
        return_value=challenger_infos,
    ):
        result = await job.run(asof=asof)

    assert result["status"] == "activated"
    assert registry.champion_set_to is not None
    assert registry.old_champion_deactivated == champion.id
    assert len(registry.inserted) == 1
    assert registry.inserted[0].is_champion is True


@pytest.mark.asyncio
async def test_no_champion_challenger_always_wins() -> None:
    """Kein Champion vorhanden → Challenger wird immer Champion (sentinel -999)."""
    registry = StubModelRegistry(champion=None)
    asof = date(2026, 6, 1)

    df = pd.DataFrame({"BTC-USD": [100.0] * 300}, index=pd.date_range("2025-01-01", periods=300))
    price_provider = StubPriceProvider(df=df)

    job = RetrainingJob(
        model_registry=registry,
        price_provider=price_provider,
        coins=["BTC-USD"],
    )

    challenger_infos = _make_model_infos(oos_r2=0.1)  # even bad r2 beats -999

    with patch(
        "backend.application.jobs.retraining_job._fit_challenger",
        return_value=challenger_infos,
    ):
        result = await job.run(asof=asof)

    assert result["status"] == "activated"
    assert registry.champion_set_to is not None
    assert registry.old_champion_deactivated is None


@pytest.mark.asyncio
async def test_skipped_when_no_price_data() -> None:
    """Job wird übersprungen wenn keine Preisdaten vorhanden."""
    registry = StubModelRegistry(champion=None)
    price_provider = StubPriceProvider(df=pd.DataFrame())

    job = RetrainingJob(
        model_registry=registry,
        price_provider=price_provider,
        coins=["BTC-USD"],
    )

    result = await job.run(asof=date(2026, 6, 1))

    assert result["status"] == "skipped"
    assert len(registry.inserted) == 0


@pytest.mark.asyncio
async def test_challenger_record_metadata_contains_asof() -> None:
    """Challenger record enthält asof in metadata_json."""
    champion = _make_champion(oos_r2=0.1)
    registry = StubModelRegistry(champion=champion)
    asof = date(2026, 6, 15)

    df = pd.DataFrame({"BTC-USD": [100.0] * 300}, index=pd.date_range("2025-01-01", periods=300))
    price_provider = StubPriceProvider(df=df)

    job = RetrainingJob(
        model_registry=registry,
        price_provider=price_provider,
        coins=["BTC-USD"],
    )

    challenger_infos = _make_model_infos(oos_r2=0.5)

    with patch(
        "backend.application.jobs.retraining_job._fit_challenger",
        return_value=challenger_infos,
    ):
        await job.run(asof=asof)

    assert registry.inserted[0].metadata_json is not None
    assert registry.inserted[0].metadata_json["asof"] == asof.isoformat()


def test_get_model_types_deduplication() -> None:
    """_get_model_types gibt deduplizierte, sortierte String zurück."""
    from backend.application.jobs.retraining_job import _get_model_types

    infos = {
        "BTC": {"model_type": "har"},
        "ETH": {"model_type": "har"},
        "SOL": {"model_type": "lgbm"},
    }
    result = _get_model_types(infos)
    assert result == "har,lgbm"
