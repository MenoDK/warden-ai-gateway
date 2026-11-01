"""Reversible pseudonymisation of personal data and secrets.

Text is rewritten with stable placeholders (``<EMAIL_1>``) *before* it leaves the trust
boundary. The placeholder -> original mapping never leaves the process and is only used to
re-hydrate the model's answer locally (``unmask``).

Detectors with a checksum (national id, payment card) validate before masking, so ordinary
digit sequences are not mangled. Dates are intentionally left untouched: they are rarely
identifying on their own and are often essential context for the model.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

_Validator = Callable[[str], bool]


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def valid_national_id(value: str) -> bool:
    """Checksum for the 11-digit Brazilian CPF."""
    d = _digits(value)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for length in (9, 10):
        total = sum(int(d[i]) * (length + 1 - i) for i in range(length))
        check = (total * 10) % 11 % 10
        if check != int(d[length]):
            return False
    return True


def luhn(value: str) -> bool:
    d = _digits(value)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def plausible_phone(value: str) -> bool:
    return 10 <= len(_digits(value)) <= 13


@dataclass(frozen=True)
class _Detector:
    entity: str
    pattern: re.Pattern[str]
    validator: _Validator | None = None


# Order = priority. A span claimed by an earlier detector cannot be claimed again.
_DETECTORS: tuple[_Detector, ...] = (
    _Detector(
        "SECRET",
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_\-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}"
            r"|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9\-]{10,})\b"
        ),
    ),
    _Detector("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    _Detector("NATIONAL_ID", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), valid_national_id),
    _Detector("CARD", re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), luhn),
    _Detector(
        "IPV4",
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
    ),
    _Detector(
        "PHONE",
        re.compile(r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,3}\)|\d{2,3})?[\s.-]?\d{4,5}[\s.-]?\d{4}(?![\w])"),
        plausible_phone,
    ),
)


@dataclass
class MaskResult:
    text: str
    entities: dict[str, int] = field(default_factory=dict)  # type -> count (no values!)
    mapping: dict[str, str] = field(default_factory=dict, repr=False)  # placeholder -> original

    @property
    def found(self) -> bool:
        return bool(self.mapping)


class PIIMasker:
    def mask(self, text: str) -> MaskResult:
        claimed: list[tuple[int, int, str]] = []
        for det in _DETECTORS:
            for m in det.pattern.finditer(text):
                start, end = m.span()
                if det.validator and not det.validator(m.group()):
                    continue
                if any(start < c_end and end > c_start for c_start, c_end, _ in claimed):
                    continue
                claimed.append((start, end, det.entity))
        if not claimed:
            return MaskResult(text=text)

        claimed.sort()
        mapping: dict[str, str] = {}
        reverse: dict[tuple[str, str], str] = {}
        counters: Counter[str] = Counter()
        pieces: list[str] = []
        cursor = 0
        for start, end, entity in claimed:
            original = text[start:end]
            key = (entity, original)
            placeholder = reverse.get(key)
            if placeholder is None:
                counters[entity] += 1
                placeholder = f"<{entity}_{counters[entity]}>"
                reverse[key] = placeholder
                mapping[placeholder] = original
            pieces.append(text[cursor:start])
            pieces.append(placeholder)
            cursor = end
        pieces.append(text[cursor:])
        return MaskResult(text="".join(pieces), entities=dict(counters), mapping=mapping)

    def detect(self, text: str) -> bool:
        return self.mask(text).found

    @staticmethod
    def unmask(text: str, mapping: dict[str, str]) -> str:
        for placeholder, original in mapping.items():
            text = text.replace(placeholder, original)
        return text
