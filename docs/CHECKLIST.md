# Master checklist

_What_ and _when_. The _how_ lives in the code and tests, the _why_ in the [ADRs](adr/README.md).

| #   | Item                                                               | Status  | Evidence                                                                              |
| --- | ------------------------------------------------------------------ | ------- | ------------------------------------------------------------------------------------- |
| 1   | Sensitivity routing that fails closed, per-provider circuit breaker | done    | [ADR 0001](adr/0001-fail-closed-sensitivity-routing.md), `tests/test_router.py`       |
| 2   | Quarantine-by-default RAG with evidence policy and citations       | done    | [ADR 0002](adr/0002-quarantine-by-default-rag.md), `tests/test_rag_pipeline.py`       |
| 3   | Partial HNSW index on a denormalised flag                          | done    | [ADR 0003](adr/0003-partial-hnsw-index.md), `tests/test_integration_stores.py`        |
| 4   | Signed, timestamped, de-duplicated webhooks                        | done    | [ADR 0004](adr/0004-signed-timestamped-deduplicated-webhooks.md), `tests/test_webhooks.py` |
| 5   | Human-in-the-loop review workflow (LangGraph, edit before approve) | done    | `tests/test_review_workflow.py`                                                       |
| 6   | Containers and health-gated compose                                | done    | `Dockerfile`, `docker-compose.yml`                                                    |
| 7   | CI workflow                                                        | written | `.github/workflows/ci.yml`: not yet run on GitHub                                     |
| 8   | Embedder backed by a semantic model                                | todo    | the two-method `Embedder` protocol is the seam; `HashingEmbedder` is lexical          |
| 9   | Durable review checkpoints and a worker for slow webhook handlers  | todo    | README "Limitations"                                                                  |

Status is one of `todo`, `doing`, `done`, `written` (exists, not yet exercised where it will run), `dropped`.
