"""User domain entity."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UserRole(StrEnum):
    admin = "admin"
    viewer = "viewer"


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str
    hashed_password: str
    role: UserRole = UserRole.viewer
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
