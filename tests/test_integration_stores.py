"""Run against real Redis / Postgres(+pgvector). Skipped unless REDIS_URL / DATABASE_URL are set.

docker compose up -d redis db
REDIS_URL=redis://localhost:6379/0 DATABASE_URL=postgresql://ai:ai@localhost:5432/ai pytest -m integration
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from ai_core.errors import Conflict
from ai_core.rag import Document, DocumentStatus, HashingEmbedder, chunk_text
from ai_core.rag.pgvector_store import PgVectorKnowledgeStore
from ai_core.webhooks import RedisIdempotencyStore

pytestmark = pytest.mark.integration
REDIS_URL = os.getenv("REDIS_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")


@pytest.mark.skipif(not REDIS_URL, reason="REDIS_URL not set")
async def test_redis_claim_is_atomic_under_concurrency() -> None:
    store = RedisIdempotencyStore(REDIS_URL)
    key = f"it:{uuid.uuid4().hex}"
    try:
        results = await asyncio.gather(*(store.claim(key, 30) for _ in range(50)))
        assert results.count(True) == 1, "exactly one concurrent caller may win the claim"
        await store.release(key)
        assert await store.claim(key, 30)
    finally:
        await store.release(key)
        await store.close()


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
async def test_pgvector_store_enforces_curation_and_ranks_by_similarity() -> None:
    embedder = HashingEmbedder(256)
    store = PgVectorKnowledgeStore(DATABASE_URL, dim=256)
    await store.init()
    await store.init()  # idempotent
    suffix = uuid.uuid4().hex

    async def add(source: str, text: str) -> Document:
        doc = Document(id=uuid.uuid4().hex, source=source, sha256=uuid.uuid4().hex + uuid.uuid4().hex)
        await store.add_document(doc)
        chunks = chunk_text(text)
        await store.add_chunks(doc.id, chunks, [embedder.embed(c.text) for c in chunks])
        return doc

    try:
        relevant = await add(f"docs/{suffix}-a.md", "Rotating credentials every 90 days limits the blast radius")
        other = await add(f"docs/{suffix}-b.md", "Bananas are rich in potassium and grow in warm climates")
        query = embedder.embed("rotate credentials every 90 days")

        async def mine(k: int = 50) -> list:  # the database may hold other rows: look at ours only
            return [h for h in await store.search(query, k) if suffix in h.source]

        assert await mine() == [], "quarantined chunks must not be searchable"

        await store.set_status(relevant.id, DocumentStatus.APPROVED)
        await store.set_status(other.id, DocumentStatus.APPROVED)
        hits = await mine()
        assert hits[0].document_id == relevant.id and hits[0].score > hits[1].score
        assert hits[0].source.endswith("-a.md") and hits[0].start == 0

        await store.set_status(relevant.id, DocumentStatus.REJECTED)
        assert all(h.document_id != relevant.id for h in await mine())

        with pytest.raises(Conflict):
            await store.add_document(Document(id=uuid.uuid4().hex, source="docs/dup.md", sha256=other.sha256))
        assert await store.ping()
    finally:
        async with store._pool.connection() as conn:
            await conn.execute("DELETE FROM kb_documents WHERE source LIKE %s", (f"docs/{suffix}-%",))
        await store.close()
