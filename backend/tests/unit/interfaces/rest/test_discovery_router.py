"""Unit-Tests für den Discovery-Router — `complete_discovery`.

Reproduziert F-DISC-3 (Usability-Audit 2026-06-16, W-3): `POST /discovery/complete`
auf eine Session, deren Turn 1 (profession) nie beantwortet wurde, lädt das Profil
aus der DB (`repo.get_by_session_id`). Diese Rekonstruktion ruft `InvestorProfile(...)`
direkt auf (kein `model_copy`), wodurch der `_validate_onboarding_consistency`-Validator
laufen würde, sobald `onboarding_complete=True` und `profession=None` gleichzeitig
vorliegen. Der Fix prüft `profession is None` explizit *vor* dem Setzen von
`onboarding_complete=True` und liefert dafür immer 422 (Client-Fehler) statt eines
ungefangenen 500 — sowohl beim ersten als auch bei jedem weiteren Aufruf.
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status

from backend.domain.entities.investor_profile import InvestorProfile
from backend.interfaces.rest.routers.discovery import complete_discovery
from backend.interfaces.rest.schemas.investor_profile import CompleteRequest

pytestmark = pytest.mark.unit


def _incomplete_profile(session_id: str, *, onboarding_complete: bool) -> InvestorProfile:
    """Profil ohne beantworteten Turn 1 (profession=None) — Defaults wie nach `create_session`."""
    return InvestorProfile(
        session_id=session_id,
        profession=None,
        onboarding_complete=onboarding_complete,
    )


def _make_repo_with_lazy_loads(loaders: list[Callable[[], InvestorProfile]]) -> MagicMock:
    """Repo-Mock, der bei jedem `get_by_session_id`-Aufruf den nächsten Loader ausführt.

    `loaders` sind aufrufbare Objekte (z.B. Lambdas), die das jeweilige
    InvestorProfile erst bei Aufruf konstruieren — analog zu
    `SQLAInvestorProfileRepository._to_domain`, das bei jedem DB-Reload
    `InvestorProfile(...)` neu aufruft (kein `model_copy`). Damit feuert ein
    fehlschlagender Validator innerhalb von `complete_discovery`, statt schon
    beim Fixture-Aufbau des Tests.
    """
    remaining = list(loaders)

    async def _next_load(_session_id: str) -> InvestorProfile | None:
        loader = remaining.pop(0)
        return loader()

    repo = MagicMock()
    repo.get_by_session_id = AsyncMock(side_effect=_next_load)
    repo.save = AsyncMock()
    return repo


def _make_service() -> MagicMock:
    service = MagicMock()
    service.get_personalized_universe = AsyncMock(return_value=[])
    return service


class TestCompleteDiscoveryWithoutTurn1:
    """Repro: Session ohne Turn 1 — jeder `complete`-Aufruf muss 422 liefern, nie 500."""

    @pytest.mark.asyncio
    async def test_first_complete_call_returns_422_not_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Schon der allererste Aufruf darf ein unvollständiges Profil nicht abschliessen.

        Vor dem Fix wurde hier `onboarding_complete=True` gesetzt und persistiert
        (kein Validierungsfehler, da `model_copy` den Validator nicht erneut
        ausführt) — der Bug schlug erst beim *nächsten* DB-Reload als 500 durch.
        Der Fix prüft `profession is None` explizit vorher, daher muss bereits
        dieser erste Aufruf sauber mit 422 abgelehnt werden.
        """
        session_id = "sess-no-turn1"
        repo = _make_repo_with_lazy_loads(
            [lambda: _incomplete_profile(session_id, onboarding_complete=False)]
        )

        monkeypatch.setattr(
            "backend.interfaces.rest.routers.discovery.SQLAInvestorProfileRepository",
            lambda session: repo,
        )

        service = _make_service()
        body = CompleteRequest(session_id=session_id)

        with pytest.raises(HTTPException) as exc_info:
            await complete_discovery(body, session=MagicMock(), service=service)

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_second_complete_call_returns_4xx_not_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falls ein Profil trotzdem (z.B. Altbestand) mit onboarding_complete=True ohne
        profession in der DB liegt, muss der DB-Reload beim `complete`-Aufruf als 4xx
        und nicht als ungefangener 500 (ValueError aus dem model_validator) durchschlagen.
        """
        session_id = "sess-legacy-inconsistent"
        repo = _make_repo_with_lazy_loads(
            [lambda: _incomplete_profile(session_id, onboarding_complete=True)]
        )

        monkeypatch.setattr(
            "backend.interfaces.rest.routers.discovery.SQLAInvestorProfileRepository",
            lambda session: repo,
        )

        service = _make_service()
        body = CompleteRequest(session_id=session_id)

        with pytest.raises(HTTPException) as exc_info:
            await complete_discovery(body, session=MagicMock(), service=service)

        assert 400 <= exc_info.value.status_code < 500
        assert exc_info.value.status_code != 500


class TestCompleteDiscoveryIdempotentHappyPath:
    """Regression: Eine bereits vollständige Session (Turn 1 beantwortet) bleibt idempotent."""

    @pytest.mark.asyncio
    async def test_second_complete_call_on_full_profile_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session_id = "sess-full-profile"
        complete_profile = InvestorProfile(
            session_id=session_id,
            profession="Lehrer",
            onboarding_complete=True,
        )
        repo = _make_repo_with_lazy_loads([lambda: complete_profile, lambda: complete_profile])

        monkeypatch.setattr(
            "backend.interfaces.rest.routers.discovery.SQLAInvestorProfileRepository",
            lambda session: repo,
        )

        service = _make_service()
        body = CompleteRequest(session_id=session_id)

        first_response = await complete_discovery(body, session=MagicMock(), service=service)
        second_response = await complete_discovery(body, session=MagicMock(), service=service)

        assert first_response.profile.onboarding_complete is True
        assert second_response.profile.onboarding_complete is True
