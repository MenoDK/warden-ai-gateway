"""The landing page shows recorded output of this service. It must be the output of *this* code."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_recorder():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("record_transcripts", ROOT / "scripts" / "record_transcripts.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["record_transcripts"] = module
    spec.loader.exec_module(module)
    return module


def test_the_committed_transcripts_are_what_the_code_produces_today() -> None:
    recorder = _load_recorder()
    committed = (ROOT / "site" / "transcripts.js").read_text(encoding="utf-8")
    assert committed == recorder.build(), "site/transcripts.js is stale: run `python scripts/record_transcripts.py`"


def test_the_story_the_page_tells_is_true() -> None:
    """Pin the claims made next to the transcripts, so a behaviour change cannot leave the copy behind."""
    text = (ROOT / "site" / "transcripts.js").read_text(encoding="utf-8")
    assert "skipped_sensitive" in text  # sensitive text is refused to the cloud
    assert "&lt;EMAIL_1&gt;" in text  # the cloud received a placeholder
    assert "quarantined" in text and "answered" in text  # held back first, then answered with provenance
    assert text.count("invalid webhook signature") == 2  # tampering and replay get the same generic answer
    assert "duplicate" in text
