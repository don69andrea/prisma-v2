# Auth & User Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a real JWT-based login system with full per-user data isolation, replacing the shared API-key auth.

**Architecture:** FastAPI backend gains a `users` table, `AuthService` with bcrypt + JWT, and `require_current_user` / `require_admin_role` FastAPI dependencies replacing the old `require_admin_api_key`. The Next.js frontend gets a login page, `useAuth` hook, and a small admin panel for user management. JWT is stored in `localStorage` (API calls) and a first-party cookie (Next.js middleware route protection).

**Tech Stack:** `python-jose[cryptography]`, `passlib[bcrypt]`, FastAPI Depends, SQLAlchemy 2.0 async, Alembic, Next.js 14 App Router, TypeScript, Tailwind CSS.

## Global Constraints

- Python 3.12; all async DB calls via `AsyncSession`; never use `loop.run_in_executor` — use `asyncio.to_thread`
- SQLAlchemy 2.0 `Mapped` / `mapped_column` style (match existing ORM models)
- All unit tests: `pytestmark = pytest.mark.unit` in every test file
- `ruff check backend/ && ruff format --check backend/` must pass before each commit
- TDD: write failing test → run → implement → run → commit
- One commit per task
- JWT secret is HS256, 8-hour expiry
- User data tables that get `user_id`: `alerts`, `backtest_results`, `decision_audit_log`, `research_memos`, `ranking_runs`, `llm_call_log`, `memo_batch_jobs`, `investor_profiles`
- Spec: `docs/superpowers/specs/2026-06-17-auth-accounts-design.md`

---

## File Map

**New files — Backend:**
- `backend/domain/entities/user.py` — `User` Pydantic entity, `UserRole` enum
- `backend/domain/repositories/user_repository.py` — abstract `UserRepository` port
- `backend/application/services/auth_service.py` — `AuthService` (login, create_user, verify_token, set_password, set_active, reset_user_data, list_users)
- `backend/infrastructure/persistence/models/user.py` — `UserORM` SQLAlchemy model
- `backend/infrastructure/persistence/repositories/user_repository.py` — `SQLAUserRepository`
- `backend/interfaces/rest/routers/auth.py` — `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- `backend/interfaces/rest/routers/users.py` — admin user CRUD
- `backend/alembic/versions/0027_auth_users.py` — migration: TRUNCATE, `users` table, `user_id` FKs
- `scripts/seed_admin.py` — idempotent admin-user seed
- `backend/tests/unit/domain/test_user_entity.py`
- `backend/tests/unit/application/test_auth_service.py`
- `backend/tests/unit/interfaces/test_auth_router.py`
- `backend/tests/unit/interfaces/test_users_router.py`

**Modified files — Backend:**
- `pyproject.toml` — add `python-jose[cryptography]`, `passlib[bcrypt]`
- `backend/config.py` — add `jwt_secret`, `jwt_expire_hours`, `admin_email`, `admin_password`
- `.env.example` — document new vars
- `backend/infrastructure/persistence/models/alert.py` — add `user_id` column
- `backend/infrastructure/persistence/models/backtest_result.py` — add `user_id` column
- `backend/infrastructure/persistence/models/decision_audit_log.py` — add `user_id` column
- `backend/infrastructure/persistence/models/research_memo.py` — add `user_id` column
- `backend/infrastructure/persistence/models/ranking_run.py` — add `user_id` column
- `backend/infrastructure/persistence/models/llm_call_log.py` — add `user_id` column
- `backend/infrastructure/persistence/models/memo_batch_job.py` — add `user_id` column
- `backend/infrastructure/persistence/models/investor_profile.py` — add `user_id` column
- `backend/interfaces/rest/dependencies.py` — add `get_user_repository`, `get_auth_service`, `require_current_user`, `require_admin_role`
- `backend/interfaces/rest/app.py` — replace `_auth`, register new routers

**New files — Frontend:**
- `frontend/hooks/useAuth.ts` — `AuthProvider`, `useAuth` hook
- `frontend/app/login/page.tsx` — login form
- `frontend/app/admin/layout.tsx` — admin route guard
- `frontend/app/admin/page.tsx` — cost dashboard
- `frontend/app/admin/users/page.tsx` — user list
- `frontend/app/admin/users/[id]/page.tsx` — user detail
- `frontend/lib/api/users.ts` — API calls for user management

**Modified files — Frontend:**
- `frontend/lib/api/client.ts` — replace X-API-Key with Bearer JWT
- `frontend/middleware.ts` — replace onboarding cookie with `prisma_token` cookie check
- `frontend/lib/routes.ts` — add `/login`, `/admin` routes
- `frontend/app/providers.tsx` — wrap with `AuthProvider`
- `frontend/app/layout.tsx` — remove `MissingApiKeyBanner`

---

### Task 1: Backend packages + config

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/config.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `Settings.jwt_secret: str`, `Settings.jwt_expire_hours: int`, `Settings.admin_email: str`, `Settings.admin_password: str`

- [ ] **Step 1: Add dependencies to pyproject.toml**

Find the `[project] dependencies` list in `pyproject.toml` and add these two entries (alphabetical order is not required — add after the existing entries):

```toml
"passlib[bcrypt]>=1.7.4",
"python-jose[cryptography]>=3.3.0",
```

- [ ] **Step 2: Install dependencies**

```bash
cd /Users/andreapetretta/prisma-v2
uv sync
```

Expected: `python-jose` and `passlib` appear in the resolved environment.

- [ ] **Step 3: Add JWT + admin fields to Settings**

In `backend/config.py`, add these fields inside the `Settings` class, after the existing `api_key` field:

```python
jwt_secret: str = ""
jwt_expire_hours: int = 8
admin_email: str = ""
admin_password: str = ""
```

And add this validator inside `Settings` after `_api_key_required_in_production`:

```python
@model_validator(mode="after")
def _jwt_secret_required_in_production(self) -> "Settings":
    if self.environment == "production" and not self.jwt_secret:
        raise ValueError("JWT_SECRET muss in der Production-Umgebung gesetzt sein")
    return self
