"""Auth router — login and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.application.services.auth_service import AuthService
from backend.domain.entities.user import User
from backend.interfaces.rest.dependencies import get_auth_service, require_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        token = await service.login(body.email, body.password)
        return TokenResponse(access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid credentials") from exc


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(require_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role.value,
    )
