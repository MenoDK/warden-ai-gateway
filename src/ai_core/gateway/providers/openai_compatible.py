"""Adapter for any OpenAI-compatible ``/chat/completions`` endpoint (Ollama, vLLM, hosted APIs)."""

from __future__ import annotations

import httpx

from ai_core.gateway.provider import (
    CompletionRequest,
    Locality,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        model: str,
        locality: Locality,
        api_key: str = "",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.name = name
        self.locality = locality
        self._model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def complete(self, request: CompletionRequest) -> str:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self._client.post(self._url, json=payload, headers=self._headers)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error: {type(exc).__name__}") from exc

        if response.status_code == 429:
            raise ProviderRateLimited("provider rate limit")
        if response.status_code >= 400:
            # Never echo the body: it may contain the prompt we were asked to protect.
            raise ProviderError(f"provider returned HTTP {response.status_code}")

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("malformed provider response") from exc
        if not isinstance(content, str):
            raise ProviderError("provider returned non-text content")
        return content

    async def aclose(self) -> None:
        await self._client.aclose()