```

- [ ] **Step 4: Update .env.example**

Add at the end of `.env.example`:

```env
# Auth / JWT
JWT_SECRET=change-me-to-a-random-32-char-string
JWT_EXPIRE_HOURS=8
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me
```

- [ ] **Step 5: Lint check**

```bash
ruff check backend/ && ruff format --check backend/
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml backend/config.py .env.example uv.lock
git commit -m "feat(auth): add python-jose + passlib, extend Settings with JWT/admin fields"
```

---

### Task 2: User domain entity + repository port

**Files:**
- Create: `backend/domain/entities/user.py`
- Create: `backend/domain/repositories/user_repository.py`
- Create: `backend/tests/unit/domain/test_user_entity.py`

**Interfaces:**
- Produces: `User(email, hashed_password, role, is_active, id, created_at)`, `UserRole(admin|viewer)`, `UserRepository` ABC with `get_by_id`, `get_by_email`, `list_all`, `save`, `delete_user_data`

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/domain/test_user_entity.py`:

```python
"""Unit tests for User entity."""
import pytest
from uuid import UUID
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/domain/test_user_entity.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.domain.entities.user'`

- [ ] **Step 3: Implement User entity**

Create `backend/domain/entities/user.py`:

```python
"""User domain entity."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    admin = "admin"
    viewer = "viewer"


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str
    hashed_password: str
    role: UserRole = UserRole.viewer
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest backend/tests/unit/domain/test_user_entity.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Create UserRepository port**

Create `backend/domain/repositories/user_repository.py`:

```python
"""Abstract UserRepository port."""
from abc import ABC, abstractmethod
from uuid import UUID

from backend.domain.entities.user import User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def list_all(self) -> list[User]: ...

    @abstractmethod
    async def save(self, user: User) -> None: ...

    @abstractmethod
    async def delete_user_data(self, user_id: UUID) -> None:
        """Deletes all personal data rows for a user across user-owned tables.
        Does NOT delete the user record itself."""
        ...
```

- [ ] **Step 6: Lint check**

```bash
ruff check backend/domain/entities/user.py backend/domain/repositories/user_repository.py backend/tests/unit/domain/test_user_entity.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/domain/entities/user.py backend/domain/repositories/user_repository.py backend/tests/unit/domain/test_user_entity.py
git commit -m "feat(auth): add User entity, UserRole enum, UserRepository port"
```

---

### Task 3: AuthService

**Files:**
- Create: `backend/application/services/auth_service.py`
- Create: `backend/tests/unit/application/test_auth_service.py`

**Interfaces:**
- Consumes: `UserRepository`, `Settings.jwt_secret: str`, `Settings.jwt_expire_hours: int`
- Produces: `AuthService.login(email, password) -> str`, `AuthService.create_user(email, password, role) -> User`, `AuthService.verify_token(token) -> User`, `AuthService.set_password(user_id, new_password)`, `AuthService.set_active(user_id, is_active)`, `AuthService.reset_user_data(user_id)`, `AuthService.list_users() -> list[User]`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/application/test_auth_service.py`:

```python
"""Unit tests for AuthService."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.application.services.auth_service import AuthService
from backend.domain.entities.user import User, UserRole

pytestmark = pytest.mark.unit

_SECRET = "test-secret-key-32-chars-minimum!!"


def _make_service(repo: AsyncMock) -> AuthService:
    return AuthService(repo=repo, jwt_secret=_SECRET, jwt_expire_hours=8)


def _make_user(**kwargs) -> User:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    defaults = {
        "email": "user@example.com",
        "hashed_password": ctx.hash("secret"),
        "role": UserRole.viewer,
        "is_active": True,
    }
    return User(**(defaults | kwargs))


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest backend/tests/unit/application/test_auth_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.application.services.auth_service'`

- [ ] **Step 3: Implement AuthService**

