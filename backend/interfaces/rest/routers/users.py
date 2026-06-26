"""User management router — admin only."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.application.services.auth_service import AuthService
from backend.domain.entities.user import User, UserRole
from backend.interfaces.rest.dependencies import get_auth_service, require_admin_role

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class CreateUserRequest(BaseModel):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""
    role: str = "viewer"


class PatchUserRequest(BaseModel):
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None


class UserItem(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    created_at: str


def _to_item(user: User) -> UserItem:
    return UserItem(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.get("", response_model=list[UserItem])
async def list_users(
    _admin: User = Depends(require_admin_role),
    service: AuthService = Depends(get_auth_service),
) -> list[UserItem]:
    users = await service.list_users()
    return [_to_item(u) for u in users]


@router.post("", response_model=UserItem, status_code=201)
async def create_user(
    body: CreateUserRequest,
    _admin: User = Depends(require_admin_role),
    service: AuthService = Depends(get_auth_service),
) -> UserItem:
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role: {body.role}") from None
    try:
        user = await service.create_user(
            body.email,
            body.password,
            role,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_item(user)


@router.patch("/{user_id}", status_code=204)
async def patch_user(
    user_id: UUID,
    body: PatchUserRequest,
    _admin: User = Depends(require_admin_role),
    service: AuthService = Depends(get_auth_service),
) -> None:
    try:
        if body.password is not None:
            await service.set_password(user_id, body.password)
        if body.first_name is not None or body.last_name is not None:
            await service.set_name(
                user_id,
                body.first_name or "",
                body.last_name or "",
            )
        if body.is_active is not None:
            await service.set_active(user_id, body.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{user_id}/data", status_code=204)
async def reset_user_data(
    user_id: UUID,
    _admin: User = Depends(require_admin_role),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.reset_user_data(user_id)
