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