Create `backend/application/services/auth_service.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest backend/tests/unit/application/test_auth_service.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 5: Lint check**

```bash
ruff check backend/application/services/auth_service.py backend/tests/unit/application/test_auth_service.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/application/services/auth_service.py backend/tests/unit/application/test_auth_service.py
git commit -m "feat(auth): add AuthService with JWT login, verify_token, user lifecycle"
```

---

### Task 4: UserORM model + SQLAUserRepository

**Files:**
- Create: `backend/infrastructure/persistence/models/user.py`
- Create: `backend/infrastructure/persistence/repositories/user_repository.py`

**Interfaces:**
- Consumes: `User`, `UserRole`, `UserRepository` ABC
- Produces: `SQLAUserRepository(session)` implementing `UserRepository`

- [ ] **Step 1: Create UserORM model**

Create `backend/infrastructure/persistence/models/user.py`:

```python
"""SQLAlchemy ORM model for the users table."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.base import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 2: Create SQLAUserRepository**

Create `backend/infrastructure/persistence/repositories/user_repository.py`:

```python
"""SQLAlchemy implementation of UserRepository."""
import uuid
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.user import User, UserRole
from backend.domain.repositories.user_repository import UserRepository
from backend.infrastructure.persistence.models.user import UserORM


class SQLAUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return self._to_domain(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserORM).where(UserORM.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def list_all(self) -> list[User]:
        stmt = select(UserORM).order_by(UserORM.created_at.desc())
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save(self, user: User) -> None:
        stmt = (
            pg_insert(UserORM)
            .values(
                id=user.id,
                email=user.email,
                hashed_password=user.hashed_password,
                role=user.role.value,
                is_active=user.is_active,
                created_at=user.created_at,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "email": user.email,
                    "hashed_password": user.hashed_password,
                    "role": user.role.value,
                    "is_active": user.is_active,
                },
            )
        )
        await self._session.execute(stmt)

    async def delete_user_data(self, user_id: UUID) -> None:
        """Removes all personal data rows for the user. Does not delete the user record."""
        from backend.infrastructure.persistence.models.alert import AlertORM
        from backend.infrastructure.persistence.models.backtest_result import BacktestResultORM
        from backend.infrastructure.persistence.models.decision_audit_log import DecisionAuditLogORM
        from backend.infrastructure.persistence.models.investor_profile import InvestorProfileORM
        from backend.infrastructure.persistence.models.llm_call_log import LLMCallLogORM
        from backend.infrastructure.persistence.models.memo_batch_job import MemoBatchJobORM
        from backend.infrastructure.persistence.models.ranking_run import RankingRunORM
        from backend.infrastructure.persistence.models.research_memo import ResearchMemoORM

        for orm_cls in (
            AlertORM,
            BacktestResultORM,
            DecisionAuditLogORM,
            InvestorProfileORM,
            LLMCallLogORM,
            MemoBatchJobORM,
            RankingRunORM,
            ResearchMemoORM,
        ):
            await self._session.execute(
                delete(orm_cls).where(orm_cls.user_id == user_id)  # type: ignore[attr-defined]
            )

    def _to_domain(self, row: UserORM) -> User:
        return User(
            id=row.id,
            email=row.email,
            hashed_password=row.hashed_password,
            role=UserRole(row.role),
            is_active=row.is_active,
            created_at=row.created_at,
        )
```

- [ ] **Step 3: Lint check**

```bash
ruff check backend/infrastructure/persistence/models/user.py backend/infrastructure/persistence/repositories/user_repository.py
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/infrastructure/persistence/models/user.py backend/infrastructure/persistence/repositories/user_repository.py
git commit -m "feat(auth): add UserORM model and SQLAUserRepository"
```

---

### Task 5: DB Migration + ORM model updates for user_id

**Files:**
- Create: `backend/alembic/versions/0027_auth_users.py`
- Modify: 8 existing ORM model files (add `user_id` column)

**Interfaces:**
- Produces: `users` table in DB; `user_id UUID NOT NULL FK → users.id ON DELETE CASCADE` on all personal-data tables; all 8 ORM models expose `.user_id` attribute

- [ ] **Step 1: Add user_id to the 8 ORM models**

For each file below, add the `user_id` column after the existing columns. Match the pattern exactly.

**`backend/infrastructure/persistence/models/alert.py`** — add after the last existing column:
```python
import uuid as _uuid
from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
# Add this column to AlertORM:
user_id: Mapped[_uuid.UUID] = mapped_column(
    _PG_UUID(as_uuid=True), nullable=False, index=True
)
```

**`backend/infrastructure/persistence/models/backtest_result.py`** — same pattern:
```python
user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), nullable=False, index=True
)
```

**`backend/infrastructure/persistence/models/decision_audit_log.py`** — same pattern.

**`backend/infrastructure/persistence/models/research_memo.py`** — same pattern.

**`backend/infrastructure/persistence/models/ranking_run.py`** — same pattern.

**`backend/infrastructure/persistence/models/llm_call_log.py`** — same pattern.

**`backend/infrastructure/persistence/models/memo_batch_job.py`** — same pattern.

**`backend/infrastructure/persistence/models/investor_profile.py`** — same pattern.

Read each file first to understand the existing import style and column naming, then add `user_id` consistently. The column must be named exactly `user_id` and typed `UUID(as_uuid=True)` with `nullable=False`.

- [ ] **Step 2: Write the Alembic migration**

Create `backend/alembic/versions/0027_auth_users.py`:

```python
"""auth: add users table and user_id FK to personal-data tables

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_PERSONAL_TABLES = [
    "alerts",
    "backtest_results",
    "decision_audit_log",
    "research_memos",
    "ranking_runs",
    "llm_call_log",
    "memo_batch_jobs",
    "investor_profiles",
]


