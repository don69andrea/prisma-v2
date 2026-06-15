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
    voyage_api_key: str = ""
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

    # MCP-Tool-API-Key für X-API-Key auf /api/v1/runs. Getrennt vom Admin-Key
    # (api_key), damit Tool-Auth unabhängig rotiert werden kann.
    # Leer = opt-in disabled, kein Auth-Enforcement.
    tool_api_key: str = ""

    # FinancialModelingPrep API-Key (kostenloser Tier, 250 Calls/Tag).
    # Leer oder bekannte Platzhalter ("your-fmp-key") = FMP-Adapter
    # deaktiviert; kein Fehler, kein HTTP-Call. Kein Boot-Fehler in
    # Entwicklung/CI ohne echten Key.
    fmp_api_key: str = ""

    # SendGrid API-Key für Alert-E-Mails.
    # Leer oder bekannte Platzhalter = E-Mail-Versand graceful deaktiviert.
    sendgrid_api_key: str = ""

    # CoinGecko API Key (optional — Free Tier: 30 Req/min, 10.000/Monat)
    coingecko_api_key: str = ""

    # Krypto-Feature aktivieren (default: true)
    crypto_feature_enabled: bool = True

    budget_cap_usd: Decimal = Decimal("20.00")
    budget_cap_threshold: Decimal = Decimal("0.95")

    max_concurrent_batch_workers: int = 3
    stale_batch_timeout_seconds: int = 600

    # Signal-Aggregation: Gewichtung der drei Signal-Quellen (Summe muss 1.0 ergeben)
    # Konfigurierbar via ENV: SIGNAL_QUANT_WEIGHT, SIGNAL_ML_WEIGHT, SIGNAL_MACRO_WEIGHT
    signal_quant_weight: float = 0.45
    signal_ml_weight: float = 0.35
    signal_macro_weight: float = 0.20

    @field_validator("signal_macro_weight", mode="after")
    @classmethod
    def validate_signal_weights_sum(cls, macro: float) -> float:
        return macro

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
    def _validate_signal_weights(self) -> "Settings":
        total = self.signal_quant_weight + self.signal_ml_weight + self.signal_macro_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"SIGNAL_*_WEIGHT Summe muss 1.0 ergeben, erhalten: {total:.4f} "
                f"(quant={self.signal_quant_weight}, ml={self.signal_ml_weight}, macro={self.signal_macro_weight})"
            )
        return self

    @model_validator(mode="after")
    def _api_key_required_in_production(self) -> "Settings":
        """In Production-Umgebung müssen API_KEY und ANTHROPIC_API_KEY explizit
        gesetzt sein — sonst booten wir nicht. Verhindert, dass ein leerer/
        Default-Wert unbemerkt in Production landet."""
        if self.environment == "production":
            if not self.api_key:
                raise ValueError("API_KEY muss in der Production-Umgebung gesetzt sein")
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY muss in der Production-Umgebung gesetzt sein")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton per process)."""
    return Settings()
