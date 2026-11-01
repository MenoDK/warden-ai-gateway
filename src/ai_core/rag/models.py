from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal


class DocumentStatus(StrEnum):
    QUARANTINED = "quarantined"  # ingested, NOT retrievable until a curator approves it
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class Document:
    id: str
    source: str
    sha256: str
    status: DocumentStatus = DocumentStatus.QUARANTINED
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    start: int  # character offsets into the original document (provenance)
    end: int


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    source: str
    sha256: str
    index: int
    text: str
    start: int
    end: int
    score: float


@dataclass(frozen=True)
class Citation:
    marker: int
    document_id: str
    source: str
    chunk_id: str
    start: int
    end: int
    score: float
    sha256: str


@dataclass(frozen=True)
class EvidenceBundle:
    question: str
    hits: tuple[SearchHit, ...]
    sufficient: bool
    reason: str


@dataclass(frozen=True)
class Answer:
    status: Literal["answered", "insufficient_evidence"]
    text: str
    # "generated": written by a model. "extractive": quoted straight from the evidence --
    # the degraded mode used when no model is available or the model's output is unusable.
    mode: Literal["generated", "extractive", "none"] = "none"
    citations: tuple[Citation, ...] = ()
    provider: str | None = None
    sensitivity: str | None = None
    pseudonymised: bool = False
    warning: str | None = None
