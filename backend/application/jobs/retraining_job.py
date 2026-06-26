"""RetrainingJob: periodischer Vol-Modell-Refit mit Champion/Challenger.

Prinzip:
  1. Fit Challenger auf expandierendem Fenster bis asof (nur Vergangenheit).
  2. Vergleiche Challenger.oos_r2 vs. aktueller Champion.oos_r2 im strikten OOS.
  3. Nur wenn Challenger strikt besser ist → aktivieren (new champion).
  4. Jeder Wechsel wird in model_registry protokolliert.

Kein Performance-Chasing: Parameter sind festgelegt und werden nicht optimiert.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

_logger = logging.getLogger(__name__)

_MODEL_NAME = "vol_forecast"
_MIN_TRAIN = 252
_STEP = 21


@dataclass
class ModelRecord:
    id: uuid.UUID
    model_name: str
    version: str
    model_type: str
    oos_r2: float
    is_champion: bool
    trained_at: datetime
    activated_at: datetime | None
    deactivated_at: datetime | None
    metadata_json: dict[str, Any] | None


class ModelRegistry(Protocol):
    async def get_champion(self, model_name: str) -> ModelRecord | None: ...

    async def insert(self, record: ModelRecord) -> None: ...

    async def set_champion(
        self, new_champion_id: uuid.UUID, old_champion_id: uuid.UUID | None
    ) -> None: ...


class PriceProvider(Protocol):
    async def get_history(self, coins: list[str], asof: date) -> Any: ...


def _fit_challenger(close_df: Any, asof: date) -> dict[str, Any]:
    """Fit Vol-Modell auf expandierendem Fenster bis asof."""
    import pandas as pd

    from backend.application.signals.vol_forecast import fit_walkforward

    asof_ts = pd.Timestamp(asof)
    close_filtered = close_df[close_df.index <= asof_ts]
    return fit_walkforward(close_filtered, min_train=_MIN_TRAIN, step=_STEP)


def _get_model_types(model_infos: dict[str, Any]) -> str:
    types = {v.get("model_type", "har") for v in model_infos.values()}
    return ",".join(sorted(types))


class RetrainingJob:
    """Periodischer Vol-Modell-Refit (monatlich)."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        price_provider: PriceProvider,
        coins: list[str],
    ) -> None:
        self._registry = model_registry
        self._prices = price_provider
        self._coins = coins

    async def run(self, asof: date) -> dict[str, Any]:
        close_df = await self._prices.get_history(self._coins, asof)
        if close_df is None or close_df.empty:
            _logger.warning("Keine Preisdaten für Retraining verfügbar")
            return {"status": "skipped", "reason": "no_data"}

        model_infos: dict[str, Any] = await asyncio.to_thread(_fit_challenger, close_df, asof)
        avg_oos_r2 = float(
            sum(v["oos_r2"] for v in model_infos.values()) / max(len(model_infos), 1)
        )

        champion = await self._registry.get_champion(_MODEL_NAME)
        champion_r2 = champion.oos_r2 if champion is not None else -999.0

        version = f"v{asof.strftime('%Y%m%d')}"
        now = datetime.now(tz=UTC)
        challenger_id = uuid.uuid4()

        should_activate = avg_oos_r2 > champion_r2

        challenger_record = ModelRecord(
            id=challenger_id,
            model_name=_MODEL_NAME,
            version=version,
            model_type=_get_model_types(model_infos),
            oos_r2=avg_oos_r2,
            is_champion=should_activate,
            trained_at=now,
            activated_at=now if should_activate else None,
            deactivated_at=None,
            metadata_json={
                "asof": asof.isoformat(),
                "n_coins": len(model_infos),
                "coin_r2s": {c: v["oos_r2"] for c, v in model_infos.items()},
                "champion_r2_before": champion_r2,
            },
        )
        await self._registry.insert(challenger_record)

        if should_activate:
            old_id = champion.id if champion is not None else None
            await self._registry.set_champion(challenger_id, old_id)
            _logger.info(
                "Champion geändert: %s → %s (OOS-R² %.4f → %.4f)",
                champion.version if champion else "none",
                version,
                champion_r2,
                avg_oos_r2,
            )
            return {
                "status": "activated",
                "new_version": version,
                "challenger_r2": avg_oos_r2,
                "champion_r2_before": champion_r2,
            }
        else:
            _logger.info(
                "Challenger %s (OOS-R² %.4f) schlägt Champion nicht (%.4f) → kein Wechsel",
                version,
                avg_oos_r2,
                champion_r2,
            )
            return {
                "status": "kept_champion",
                "challenger_r2": avg_oos_r2,
                "champion_r2": champion_r2,
            }
