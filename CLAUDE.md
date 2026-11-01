# warden-ai-gateway

A FastAPI service for putting language models behind rules: requests are routed by the sensitivity of their content and
fail closed, knowledge enters a retrieval index only after a human approves it, and webhooks are signed, timestamped and
de-duplicated. Python 3.11+, `mypy --strict`, pgvector, Redis, LangGraph.

## Start here

- Map of every document: [docs/00-READ-FIRST.md](docs/00-READ-FIRST.md). Open a document only when the map says to.
- Resuming work: `docs/HANDOFF.md` first; rewrite it before you stop.
- Commands and definition of done: @AGENTS.md

## Layout

- `src/ai_core/gateway/`: provider port, sensitivity router, circuit breaker, JSON repair, adapters.
- `src/ai_core/rag/`: chunking, curation pipeline, safety filters, stores (memory and pgvector).
- `src/ai_core/webhooks/`: signature, idempotency stores, dispatcher. `src/ai_core/api/`: thin HTTP layer.
- `src/ai_core/container.py`: the only module that imports concrete adapters.
- `src/ai_core/lab.py` and `api/lab.py`: lab mode, off by default and refused in production (ADR 0006).
- `site/`: landing page and lab UI, plain JS and CSS served by the API when `SITE_DIR` is set. `e2e/`: Playwright tests.

## Rules that apply to every task

1. **Sensitive data never reaches an external provider.** A policy failure raises a typed error; never add a fallback
   that skips the policy. See ADR 0001.
2. **Retrieval sees only `approved` documents, and the store enforces it**, not the caller. See ADR 0002 and ADR 0003.
3. **Secrets are redacted before embedding and storage**, and never printed in logs or error bodies.
4. **Tests build their own credentials at run time** and use fictitious data only.
5. **New adapters go behind a `Protocol` and are wired in `container.py` only.** See ADR 0005.
6. **Lab mode never reaches production.** The settings validator refuses it; do not add another way in. See ADR 0006.
7. **The site loads nothing from another origin** and keeps inline script and style out (strict CSP); `make e2e` checks it.
8. **Docs are code.** A new document is added to the map in the same commit; `docsguard check` must pass.

Advice versus enforcement: this file is advice. If `docsguard` is installed, `.claude/settings.json` turns the key rules
into hooks (destructive git is refused, and so are writes to secrets and keys).
