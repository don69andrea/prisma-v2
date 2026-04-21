"""Application-wide settings loaded from environment variables or a .env file."""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://prisma:prisma@db:5432/prisma"
    anthropic_api_key: str = ""
    environment: str = "development"

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_asyncpg_scheme(cls, value: object) -> object:
        """Render stellt DATABASE_URL als 'postgresql://...' bereit, unser
        async SQLAlchemy-Engine braucht aber 'postgresql+asyncpg://...'.
        Dieser Validator normalisiert das transparent."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    # NoDecode prevents pydantic-settings from JSON-decoding the raw env string;
    # the validator below accepts either comma-separated strings or real lists.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    api_key: str = "change-me"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        """Allow CORS_ORIGINS to be given as either a comma-separated string
        or an actual Python list (the latter is used in tests)."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(item) for item in value]
        raise TypeError(f"cannot parse cors_origins from {type(value).__name__}")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton per process)."""
    return Settings()
