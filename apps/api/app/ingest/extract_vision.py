"""Vision PDF extract — gated on INGEST_VISION=ollama + qwen3-vl installed (ING-4)."""

from __future__ import annotations

import base64
import json

import httpx

from app.ingest.extract_pdf import extract_pdf_from_text
from app.ingest.schema import DocType, IngestRef, IngestTable
from app.settings import settings


class VisionNotReadyError(ValueError):
    """Raised when vision path is enabled but qwen3-vl is not installed."""


def ingest_vision_enabled() -> bool:
    return settings.ingest_vision.strip().lower() == "ollama"


def _ollama_tags() -> list[str]:
    base = settings.ollama_base_url.rstrip("/")
    try:
        resp = httpx.get(f"{base}/api/tags", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return []
    models = data.get("models") or []
    return [str(m.get("name") or "") for m in models]


def check_vision_model() -> tuple[bool, str]:
    if not ingest_vision_enabled():
        return False, "INGEST_VISION=off — text PDF path only"
    target = settings.ingest_vision_model.strip()
    names = _ollama_tags()
    if any(target in n or n.startswith("qwen3-vl") for n in names):
        return True, f"vision model available: {target}"
    return False, f"Final step: ollama pull {target}"


def pdf_needs_vision(raw: bytes) -> bool:
    from app.ingest.extract_pdf import extract_text_from_pdf

    try:
        extract_text_from_pdf(raw)
        return False
    except ValueError:
        return True


def extract_pdf_with_vision(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
    db=None,
) -> tuple[list[IngestTable], list[IngestRef], list[str]]:
    ready, msg = check_vision_model()
    if not ready:
        raise VisionNotReadyError(msg)

    b64 = base64.b64encode(raw).decode("ascii")
    base = settings.ollama_base_url.rstrip("/")
    model = settings.ingest_vision_model
    prompt = (
        f"OCR this {doc_type} business document. Return plain text tables only — "
        "preserve columns and qty-break tiers for price lists."
    )
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
    }
    resp = httpx.post(f"{base}/api/chat", json=body, timeout=120.0)
    resp.raise_for_status()
    data = resp.json()
    text = str((data.get("message") or {}).get("content") or "").strip()
    if not text:
        raise ValueError("Vision model returned empty text")

    tables, refs, warnings = extract_pdf_from_text(
        filename=filename, text=text, doc_type=doc_type, db=db
    )
    return tables, refs, [f"vision:{model}", msg, *warnings]
