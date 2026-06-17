"""Unit tests for AuthService."""

from __future__ import annotations

from unittest.mock import AsyncMock

import bcrypt
import pytest

from backend.application.services.auth_service import AuthService
from backend.domain.entities.user import User, UserRole

pytestmark = pytest.mark.unit

_SECRET = "test-secret-key-32-chars-minimum!!"


def _make_service(repo: AsyncMock) -> AuthService:
    return AuthService(repo=repo, jwt_secret=_SECRET, jwt_expire_hours=8)


def _make_user(
    email: str = "user@example.com",
    role: UserRole = UserRole.viewer,
    is_active: bool = True,
) -> User:
    return User(
        email=email,
        hashed_password=bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode("utf-8"),
        role=role,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_create_user_returns_user_with_hashed_password():
    repo = AsyncMock()
    repo.get_by_email.return_value = None
    repo.save.return_value = None
    service = _make_service(repo)

    user = await service.create_user("new@example.com", "pass123")

    assert user.email == "new@example.com"
    assert user.hashed_password != "pass123"
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_user_raises_if_email_exists():
    repo = AsyncMock()
    repo.get_by_email.return_value = _make_user()
    service = _make_service(repo)

    with pytest.raises(ValueError, match="already exists"):
        await service.create_user("user@example.com", "pass")


@pytest.mark.asyncio
async def test_login_returns_token():
    user = _make_user()
    repo = AsyncMock()
    repo.get_by_email.return_value = user
    service = _make_service(repo)

    token = await service.login("user@example.com", "secret")
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.asyncio
async def test_login_raises_on_wrong_password():
    user = _make_user()
    repo = AsyncMock()
    repo.get_by_email.return_value = user
    service = _make_service(repo)

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("user@example.com", "wrong")


@pytest.mark.asyncio
async def test_login_raises_on_inactive_user():
    user = _make_user(is_active=False)
    repo = AsyncMock()
    repo.get_by_email.return_value = user
    service = _make_service(repo)

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("user@example.com", "secret")


@pytest.mark.asyncio
async def test_verify_token_returns_user():
    user = _make_user()
    repo = AsyncMock()
    repo.get_by_email.return_value = user
    repo.get_by_id.return_value = user
    service = _make_service(repo)

    token = await service.login("user@example.com", "secret")
    result = await service.verify_token(token)
    assert result.email == user.email


@pytest.mark.asyncio
async def test_verify_token_raises_on_garbage():
    repo = AsyncMock()
    service = _make_service(repo)

    with pytest.raises(ValueError, match="Invalid token"):
        await service.verify_token("not.a.jwt")
