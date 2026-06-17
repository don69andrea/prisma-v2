"""Unit tests for User entity."""

from uuid import UUID

import pytest

from backend.domain.entities.user import User, UserRole

pytestmark = pytest.mark.unit


def test_user_defaults():
    user = User(email="test@example.com", hashed_password="hashed")
    assert isinstance(user.id, UUID)
    assert user.role == UserRole.viewer
    assert user.is_active is True
    assert user.created_at is not None


def test_user_role_admin():
    user = User(email="admin@example.com", hashed_password="hashed", role=UserRole.admin)
    assert user.role == UserRole.admin


def test_user_role_enum_values():
    assert UserRole.admin.value == "admin"
    assert UserRole.viewer.value == "viewer"


def test_user_model_copy_preserves_id():
    user = User(email="a@b.com", hashed_password="x")
    updated = user.model_copy(update={"is_active": False})
    assert updated.id == user.id
    assert updated.is_active is False
