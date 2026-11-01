"""Composition root: the only place that knows which concrete adapters are wired in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_core.config import Settings
from ai_core.gateway.provider import LLMProvider, Locality
from ai_core.gateway.providers import DemoLocalProvider, OpenAICompatibleProvider
from ai_core.gateway.router import SensitivityRouter
from ai_core.observability.metrics import Metrics
from ai_core.privacy.masker import PIIMasker
from ai_core.rag.embeddings import HashingEmbedder
from ai_core.rag.pgvector_store import PgVectorKnowledgeStore
from ai_core.rag.pipeline import RagPipeline
from ai_core.rag.store import InMemoryKnowledgeStore, KnowledgeStore
from ai_core.webhooks.dispatcher import EventDispatcher
from ai_core.webhooks.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
)
from ai_core.workflows.review import ReviewWorkflow


@dataclass
class Container:
    settings: Settings
    metrics: Metrics
    masker: PIIMasker
    router: SensitivityRouter
    store: KnowledgeStore
    pipeline: RagPipeline
    workflow: ReviewWorkflow
    idempotency: IdempotencyStore
    dispatcher: EventDispatcher
    providers: list[LLMProvider]

    async def startup(self) -> None:
        await self.store.init()

    async def shutdown(self) -> None:
        await self.store.close()
        await self.idempotency.close()
        for provider in self.providers:
            close: Any = getattr(provider, "aclose", None)
            if close:
                await close()


def default_providers(settings: Settings) -> list[LLMProvider]:
    providers: list[LLMProvider] = []
    if settings.local_llm_url:
        providers.append(
            OpenAICompatibleProvider(
                name="local-llm",
                base_url=settings.local_llm_url,
                model=settings.local_llm_model,
                locality=Locality.LOCAL,
                timeout_seconds=settings.provider_timeout_seconds,
            )
        )
    elif settings.app_env != "production":
        providers.append(DemoLocalProvider())  # never silently used in production
    if settings.external_llm_url and settings.external_llm_key.get_secret_value():
        providers.append(
            OpenAICompatibleProvider(
                name="external-llm",
                base_url=settings.external_llm_url,
                model=settings.external_llm_model,
                locality=Locality.EXTERNAL,
                api_key=settings.external_llm_key.get_secret_value(),
                timeout_seconds=settings.provider_timeout_seconds,
            )
        )
    return providers


def build_container(
    settings: Settings,
    *,
    providers: list[LLMProvider] | None = None,
    store: KnowledgeStore | None = None,
    idempotency: IdempotencyStore | None = None,
) -> Container:
    metrics = Metrics()
    masker = PIIMasker()
    providers = default_providers(settings) if providers is None else providers
    router = SensitivityRouter(
        providers,
        masker,
        timeout_seconds=settings.provider_timeout_seconds,
        failure_threshold=settings.breaker_failure_threshold,
        reset_seconds=settings.breaker_reset_seconds,
        on_attempt=metrics.on_attempt,
        on_breaker_change=metrics.on_breaker_change,
    )
    embedder = HashingEmbedder(settings.embedding_dim)
    if store is None:
        store = (
            PgVectorKnowledgeStore(settings.database_url, dim=settings.embedding_dim)
            if settings.database_url
            else InMemoryKnowledgeStore()
        )
    if idempotency is None:
        idempotency = RedisIdempotencyStore(settings.redis_url) if settings.redis_url else InMemoryIdempotencyStore()
    pipeline = RagPipeline(
        store,
        embedder,
        router,
        allowed_source_patterns=settings.allowed_source_patterns,
        min_score=settings.rag_min_score,
        min_evidence=settings.rag_min_evidence,
        top_k=settings.rag_top_k,
        max_document_chars=settings.max_document_chars,
    )
    dispatcher = EventDispatcher()

    async def on_document_ingested(payload: dict[str, Any]) -> None:
        # Quarantined like any other ingestion: a webhook can never publish knowledge directly.
        await pipeline.ingest(str(payload["source"]), str(payload["text"]), {"via": "webhook"})

    dispatcher.register("document.ingested", on_document_ingested)

    return Container(
        settings=settings,
        metrics=metrics,
        masker=masker,
        router=router,
        store=store,
        pipeline=pipeline,
        workflow=ReviewWorkflow(pipeline, masker),
        idempotency=idempotency,
        dispatcher=dispatcher,
        providers=providers,
    )
