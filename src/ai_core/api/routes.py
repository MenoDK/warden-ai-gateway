"""HTTP surface. Handlers stay thin: validate, delegate, shape the response."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Path, Request, Response
from fastapi.responses import JSONResponse

from ai_core.api.deps import Authenticated, ContainerDep
from ai_core.api.schemas import (
    AnswerOut,
    AttemptOut,
    CompletionIn,
    CompletionOut,
    DecisionIn,
    DocumentIn,
    DocumentOut,
    MaskIn,
    MaskOut,
    QueryIn,
    ReviewIn,
    ReviewOut,
)
from ai_core.errors import AppError, BadRequest, PayloadTooLarge, Unauthorized
from ai_core.gateway.provider import CompletionRequest
from ai_core.gateway.structured import StructuredOutputError, parse_json_lenient
from ai_core.rag.models import Answer, Document, DocumentStatus
from ai_core.webhooks.signature import SignatureError, verify_signature

router = APIRouter()
MAX_WEBHOOK_BYTES = 1_000_000


def _document_out(doc: Document) -> DocumentOut:
    return DocumentOut(id=doc.id, source=doc.source, sha256=doc.sha256, status=doc.status.value, metadata=doc.metadata)


def _answer_out(answer: Answer) -> AnswerOut:
    return AnswerOut(
        status=answer.status,
        mode=answer.mode,
        text=answer.text,
        citations=[asdict(c) for c in answer.citations],
        provider=answer.provider,
        sensitivity=answer.sensitivity,
        pseudonymised=answer.pseudonymised,
        warning=answer.warning,
    )


# --- health -----------------------------------------------------------------------------
@router.get("/health/live", tags=["ops"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", tags=["ops"])
async def ready(c: ContainerDep) -> JSONResponse:
    store_ok = await c.store.ping()
    body = {
        "status": "ok" if store_ok else "degraded",
        "store": store_ok,
        "providers": {name: state.value for name, state in c.router.breaker_states().items()},
    }
    return JSONResponse(body, status_code=200 if store_ok else 503)


@router.get("/metrics", tags=["ops"], include_in_schema=False)
async def metrics(c: ContainerDep) -> Response:
    return Response(c.metrics.render(), media_type="text/plain; version=0.0.4")


# --- gateway ----------------------------------------------------------------------------
@router.post("/v1/completions", tags=["gateway"], dependencies=[Authenticated])
async def complete(body: CompletionIn, c: ContainerDep) -> CompletionOut:
    result = await c.router.complete(
        CompletionRequest(prompt=body.prompt, system=body.system, max_tokens=body.max_tokens, json_mode=body.json_mode),
        body.sensitivity,
    )
    structured: dict[str, Any] | None = None
    if body.json_mode:
        try:
            parsed = parse_json_lenient(result.text)
            structured = {"ok": True, "repaired": parsed.repaired, "value": parsed.value}
        except StructuredOutputError as exc:
            structured = {"ok": False, "error": str(exc)}  # explicit, never silently empty
    return CompletionOut(
        text=result.text,
        provider=result.provider,
        locality=result.locality.value,
        sensitivity=result.sensitivity.value,
        pseudonymised=result.pseudonymised,
        attempts=[AttemptOut(**asdict(a)) for a in result.attempts],
        structured=structured,
    )


@router.post("/v1/privacy/mask", tags=["gateway"], dependencies=[Authenticated])
async def mask(body: MaskIn, c: ContainerDep) -> MaskOut:
    result = c.masker.mask(body.text)
    return MaskOut(text=result.text, entities=result.entities)  # mapping is never returned


# --- knowledge base ---------------------------------------------------------------------
@router.post("/v1/rag/documents", status_code=201, tags=["rag"], dependencies=[Authenticated])
async def ingest(body: DocumentIn, c: ContainerDep) -> DocumentOut:
    return _document_out(await c.pipeline.ingest(body.source, body.text, body.metadata))


@router.get("/v1/rag/documents", tags=["rag"], dependencies=[Authenticated])
async def list_documents(c: ContainerDep, status: DocumentStatus | None = None) -> list[DocumentOut]:
    return [_document_out(d) for d in await c.store.list_documents(status)]


@router.post("/v1/rag/documents/{document_id}/approve", tags=["rag"], dependencies=[Authenticated])
async def approve(document_id: str, c: ContainerDep) -> DocumentOut:
    return _document_out(await c.pipeline.approve(document_id))


@router.post("/v1/rag/documents/{document_id}/reject", tags=["rag"], dependencies=[Authenticated])
async def reject(document_id: str, c: ContainerDep) -> DocumentOut:
    return _document_out(await c.pipeline.reject(document_id))


@router.post("/v1/rag/query", tags=["rag"], dependencies=[Authenticated])
async def query(body: QueryIn, c: ContainerDep) -> AnswerOut:
    return _answer_out(await c.pipeline.answer(body.question, body.k, body.sensitivity))


# --- human review workflow --------------------------------------------------------------
@router.post("/v1/reviews", status_code=201, tags=["workflow"], dependencies=[Authenticated])
async def start_review(body: ReviewIn, c: ContainerDep) -> ReviewOut:
    return ReviewOut(**asdict(await c.workflow.start(body.question)))


@router.get("/v1/reviews/{review_id}", tags=["workflow"], dependencies=[Authenticated])
async def get_review(review_id: str, c: ContainerDep) -> ReviewOut:
    return ReviewOut(**asdict(await c.workflow.get(review_id)))


@router.post("/v1/reviews/{review_id}/decision", tags=["workflow"], dependencies=[Authenticated])
async def decide_review(review_id: str, body: DecisionIn, c: ContainerDep) -> ReviewOut:
    view = await c.workflow.decide(review_id, approved=body.approved, edited_text=body.edited_text)
    return ReviewOut(**asdict(view))


# --- webhooks ---------------------------------------------------------------------------
@router.post("/v1/webhooks/{source}", tags=["webhooks"])
async def receive_webhook(
    source: Annotated[str, Path(pattern=r"^[a-z0-9_-]{1,40}$")],
    request: Request,
    c: ContainerDep,
) -> JSONResponse:
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BYTES:
        raise PayloadTooLarge("webhook body too large")

    settings = c.settings
    try:
        verify_signature(
            request.headers.get("x-signature"),
            body,
            settings.webhook_secret_list,
            tolerance_seconds=settings.webhook_tolerance_seconds,
        )
    except SignatureError as exc:
        c.metrics.webhooks.labels(f"rejected_{exc.reason}").inc()
        # One generic message for every reason: do not teach an attacker which check failed.
        raise Unauthorized("invalid webhook signature") from None

    try:
        event = json.loads(body)
        event_id, event_type = event["id"], event["type"]
        if not (isinstance(event_id, str) and isinstance(event_type, str) and 0 < len(event_id) <= 200):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        c.metrics.webhooks.labels("rejected_payload").inc()
        raise BadRequest("webhook payload must be a JSON object with string 'id' and 'type'") from None

    key = f"{source}:{event_id}"
    if not await c.idempotency.claim(key, settings.webhook_dedupe_ttl_seconds):
        c.metrics.webhooks.labels("duplicate").inc()
        return JSONResponse({"status": "duplicate"}, status_code=200)

    try:
        handled = await c.dispatcher.dispatch(event_type, event)
    except AppError:
        # Deterministic rejection: retrying the same event cannot succeed, so keep the claim.
        c.metrics.webhooks.labels("rejected_by_handler").inc()
        raise
    except Exception:
        # Transient failure: release the claim so the sender's retry is processed.
        await c.idempotency.release(key)
        c.metrics.webhooks.labels("failed").inc()
        raise

    outcome = "accepted" if handled else "ignored"
    c.metrics.webhooks.labels(outcome).inc()
    return JSONResponse({"status": outcome}, status_code=202)
