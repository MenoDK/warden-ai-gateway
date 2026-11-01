# ADR-0003: Partial HNSW index on a denormalised `approved` flag

**Status:** accepted

## Context
Retrieval must only return chunks of `approved` documents. The natural schema keeps the status on `kb_documents`
and joins at query time. An approximate-nearest-neighbour index, however, returns its top candidates *before* the
join filters them: when most chunks belong to quarantined or rejected documents, a `LIMIT k` query can return far
fewer than *k* rows (or none) even though enough approved chunks exist.

## Decision
- Denormalise the flag onto the row: `kb_chunks.approved boolean`.
- Index only retrievable chunks: `CREATE INDEX … USING hnsw (embedding vector_cosine_ops) WHERE approved`.
- Queries use `WHERE c.approved`, which lets the planner use the partial index.
- Approving or rejecting a document updates `kb_documents.status` **and** `kb_chunks.approved` in one transaction, so
  the two can never disagree.
- `UNIQUE (document_id, chunk_index)` and `UNIQUE (sha256)` protect integrity; `(status, created_at)` serves the curator's queue.

## Consequences
- (+) Index size and recall depend on what is *retrievable*, not on everything ever ingested.
- (+) Quarantined content is physically absent from the search index.
- (−) One redundant column to keep consistent — contained in a single transactional method and covered by an
  integration test against a real database.
