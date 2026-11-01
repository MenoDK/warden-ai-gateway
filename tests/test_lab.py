"""Laboratory mode: outage switches and the "what did the third party see?" inbox.

The adversarial question these tests ask: with the local model down, can sensitive text reach the simulated
cloud by any route? It must not, and the inbox is the evidence.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from ai_core.config import Settings
from ai_core.container import build_container
from ai_core.main import create_app
from ai_core.webhooks import build_signature_header
from tests.conftest import AUTH

EMAIL = "ana.souza@example.com"


def lab_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "api_key": SecretStr("test-api-key"),
        "webhook_secrets": SecretStr("whsec_current_for_tests"),
        "database_url": "",
        "redis_url": "",
        "lab_mode": True,
        "breaker_failure_threshold": 3,
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def lab() -> Iterator[TestClient]:
    settings = lab_settings()
    with TestClient(create_app(settings, container=build_container(settings))) as client:
        yield client


def switch(client: TestClient, provider: str, *, down: bool) -> None:
    assert client.post(f"/v1/lab/providers/{provider}", headers=AUTH, json={"down": down}).status_code == 200


def complete(client: TestClient, prompt: str, sensitivity: str = "auto") -> dict[str, object]:
    return client.post("/v1/completions", headers=AUTH, json={"prompt": prompt, "sensitivity": sensitivity}).json()  # type: ignore[no-any-return]


def inbox(client: TestClient) -> list[str]:
    return client.get("/v1/lab/cloud-inbox", headers=AUTH).json()["received"]  # type: ignore[no-any-return]


def test_lab_routes_do_not_exist_unless_the_mode_is_on() -> None:
    settings = lab_settings(lab_mode=False)
    with TestClient(create_app(settings, container=build_container(settings))) as client:
        assert client.get("/v1/lab/config").status_code == 404
        assert client.get("/health/ready").json()["providers"] == {"demo-local": "closed"}


def test_the_mode_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="refused in production"):
        lab_settings(app_env="production", api_key=SecretStr("a-real-production-key"))


def test_an_unset_webhook_secret_becomes_a_private_random_one_only_in_the_lab() -> None:
    settings = lab_settings(webhook_secrets=SecretStr(""))
    (secret,) = settings.webhook_secret_list
    assert len(secret) >= 24
    assert lab_settings(webhook_secrets=SecretStr("")).webhook_secret_list != [secret]  # fresh per process
    with TestClient(create_app(settings, container=build_container(settings))) as client:
        assert client.get("/v1/lab/state", headers=AUTH).json()["webhook_secret"] == secret
        body = b'{"id": "evt_lab_1", "type": "ping"}'
        sent = client.post(
            "/v1/webhooks/partner", content=body, headers={"x-signature": build_signature_header(secret, body)}
        )
        assert sent.status_code == 202
    # Outside the lab nothing is invented: no secret means no webhook can ever verify (fail closed).
    assert lab_settings(lab_mode=False, webhook_secrets=SecretStr("")).webhook_secret_list == []


def test_switches_and_inbox_need_the_api_key_but_config_does_not(lab: TestClient) -> None:
    assert lab.get("/v1/lab/config").json() == {"lab": True, "default_key_in_use": False}
    for method, path in (("get", "/v1/lab/state"), ("get", "/v1/lab/cloud-inbox"), ("post", "/v1/lab/breakers/reset")):
        assert getattr(lab, method)(path).status_code == 401
    assert lab.post("/v1/lab/providers/demo-local", json={"down": True}).status_code == 401


def test_state_lists_both_providers_and_the_webhook_secret(lab: TestClient) -> None:
    state = lab.get("/v1/lab/state", headers=AUTH).json()
    assert [(p["name"], p["locality"], p["down"]) for p in state["providers"]] == [
        ("demo-local", "local", False),
        ("demo-cloud", "external", False),
    ]
    assert state["webhook_secret"] == "whsec_current_for_tests"


def test_a_healthy_local_model_answers_and_the_cloud_sees_nothing(lab: TestClient) -> None:
    body = complete(lab, "What is a circuit breaker?", "internal")
    assert body["provider"] == "demo-local"
    assert inbox(lab) == []


def test_sensitive_text_is_never_sent_to_the_cloud_even_when_the_local_model_is_down(lab: TestClient) -> None:
    switch(lab, "demo-local", down=True)
    response = lab.post("/v1/completions", headers=AUTH, json={"prompt": f"Draft a reply to {EMAIL}"})
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "all_providers_failed"
    assert {"provider": "demo-cloud", "outcome": "skipped_sensitive"} in error["attempts"]
    assert inbox(lab) == []  # the evidence: nothing crossed the boundary


def test_internal_text_may_use_the_cloud_but_only_as_placeholders(lab: TestClient) -> None:
    switch(lab, "demo-local", down=True)
    body = complete(lab, f"Draft a reply to {EMAIL}", "internal")
    assert body["provider"] == "demo-cloud"
    assert body["pseudonymised"] is True
    assert EMAIL in str(body["text"])  # re-hydrated locally on the way back
    received = inbox(lab)
    assert len(received) == 1
    assert EMAIL not in received[0] and "<EMAIL_1>" in received[0]


def test_repeated_failures_open_the_breaker_and_the_operator_can_close_it(lab: TestClient) -> None:
    switch(lab, "demo-local", down=True)
    switch(lab, "demo-cloud", down=True)
    for _ in range(3):
        assert (
            lab.post("/v1/completions", headers=AUTH, json={"prompt": "x", "sensitivity": "public"}).status_code == 503
        )
    states = {p["name"]: p["breaker"] for p in lab.get("/v1/lab/state", headers=AUTH).json()["providers"]}
    assert states == {"demo-local": "open", "demo-cloud": "open"}

    skipped = lab.post("/v1/completions", headers=AUTH, json={"prompt": "x", "sensitivity": "public"}).json()
    assert {a["outcome"] for a in skipped["error"]["attempts"]} == {"circuit_open"}

    switch(lab, "demo-local", down=False)
    switch(lab, "demo-cloud", down=False)
    assert set(lab.post("/v1/lab/breakers/reset", headers=AUTH).json().values()) == {"closed"}
    assert complete(lab, "x", "public")["provider"] == "demo-local"


def test_start_over_restores_a_clean_lab(lab: TestClient) -> None:
    assert lab.post("/v1/lab/reset").status_code == 401  # a visitor without the key cannot wipe the demo
    doc = lab.post("/v1/rag/documents", headers=AUTH, json={"source": "docs/a.md", "text": "Refunds take 14 days."})
    assert doc.status_code == 201
    complete(lab, "Draft a reply to " + EMAIL, "internal")  # leaves a prompt in the cloud inbox
    switch(lab, "demo-local", down=True)
    for _ in range(3):
        complete(lab, "plain question")  # opens the local breaker

    assert lab.post("/v1/lab/reset", headers=AUTH).json() == {"reset": True}

    state = lab.get("/v1/lab/state", headers=AUTH).json()
    assert [p["down"] for p in state["providers"]] == [False, False]
    assert {p["breaker"] for p in state["providers"]} == {"closed"}
    assert inbox(lab) == []
    assert lab.get("/v1/rag/documents", headers=AUTH).json() == []
    # the same content can be ingested again: nothing of the old document is left behind
    again = lab.post("/v1/rag/documents", headers=AUTH, json={"source": "docs/a.md", "text": "Refunds take 14 days."})
    assert again.status_code == 201


def test_an_unknown_provider_is_a_404_not_a_silent_success(lab: TestClient) -> None:
    response = lab.post("/v1/lab/providers/nope", headers=AUTH, json={"down": True})
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"


def test_the_inbox_keeps_only_the_most_recent_prompts(lab: TestClient) -> None:
    switch(lab, "demo-local", down=True)
    for i in range(25):
        complete(lab, f"question number {i}", "internal")
    received = inbox(lab)
    assert len(received) == 20 and received[-1] == "question number 24" and received[0] == "question number 5"


def test_the_site_is_served_under_a_strict_policy_and_never_shadows_the_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>site</title>")
    settings = lab_settings(site_dir=str(tmp_path))
    with TestClient(create_app(settings, container=build_container(settings))) as client:
        page = client.get("/")
        assert page.status_code == 200 and "<title>site</title>" in page.text
        csp = page.headers["content-security-policy"]
        assert "script-src 'self'" in csp and "style-src 'self'" in csp and "'unsafe-inline'" not in csp
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/v1/lab/config").json()["lab"] is True
        assert client.get("/docs").headers.get("content-security-policy") is None  # the API docs load a CDN UI


def test_a_missing_site_directory_fails_at_startup() -> None:
    settings = lab_settings(site_dir="/definitely/not/here")
    with pytest.raises(ValueError, match="SITE_DIR"):
        create_app(settings, container=build_container(settings))
