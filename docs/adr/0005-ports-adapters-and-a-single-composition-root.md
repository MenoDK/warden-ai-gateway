# ADR 0005: Ports and adapters with one composition root

Status: Accepted

## Context
The service depends on things that change between a laptop, a test run and production: the model providers, the
knowledge store, the idempotency store, the embedder. Tests that patch concrete classes are tied to how the code happens
to call them, and break when it is refactored.

## Decision
- `LLMProvider`, `KnowledgeStore`, `IdempotencyStore` and `Embedder` are `Protocol`s.
- `src/ai_core/container.py` is the only module that imports concrete adapters. Everything else receives what it needs.
- The in-memory adapters are first-class implementations, not mocks. They run the same behaviour tests as the real ones,
  and the integration tests exercise the Postgres and Redis adapters against real services.
- `HashingEmbedder` is deterministic and dependency-free so the retrieval tests can be exact. The two-method `Embedder`
  protocol is where a semantic model plugs in.
- No queue, worker, ORM or authentication framework: nothing here needs one yet (see the limitations in the README).

## Rejected alternatives
- **Patching concrete classes in tests** (`unittest.mock.patch` on module paths). Couples the tests to the call sites.
- **A dependency-injection framework.** One dataclass built in one function is enough for four ports.
- **A task queue from the start.** Webhook handlers run inline and are fast; an outbox plus worker is the next step if
  they stop being fast, and the README says so.

## Consequences
- (+) Swapping an adapter is a one-line change in the container, and tests need no patching.
- (+) `mypy --strict` checks every port boundary.
- (−) The in-memory adapters must be kept behaviourally equal to the real ones; the shared tests are what enforces it.
