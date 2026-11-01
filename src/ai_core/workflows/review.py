"""Human-in-the-loop answer workflow built on LangGraph.

    anonymize -> retrieve --(insufficient)--> insufficient -> END
                    |
                    v
                  draft -> human_review (graph PAUSES here) -> finalize | rejected -> END

* The graph **interrupts** before anything is released: a person approves, edits or rejects
  the draft. State is checkpointed, so the pause can last seconds or days and survives
  between HTTP requests. (``MemorySaver`` here; pass a Postgres checkpointer in production.)
* Personal data found in the question forces ``SENSITIVE`` routing for the whole run, so the
  draft is produced by a local model only.
* Graph state is plain JSON-compatible data (no custom classes) so any checkpointer works.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ai_core.errors import InvalidState, NotFound
from ai_core.gateway.provider import Sensitivity
from ai_core.privacy.masker import PIIMasker
from ai_core.rag.models import EvidenceBundle, SearchHit
from ai_core.rag.pipeline import RagPipeline


class ReviewState(TypedDict, total=False):
    question: str
    masked_question: str
    pii_entities: dict[str, int]
    hits: list[dict[str, Any]]
    sufficient: bool
    reason: str
    draft: str
    mode: str
    provider: str | None
    citations: list[dict[str, Any]]
    decision: dict[str, Any]
    final_text: str
    status: str


@dataclass
class ReviewView:
    id: str
    status: str  # awaiting_review | approved | rejected | insufficient_evidence
    question: str  # always the *masked* question: raw PII is not retained in the checkpoint
    draft: str = ""
    mode: str = ""
    provider: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    final_text: str = ""
    pii_entities: dict[str, int] = field(default_factory=dict)
    reason: str = ""


class ReviewWorkflow:
    def __init__(
        self,
        pipeline: RagPipeline,
        masker: PIIMasker,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._masker = masker
        self._graph = self._build().compile(checkpointer=checkpointer or MemorySaver())

    # -- graph ---------------------------------------------------------------------
    def _build(self) -> StateGraph[ReviewState]:
        async def anonymize(state: ReviewState) -> ReviewState:
            masked = self._masker.mask(state["question"])
            # The raw question is dropped from state: only the pseudonymised form persists.
            return {"masked_question": masked.text, "pii_entities": masked.entities, "question": ""}

        async def retrieve(state: ReviewState) -> ReviewState:
            bundle = await self._pipeline.retrieve(state["masked_question"])
            return {
                "hits": [asdict(h) for h in bundle.hits],
                "sufficient": bundle.sufficient,
                "reason": bundle.reason,
            }

        async def draft(state: ReviewState) -> ReviewState:
            bundle = EvidenceBundle(
                question=state["masked_question"],
                hits=tuple(SearchHit(**h) for h in state["hits"]),
                sufficient=True,
                reason=state["reason"],
            )
            sensitivity = Sensitivity.SENSITIVE if state.get("pii_entities") else Sensitivity.AUTO
            answer = await self._pipeline.generate(bundle, sensitivity)
            return {
                "draft": answer.text,
                "mode": answer.mode,
                "provider": answer.provider,
                "citations": [asdict(c) for c in answer.citations],
            }

        async def human_review(state: ReviewState) -> ReviewState:
            decision = interrupt({"draft": state["draft"], "citations": state["citations"]})
            return {"decision": decision}

        async def finalize(state: ReviewState) -> ReviewState:
            edited = (state["decision"].get("edited_text") or "").strip()
            return {"status": "approved", "final_text": edited or state["draft"]}

        async def rejected(_: ReviewState) -> ReviewState:
            return {"status": "rejected", "final_text": ""}

        async def insufficient(_: ReviewState) -> ReviewState:
            return {"status": "insufficient_evidence", "final_text": ""}

        def after_retrieve(state: ReviewState) -> str:
            return "draft" if state["sufficient"] else "insufficient"

        def after_review(state: ReviewState) -> str:
            return "finalize" if state["decision"].get("approved") is True else "rejected"

        g: StateGraph[ReviewState] = StateGraph(ReviewState)
        nodes: dict[str, Any] = {
            "anonymize": anonymize,
            "retrieve": retrieve,
            "draft": draft,
            "human_review": human_review,
            "finalize": finalize,
            "rejected": rejected,
            "insufficient": insufficient,
        }
        for name, node in nodes.items():
            g.add_node(name, node)
        g.add_edge(START, "anonymize")
        g.add_edge("anonymize", "retrieve")
        g.add_conditional_edges("retrieve", after_retrieve, ["draft", "insufficient"])
        g.add_edge("draft", "human_review")
        g.add_conditional_edges("human_review", after_review, ["finalize", "rejected"])
        for terminal in ("finalize", "rejected", "insufficient"):
            g.add_edge(terminal, END)
        return g

    # -- public API ----------------------------------------------------------------
    @staticmethod
    def _config(review_id: str) -> Any:
        return {"configurable": {"thread_id": review_id}}

    async def start(self, question: str) -> ReviewView:
        review_id = uuid.uuid4().hex
        await self._graph.ainvoke({"question": question}, self._config(review_id))
        return await self.get(review_id)

    async def decide(self, review_id: str, *, approved: bool, edited_text: str | None = None) -> ReviewView:
        view = await self.get(review_id)
        if view.status != "awaiting_review":
            raise InvalidState(f"review is '{view.status}', not awaiting a decision")
        await self._graph.ainvoke(
            Command(resume={"approved": approved, "edited_text": edited_text}),
            self._config(review_id),
        )
        return await self.get(review_id)

    async def get(self, review_id: str) -> ReviewView:
        snapshot = await self._graph.aget_state(self._config(review_id))
        values: ReviewState = snapshot.values  # type: ignore[assignment]
        if not values:
            raise NotFound("review not found")
        status = "awaiting_review" if snapshot.next else values.get("status", "unknown")
        return ReviewView(
            id=review_id,
            status=status,
            question=values.get("masked_question", ""),
            draft=values.get("draft", ""),
            mode=values.get("mode", ""),
            provider=values.get("provider"),
            citations=values.get("citations", []),
            final_text=values.get("final_text", ""),
            pii_entities=values.get("pii_entities", {}),
            reason=values.get("reason", ""),
        )
