"""Application-wide settings loaded from environment variables or a .env file."""

from decimal import Decimal
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
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

    # Bewusst leerer Default — kein "change-me", damit Tests, die einen
    # bestimmten Key voraussetzen, nicht heimlich an einem Production-Default
    # hängen können. Der Validator unten bricht den Boot in Production ab,
    # wenn API_KEY nicht gesetzt ist.
    api_key: str = ""

    budget_cap_usd: Decimal = Decimal("20.00")
    budget_cap_threshold: Decimal = Decimal("0.95")

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

    @field_validator("budget_cap_threshold", mode="before")
    @classmethod
    def validate_budget_cap_threshold(cls, value: object) -> Decimal:
        """Stellt sicher, dass budget_cap_threshold im Bereich [0, 1] liegt
        und reicht den geparsten Decimal-Wert weiter — sonst kämen z.B.
        Strings aus ENV-Vars unverändert durch."""
        decimal_value = Decimal(str(value))
        if not (Decimal("0") <= decimal_value <= Decimal("1")):
            raise ValueError(
                f"budget_cap_threshold muss zwischen 0 und 1 liegen, erhalten: {value}"
            )
        return decimal_value

    @model_validator(mode="after")
    def _api_key_required_in_production(self) -> "Settings":
        """In Production-Umgebung muss API_KEY explizit gesetzt sein —
        sonst booten wir nicht. Verhindert, dass ein leerer/Default-Wert
        unbemerkt in Production landet."""
        if self.environment == "production" and not self.api_key:
            raise ValueError("API_KEY muss in der Production-Umgebung gesetzt sein")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton per process)."""
    return Settings()