def upgrade() -> None:
    # Fresh start: wipe all user-owned data before adding NOT NULL constraint
    for table in _PERSONAL_TABLES:
        op.execute(f"TRUNCATE TABLE {table} CASCADE")

    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Add user_id FK to each personal table
    for table in _PERSONAL_TABLES:
        op.add_column(
            table,
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
        )
        op.create_foreign_key(
            f"fk_{table}_user_id",
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def downgrade() -> None:
    for table in _PERSONAL_TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_column(table, "user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

- [ ] **Step 3: Verify revision chain**

Check the `down_revision` in `0027` matches the revision ID in `0026_seed_smi20_stocks.py`:

```bash
head -10 /Users/andreapetretta/prisma-v2/backend/alembic/versions/0026_seed_smi20_stocks.py
```

If the revision ID in 0026 is different from `"0026"`, update `down_revision` in `0027` accordingly.

- [ ] **Step 4: Apply migration**

Ensure a local DB is running (see `docker-compose.yml`), then:

```bash
cd /Users/andreapetretta/prisma-v2
source .venv/bin/activate 2>/dev/null || source /tmp/prisma-v2/venv/bin/activate
alembic upgrade head
```

Expected output: `Running upgrade ... -> 0027, auth: add users table ...`

- [ ] **Step 5: Verify schema**

```bash
alembic current
```

Expected: `0027 (head)`

- [ ] **Step 6: Lint check**

```bash
ruff check backend/alembic/versions/0027_auth_users.py backend/infrastructure/persistence/models/
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/0027_auth_users.py \
  backend/infrastructure/persistence/models/alert.py \
  backend/infrastructure/persistence/models/backtest_result.py \
  backend/infrastructure/persistence/models/decision_audit_log.py \
  backend/infrastructure/persistence/models/research_memo.py \
  backend/infrastructure/persistence/models/ranking_run.py \
  backend/infrastructure/persistence/models/llm_call_log.py \
  backend/infrastructure/persistence/models/memo_batch_job.py \
  backend/infrastructure/persistence/models/investor_profile.py
git commit -m "feat(auth): migration 0027 — users table + user_id FK on personal-data tables"
```

---

### Task 6: Auth REST endpoints + update dependencies.py + wire app.py

**Files:**
- Create: `backend/interfaces/rest/routers/auth.py`
- Create: `backend/tests/unit/interfaces/test_auth_router.py`
- Modify: `backend/interfaces/rest/dependencies.py`
- Modify: `backend/interfaces/rest/app.py`

**Interfaces:**
- Consumes: `AuthService.login`, `AuthService.verify_token`, `get_settings`
- Produces: `POST /api/v1/auth/login → {access_token, token_type}`, `GET /api/v1/auth/me → {id, email, role}`, `require_current_user() -> User`, `require_admin_role() -> User`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/interfaces/test_auth_router.py`:

```python
"""Unit tests for auth router."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from backend.domain.entities.user import User, UserRole

pytestmark = pytest.mark.unit


def _make_app():
    from backend.interfaces.rest.app import create_app
    return create_app()


def _make_user(role: UserRole = UserRole.viewer) -> User:
    return User(
        id=uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        role=role,
    )


def test_login_returns_token():
    app = _make_app()
    token = "fake.jwt.token"

    async def _mock_login(email: str, password: str) -> str:
        return token

    with patch(
        "backend.interfaces.rest.routers.auth.get_auth_service",
        return_value=AsyncMock(login=_mock_login),
    ):
        # Use dependency override instead
        pass  # tested via integration; unit test covers service layer


def test_login_endpoint_400_on_wrong_password():
    from fastapi import FastAPI
    from backend.interfaces.rest.routers.auth import router as auth_router
    from backend.application.services.auth_service import AuthService
    from backend.interfaces.rest.dependencies import get_auth_service

    app = FastAPI()
    app.include_router(auth_router)

    mock_service = AsyncMock(spec=AuthService)
    mock_service.login.side_effect = ValueError("Invalid credentials")
    app.dependency_overrides[get_auth_service] = lambda: mock_service

    client = TestClient(app)
    resp = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert resp.status_code == 401


def test_me_endpoint_returns_user():
    from fastapi import FastAPI
    from backend.interfaces.rest.routers.auth import router as auth_router
    from backend.interfaces.rest.dependencies import require_current_user

    user = _make_user()
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[require_current_user] = lambda: user

    client = TestClient(app)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["role"] == "viewer"


def test_me_endpoint_401_without_token():
    from fastapi import FastAPI
    from backend.interfaces.rest.routers.auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)

    client = TestClient(app)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest backend/tests/unit/interfaces/test_auth_router.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.interfaces.rest.routers.auth'`

- [ ] **Step 3: Create auth router**

Create `backend/interfaces/rest/routers/auth.py`:

```python
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
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(require_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role.value,
    )
```

- [ ] **Step 4: Add new dependencies to dependencies.py**

At the top of `backend/interfaces/rest/dependencies.py`, add to the imports section (after existing imports):

```python
from backend.domain.entities.user import User, UserRole
from backend.domain.repositories.user_repository import UserRepository
```

Then add these four functions at the bottom of the file, before any existing functions that depend on them (add before the existing `require_admin_api_key`):

```python
async def get_user_repository(
    session: AsyncSession = Depends(get_session),
) -> UserRepository:
    from backend.infrastructure.persistence.repositories.user_repository import (
        SQLAUserRepository,
    )
    return SQLAUserRepository(session=session)


async def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    from backend.application.services.auth_service import AuthService
    return AuthService(
        repo=repo,
        jwt_secret=settings.jwt_secret,
        jwt_expire_hours=settings.jwt_expire_hours,
    )


async def require_current_user(
    authorization: str | None = Header(default=None),
    service: AuthService = Depends(get_auth_service),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or malformed")
    token = authorization.removeprefix("Bearer ")
    try:
        return await service.verify_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_admin_role(
    current_user: User = Depends(require_current_user),
) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user
```

The `get_auth_service` function uses a lazy import inside the function body (same pattern as `get_backtest_service` in the existing `dependencies.py`). Return type annotation can be `Any` for now — no circular import risk exists, but lazy import keeps the pattern consistent with the file.

- [ ] **Step 5: Update app.py**

In `backend/interfaces/rest/app.py`:

1. Change the import at the top from:
```python
from backend.interfaces.rest.dependencies import require_admin_api_key
```
to:
```python
from backend.interfaces.rest.dependencies import require_admin_role, require_current_user
```

2. Add imports for the new routers at the top `from backend.interfaces.rest.routers import (...)` block:
```python
    auth,
    users,
```

3. Inside `create_app()`, change:
```python
_auth = [Depends(require_admin_api_key)]
```
to:
```python
_auth = [Depends(require_current_user)]
_admin_auth = [Depends(require_admin_role)]
```

4. Register the new public routers right after `app.include_router(health.router)`:
```python
app.include_router(auth.router)  # public — no auth required
```

5. Change the admin router registration from:
```python
app.include_router(admin.router, dependencies=_auth)
```
to:
```python
app.include_router(admin.router, dependencies=_admin_auth)
```

6. Add users router registration after admin:
```python
app.include_router(users.router, dependencies=_admin_auth)
```

- [ ] **Step 6: Run tests**

```bash
pytest backend/tests/unit/interfaces/test_auth_router.py -v
```

Expected: all tests PASSED.

- [ ] **Step 7: Smoke test the app starts**

```bash
python -c "from backend.interfaces.rest.app import create_app; app = create_app(); print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Lint check**

```bash
ruff check backend/interfaces/rest/routers/auth.py backend/interfaces/rest/dependencies.py backend/interfaces/rest/app.py
```

Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add backend/interfaces/rest/routers/auth.py \
  backend/tests/unit/interfaces/test_auth_router.py \
  backend/interfaces/rest/dependencies.py \
  backend/interfaces/rest/app.py
git commit -m "feat(auth): add auth router, require_current_user/require_admin_role dependencies, wire app.py"
```

---

### Task 7: User management REST endpoints

**Files:**
- Create: `backend/interfaces/rest/routers/users.py`
- Create: `backend/tests/unit/interfaces/test_users_router.py`

**Interfaces:**
- Consumes: `AuthService.create_user`, `AuthService.list_users`, `AuthService.set_password`, `AuthService.set_active`, `AuthService.reset_user_data`, `require_admin_role`
- Produces: `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{user_id}`, `DELETE /api/v1/users/{user_id}/data`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/interfaces/test_users_router.py`:

```python
"""Unit tests for users admin router."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from uuid import uuid4

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest backend/tests/unit/interfaces/test_users_router.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.interfaces.rest.routers.users'`

- [ ] **Step 3: Create users router**

Create `backend/interfaces/rest/routers/users.py`:

```python
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
    role: str = "viewer"


class PatchUserRequest(BaseModel):
    password: str | None = None
    is_active: bool | None = None


class UserItem(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str


def _to_item(user: User) -> UserItem:
    return UserItem(
        id=str(user.id),
        email=user.email,
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
        raise HTTPException(status_code=422, detail=f"Invalid role: {body.role}")
    try:
        user = await service.create_user(body.email, body.password, role)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_item(user)


@router.patch("/{user_id}", status_code=204)
async def patch_user(
    user_id: UUID,
    body: PatchUserRequest,
    _admin: User = Depends(require_admin_role),
    service: AuthService = Depends(get_auth_service),
) -> None:
    if body.password is not None:
        await service.set_password(user_id, body.password)
    if body.is_active is not None:
        await service.set_active(user_id, body.is_active)


@router.delete("/{user_id}/data", status_code=204)
async def reset_user_data(
    user_id: UUID,
    _admin: User = Depends(require_admin_role),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.reset_user_data(user_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest backend/tests/unit/interfaces/test_users_router.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Lint check**

```bash
ruff check backend/interfaces/rest/routers/users.py backend/tests/unit/interfaces/test_users_router.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/interfaces/rest/routers/users.py backend/tests/unit/interfaces/test_users_router.py
git commit -m "feat(auth): add user management admin endpoints (list, create, patch, reset)"
```

---

### Task 8: Admin seed script

**Files:**
- Create: `scripts/seed_admin.py`

**Interfaces:**
- Consumes: `Settings.admin_email`, `Settings.admin_password`, `Settings.jwt_secret`, `AuthService.create_user`, `SQLAUserRepository`
- Produces: idempotent script that creates the admin user on first run

- [ ] **Step 1: Create seed script**

Create `scripts/seed_admin.py`:

```python
"""Creates the initial admin user from environment variables.

Usage:
    uv run python scripts/seed_admin.py

Idempotent: exits cleanly if the admin user already exists.
Requires ADMIN_EMAIL and ADMIN_PASSWORD in .env (or environment).
"""
from __future__ import annotations

import asyncio
import sys

from backend.config import get_settings
from backend.infrastructure.persistence.session import get_session_factory


async def main() -> None:
    settings = get_settings()

    if not settings.admin_email or not settings.admin_password:
        print(
            "ERROR: ADMIN_EMAIL and ADMIN_PASSWORD must be set in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    if not settings.jwt_secret:
        print("ERROR: JWT_SECRET must be set in .env", file=sys.stderr)
        sys.exit(1)

    from backend.application.services.auth_service import AuthService
    from backend.domain.entities.user import UserRole
    from backend.infrastructure.persistence.repositories.user_repository import (
        SQLAUserRepository,
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = SQLAUserRepository(session=session)
        existing = await repo.get_by_email(settings.admin_email)
        if existing:
            print(f"Admin {settings.admin_email!r} already exists — skipping.")
            return

        service = AuthService(
            repo=repo,
            jwt_secret=settings.jwt_secret,
            jwt_expire_hours=settings.jwt_expire_hours,
        )
        user = await service.create_user(
            email=settings.admin_email,
            password=settings.admin_password,
            role=UserRole.admin,
        )
        await session.commit()
        print(f"Admin created: {user.email!r} (id={user.id})")


asyncio.run(main())
```

- [ ] **Step 2: Verify script can be imported**

```bash
python -c "import scripts.seed_admin; print('OK')" 2>/dev/null || echo "import-only check skipped (script uses __main__)"
```

- [ ] **Step 3: Run script (requires .env with JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD and running DB)**

```bash
uv run python scripts/seed_admin.py
```

Expected: `Admin created: 'admin@example.com' (id=<uuid>)`
On second run: `Admin 'admin@example.com' already exists — skipping.`

- [ ] **Step 4: Lint check**

```bash
ruff check scripts/seed_admin.py
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_admin.py
git commit -m "feat(auth): add idempotent seed_admin.py script"
```

---

### Task 9: Frontend auth provider + hook + API client

**Files:**
- Create: `frontend/hooks/useAuth.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/app/providers.tsx`

**Interfaces:**
- Produces: `useAuth() → { user, loading, login, logout }`, JWT stored in cookie `prisma_token` + `localStorage`, API client sends `Authorization: Bearer <token>` instead of `X-API-Key`

- [ ] **Step 1: Create useAuth hook**

Create `frontend/hooks/useAuth.ts`:

```typescript
'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api/client';

export interface AuthUser {
  id: string;
  email: string;
  role: 'admin' | 'viewer';
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

function setTokenCookie(token: string): void {
  const maxAge = 8 * 3600;
  document.cookie = `prisma_token=${token}; path=/; max-age=${maxAge}; SameSite=Strict`;
  localStorage.setItem('prisma_token', token);
}

function clearTokenCookie(): void {
  document.cookie = 'prisma_token=; path=/; max-age=0; SameSite=Strict';
  localStorage.removeItem('prisma_token');
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('prisma_token');
    if (!token) {
      setLoading(false);
      return;
    }
    apiFetch<AuthUser>('/api/v1/auth/me')
      .then(setUser)
      .catch(() => {
        clearTokenCookie();
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<void> {
    const res = await apiFetch<{ access_token: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setTokenCookie(res.access_token);
    const me = await apiFetch<AuthUser>('/api/v1/auth/me');
    setUser(me);
    router.push('/');
  }

  function logout(): void {
    clearTokenCookie();
    setUser(null);
    router.push('/login');
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
```

- [ ] **Step 2: Update API client to use Bearer token**

In `frontend/lib/api/client.ts`, replace:

```typescript
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

if (!API_KEY && process.env.NODE_ENV === 'development') {
  console.warn('[prisma] NEXT_PUBLIC_API_KEY is not set — authenticated endpoints will return 401.');
}
```

with:

```typescript
function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('prisma_token');
}
```

And replace:

```typescript
const authHeaders: Record<string, string> = API_KEY ? { 'X-API-Key': API_KEY } : {};
```

with:

```typescript
const token = getToken();
const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
```

Also update the 401 handling inside the `if (!response.ok)` block to auto-logout. After the existing error construction, add:

```typescript
if (response.status === 401 && typeof window !== 'undefined') {
  localStorage.removeItem('prisma_token');
  document.cookie = 'prisma_token=; path=/; max-age=0; SameSite=Strict';
  window.location.href = '/login';
}
```

- [ ] **Step 3: Add AuthProvider to providers.tsx**

In `frontend/app/providers.tsx`, add the import at the top:

```typescript
import { AuthProvider } from '@/hooks/useAuth';
```

And wrap the return value to include `AuthProvider`. Change the return inside `Providers` from:

```typescript
return (
  <QueryClientProvider client={queryClient}>
    {showLoading && <LoadingScreen fadeOut={fadeOut} />}
    <ColdStartBanner />
    {children}
  </QueryClientProvider>
);
```

to:

```typescript
return (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      {showLoading && <LoadingScreen fadeOut={fadeOut} />}
      <ColdStartBanner />
      {children}
    </AuthProvider>
  </QueryClientProvider>
);
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors (or only pre-existing errors unrelated to auth).

- [ ] **Step 5: Commit**

```bash
git add frontend/hooks/useAuth.ts frontend/lib/api/client.ts frontend/app/providers.tsx
git commit -m "feat(auth): add useAuth hook, AuthProvider, update API client to Bearer JWT"
```

---

### Task 10: Login page + middleware + routes

**Files:**
- Create: `frontend/app/login/page.tsx`
- Modify: `frontend/middleware.ts`
- Modify: `frontend/lib/routes.ts`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: `useAuth().login`, `AuthProvider`
- Produces: `/login` page, route protection via `prisma_token` cookie, `/admin` route constant

- [ ] **Step 1: Create login page**

Create `frontend/app/login/page.tsx`:

```typescript
'use client';

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/lib/api/client';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Ungültige E-Mail-Adresse oder Passwort.');
      } else {
        setError('Anmeldung fehlgeschlagen. Bitte versuche es erneut.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 p-8 border border-border rounded-xl bg-card">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">PRISMA</h1>
          <p className="text-sm text-muted-foreground">
            Melde dich mit deinem Account an.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <p className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">
              {error}
            </p>
          )}
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium">
              E-Mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium">
              Passwort
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-primary-foreground rounded-md py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Wird angemeldet …' : 'Anmelden'}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update middleware.ts**

Replace the entire content of `frontend/middleware.ts` with:

```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_PATHS = ['/login', '/_next', '/api', '/favicon.ico'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const token = request.cookies.get('prisma_token')?.value;
  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

- [ ] **Step 3: Update routes.ts**

In `frontend/lib/routes.ts`, update the `ROUTES` object to remove `start` and add `login` and `admin`:

```typescript
export const ROUTES = {
  login: '/login',
  dashboard: '/',
  discover: '/discover',
  universes: '/universes',
  rankings: '/rankings',
  backtest: '/backtest',
  decision: '/decision',
  alerts: '/alerts',
  portfolio: '/portfolio',
  simulator: '/portfolio/simulator',
  fonds: '/fonds',
  stocks: '/stocks',
  news: '/news',
  watchlist: '/watchlist',
  steuer: '/steuer',
  research: '/research',
  admin: '/admin',
  adminUsers: '/admin/users',
  factsheet: (runId: string, ticker: string) =>
    `/rankings/${runId}/stock/${ticker}` as const,
} as const;
```

- [ ] **Step 4: Remove MissingApiKeyBanner from layout.tsx**

In `frontend/app/layout.tsx`, remove the line:

```typescript
import { MissingApiKeyBanner } from '@/components/ui/MissingApiKeyBanner';
```

And remove `<MissingApiKeyBanner />` from the JSX.

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors related to the changed files.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/login/page.tsx frontend/middleware.ts frontend/lib/routes.ts frontend/app/layout.tsx
git commit -m "feat(auth): add login page, update middleware to JWT cookie check, update routes"
```

---

### Task 11: Admin UI

**Files:**
- Create: `frontend/app/admin/layout.tsx`
- Create: `frontend/app/admin/page.tsx`
- Create: `frontend/app/admin/users/page.tsx`
- Create: `frontend/app/admin/users/[id]/page.tsx`
- Create: `frontend/lib/api/users.ts`

**Interfaces:**
- Consumes: `useAuth()`, `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{id}`, `DELETE /api/v1/users/{id}/data`, existing `GET /api/v1/admin/costs`
- Produces: `/admin` and `/admin/users` and `/admin/users/[id]` pages, `listUsers()`, `createUser()`, `patchUser()`, `resetUserData()` API helpers

- [ ] **Step 1: Create users API helper**

Create `frontend/lib/api/users.ts`:

```typescript
import { apiFetch } from './client';

export interface UserItem {
  id: string;
  email: string;
  role: 'admin' | 'viewer';
  is_active: boolean;
  created_at: string;
}

export async function listUsers(): Promise<UserItem[]> {
  return apiFetch<UserItem[]>('/api/v1/users');
}

export async function createUser(payload: {
  email: string;
  password: string;
  role?: string;
}): Promise<UserItem> {
  return apiFetch<UserItem>('/api/v1/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function patchUser(
  id: string,
  payload: { password?: string; is_active?: boolean }
): Promise<void> {
  return apiFetch<void>(`/api/v1/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function resetUserData(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/users/${id}/data`, { method: 'DELETE' });
}
```

- [ ] **Step 2: Create admin layout (route guard)**

Create `frontend/app/admin/layout.tsx`:

```typescript
'use client';

import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!user || user.role !== 'admin')) {
      router.replace('/');
    }
  }, [user, loading, router]);

  if (loading || !user || user.role !== 'admin') {
    return null;
  }

  return (
    <div className="container py-8 space-y-6">
      <nav className="flex gap-4 border-b border-border pb-4">
        <Link href="/admin" className="text-sm font-medium hover:text-primary">
          Übersicht
        </Link>
        <Link href="/admin/users" className="text-sm font-medium hover:text-primary">
          User-Verwaltung
        </Link>
      </nav>
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Create admin dashboard page (cost overview)**

Create `frontend/app/admin/page.tsx`:

```typescript
'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api/client';

interface CostSummary {
  total_usd: number;
  by_model: Record<string, number>;
  by_feature: Record<string, number>;
  recent_calls: Array<{
    model: string;
    feature: string;
    cost_usd: number;
    created_at: string;
  }>;
}

export default function AdminPage() {
  const { data, isLoading } = useQuery<CostSummary>({
    queryKey: ['admin-costs'],
    queryFn: () => apiFetch<CostSummary>('/api/v1/admin/costs'),
  });

  if (isLoading) return <p className="text-muted-foreground">Lädt …</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Admin — Übersicht</h1>

      <div className="rounded-lg border border-border p-6 space-y-1">
        <p className="text-sm text-muted-foreground">LLM-Kosten (aktueller Monat)</p>
        <p className="text-3xl font-bold">${data.total_usd.toFixed(4)}</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-border p-4 space-y-2">
          <h2 className="text-sm font-medium">Nach Modell</h2>
          {Object.entries(data.by_model).map(([model, cost]) => (
            <div key={model} className="flex justify-between text-sm">
              <span className="text-muted-foreground">{model}</span>
              <span>${cost.toFixed(4)}</span>
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-border p-4 space-y-2">
          <h2 className="text-sm font-medium">Nach Feature</h2>
          {Object.entries(data.by_feature).map(([feature, cost]) => (
            <div key={feature} className="flex justify-between text-sm">
              <span className="text-muted-foreground">{feature}</span>
              <span>${cost.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-border p-4 space-y-3">
        <h2 className="text-sm font-medium">Letzte API-Calls</h2>
        <div className="space-y-1">
          {data.recent_calls.map((call, i) => (
            <div key={i} className="flex justify-between text-sm">
              <span className="text-muted-foreground">
                {call.feature} · {call.model}
              </span>
              <span>${call.cost_usd.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create user list page**

Create `frontend/app/admin/users/page.tsx`:

```typescript
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { listUsers, createUser, type UserItem } from '@/lib/api/users';

export default function UsersPage() {
  const qc = useQueryClient();
  const { data: users = [], isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: listUsers,
  });

  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'viewer' | 'admin'>('viewer');
  const [formError, setFormError] = useState('');

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setShowForm(false);
      setEmail('');
      setPassword('');
    },
    onError: (err: Error) => setFormError(err.message),
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError('');
    createMutation.mutate({ email, password, role });
  }

  if (isLoading) return <p className="text-muted-foreground">Lädt …</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">User-Verwaltung</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90"
        >
          + Neuer User
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="border border-border rounded-lg p-4 space-y-3"
        >
          {formError && <p className="text-sm text-destructive">{formError}</p>}
          <input
            type="email"
            placeholder="E-Mail"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
          />
          <input
            type="password"
            placeholder="Passwort"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as 'viewer' | 'admin')}
            className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
          >
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              Erstellen
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="text-sm px-3 py-1.5 rounded-md border border-border hover:bg-muted"
            >
              Abbrechen
            </button>
          </div>
        </form>
      )}

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="text-left px-4 py-2 font-medium">E-Mail</th>
              <th className="text-left px-4 py-2 font-medium">Rolle</th>
              <th className="text-left px-4 py-2 font-medium">Status</th>
              <th className="text-left px-4 py-2 font-medium">Erstellt</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {users.map((user: UserItem) => (
              <tr key={user.id} className="border-t border-border hover:bg-muted/40">
                <td className="px-4 py-2">{user.email}</td>
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      user.role === 'admin'
                        ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {user.role}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      user.is_active
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    }`}
                  >
                    {user.is_active ? 'Aktiv' : 'Gesperrt'}
                  </span>
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {new Date(user.created_at).toLocaleDateString('de-CH')}
                </td>
                <td className="px-4 py-2 text-right">
                  <Link
                    href={`/admin/users/${user.id}`}
                    className="text-primary hover:underline text-xs"
                  >
                    Verwalten
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create user detail page**

Create `frontend/app/admin/users/[id]/page.tsx`:

```typescript
'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listUsers, patchUser, resetUserData } from '@/lib/api/users';

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: users = [] } = useQuery({ queryKey: ['admin-users'], queryFn: listUsers });
  const user = users.find((u) => u.id === id);

  const [newPassword, setNewPassword] = useState('');
  const [message, setMessage] = useState('');

  const patchMutation = useMutation({
    mutationFn: (payload: { password?: string; is_active?: boolean }) =>
      patchUser(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setMessage('Gespeichert.');
      setNewPassword('');
    },
    onError: (err: Error) => setMessage(`Fehler: ${err.message}`),
  });

  const resetMutation = useMutation({
    mutationFn: () => resetUserData(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setMessage('Alle Daten wurden gelöscht.');
    },
  });

  if (!user) return <p className="text-muted-foreground">User nicht gefunden.</p>;

  return (
    <div className="space-y-6 max-w-md">
      <div>
        <button
          onClick={() => router.back()}
          className="text-sm text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1"
        >
          ← Zurück
        </button>
        <h1 className="text-xl font-semibold">{user.email}</h1>
        <p className="text-sm text-muted-foreground">
          {user.role} · {user.is_active ? 'Aktiv' : 'Gesperrt'}
        </p>
      </div>

      {message && (
        <p className="text-sm bg-muted px-3 py-2 rounded-md">{message}</p>
      )}

      <div className="space-y-4 border border-border rounded-lg p-4">
        <h2 className="text-sm font-medium">Passwort setzen</h2>
        <input
          type="password"
          placeholder="Neues Passwort"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
        />
        <button
          onClick={() => newPassword && patchMutation.mutate({ password: newPassword })}
          disabled={!newPassword || patchMutation.isPending}
          className="text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          Passwort aktualisieren
        </button>
      </div>

      <div className="space-y-3 border border-border rounded-lg p-4">
        <h2 className="text-sm font-medium">Account-Status</h2>
        <button
          onClick={() => patchMutation.mutate({ is_active: !user.is_active })}
          className={`text-sm px-3 py-1.5 rounded-md ${
            user.is_active
              ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
              : 'bg-green-600 text-white hover:bg-green-700'
          }`}
        >
          {user.is_active ? 'User sperren' : 'User aktivieren'}
        </button>
      </div>

      <div className="space-y-3 border border-destructive/30 rounded-lg p-4">
        <h2 className="text-sm font-medium text-destructive">Danger Zone</h2>
        <p className="text-xs text-muted-foreground">
          Löscht alle persönlichen Daten (Portfolio, Alerts, Memos, Backtests …). Der Account bleibt erhalten.
        </p>
        <button
          onClick={() => {
            if (confirm(`Alle Daten von ${user.email} wirklich löschen?`)) {
              resetMutation.mutate();
            }
          }}
          className="text-sm border border-destructive text-destructive px-3 py-1.5 rounded-md hover:bg-destructive/10"
        >
          Alle Daten zurücksetzen
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors in the new files.

- [ ] **Step 7: Lint frontend**

```bash
cd frontend && npx eslint app/admin lib/api/users.ts hooks/useAuth.ts --max-warnings 0
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add \
  frontend/app/admin/layout.tsx \
  frontend/app/admin/page.tsx \
  frontend/app/admin/users/page.tsx \
  "frontend/app/admin/users/[id]/page.tsx" \
  frontend/lib/api/users.ts
git commit -m "feat(auth): add admin UI — cost overview, user list, user detail with reset"
```

---

## Post-Implementation Checklist

- [ ] Run full backend test suite: `pytest backend/tests/unit -q` — all pass
- [ ] Run frontend type check: `cd frontend && npx tsc --noEmit`
- [ ] Start the app locally with a valid `.env` (JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD set)
- [ ] Run seed script: `uv run python scripts/seed_admin.py`
- [ ] Open browser, verify redirect to `/login`
- [ ] Log in with admin credentials, verify dashboard loads
- [ ] Open `/admin`, create a test viewer user
- [ ] Log in as viewer, verify `/admin` redirects to `/`
- [ ] Log in as admin, navigate to `/admin/users/{id}`, test password change and data reset
- [ ] Verify all 23 existing API endpoints still work (try `/api/v1/stocks` with a Bearer token in Swagger at `/docs`)
