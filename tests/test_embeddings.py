"""The lexical embedder must rank a relevant passage above an irrelevant one, or the evidence policy is noise."""

from __future__ import annotations

import pytest

from ai_core.rag.chunking import chunk_text
from ai_core.rag.embeddings import HashingEmbedder

POLICY = (
    "Refunds are issued to the original payment method within 14 days of the request. "
    "Digital goods can be refunded within 30 days if they were not downloaded. "
    "Support answers every ticket within one business day, and urgent billing problems are escalated to the "
    "finance team the same day. Customers who paid by bank transfer receive the refund by transfer, and the "
    "confirmation e-mail lists the amount and the reference. Partial refunds are possible when only part of an "
    "order is returned; the shipping fee is refunded only when the item arrived damaged. "
)
THRESHOLD = 0.2  # the default evidence threshold (RAG_MIN_SCORE)


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@pytest.fixture
def passage() -> list[float]:
    chunk = chunk_text(POLICY)[0]
    return HashingEmbedder().embed(POLICY[chunk.start : chunk.end])


@pytest.mark.parametrize(
    "question",
    [
        "How long do refunds take?",
        "When are refunds issued?",
        "Can I get a refund for digital goods?",
        "How fast does support answer a ticket?",
        "Is the shipping fee refunded?",
    ],
)
def test_natural_questions_about_the_passage_clear_the_default_threshold(question: str, passage: list[float]) -> None:
    assert cosine(HashingEmbedder().embed(question), passage) >= THRESHOLD


@pytest.mark.parametrize(
    "question", ["What is the capital of France?", "How do I reset my password?", "Who won the world cup?"]
)
def test_unrelated_questions_stay_below_it(question: str, passage: list[float]) -> None:
    assert cosine(HashingEmbedder().embed(question), passage) < THRESHOLD


def test_plurals_and_tenses_fold_together() -> None:
    e = HashingEmbedder()
    assert cosine(e.embed("refunds"), e.embed("refunded")) == pytest.approx(1.0)


def test_scores_are_never_negative_because_hashing_is_unsigned() -> None:
    e = HashingEmbedder()
    for a, b in (("alpha beta gamma", "delta epsilon zeta"), ("cats dogs birds", "invoice ledger audit")):
        assert cosine(e.embed(a), e.embed(b)) >= 0.0


def test_repetition_does_not_dominate() -> None:
    e = HashingEmbedder()
    spam = "refund " * 50 + "invoice"
    assert cosine(e.embed(spam), e.embed("invoice")) > 0.1


def test_output_is_deterministic_normalised_and_zero_for_stop_words_only() -> None:
    e = HashingEmbedder(64)
    v = e.embed("Audit logs are append-only")
    assert v == e.embed("Audit logs are append-only")
    assert sum(x * x for x in v) == pytest.approx(1.0)
    assert e.embed("the of and to") == [0.0] * 64
