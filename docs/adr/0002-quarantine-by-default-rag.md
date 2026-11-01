# ADR-0002: Quarantine-by-default knowledge ingestion

**Status:** accepted

## Context
A RAG index is a trust boundary: whatever is retrievable ends up inside a prompt. Documents can contain credentials,
irrelevant noise, or text written to hijack the model (indirect prompt injection).

## Decision
1. Only sources matching an allow-list are accepted at all; size is capped; identical content is rejected (SHA-256).
2. Secrets are **redacted before** embedding and storage.
3. Chunks that address the model are **excluded as a whole** (neutralising only the offending sentence leaves the rest
   of a poisoned passage steering the model). Their offsets — not their text — are recorded for the curator.
4. A new document is `quarantined`. Retrieval only ever sees `approved` documents; the store enforces this, not the caller.
5. Retrieval is gated by an evidence policy (similarity threshold **and** minimum evidence count). Below it the
   pipeline answers `insufficient_evidence` and does not call the model.
6. A generated answer must cite sources that were actually provided; otherwise it is replaced by an extractive answer.

## Consequences
- (+) Poisoned or secret-bearing content cannot reach a prompt without passing a human and three automated checks.
- (+) "Not enough evidence" is a normal, cheap outcome.
- (−) A human curation step. Acceptable for a knowledge base that matters; auto-approval can be added per source later.
- (−) The injection heuristic can have false positives. It is intentionally narrow and tested against benign
  technical prose; quarantined chunks are reported, never silently lost.
