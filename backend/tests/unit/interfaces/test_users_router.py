"""Unit tests for users admin router."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.domain.entities.user import User, UserRole
from backend.interfaces.rest.dependencies import get_auth_service, require_admin_role

pytestmark = pytest.mark.unit


def _make_user(role: UserRole = UserRole.viewer) -> User:
    return User(id=uuid4(), email="u@example.com", hashed_password="x", role=role)


def _app_with_mocks(mock_service: AsyncMock) -> tuple[FastAPI, TestClient]:
    from backend.interfaces.rest.routers.users import router

    app = FastAPI()
    app.include_router(router)
    admin_user = _make_user(role=UserRole.admin)
    app.dependency_overrides[require_admin_role] = lambda: admin_user
    app.dependency_overrides[get_auth_service] = lambda: mock_service
    return app, TestClient(app)


def test_list_users_returns_list():
    svc = AsyncMock()
    svc.list_users.return_value = [_make_user()]
    _, client = _app_with_mocks(svc)

    resp = client.get("/api/v1/users")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 1


def test_create_user_returns_201():
    new_user = _make_user()
    svc = AsyncMock()
    svc.create_user.return_value = new_user
    _, client = _app_with_mocks(svc)

    resp = client.post("/api/v1/users", json={"email": "new@x.com", "password": "pass123"})
    assert resp.status_code == 201
    assert resp.json()["email"] == "u@example.com"


def test_patch_user_calls_set_active():
    svc = AsyncMock()
    user_id = uuid4()
    _, client = _app_with_mocks(svc)

    resp = client.patch(f"/api/v1/users/{user_id}", json={"is_active": False})
    assert resp.status_code == 204
    svc.set_active.assert_awaited_once_with(user_id, False)


def test_reset_user_data_calls_service():
    svc = AsyncMock()
    user_id = uuid4()
    _, client = _app_with_mocks(svc)

    resp = client.delete(f"/api/v1/users/{user_id}/data")
    assert resp.status_code == 204
    svc.reset_user_data.assert_awaited_once_with(user_id)
