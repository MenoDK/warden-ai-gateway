from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ai_core.gateway.provider import Sensitivity


class CompletionIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    system: str = Field(default="", max_length=4_000)
    sensitivity: Sensitivity = Sensitivity.AUTO
    json_mode: bool = False
    max_tokens: int = Field(default=512, ge=1, le=4096)


class AttemptOut(BaseModel):
    provider: str
    locality: str
    outcome: str
    detail: str = ""


class CompletionOut(BaseModel):
    text: str
    provider: str
    locality: str
    sensitivity: str
    pseudonymised: bool
    attempts: list[AttemptOut]
    structured: dict[str, Any] | None = None


class MaskIn(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


class MaskOut(BaseModel):
    text: str
    entities: dict[str, int]


class DocumentIn(BaseModel):
    source: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentOut(BaseModel):
    id: str
    source: str
    sha256: str
    status: str
    metadata: dict[str, Any]


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    k: int | None = Field(default=None, ge=1, le=20)
    sensitivity: Sensitivity = Sensitivity.AUTO


class CitationOut(BaseModel):
    marker: int
    document_id: str
    source: str
    chunk_id: str
    start: int
    end: int
    score: float
    sha256: str


class AnswerOut(BaseModel):
    status: str
    mode: str
    text: str
    citations: list[CitationOut]
    provider: str | None = None
    sensitivity: str | None = None
    pseudonymised: bool = False
    warning: str | None = None


class ReviewIn(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class DecisionIn(BaseModel):
    approved: bool
    edited_text: str | None = Field(default=None, max_length=20_000)


class ReviewOut(BaseModel):
    id: str
    status: str
    question: str
    draft: str
    mode: str
    provider: str | None
    citations: list[dict[str, Any]]
    final_text: str
    pii_entities: dict[str, int]
    reason: str
