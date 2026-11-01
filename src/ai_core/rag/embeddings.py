"""Embedding port + a dependency-free, deterministic implementation.

``HashingEmbedder`` (feature hashing over unigrams and bigrams) is not semantic -- it will not
know that "car" and "automobile" are related -- but it is stable across processes, needs no
model download, and is more than enough to exercise the retrieval, thresholding and
provenance machinery. Swap in ``sentence-transformers`` or a hosted model by implementing the
two-method ``Embedder`` protocol; nothing else changes.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import re
from typing import Protocol

_TOKEN = re.compile(r"[\w']+", re.UNICODE)


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        tokens = [t.lower() for t in _TOKEN.findall(text)]
        features = tokens + [f"{a}_{b}" for a, b in itertools.pairwise(tokens)]
        vector = [0.0] * self.dim
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vector[value % self.dim] += sign
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector] if norm else vector
