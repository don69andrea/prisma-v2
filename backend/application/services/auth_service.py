"""AuthService — login, JWT creation/validation, user lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.domain.entities.user import User, UserRole
from backend.domain.repositories.user_repository import UserRepository

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(
        self,
        repo: UserRepository,
        jwt_secret: str,
        jwt_expire_hours: int = 8,
    ) -> None:
        self._repo = repo
        self._jwt_secret = jwt_secret
        self._jwt_expire_hours = jwt_expire_hours

    async def create_user(
        self,
        email: str,
        password: str,
        role: UserRole = UserRole.viewer,
    ) -> User:
        existing = await self._repo.get_by_email(email)
        if existing:
            raise ValueError(f"User with email {email} already exists")
        user = User(
            email=email,
            hashed_password=_pwd_context.hash(password),
            role=role,
        )
        await self._repo.save(user)
        return user

    async def login(self, email: str, password: str) -> str:
        user = await self._repo.get_by_email(email)
        if not user or not user.is_active:
            raise ValueError("Invalid credentials")
        if not _pwd_context.verify(password, user.hashed_password):
            raise ValueError("Invalid credentials")
        return self._create_token(user)

    async def verify_token(self, token: str) -> User:
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
            user_id = UUID(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise ValueError("Invalid token") from exc
        user = await self._repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise ValueError("Invalid token")
        return user

    async def set_password(self, user_id: UUID, new_password: str) -> None:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        updated = user.model_copy(update={"hashed_password": _pwd_context.hash(new_password)})
        await self._repo.save(updated)

    async def set_active(self, user_id: UUID, is_active: bool) -> None:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        updated = user.model_copy(update={"is_active": is_active})
        await self._repo.save(updated)

    async def reset_user_data(self, user_id: UUID) -> None:
        await self._repo.delete_user_data(user_id)

    async def list_users(self) -> list[User]:
        return await self._repo.list_all()

    def _create_token(self, user: User) -> str:
        expire = datetime.now(UTC) + timedelta(hours=self._jwt_expire_hours)
        payload = {"sub": str(user.id), "role": user.role.value, "exp": expire}
        return jwt.encode(payload, self._jwt_secret, algorithm="HS256")
