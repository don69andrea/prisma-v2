"""Unit-Tests für SQLAUniverseRepository — Constraint-Mapping ohne Live-DB.

Regression zu K-4/F-BTCR-3 (docs/usability-performance-audit-2026-06-16.md):
`save()` nutzt `ON CONFLICT (id) DO UPDATE`, der Conflict-Handler greift nie
auf den `name`-Unique-Index (`ix_universes_name`), da `create_universe()`
immer eine neue UUID generiert. Ein Namens-Duplikat löst stattdessen eine
rohe `IntegrityError` aus, die bislang ungefangen bis zum globalen
Exception-Handler durchschlug (HTTP 500 "Interner Serverfehler.").
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.domain.entities.universe import Universe
from backend.domain.repositories.universe_repository import DuplicateUniverseNameError
from backend.infrastructure.persistence.repositories.universe_repository import (
    SQLAUniverseRepository,
)

pytestmark = pytest.mark.unit


def _make_universe(name: str = "Swiss-Quality") -> Universe:
    return Universe(id=uuid.uuid4(), name=name, region="CH", tickers=("NESN", "NOVN"))


def _integrity_error_for_name_index() -> IntegrityError:
    """Baut eine IntegrityError, deren `orig`-String den echten Index-Namen enthält
    (analog dem realen asyncpg.UniqueViolationError-Text bei Verstoss gegen
    `ix_universes_name`)."""
    orig = Exception(
        'duplicate key value violates unique constraint "ix_universes_name"\n'
        "DETAIL:  Key (name)=(Swiss-Quality) already exists."
    )
    return IntegrityError(statement="INSERT INTO universes ...", params={}, orig=orig)


async def test_save_raises_duplicate_name_error_on_unique_violation() -> None:
    """Bug-Reproduktion: IntegrityError auf ix_universes_name muss als fachliche
    DuplicateUniverseNameError propagieren, nicht als rohe IntegrityError."""
    session = AsyncMock()
    session.execute.side_effect = _integrity_error_for_name_index()
    repo = SQLAUniverseRepository(session)

    with pytest.raises(DuplicateUniverseNameError) as exc_info:
        await repo.save(_make_universe(name="Swiss-Quality"))

    assert "Swiss-Quality" in str(exc_info.value)


async def test_save_reraises_other_integrity_errors() -> None:
    """Nicht-Name-Constraint-Verletzungen sollen weiterhin unverändert propagieren."""
    session = AsyncMock()
    other_orig = Exception('violates foreign key constraint "fk_something_else"')
    session.execute.side_effect = IntegrityError(
        statement="INSERT INTO universes ...",
        params={},
        orig=other_orig,
    )
    repo = SQLAUniverseRepository(session)

    with pytest.raises(IntegrityError):
        await repo.save(_make_universe())


async def test_save_succeeds_without_conflict() -> None:
    """Happy-Path bleibt unverändert: kein Fehler, execute() wird einmal aufgerufen."""
    session = AsyncMock()
    repo = SQLAUniverseRepository(session)

    await repo.save(_make_universe())

    session.execute.assert_called_once()
