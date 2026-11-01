# Handoff

Updated: 2026-11-01

Rewritten at the end of every session. A fresh session must be able to resume from disk alone.

## 1. What is live

Nothing is deployed. The compose stack (`api`, `db` with pgvector, `redis`) runs locally.

## 2. Where we stopped

The service, its tests, delivery files and documentation are complete and verified. Open items are in the checklist (a
semantic embedder, durable review checkpoints).

## 3. What the owner does now

Push to GitHub and enable Actions: the workflow in `.github/workflows/ci.yml` is linted but has never run there.

## 4. Deadlines

None.

## 5. What NOT to do

- Do not add a provider fallback that bypasses the sensitivity policy: [ADR 0001](adr/0001-fail-closed-sensitivity-routing.md).
- Do not make chunks retrievable before a curator approves them: [ADR 0002](adr/0002-quarantine-by-default-rag.md).
- Do not return distinct webhook errors per failed check; the reasons belong in metrics: [ADR 0004](adr/0004-signed-timestamped-deduplicated-webhooks.md).
- Do not let unit tests read `DATABASE_URL` or `REDIS_URL` from the environment; they must use the in-memory adapters.

## 6. Decisions

- Routing, quarantine, index, webhooks, composition: [ADR 0001](adr/0001-fail-closed-sensitivity-routing.md) to [ADR 0005](adr/0005-ports-adapters-and-a-single-composition-root.md).

## 7. Learned, not in the code

- The chunker once dropped most of a document that contained one very long token; the regression test is kept.
- A malformed webhook once answered 500 instead of 400 because the base error class carried the wrong status.
- Unit tests picked up the CI environment's database URL and started using real stores.

## 8. Suite state

Measured on 2026-11-01: 138 unit and API tests, 2 integration tests against real Postgres with pgvector and Redis,
`ruff` clean, `mypy --strict` clean over 36 source files.
