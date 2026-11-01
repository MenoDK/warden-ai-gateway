# Architecture decision records

Each record states the problem, what was chosen, **what was rejected and why**, and the cost that was accepted.

| # | Decision |
|---|----------|
| [0001](0001-fail-closed-sensitivity-routing.md) | Fail-closed, sensitivity-aware model routing |
| [0002](0002-quarantine-by-default-rag.md) | Quarantine-by-default knowledge ingestion |
| [0003](0003-partial-hnsw-index.md) | Partial HNSW index on a denormalised `approved` flag |
| [0004](0004-signed-timestamped-deduplicated-webhooks.md) | Signed, timestamped, de-duplicated webhooks |
| [0005](0005-ports-adapters-and-a-single-composition-root.md) | Ports and adapters with one composition root |
| [0006](0006-a-lab-mode-that-cannot-reach-production.md) | A lab mode that makes failure visible and cannot reach production |

A record is never rewritten to hide a reversal: a new record supersedes it and the old one says so
(`Superseded by: ADR NNNN`). Template and rules: the `adr` skill in `.claude/skills/adr/`.
