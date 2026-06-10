"""Pydantic-Schemas für Chat API."""

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    role: str = Field("user", pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessageRequest] = Field(default_factory=list, max_length=20)
