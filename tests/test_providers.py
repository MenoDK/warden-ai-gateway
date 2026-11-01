import httpx
import pytest

from ai_core.gateway.provider import CompletionRequest, Locality, ProviderError, ProviderRateLimited, ProviderTimeout
from ai_core.gateway.providers import DemoLocalProvider, OpenAICompatibleProvider


def provider(handler: httpx.MockTransport | None = None, **kwargs: object) -> OpenAICompatibleProvider:
    client = httpx.AsyncClient(transport=handler) if handler else None
    return OpenAICompatibleProvider(
        name="p",
        base_url="http://llm.test/v1/",
        model="m",
        locality=Locality.LOCAL,
        client=client,
        **kwargs,  # type: ignore[arg-type]
    )


def ok(content: object = "hello") -> httpx.MockTransport:
    return httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}}]}))


async def test_builds_an_openai_compatible_request() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    p = provider(httpx.MockTransport(handler), api_key="secret-for-test")
    out = await p.complete(CompletionRequest("question", system="be brief", json_mode=True))
    assert out == "hi"
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-for-test"
    body = str(seen["body"])
    assert '"role":"system"' in body.replace(" ", "") and "json_object" in body


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(429), ProviderRateLimited),
        (httpx.Response(500, text="the prompt was: TOP SECRET"), ProviderError),
        (httpx.Response(200, json={"unexpected": True}), ProviderError),
        (httpx.Response(200, text="not json"), ProviderError),
    ],
)
async def test_failures_map_to_typed_errors(response: httpx.Response, expected: type[Exception]) -> None:
    p = provider(httpx.MockTransport(lambda r: response))
    with pytest.raises(expected) as exc:
        await p.complete(CompletionRequest("q"))
    assert "TOP SECRET" not in str(exc.value), "error text must never echo provider bodies"


async def test_non_string_content_is_rejected() -> None:
    with pytest.raises(ProviderError):
        await provider(ok(content=["not", "text"])).complete(CompletionRequest("q"))


async def test_timeout_and_transport_errors() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def refused(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderTimeout):
        await provider(httpx.MockTransport(timeout)).complete(CompletionRequest("q"))
    with pytest.raises(ProviderError) as exc:
        await provider(httpx.MockTransport(refused)).complete(CompletionRequest("q"))
    assert not isinstance(exc.value, ProviderTimeout)


async def test_demo_provider_quotes_the_first_source() -> None:
    prompt = "Sources:\n[1] (source: docs/a.md#0)\nKeys rotate every 90 days. Always.\n\nQuestion: when?"
    assert await DemoLocalProvider().complete(CompletionRequest(prompt)) == "Keys rotate every 90 days. [1]"
