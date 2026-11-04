# Handoff

Updated: 2026-11-01

Rewritten at the end of every session. A fresh session must be able to resume from disk alone.

## 1. What is live

Nothing is deployed. `make demo` runs the stack locally (`api`, `db` with pgvector, `redis`) with the lab on, at
http://localhost:8000; plain `docker compose up` runs the API alone, as it would run for real.

## 2. Where we stopped

The service, the landing page and lab UI (`site/`), the browser tests (`e2e/`), delivery files and documentation are
complete and verified. Open items are in the checklist (a semantic embedder, durable review checkpoints).

## 3. What the owner does now

Push to GitHub and enable Actions: the workflow in `.github/workflows/ci.yml` is linted but has never run there.

## 4. Deadlines

None.

## 5. What NOT to do

- Do not add a provider fallback that bypasses the sensitivity policy: [ADR 0001](adr/0001-fail-closed-sensitivity-routing.md).
- Do not make chunks retrievable before a curator approves them: [ADR 0002](adr/0002-quarantine-by-default-rag.md).
- Do not return distinct webhook errors per failed check; the reasons belong in metrics: [ADR 0004](adr/0004-signed-timestamped-deduplicated-webhooks.md).
- Do not let unit tests read `DATABASE_URL` or `REDIS_URL` from the environment; they must use the in-memory adapters.
- Do not allow `LAB_MODE` with `APP_ENV=production`, and do not mount `/v1/lab` conditionally on anything else: [ADR 0006](adr/0006-a-lab-mode-that-cannot-reach-production.md).
- Do not edit `site/transcripts.js` by hand: `make transcripts` records it from the running code, and a test compares them.
- Do not add a script, font or stylesheet from another origin to `site/`; the Content Security Policy and the e2e suite refuse it.
- Do not hand-edit one language table to "fix" a string and leave the others: `site/i18n/<code>.js` mirrors `content.js` key for key (English is the source and the fallback), and `e2e/tests/i18n.spec.ts` reads the tables. Strings that quote the lab's English buttons stay English on purpose.

## 6. Decisions

- Routing, quarantine, index, webhooks, composition, lab mode: [ADR 0001](adr/0001-fail-closed-sensitivity-routing.md) to [ADR 0006](adr/0006-a-lab-mode-that-cannot-reach-production.md).

## 7. Learned, not in the code

- The chunker once dropped most of a document that contained one very long token; the regression test is kept.
- A malformed webhook once answered 500 instead of 400 because the base error class carried the wrong status.
- Unit tests picked up the CI environment's database URL and started using real stores.
- A webhook with a new event id but known content answered 409, which a sender retries for ever; found by driving the lab.
- The first embedder hashed with a sign, so an irrelevant question out-scored a relevant one; it is now unsigned, with
  stop words and light stemming, and a test measures the gap.
- A headless browser reached over a container hostname is not a secure context, so WebCrypto vanished; the e2e container
  now shares the API's network and uses `localhost`.
- Clicking "Send valid" before the lab secret arrived signed with nothing; the lab now waits for it.
- With `?lang=` in the address the saved language lost after a reload (the address outranks storage); found by a test that switched language on the lab page. `switchLanguage` now rewrites the parameter.
- Right-to-left: SVG text anchored at its start ran off the artwork card when the page direction leaked into it; the artwork, recorded output and commands are forced left-to-right and a test measures the labels.

## 8. Suite state

Measured on 2026-11-01: 167 unit and API tests, 3 integration tests against real Postgres with pgvector and Redis,
43 browser tests (`make e2e`, against the compose stack, with axe scans of the landing page and every lab tab in both
themes), `ruff` clean, `mypy --strict` clean over 38 source files.
