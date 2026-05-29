"""Pydantic-Schema für LLM-Output beim Universe-Wizard."""

from pydantic import BaseModel, Field


class UniverseSuggestionSchema(BaseModel):
    """LLM-Tool-Output. Strikte Validierung — fehlerhafte Outputs verwerfen."""

    name: str = Field(..., min_length=2, max_length=40)
    region: str = Field(..., min_length=2, max_length=20)
    tickers: list[str] = Field(..., min_length=2, max_length=15)
    reasoning: str = Field(..., min_length=10, max_length=400)
