"""Universe-Entity und WeightConfig-Value-Object."""

from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

VALID_MODELS = frozenset(
    {"quality_classic", "alpha", "trend_momentum", "value_alpha_potential", "diversification"}
)
_WEIGHT_TOLERANCE = 1e-6


class WeightConfig(BaseModel):
    """Gewichtung der 5 Quant-Modelle — muss exakt zu 1.0 summieren."""

    model_config = {"frozen": True}

    weights: dict[str, float]

    @field_validator("weights")
    @classmethod
    def validate_model_names(cls, v: dict[str, float]) -> dict[str, float]:
        unknown = set(v.keys()) - VALID_MODELS
        if unknown:
            raise ValueError(f"Unbekannte Modell-Namen: {unknown}")
        return v

    @model_validator(mode="after")
    def validate_sum(self) -> "WeightConfig":
        total = sum(self.weights.values())
        if abs(total - 1.0) > _WEIGHT_TOLERANCE:
            raise ValueError(f"Gewichte müssen zu 1.0 summieren, erhalten: {total:.6f}")
        return self

    @classmethod
    def equal(cls) -> "WeightConfig":
        """Erstellt eine gleichgewichtete Konfiguration (je 0.20)."""
        return cls(weights={m: 0.20 for m in VALID_MODELS})


class Universe(BaseModel):
    """Menge von Aktien, die gemeinsam gerankt werden."""

    model_config = {"frozen": True}

    id: UUID
    name: str
    tickers: tuple[str, ...]
    region: str

    @field_validator("tickers", mode="before")
    @classmethod
    def uppercase_tickers(cls, v: object) -> tuple[str, ...]:
        if not isinstance(v, (list, tuple)):
            raise ValueError("tickers must be a list or tuple")
        return tuple(t.upper() for t in v)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name darf nicht leer sein")
        return v
