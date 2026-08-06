"""Vision PDF/image extract — gated on INGEST_VISION=ollama + qwen3-vl (ING-4)."""

from __future__ import annotations

import base64
import json

import httpx

from app.ingest.extract_pdf import extract_pdf_from_text
from app.ingest.schema import DocType, IngestRef, IngestTable
from app.settings import settings

_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"RIFF", "webp"),  # further check needed
)


class VisionNotReadyError(ValueError):
    """Raised when vision path is enabled but qwen3-vl is not installed."""


def ingest_vision_enabled() -> bool:
    return settings.ingest_vision.strip().lower() == "ollama"


def is_image_bytes(raw: bytes) -> bool:
    if not raw or len(raw) < 8:
        return False
    for magic, kind in _IMAGE_MAGIC:
        if raw.startswith(magic):
            if kind == "webp":
                return len(raw) > 12 and raw[8:12] == b"WEBP"
            return True
    return False


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
        return False, "INGEST_VISION=off — text PDF / CSV path only"
    target = settings.ingest_vision_model.strip()
    names = _ollama_tags()
    if any(target in n or n.startswith("qwen3-vl") for n in names):
        return True, f"vision model available: {target}"
    return False, f"Final step: ollama pull {target}"


def pdf_needs_vision(raw: bytes) -> bool:
    from app.ingest.extract_pdf import extract_text_from_pdf

    try:
        extract_text_from_pdf(raw)
    except ValueError:
        return True
    return False


def _vision_ocr_text(*, raw: bytes, doc_type: DocType, prompt_extra: str = "") -> str:
    ready, msg = check_vision_model()
    if not ready:
        raise VisionNotReadyError(msg)

    b64 = base64.b64encode(raw).decode("ascii")
    base = settings.ollama_base_url.rstrip("/")
    model = settings.ingest_vision_model
    prompt = (
        f"OCR this {doc_type} business document. Return plain text tables only — "
        "preserve columns and qty-break tiers for price lists. "
        "For BoMs keep parent product and component lines distinct. "
        f"{prompt_extra}"
    ).strip()
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
    }
    resp = httpx.post(f"{base}/api/chat", json=body, timeout=180.0)
    resp.raise_for_status()
    data = resp.json()
    text = str((data.get("message") or {}).get("content") or "").strip()
    if not text:
        raise ValueError("Vision model returned empty text")
    return text


def extract_pdf_with_vision(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
    db=None,
) -> tuple[list[IngestTable], list[IngestRef], list[str]]:
    text = _vision_ocr_text(raw=raw, doc_type=doc_type)
    ready, msg = check_vision_model()
    tables, refs, warnings = extract_pdf_from_text(
        filename=filename, text=text, doc_type=doc_type, db=db
    )
    return tables, refs, [f"vision:{settings.ingest_vision_model}", msg, *warnings]


def extract_image_with_vision(
    *,
    filename: str,
    raw: bytes,
    doc_type: DocType,
    db=None,
) -> tuple[list[IngestTable], list[IngestRef], list[str]]:
    if not is_image_bytes(raw) and not filename.lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".gif")
    ):
        raise ValueError(f"Not an image file: {filename}")
    text = _vision_ocr_text(
        raw=raw,
        doc_type=doc_type,
        prompt_extra="This is a photograph or scan of a paper document.",
    )
    ready, msg = check_vision_model()
    tables, refs, warnings = extract_pdf_from_text(
        filename=filename, text=text, doc_type=doc_type, db=db
    )
    return tables, refs, [f"vision_image:{settings.ingest_vision_model}", msg, *warnings]
