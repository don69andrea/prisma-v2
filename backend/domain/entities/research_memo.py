"""Research-Memo Domain-Typen: ContradictionItem (Value-Object) und ResearchMemo (Entity)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Sentinel-Wert für Memos die bei LLM-Fehler als Fallback persistiert wurden.
# Referenz: NarrativeService._build_error_memo_schema()
# Zentrale Definition vermeidet Magic-String-Drift zwischen Service und Router.
ERROR_FALLBACK_MODEL_VERSION = "error-fallback"


class ContradictionItem(BaseModel):
    """Modell-zu-Modell-Widerspruch.

    Lebt hier (nicht im Schema-File), weil sowohl ResearchMemoSchema
    als auch ResearchMemo ihn nutzen.
    """

    model_config = {"frozen": True}

    model_a: str = Field(..., min_length=1, max_length=64)
    model_b: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., max_length=200)


class ResearchMemo(BaseModel):
    """Persistierte Domain-Entity für ein Research-Memo.

    Constraints sind die DB-CHECK/Length-Constraints. Strengere
    LLM-Output-Validation lebt im ResearchMemoSchema (siehe schemas/).
    """

    model_config = {"frozen": True}

    id: UUID
    stock_id: UUID
    model_run_id: UUID
    language: Literal["de", "en"] = "de"
    created_at: datetime

    one_liner: str = Field(..., max_length=150)
    ranking_interpretation: str = Field(..., max_length=1000)
    sweet_spot: bool
    sweet_spot_explanation: str | None = Field(None, max_length=300)
    contradictions: list[ContradictionItem] = Field(default_factory=list)
    key_strengths: list[str]
    key_risks: list[str]
    confidence: Literal["low", "medium", "high"]
    model_version: str = Field(..., max_length=64)
