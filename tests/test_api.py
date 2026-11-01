import re

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from ai_core.config import Settings
from ai_core.container import build_container
from ai_core.gateway.provider import Locality
from ai_core.main import create_app
from tests.conftest import AUTH, CORPUS, FakeProvider

PROTECTED = [
    ("post", "/v1/completions", {"prompt": "hi"}),
    ("post", "/v1/privacy/mask", {"text": "hi"}),
    ("post", "/v1/rag/documents", {"source": "docs/a.md", "text": "hi"}),
    ("get", "/v1/rag/documents", None),
    ("post", "/v1/rag/query", {"question": "hi"}),
    ("post", "/v1/reviews", {"question": "hi"}),
]


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED)
def test_every_business_route_requires_the_api_key(client: TestClient, method: str, path: str, body: object) -> None:
    for headers in ({}, {"x-api-key": "wrong"}):
        response = getattr(client, method)(path, headers=headers, **({"json": body} if body else {}))
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


def test_health_and_metrics_are_open(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["providers"] == {"demo-local": "closed"}
    assert "http_requests_total" in client.get("/metrics").text


def test_request_id_is_propagated_or_generated_and_sanitised(client: TestClient) -> None:
    assert client.get("/health/live", headers={"x-request-id": "abc-123"}).headers["x-request-id"] == "abc-123"
    generated = client.get("/health/live", headers={"x-request-id": "bad id\r\ninjected"}).headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", generated)
    assert client.get("/health/live").headers["cache-control"] == "no-store"


def test_completion_routes_pii_to_the_local_provider(settings: Settings) -> None:
    local = FakeProvider("local", Locality.LOCAL, "local says hi")
    cloud = FakeProvider("cloud", Locality.EXTERNAL, "cloud says hi")
    with TestClient(create_app(settings, container=build_container(settings, providers=[cloud, local]))) as client:
        body = client.post("/v1/completions", headers=AUTH, json={"prompt": "Reply to ana@example.com"}).json()
        assert (body["provider"], body["sensitivity"]) == ("local", "sensitive")
        assert [a["outcome"] for a in body["attempts"]] == ["skipped_sensitive", "ok"]
        assert cloud.requests == []
        metrics = client.get("/metrics").text
        assert 'llm_provider_attempts_total{locality="local",outcome="ok",provider="local"} 1.0' in metrics


def test_json_mode_reports_repair_explicitly(settings: Settings) -> None:
    truncated = FakeProvider("local", Locality.LOCAL, '{"a": 1, "b": [1, 2')
    with TestClient(create_app(settings, container=build_container(settings, providers=[truncated]))) as client:
        out = client.post("/v1/completions", headers=AUTH, json={"prompt": "x", "json_mode": True}).json()
        assert out["structured"] == {"ok": True, "repaired": True, "value": {"a": 1, "b": [1, 2]}}
        truncated.reply = "no json here"
        out = client.post("/v1/completions", headers=AUTH, json={"prompt": "x", "json_mode": True}).json()
        assert out["structured"]["ok"] is False


def test_gateway_failures_are_503_with_a_trace_and_no_prompt_content(settings: Settings) -> None:
    broken = FakeProvider("local", Locality.LOCAL, fail=True)
    with TestClient(create_app(settings, container=build_container(settings, providers=[broken]))) as client:
        response = client.post("/v1/completions", headers=AUTH, json={"prompt": "ana@example.com"})
        error = response.json()["error"]
        assert response.status_code == 503 and error["code"] == "all_providers_failed"
        assert error["attempts"] == [{"provider": "local", "outcome": "error"}]
        assert "ana@example.com" not in response.text


def test_sensitive_with_only_external_providers_is_503_no_eligible_provider(settings: Settings) -> None:
    cloud = FakeProvider("cloud", Locality.EXTERNAL)
    with TestClient(create_app(settings, container=build_container(settings, providers=[cloud]))) as client:
        response = client.post("/v1/completions", headers=AUTH, json={"prompt": "x", "sensitivity": "sensitive"})
        assert response.status_code == 503 and response.json()["error"]["code"] == "no_eligible_provider"
        assert cloud.requests == []


def test_mask_endpoint_never_returns_the_mapping(client: TestClient) -> None:
    out = client.post("/v1/privacy/mask", headers=AUTH, json={"text": "ana@example.com"}).json()
    assert out == {"text": "<EMAIL_1>", "entities": {"EMAIL": 1}}


def test_validation_errors_are_422(client: TestClient) -> None:
    assert client.post("/v1/completions", headers=AUTH, json={"prompt": ""}).status_code == 422
    assert client.post("/v1/completions", headers=AUTH, json={"prompt": "x", "max_tokens": 10**6}).status_code == 422


def test_rag_flow_over_http(client: TestClient) -> None:
    created = client.post("/v1/rag/documents", headers=AUTH, json={"source": "docs/security.md", "text": CORPUS})
    assert created.status_code == 201 and created.json()["status"] == "quarantined"
    doc_id = created.json()["id"]

    assert (
        client.post("/v1/rag/documents", headers=AUTH, json={"source": "docs/b.md", "text": CORPUS}).status_code == 409
    )
    assert client.post("/v1/rag/documents", headers=AUTH, json={"source": "etc/passwd", "text": "x"}).status_code == 422

    approved = client.post(f"/v1/rag/documents/{doc_id}/approve", headers=AUTH)
    assert approved.json()["status"] == "approved"
    assert client.post(f"/v1/rag/documents/{doc_id}/reject", headers=AUTH).status_code == 409
    assert client.post("/v1/rag/documents/nope/approve", headers=AUTH).status_code == 404

    answer = client.post(
        "/v1/rag/query", headers=AUTH, json={"question": "Why rotate credentials every 90 days?"}
    ).json()
    assert answer["status"] == "answered" and answer["citations"][0]["source"] == "docs/security.md"
    listed = client.get("/v1/rag/documents", headers=AUTH, params={"status": "approved"}).json()
    assert [d["id"] for d in listed] == [doc_id]


def test_unhandled_errors_do_not_leak_internals(settings: Settings) -> None:
    container = build_container(settings)

    async def explode(*_: object, **__: object) -> None:
        raise RuntimeError("database password is hunter2")

    container.pipeline.answer = explode  # type: ignore[method-assign]
    with TestClient(create_app(settings, container=container), raise_server_exceptions=False) as client:
        response = client.post("/v1/rag/query", headers=AUTH, json={"question": "x"})
    assert response.status_code == 500 and "hunter2" not in response.text
    assert response.json()["error"]["code"] == "internal_error"


def test_production_refuses_the_default_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production")  # type: ignore[call-arg]
    Settings(_env_file=None, app_env="production", api_key=SecretStr("a-real-secret"))  # type: ignore[call-arg]


def test_production_never_falls_back_to_the_demo_provider() -> None:
    settings = Settings(_env_file=None, app_env="production", api_key=SecretStr("a-real-secret"))  # type: ignore[call-arg]
    assert build_container(settings).providers == []
