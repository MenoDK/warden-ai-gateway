from fastapi.testclient import TestClient
from pydantic import SecretStr

from ai_core.config import Settings
from ai_core.container import build_container
from ai_core.gateway.provider import Locality
from ai_core.main import create_app
from tests.conftest import AUTH, CORPUS, FakeProvider

QUESTION = "Why rotate credentials every 90 days?"


def seed(client: TestClient) -> None:
    doc = client.post("/v1/rag/documents", headers=AUTH, json={"source": "docs/s.md", "text": CORPUS}).json()
    client.post(f"/v1/rag/documents/{doc['id']}/approve", headers=AUTH)


def start(client: TestClient, question: str = QUESTION) -> dict[str, object]:
    response = client.post("/v1/reviews", headers=AUTH, json={"question": question})
    assert response.status_code == 201
    return response.json()


def test_graph_pauses_for_a_human_and_resumes_on_approval(client: TestClient) -> None:
    seed(client)
    review = start(client)
    assert review["status"] == "awaiting_review"
    assert review["draft"] and review["final_text"] == ""  # nothing is released yet
    assert client.get(f"/v1/reviews/{review['id']}", headers=AUTH).json()["status"] == "awaiting_review"

    done = client.post(f"/v1/reviews/{review['id']}/decision", headers=AUTH, json={"approved": True}).json()
    assert done["status"] == "approved" and done["final_text"] == review["draft"]


def test_reviewer_can_edit_before_approving(client: TestClient) -> None:
    seed(client)
    review = start(client)
    done = client.post(
        f"/v1/reviews/{review['id']}/decision",
        headers=AUTH,
        json={"approved": True, "edited_text": "  Edited by a human [1]  "},
    ).json()
    assert done["final_text"] == "Edited by a human [1]"


def test_rejection_releases_nothing(client: TestClient) -> None:
    seed(client)
    review = start(client)
    done = client.post(f"/v1/reviews/{review['id']}/decision", headers=AUTH, json={"approved": False}).json()
    assert done["status"] == "rejected" and done["final_text"] == ""


def test_a_decision_is_final(client: TestClient) -> None:
    seed(client)
    review = start(client)
    url = f"/v1/reviews/{review['id']}/decision"
    assert client.post(url, headers=AUTH, json={"approved": True}).status_code == 200
    again = client.post(url, headers=AUTH, json={"approved": False})
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_state"


def test_insufficient_evidence_skips_the_human_and_the_model(client: TestClient) -> None:
    seed(client)
    review = start(client, "What is the capital of France?")
    assert review["status"] == "insufficient_evidence" and review["draft"] == ""


def test_unknown_review_is_404(client: TestClient) -> None:
    assert client.get("/v1/reviews/does-not-exist", headers=AUTH).status_code == 404
    assert client.post("/v1/reviews/does-not-exist/decision", headers=AUTH, json={"approved": True}).status_code == 404


def test_pii_forces_local_only_and_the_raw_question_is_not_retained(settings: Settings) -> None:
    local = FakeProvider("local", Locality.LOCAL, "Rotate every 90 days [1].")
    cloud = FakeProvider("cloud", Locality.EXTERNAL, "cloud [1]")
    container = build_container(settings, providers=[cloud, local])
    with TestClient(create_app(settings, container=container)) as client:
        seed(client)
        review = start(client, "ana@example.com asks: why rotate credentials every 90 days?")
        assert review["provider"] == "local" and cloud.requests == []
        assert "ana@example.com" not in str(review) and "<EMAIL_1>" in str(review["question"])
        assert review["pii_entities"] == {"EMAIL": 1}


def test_review_state_survives_between_requests_of_different_clients(settings: Settings) -> None:
    container = build_container(settings)
    app = create_app(settings, container=container)
    with TestClient(app) as first:
        seed(first)
        review_id = start(first)["id"]
    with TestClient(app) as second:  # a different HTTP client/connection: state lives in the checkpointer
        assert second.get(f"/v1/reviews/{review_id}", headers=AUTH).json()["status"] == "awaiting_review"


def test_settings_secret_never_appears_in_repr() -> None:
    assert "super-secret" not in repr(Settings(_env_file=None, api_key=SecretStr("super-secret")))  # type: ignore[call-arg]
