"""Knowledge store port and its in-memory implementation.

The store is the enforcement point for curation: ``search`` only ever sees chunks of
``APPROVED`` documents, so a quarantined or rejected document cannot leak into an answer no
matter what the caller asks for.
"""

from __future__ import annotations

from typing import Protocol

from ai_core.errors import Conflict, NotFound
from ai_core.rag.models import Chunk, Document, DocumentStatus, SearchHit


class KnowledgeStore(Protocol):
    async def init(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool: ...

    async def add_document(self, doc: Document) -> None:
        """Raises ``Conflict`` if a document with the same content hash exists."""

    async def add_chunks(self, document_id: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None: ...

    async def get_document(self, document_id: str) -> Document: ...
    async def find_by_hash(self, sha256: str) -> Document | None: ...
    async def list_documents(self, status: DocumentStatus | None = None) -> list[Document]: ...
    async def set_status(self, document_id: str, status: DocumentStatus) -> Document: ...
    async def search(self, embedding: list[float], k: int) -> list[SearchHit]: ...


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._chunks: dict[str, list[tuple[Chunk, list[float]]]] = {}

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def add_document(self, doc: Document) -> None:
        if any(d.sha256 == doc.sha256 for d in self._docs.values()):
            raise Conflict("a document with identical content already exists")
        self._docs[doc.id] = doc
        self._chunks[doc.id] = []

    async def add_chunks(self, document_id: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if document_id not in self._docs:
            raise NotFound("document not found")
        self._chunks[document_id] = list(zip(chunks, embeddings, strict=True))

    async def get_document(self, document_id: str) -> Document:
        try:
            return self._docs[document_id]
        except KeyError:
            raise NotFound("document not found") from None

    async def find_by_hash(self, sha256: str) -> Document | None:
        return next((d for d in self._docs.values() if d.sha256 == sha256), None)

    async def list_documents(self, status: DocumentStatus | None = None) -> list[Document]:
        docs = sorted(self._docs.values(), key=lambda d: d.created_at)
        return [d for d in docs if status is None or d.status is status]

    async def set_status(self, document_id: str, status: DocumentStatus) -> Document:
        doc = await self.get_document(document_id)
        doc.status = status
        return doc

    async def search(self, embedding: list[float], k: int) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for doc_id, entries in self._chunks.items():
            doc = self._docs[doc_id]
            if doc.status is not DocumentStatus.APPROVED:
                continue
            for chunk, vector in entries:
                hits.append(
                    SearchHit(
                        chunk_id=f"{doc_id}:{chunk.index}",
                        document_id=doc_id,
                        source=doc.source,
                        sha256=doc.sha256,
                        index=chunk.index,
                        text=chunk.text,
                        start=chunk.start,
                        end=chunk.end,
                        score=_dot(embedding, vector),
                    )
                )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
