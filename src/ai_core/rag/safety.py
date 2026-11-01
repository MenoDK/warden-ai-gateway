"""Treat retrieved documents as *data*, never as instructions.

Three independent defences, because any single one will eventually be bypassed:

1. ``redact_secrets``      -- credentials never reach the index (or the embedder).
2. ``looks_like_injection`` -- a passage that talks *to the model* ("ignore previous
   instructions...") is quarantined: left out of the index and reported for human review.
   Neutralising just the offending sentence is not enough, the rest of a poisoned passage
   keeps steering the model, so the whole chunk is excluded.
3. ``neutralize_template_tokens`` -- chat-template control tokens inside untrusted text are
   defused before they can end up in a prompt.

The injection heuristic is deliberately narrow (imperative forms, role markers only at the
start of a line). Tests include benign technical text that *mentions* these words, because a
detector that quarantines legitimate documentation is its own kind of outage.
"""

from __future__ import annotations

import re

from ai_core.privacy.masker import PIIMasker

_TEMPLATE_TOKENS = re.compile(
    r"<\|im_start\|>|<\|im_end\|>|<\|system\|>|\[/?INST\]|<<SYS>>|<</SYS>>|###\s*Instruction",
    re.IGNORECASE,
)
_ROLE_MARKER = re.compile(r"^\s*(system|assistant|human)\s*:\s", re.IGNORECASE | re.MULTILINE)
_NATURAL = re.compile(
    r"\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|your)\s+"
    r"(instructions|rules|prompt)"
    r"|\bsystem\s+override\b"
    r"|\bnew\s+instructions\s*:"
    r"|\bfrom\s+now\s+on,?\s+(you|respond|answer|act|begin|start)\b"
    r"|\byou\s+are\s+now\b"
    r"|\b(reveal|print|show)\s+(the\s+)?(contents\s+of\s+(the\s+)?)?(\.env|system\s+prompt)"
    r"|\b(send|forward)\s+(the\s+)?(conversation|chat)\s+history\b"
    # Portuguese imperative forms
    r"|\b(ignore|desconsidere|esque[cç]a)\s+(todas?\s+)?(as\s+)?(suas\s+)?"
    r"(instru[cç][oõ]es|regras|ordens)\s+(anteriores|acima)"
    r"|\ba\s+partir\s+de\s+agora,?\s+(voc[eê]|responda|diga|aja)\b",
    re.IGNORECASE,
)

_MASKER = PIIMasker()


def looks_like_injection(text: str) -> bool:
    return bool(_TEMPLATE_TOKENS.search(text) or _ROLE_MARKER.search(text) or _NATURAL.search(text))


def neutralize_template_tokens(text: str) -> str:
    return _TEMPLATE_TOKENS.sub("[removed-token]", text)


def redact_secrets(text: str) -> tuple[str, int]:
    """Replace credentials with ``<SECRET_n>``; returns the clean text and how many were found."""
    result = _MASKER.mask(text)
    # Only secrets are *redacted* at ingestion; personal data is the caller's policy decision.
    count = 0
    cleaned = text
    for placeholder, original in result.mapping.items():
        if placeholder.startswith("<SECRET_"):
            cleaned = cleaned.replace(original, placeholder)
            count += 1
    return cleaned, count


_CITATION = re.compile(r"\[(\d+)\]")


def check_citations(text: str, source_count: int) -> tuple[bool, str, int]:
    """Validate that bracketed citations point at sources that were actually provided.

    Returns ``(grounded, cleaned_text, removed_markers)``. ``grounded`` is False when the text
    cites nothing valid -- the caller should then not trust it as a sourced answer.
    """
    removed = 0

    def _keep(match: re.Match[str]) -> str:
        nonlocal removed
        if 1 <= int(match.group(1)) <= source_count:
            return match.group(0)
        removed += 1
        return ""

    cleaned = _CITATION.sub(_keep, text).strip()
    grounded = any(1 <= int(n) <= source_count for n in _CITATION.findall(cleaned))
    return grounded, cleaned, removed
