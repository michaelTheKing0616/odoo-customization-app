"""Per-connection client-document index (not domain-pack RAG)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]{3,}")
_CHUNK_CHARS = 900
_MAX_CHUNKS_PER_FILE = 40
_MAX_FILES = 40


def _cache_dir() -> Path:
    return Path(__file__).resolve().parents[4] / ".cache" / "job_docs"


def _index_path(connection_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", (connection_id or "unknown"))[:80]
    return _cache_dir() / f"{safe}.json"


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall((text or "").lower()))


def _chunks_from_text(filename: str, text: str) -> list[dict[str, Any]]:
    body = (text or "").strip()
    if not body:
        return [{"filename": filename, "text": filename, "tokens": sorted(_tokens(filename))}]
    out: list[dict[str, Any]] = []
    start = 0
    while start < len(body) and len(out) < _MAX_CHUNKS_PER_FILE:
        piece = body[start : start + _CHUNK_CHARS]
        out.append(
            {
                "filename": filename,
                "text": piece,
                "tokens": sorted(_tokens(piece)),
            }
        )
        start += _CHUNK_CHARS
    return out


def upsert_client_docs(
    connection_id: str,
    excerpts: list[tuple[str, str]],
) -> int:
    """Merge file excerpts into the connection's on-disk chunk index. Returns chunk count."""
    if not connection_id or not excerpts:
        return 0
    path = _index_path(connection_id)
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("chunks"), list):
                existing = [c for c in raw["chunks"] if isinstance(c, dict)]
        except (OSError, json.JSONDecodeError):
            existing = []
    added: list[dict[str, Any]] = []
    for name, text in excerpts[:_MAX_FILES]:
        existing = [c for c in existing if str(c.get("filename") or "") != name]
        added.extend(_chunks_from_text(name, text))
    chunks = existing + added
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"connection_id": connection_id, "chunks": chunks},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return len(chunks)


def retrieve_grounding(
    connection_id: str,
    query: str,
    *,
    k: int = 8,
) -> list[str]:
    """Jaccard retrieve client-doc chunks. Empty if no index — never pack RAG."""
    path = _index_path(connection_id)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    chunks = raw.get("chunks") if isinstance(raw, dict) else None
    if not isinstance(chunks, list):
        return []
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[float, str]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        tokens = chunk.get("tokens")
        if isinstance(tokens, list):
            tset = {str(t).lower() for t in tokens}
        else:
            tset = _tokens(str(chunk.get("text") or ""))
        if not tset:
            continue
        score = len(q & tset) / max(len(q | tset), 1)
        if score <= 0:
            continue
        label = str(chunk.get("filename") or "doc")
        body = str(chunk.get("text") or "").strip()
        if body:
            scored.append((score, f"{label}: {body[:400]}"))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [text for _s, text in scored[:k]]


__all__ = ["retrieve_grounding", "upsert_client_docs"]
