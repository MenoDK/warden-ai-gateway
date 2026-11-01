"""Deterministic offline provider so the whole stack runs (and is testable) with no model.

It is *not* a language model: it echoes the strongest evidence it was handed. That is exactly
what makes the grounded-answer and citation plumbing observable in demos and in tests.
"""

from __future__ import annotations

import json
import re

from ai_core.gateway.provider import CompletionRequest, Locality

_SOURCE_BLOCK = re.compile(r"^\[(\d+)\] \(source: [^)]*\)\s*(.+)$", re.MULTILINE)


class DemoLocalProvider:
    name = "demo-local"
    locality = Locality.LOCAL

    async def complete(self, request: CompletionRequest) -> str:
        sources = _SOURCE_BLOCK.findall(request.prompt)
        if sources:
            number, snippet = sources[0]
            first_sentence = re.split(r"(?<=[.!?])\s", snippet.strip(), maxsplit=1)[0]
            body = f"{first_sentence} [{number}]"
        else:
            body = f"(demo model) received {len(request.prompt)} characters"
        if request.json_mode:
            return json.dumps({"answer": body, "provider": self.name})
        return body
