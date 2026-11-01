import json
import time

import pytest
from fastapi.testclient import TestClient

from ai_core.webhooks import (
    InMemoryIdempotencyStore,
    SignatureError,
    build_signature_header,
    verify_signature,
)
from tests.conftest import AUTH, CORPUS, OLD_WEBHOOK_SECRET, WEBHOOK_SECRET, FakeClock

BODY = b'{"id":"evt_1","type":"ping"}'
SECRETS = ["current", "previous"]


# --- signature ----------------------------------------------------------------------------


def test_valid_signature_returns_timestamp() -> None:
    header = build_signature_header("current", BODY, timestamp=1_000)
    assert verify_signature(header, BODY, SECRETS, now=1_100) == 1_000


def test_rotation_accepts_the_previous_secret() -> None:
    header = build_signature_header("previous", BODY, timestamp=1_000)
    assert verify_signature(header, BODY, SECRETS, now=1_000) == 1_000


@pytest.mark.parametrize(
    ("header", "reason"),
    [
        (None, "missing"),
        ("", "missing"),
        ("garbage", "malformed"),
        ("t=abc,v1=00", "malformed"),
        ("t=1000", "malformed"),
        ("v1=deadbeef", "malformed"),
    ],
)
def test_rejects_unusable_headers(header: str | None, reason: str) -> None:
    with pytest.raises(SignatureError) as exc:
        verify_signature(header, BODY, SECRETS, now=1_000)
    assert exc.value.reason == reason


def test_replay_outside_the_tolerance_window_is_rejected() -> None:
    header = build_signature_header("current", BODY, timestamp=1_000)
    with pytest.raises(SignatureError) as exc:
        verify_signature(header, BODY, SECRETS, tolerance_seconds=300, now=1_301)
    assert exc.value.reason == "expired"
    assert verify_signature(header, BODY, SECRETS, tolerance_seconds=300, now=1_300) == 1_000


def test_timestamp_from_the_future_is_rejected() -> None:
    header = build_signature_header("current", BODY, timestamp=5_000)
    with pytest.raises(SignatureError) as exc:
        verify_signature(header, BODY, SECRETS, now=1_000)
    assert exc.value.reason == "future"


def test_tampering_with_body_or_timestamp_is_detected() -> None:
    header = build_signature_header("current", BODY, timestamp=1_000)
    with pytest.raises(SignatureError):
        verify_signature(header, BODY + b" ", SECRETS, now=1_000)
    # refreshing an old capture by editing t does not work: t is inside the MAC
    forged = header.replace("t=1000", "t=1200")
    with pytest.raises(SignatureError) as exc:
        verify_signature(forged, BODY, SECRETS, now=1_200)
    assert exc.value.reason == "mismatch"


def test_no_configured_secret_fails_closed() -> None:
    header = build_signature_header("anything", BODY, timestamp=1_000)
    with pytest.raises(SignatureError):
        verify_signature(header, BODY, [], now=1_000)


# --- idempotency ------------------------------------------------------------------------------


async def test_in_memory_claims_are_exclusive_expire_and_release() -> None:
    clock = FakeClock()
    store = InMemoryIdempotencyStore(clock)
    assert await store.claim("k", 60)
    assert not await store.claim("k", 60)
    clock.advance(61)
    assert await store.claim("k", 60), "expired claims can be taken again"
    await store.release("k")
    assert await store.claim("k", 60)


# --- HTTP endpoint ----------------------------------------------------------------------------


def post(
    client: TestClient,
    payload: dict[str, object],
    *,
    secret: str = WEBHOOK_SECRET,
    source: str = "partner",
    ts: int | None = None,
):
    body = json.dumps(payload).encode()
    return client.post(
        f"/v1/webhooks/{source}",
        content=body,
        headers={"x-signature": build_signature_header(secret, body, timestamp=ts), "content-type": "application/json"},
    )


def test_unsigned_and_badly_signed_requests_are_401_with_one_generic_message(client: TestClient) -> None:
    bodies = {
        "missing": client.post("/v1/webhooks/partner", json={"id": "1", "type": "ping"}),
        "wrong secret": post(client, {"id": "1", "type": "ping"}, secret="not-the-secret"),
        "expired": post(client, {"id": "1", "type": "ping"}, ts=int(time.time()) - 3_600),
    }
    assert {r.status_code for r in bodies.values()} == {401}
    assert len({r.json()["error"]["message"] for r in bodies.values()}) == 1  # no oracle


def test_duplicate_delivery_is_processed_once(client: TestClient) -> None:
    first = post(client, {"id": "evt_9", "type": "ping"})
    again = post(client, {"id": "evt_9", "type": "ping"})
    assert (first.status_code, first.json()) == (202, {"status": "ignored"})
    assert (again.status_code, again.json()) == (200, {"status": "duplicate"})


def test_same_event_id_from_another_source_is_independent(client: TestClient) -> None:
    assert post(client, {"id": "evt_1", "type": "ping"}, source="a").status_code == 202
    assert post(client, {"id": "evt_1", "type": "ping"}, source="b").status_code == 202


def test_rotated_old_secret_is_still_accepted(client: TestClient) -> None:
    assert post(client, {"id": "evt_r", "type": "ping"}, secret=OLD_WEBHOOK_SECRET).status_code == 202


def test_payload_must_have_id_and_type(client: TestClient) -> None:
    assert post(client, {"type": "ping"}).status_code == 400
    assert post(client, {"id": 5, "type": "ping"}).status_code == 400


def test_webhook_ingestion_lands_in_quarantine_not_in_the_knowledge(client: TestClient) -> None:
    event = {"id": "evt_doc", "type": "document.ingested", "source": "docs/from-webhook.md", "text": CORPUS}
    assert post(client, event).json() == {"status": "accepted"}
    docs = client.get("/v1/rag/documents", headers=AUTH).json()
    assert [d["status"] for d in docs] == ["quarantined"]
    answer = client.post("/v1/rag/query", headers=AUTH, json={"question": "Why rotate credentials every 90 days?"})
    assert answer.json()["status"] == "insufficient_evidence"


def test_handler_rejection_keeps_the_claim_but_transient_failure_releases_it(client: TestClient) -> None:
    bad = {"id": "evt_bad", "type": "document.ingested", "source": "secrets/x.md", "text": CORPUS}
    assert post(client, bad).status_code == 422  # deterministic: not allow-listed
    assert post(client, bad).json() == {"status": "duplicate"}  # no retry storm

    container = client.app.state.container  # type: ignore[attr-defined]
    calls = {"n": 0}

    async def flaky(_: dict[str, object]) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("downstream is down")

    container.dispatcher.register("flaky", flaky)
    # raise_server_exceptions=False via a fresh client would also work; here we assert on state
    with pytest.raises(RuntimeError):
        post(client, {"id": "evt_flaky", "type": "flaky"})
    assert post(client, {"id": "evt_flaky", "type": "flaky"}).json() == {"status": "accepted"}
    assert calls["n"] == 2
