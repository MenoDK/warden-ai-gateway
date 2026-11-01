"""PostgreSQL + pgvector implementation of ``KnowledgeStore``."""

from __future__ import annotations

import json
from typing import Any, cast

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from ai_core.errors import Conflict, NotFound
from ai_core.rag.models import Chunk, Document, DocumentStatus, SearchHit


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vector) + "]"


def _doc(row: dict[str, Any]) -> Document:
    return Document(
        id=row["id"],
        source=row["source"],
        sha256=row["sha256"],
        status=DocumentStatus(row["status"]),
        metadata=row["metadata"],
        created_at=row["created_at"],
    )


class PgVectorKnowledgeStore:
    def __init__(self, dsn: str, *, dim: int) -> None:
        self._dim = int(dim)  # interpolated into DDL below, so force an int
        self._pool = AsyncConnectionPool(dsn, min_size=1, max_size=5, open=False, kwargs={"row_factory": dict_row})

    async def init(self) -> None:
        await self._pool.open()
        async with self._pool.connection() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_documents (
                  id          text PRIMARY KEY,
                  source      text NOT NULL,
                  sha256      text NOT NULL UNIQUE,
                  status      text NOT NULL CHECK (status IN ('quarantined','approved','rejected')),
                  metadata    jsonb NOT NULL DEFAULT '{}',
                  created_at  timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS kb_chunks (
                  id           text PRIMARY KEY,
                  document_id  text NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
                  chunk_index  int  NOT NULL,
                  text         text NOT NULL,
                  start_offset int  NOT NULL,
                  end_offset   int  NOT NULL,
                  -- Denormalised from kb_documents.status. Why: an ANN index cannot cheaply
                  -- post-filter by a joined column (it may return fewer than k rows once most
                  -- chunks are quarantined). A flag on the row lets us use a *partial* HNSW
                  -- index that contains only retrievable chunks.
                  approved     boolean NOT NULL DEFAULT false,
                  embedding    vector({self._dim}) NOT NULL,
                  UNIQUE (document_id, chunk_index)
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS kb_chunks_embedding_approved_idx "
                "ON kb_chunks USING hnsw (embedding vector_cosine_ops) WHERE approved"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS kb_documents_status_created_idx ON kb_documents (status, created_at)"
            )

    async def close(self) -> None:
        await self._pool.close()

    async def ping(self) -> bool:
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def add_document(self, doc: Document) -> None:
        try:
            async with self._pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO kb_documents (id, source, sha256, status, metadata, created_at) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb, %s)",
                    (doc.id, doc.source, doc.sha256, doc.status.value, json.dumps(doc.metadata), doc.created_at),
                )
        except UniqueViolation:
            raise Conflict("a document with identical content already exists") from None

    async def add_chunks(self, document_id: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute("DELETE FROM kb_chunks WHERE document_id = %s", (document_id,))
            for chunk, vector in zip(chunks, embeddings, strict=True):
                await conn.execute(
                    "INSERT INTO kb_chunks (id, document_id, chunk_index, text, start_offset, end_offset, embedding) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
                    (
                        f"{document_id}:{chunk.index}",
                        document_id,
                        chunk.index,
                        chunk.text,
                        chunk.start,
                        chunk.end,
                        _vector_literal(vector),
                    ),
                )

    async def get_document(self, document_id: str) -> Document:
        async with self._pool.connection() as conn:
            cur = await conn.execute("SELECT * FROM kb_documents WHERE id = %s", (document_id,))
            row = cast("dict[str, Any] | None", await cur.fetchone())
        if row is None:
            raise NotFound("document not found")
        return _doc(row)

    async def find_by_hash(self, sha256: str) -> Document | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute("SELECT * FROM kb_documents WHERE sha256 = %s", (sha256,))
            row = cast("dict[str, Any] | None", await cur.fetchone())
        return _doc(row) if row else None

    async def list_documents(self, status: DocumentStatus | None = None) -> list[Document]:
        async with self._pool.connection() as conn:
            if status is None:
                cur = await conn.execute("SELECT * FROM kb_documents ORDER BY created_at")
            else:
                cur = await conn.execute(
                    "SELECT * FROM kb_documents WHERE status = %s ORDER BY created_at", (status.value,)
                )
            return [_doc(r) for r in cast("list[dict[str, Any]]", await cur.fetchall())]

    async def set_status(self, document_id: str, status: DocumentStatus) -> Document:
        # One transaction: the document status and its chunks' retrievability flip together.
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "UPDATE kb_documents SET status = %s WHERE id = %s RETURNING *", (status.value, document_id)
            )
            row = cast("dict[str, Any] | None", await cur.fetchone())
            if row is None:
                raise NotFound("document not found")
            await conn.execute(
                "UPDATE kb_chunks SET approved = %s WHERE document_id = %s",
                (status is DocumentStatus.APPROVED, document_id),
            )
        return _doc(row)

    async def search(self, embedding: list[float], k: int) -> list[SearchHit]:
        literal = _vector_literal(embedding)
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT c.id, c.document_id, d.source, d.sha256, c.chunk_index, c.text,
                       c.start_offset, c.end_offset,
                       1 - (c.embedding <=> %s::vector) AS score
                FROM kb_chunks c
                JOIN kb_documents d ON d.id = c.document_id
                WHERE c.approved
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (literal, literal, k),
            )
            rows = cast("list[dict[str, Any]]", await cur.fetchall())
        return [
            SearchHit(
                chunk_id=r["id"],
                document_id=r["document_id"],
                source=r["source"],
                sha256=r["sha256"],
                index=r["chunk_index"],
                text=r["text"],
                start=r["start_offset"],
                end=r["end_offset"],
                score=float(r["score"]),
            )
            for r in rows
        ]
