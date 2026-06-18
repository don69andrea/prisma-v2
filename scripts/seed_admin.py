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
