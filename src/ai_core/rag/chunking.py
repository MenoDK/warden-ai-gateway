from __future__ import annotations

from ai_core.rag.models import Chunk


def chunk_text(text: str, *, size: int = 500, overlap: int = 80) -> list[Chunk]:
    """Sliding window that snaps to word boundaries and keeps exact source offsets.

    Invariant (tested): ``text[c.start:c.end] == c.text`` for every chunk, so a citation can
    always point back to the precise span of the original document.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if not 0 <= overlap < size:
        raise ValueError("overlap must be in [0, size)")

    n = len(text)
    chunks: list[Chunk] = []
    start = 0
    while start < n:
        while start < n and text[start].isspace():
            start += 1
        if start >= n:
            break

        end = min(start + size, n)
        if end < n:
            boundary = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
            if boundary > start:
                end = boundary
        piece_end = end
        while piece_end > start and text[piece_end - 1].isspace():
            piece_end -= 1
        chunks.append(Chunk(index=len(chunks), text=text[start:piece_end], start=start, end=piece_end))

        if end >= n:
            break
        next_start = max(end - overlap, start + 1)
        # Never begin a chunk in the middle of a word -- but only look as far as this chunk's
        # end. A "word" longer than the window (a base64 blob, a minified file) is hard-cut
        # instead; skipping ahead to its end would silently drop everything in between.
        while next_start < end and not text[next_start - 1].isspace():
            next_start += 1
        start = next_start
    return chunks
