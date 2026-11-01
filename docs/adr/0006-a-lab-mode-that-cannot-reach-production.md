# ADR 0006: A lab mode that makes failure visible and cannot reach production

Status: Accepted

## Context
The valuable behaviour of this service is what it does when things go wrong: a local model is down, a document is
hostile, a webhook is replayed. A reviewer cannot see any of that by sending happy-path requests, and asking them to
stop containers and craft HMAC signatures by hand means most will not try. A demonstration needs outage switches, a way
to see what a third party received, and a way to sign events in a browser. Those are also exactly the features that must
never exist on a real deployment: a switch that turns off a provider, an endpoint that prints the webhook secret.

## Decision
- One flag, `LAB_MODE`, off by default. When on, the container wraps each provider in a switchable one and adds a
  simulated external model (`demo-cloud`) that **records every prompt it receives**, so the page can show what crossed
  the trust boundary. The routes live under `/v1/lab` and are mounted only when the flag is on; otherwise they are a 404.
- The settings validator **refuses** `LAB_MODE` when `APP_ENV=production`, the same way it refuses the default API key.
  The process does not start; there is no warning to ignore.
- `SITE_DIR` serves the landing page and the lab UI from the same process, under a strict Content Security Policy
  (`default-src 'self'`, no inline script or style). Unset by default.
- If no webhook secret is configured, lab mode invents one for the life of the process, so the demo works without any
  setup. Outside the lab an unset secret stays empty and no webhook can verify.
- `POST /v1/lab/reset` empties the knowledge base, the inbox and the switches. Event ids are left alone on purpose:
  forgetting them would make an old capture replayable.
- The lab is covered by the same quality bar as the service: API tests, an integration test, and a Playwright suite with
  accessibility scans, run in CI against the real stack.

## Rejected alternatives
- **A separate demo application.** It would drift from the service it claims to show, and a reviewer could not tell
  whether the behaviour on screen is the behaviour that is tested.
- **Screenshots and a recorded video only.** Cheap, and unfalsifiable. The landing page does show recorded output, but
  a test fails if that output stops being what the service produces (`tests/test_transcripts.py`).
- **Always-on debug endpoints behind the API key.** One leaked key would then turn off a provider or read the secret.
  Not mounting the routes at all is a stronger guarantee than guarding them.
- **A warning in production when the flag is on.** Warnings are read once and then ignored.

## Consequences
- (+) Every hard part can be tried in a browser in under a minute, and the claim "the cloud never saw it" is evidence,
  not assertion.
- (+) The refusal is tested (`tests/test_lab.py::test_the_mode_is_refused_in_production`).
- (−) The lab exposes the webhook secret to whoever holds the API key, by design. That is acceptable for a local demo and
  is the reason the mode cannot run in production.
- (−) The simulated cloud model is not a model. It demonstrates the boundary, not answer quality.
