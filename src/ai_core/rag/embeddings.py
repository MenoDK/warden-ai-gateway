"""Embedding port + a dependency-free, deterministic implementation.

``HashingEmbedder`` is lexical, not semantic: it will not know that "car" and "automobile" are related. It is
stable across processes, needs no model download, and is good enough to exercise the retrieval, thresholding
and provenance machinery. Swap in ``sentence-transformers`` or a hosted model by implementing the two-method
``Embedder`` protocol; nothing else changes.

Three choices keep a lexical vector honest (each one was a measured fix, see ``tests/test_embeddings.py``):

* **Stop words are dropped and plurals/tenses are folded** ("refunds", "refunded" -> "refund"), so the words
  that carry the topic are the only ones that count.
* **Sub-linear term frequency** (``1 + ln(count)``), so a word repeated ten times does not drown the rest.
* **Unsigned hashing.** A signed hash lets two unrelated texts cancel or reinforce each other by collision,
  which produced negative scores for relevant passages and positive ones for irrelevant passages.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN = re.compile(r"[\w']+", re.UNICODE)
_STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "do",
        "does",
        "did",
        "how",
        "what",
        "when",
        "where",
        "who",
        "whom",
        "why",
        "which",
        "can",
        "could",
        "should",
        "would",
        "will",
        "with",
        "as",
        "at",
        "by",
        "from",
        "i",
        "you",
        "we",
        "they",
        "he",
        "she",
        "my",
        "your",
        "our",
        "their",
        "not",
        "no",
        "if",
        "then",
        "than",
        "so",
    ]
)
_SUFFIXES = ("ing", "ed", "es", "s")


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


class HashingEmbedder:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        counts: dict[str, int] = {}
        for raw in _TOKEN.findall(text.lower()):
            if raw not in _STOP_WORDS:
                word = _stem(raw)
                counts[word] = counts.get(word, 0) + 1
        vector = [0.0] * self.dim
        for word, count in counts.items():
            digest = hashlib.blake2b(word.encode(), digest_size=8).digest()
            vector[int.from_bytes(digest, "big") % self.dim] += 1.0 + math.log(count)
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector] if norm else vector
