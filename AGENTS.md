# Agent contract

Tool-neutral: what any engineer or coding agent needs to work here without asking.

## Commands

| Task                                                       | Command                                                           |
| ---------------------------------------------------------- | ----------------------------------------------------------------- |
| Install                                                    | `make install`                                                    |
| Everything static (ruff, mypy --strict, unit and API tests) | `make check`                                                      |
| Integration tests (real Postgres with pgvector, Redis)     | `docker compose up -d db redis`, then `make test-integration`     |
| Run the whole stack                                        | `make up`                                                         |
| Documentation guards                                       | `docsguard check`                                                 |

## Definition of done

1. A test covers it and fails without the change; a security rule gets an adversarial test (try to break it).
2. `make check` passes and you can quote its output; an integration test covers any change to a store.
3. An ADR exists for any decision a newcomer would have to reverse-engineer, with the rejected alternatives.
4. `docs/HANDOFF.md` carries the numbers that were printed, not the ones that were expected.

## Boundaries

- Do not weaken the sensitivity policy, the quarantine rule or the signature check to make a test pass.
- Ask before adding a dependency or changing a public route, an error code or a configuration key.
- Anything outside the task goes into `docs/CHECKLIST.md`, not into this change.

## Reporting

Say what happened, not what was expected. A failed test, a skipped check or an unverified claim goes in the report as it is.
