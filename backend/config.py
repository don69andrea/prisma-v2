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
        return list(value)  # type: ignore[arg-type]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton per process)."""
    return Settings()
