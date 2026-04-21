"""Stock-Entity — reine Domain-Klasse ohne externe Framework-Abhängigkeiten."""

from uuid import UUID

from pydantic import BaseModel, field_validator


class Stock(BaseModel):
    """Repräsentiert ein reales Unternehmen als Basiseinheit im PRISMA-Universum.

    Alle Felder sind immutable (frozen=True) damit Stock-Instanzen sicher als
    Value-Objects in Sets und als Dict-Keys verwendet werden können.
    """

    model_config = {"frozen": True}

    id: UUID
    ticker: str
    name: str
    isin: str | None = None
    sector: str | None = None
    country: str | None = None
    # ISO 4217 three-letter currency code, e.g. "USD", "CHF"
    currency: str

    @field_validator("ticker", mode="before")
    @classmethod
    def ticker_must_be_uppercase(cls, value: str) -> str:
        """Ticker-Symbole werden immer in Grossbuchstaben gespeichert."""
        if not isinstance(value, str):
            raise ValueError("ticker must be a string")
        return value.upper()

    @field_validator("currency", mode="before")
    @classmethod
    def currency_must_be_three_letters(cls, value: str) -> str:
        """ISO-4217-Codes sind exakt 3 Buchstaben lang."""
        if not isinstance(value, str) or len(value) != 3:
            raise ValueError("currency must be a 3-letter ISO 4217 code")
        return value.upper()
