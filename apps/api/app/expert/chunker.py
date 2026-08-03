"""RST/Markdown heading-hierarchy chunker for Expert RAG ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MIN_TOKENS = 300
MAX_TOKENS = 900
SPLIT_THRESHOLD = MAX_TOKENS * 2

_RST_UNDERLINE = re.compile(r"^(=|-|\~|\^|\"|\')+$")
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_CONTINUATION_PREFIX = "(continued from {breadcrumb})"
_CONTINUATION_SUFFIX = "(continued)"


@dataclass(frozen=True)
class DocChunk:
    breadcrumb: str
    text: str
    source_path: str = ""


def estimate_tokens(text: str) -> int:
    """Approximate token count (~1.3 tokens per word)."""
    words = len(text.split())
    return max(1, int(words * 1.3))


def _split_paragraphs(body: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    return parts or ([body.strip()] if body.strip() else [])


def _split_oversized_body(breadcrumb: str, body: str) -> list[str]:
    """Split a section that exceeds 2x MAX at paragraph boundaries with continuation markers."""
    paragraphs = _split_paragraphs(body)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        text = "\n\n".join(current)
        if chunks:
            text = f"{_CONTINUATION_PREFIX.format(breadcrumb=breadcrumb)}\n\n{text}"
        if estimate_tokens(body) > SPLIT_THRESHOLD and len(chunks) + 1 < len(paragraphs):
            text = f"{text}\n\n{_CONTINUATION_SUFFIX}"
        chunks.append(text)
        current = []
        current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        if para_tokens > SPLIT_THRESHOLD:
            flush()
            chunks.append(
                f"{_CONTINUATION_PREFIX.format(breadcrumb=breadcrumb)}\n\n{para}\n\n{_CONTINUATION_SUFFIX}"
                if chunks
                else para
            )
            continue
        if current and current_tokens + para_tokens > MAX_TOKENS:
            flush()
        current.append(para)
        current_tokens += para_tokens

    flush()
    return chunks or [body.strip()]


def _merge_small_sections(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge adjacent small sections until each chunk is at least MIN_TOKENS when possible."""
    if not sections:
        return []

    merged: list[tuple[str, str]] = []
    pending_bc: str | None = None
    pending_body: list[str] = []
    pending_tokens = 0

    def flush_pending() -> None:
        nonlocal pending_bc, pending_body, pending_tokens
        if pending_bc is None or not pending_body:
            pending_bc = None
            pending_body = []
            pending_tokens = 0
            return
        merged.append((pending_bc, "\n\n".join(pending_body)))
        pending_bc = None
        pending_body = []
        pending_tokens = 0

    for breadcrumb, body in sections:
        tokens = estimate_tokens(body)
        if tokens >= SPLIT_THRESHOLD:
            flush_pending()
            for part in _split_oversized_body(breadcrumb, body):
                merged.append((breadcrumb, part))
            continue

        if tokens >= MIN_TOKENS and tokens <= MAX_TOKENS:
            flush_pending()
            merged.append((breadcrumb, body))
            continue

        if pending_bc is None:
            pending_bc = breadcrumb
            pending_body = [body]
            pending_tokens = tokens
        elif pending_tokens + tokens <= MAX_TOKENS:
            pending_bc = breadcrumb
            pending_body.append(body)
            pending_tokens += tokens
        else:
            flush_pending()
            pending_bc = breadcrumb
            pending_body = [body]
            pending_tokens = tokens

        if pending_tokens >= MIN_TOKENS:
            flush_pending()

    flush_pending()
    return merged


def _parse_rst_sections(text: str) -> list[tuple[str, str, int]]:
    """Return [(title, body, level)] parsed from RST heading underlines."""
    lines = text.splitlines()
    sections: list[tuple[str, str, int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and line.strip() and _RST_UNDERLINE.match(lines[i + 1].strip()):
            title = line.strip()
            underline = lines[i + 1].strip()
            level = {"=": 1, "-": 2, "~": 3, "^": 4, '"': 5, "'": 6}.get(underline[0], 2)
            i += 2
            body_lines: list[str] = []
            while i < len(lines):
                if (
                    i + 1 < len(lines)
                    and lines[i].strip()
                    and _RST_UNDERLINE.match(lines[i + 1].strip())
                ):
                    break
                body_lines.append(lines[i])
                i += 1
            sections.append((title, "\n".join(body_lines).strip(), level))
            continue
        i += 1

    if not sections and text.strip():
        sections.append(("Document", text.strip(), 1))
    return sections


def _parse_md_sections(text: str) -> list[tuple[str, str, int]]:
    """Return [(title, body, level)] parsed from Markdown # headings."""
    lines = text.splitlines()
    sections: list[tuple[str, str, int]] = []
    current_title = "Document"
    current_level = 1
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal body_lines
        body = "\n".join(body_lines).strip()
        if body or sections:
            sections.append((current_title, body, current_level))
        body_lines = []

    for line in lines:
        m = _MD_HEADING.match(line)
        if m:
            flush()
            current_level = len(m.group(1))
            current_title = m.group(2).strip()
            continue
        body_lines.append(line)

    flush()
    if not sections and text.strip():
        sections.append(("Document", text.strip(), 1))
    return sections


def _breadcrumb_stack(stack: list[tuple[int, str]], level: int, title: str) -> str:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))
    return " > ".join(t for _lvl, t in stack)


def chunk_document(text: str, *, source_path: str = "", fmt: str | None = None) -> list[DocChunk]:
    """Chunk RST or Markdown by heading hierarchy with token targets."""
    path = Path(source_path)
    resolved_fmt = (fmt or path.suffix.lstrip(".")).lower()
    if resolved_fmt in {"md", "markdown"}:
        raw_sections = _parse_md_sections(text)
    else:
        raw_sections = _parse_rst_sections(text)

    stack: list[tuple[int, str]] = []
    prepared: list[tuple[str, str]] = []
    for title, body, level in raw_sections:
        _breadcrumb_stack(stack, level, title)
        if not body.strip():
            continue
        breadcrumb = " > ".join(t for _lvl, t in stack)
        prepared.append((breadcrumb, body.strip()))

    merged = _merge_small_sections(prepared)
    return [
        DocChunk(breadcrumb=bc, text=body, source_path=source_path)
        for bc, body in merged
        if body.strip()
    ]


def chunk_file(path: Path) -> list[DocChunk]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return chunk_document(text, source_path=str(path), fmt=path.suffix.lstrip("."))
