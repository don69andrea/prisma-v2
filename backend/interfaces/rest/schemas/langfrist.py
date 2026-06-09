"""Pydantic-Schema für den VIAC Langfrist-Score-Endpoint."""

from pydantic import BaseModel


class LangfristScoreResponse(BaseModel):
    ticker: str
    value: float
    components: dict[str, float]
    explanation: str
    disclaimer: str = (
        "Dieser Score dient ausschliesslich zu Informationszwecken "
        "und stellt keine Anlageberatung dar. Wertentwicklungen der "
        "Vergangenheit sind kein verlässlicher Indikator für künftige Ergebnisse."
    )
