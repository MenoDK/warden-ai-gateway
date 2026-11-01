"""Tolerant parsing of model output that is supposed to be JSON.

Models wrap JSON in prose or code fences, and ``max_tokens`` cuts it in the middle of a
string. ``parse_json_lenient`` recovers what can be recovered, and says so (``repaired``)
so callers can treat a salvaged result with the suspicion it deserves.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)(?:```|$)", re.DOTALL | re.IGNORECASE)
_DANGLING_KEY = re.compile(r'([,{])\s*"(?:[^"\\]|\\.)*"\s*:?\s*$')
_DANGLING_LITERAL = re.compile(r"([\[:,])\s*(?:-|\d+\.|\d+[eE][+-]?|t|tr|tru|f|fa|fal|fals|n|nu|nul)$")


class StructuredOutputError(ValueError):
    """The text contains no recoverable JSON object/array."""


@dataclass(frozen=True)
class ParsedJson:
    value: dict[str, Any] | list[Any]
    repaired: bool


def _loads(candidate: str) -> dict[str, Any] | list[Any] | None:
    try:
        value = json.loads(candidate)
    except (json.JSONDecodeError, RecursionError):
        return None
    return value if isinstance(value, dict | list) else None


def _close_open_structures(fragment: str) -> str:
    stack: list[str] = []
    in_string = False
    escaped = False
    for ch in fragment:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()

    out = fragment
    if in_string:
        if escaped:  # cut right after a backslash
            out = out[:-1]
        out += '"'
    out = out.rstrip()

    # A key that never received its value cannot be kept.
    if stack and stack[-1] == "}":
        m = _DANGLING_KEY.search(out)
        if m:
            out = out[: m.start()] + ("{" if m.group(1) == "{" else "")
    out = _DANGLING_LITERAL.sub(r"\1", out).rstrip()
    out = re.sub(r"[,:]\s*$", "", out)  # trailing comma / orphan colon
    return out + "".join(reversed(stack))


def parse_json_lenient(text: str) -> ParsedJson:
    stripped = text.strip()
    if not stripped:
        raise StructuredOutputError("empty output")

    # 1. The happy path.
    if (value := _loads(stripped)) is not None:
        return ParsedJson(value, repaired=False)

    # 2. Inside a markdown fence (possibly unterminated).
    candidates = [m.group(1).strip() for m in _FENCE.finditer(stripped)]
    # 3. Embedded in prose: start at the first opener.
    openers = [i for i in (stripped.find("{"), stripped.find("[")) if i != -1]
    if openers:
        candidates.append(stripped[min(openers) :])

    decoder = json.JSONDecoder()
    for candidate in candidates:
        if (value := _loads(candidate)) is not None:
            return ParsedJson(value, repaired=False)
        start = next((i for i, c in enumerate(candidate) if c in "{["), None)
        if start is None:
            continue
        try:  # valid JSON followed by chatter
            obj, _ = decoder.raw_decode(candidate[start:])
            if isinstance(obj, dict | list):
                return ParsedJson(obj, repaired=False)
        except json.JSONDecodeError:
            pass
        # 4. Truncated output: close what is open and drop what cannot be completed.
        if (value := _loads(_close_open_structures(candidate[start:]))) is not None:
            return ParsedJson(value, repaired=True)

    raise StructuredOutputError("no recoverable JSON found in model output")
