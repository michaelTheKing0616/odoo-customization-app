"""Live photograph → sketch JSON → existing Stage H path.

JSON fixtures still go through ``app.wireframe.reader``. This module is the
only place an uploaded photo is sent to a vision model. Gemini is the default.
Claude is used only when the vision provider setting is FRONTIER_PROVIDER.
A missing Gemini key does not invent regions and does not fall through to Claude.
"""

from __future__ import annotations

from typing import Any

from app.llm_gateway.providers import (
    DEFAULT_VISION_PROVIDER,
    FRONTIER_PROVIDER,
    vision_binding,
    vision_provider_name,
)
from app.llm_json import parse_llm_json_object
from app.llm_provider import AnthropicProvider, GeminiProvider, LLMProvider
from app.settings import settings
from app.wireframe.reader import Sketch
from app.wireframe.review import apply_sketch_clarification, sketch_to_module_spec

_SKETCH_SYSTEM = (
    "You transcribe a photographed form or whiteboard sketch into JSON. "
    "Return only a JSON object with title, prompt, source, and regions. "
    "Each region has id, label, hint, optional widget, optional relation, confidence (0-1), "
    "and box: [x, y, width, height] as fractions of the image (0-1) around the region. "
    "hint is one of: char, date, email, phone, host, image, priority, text, many2one, boolean. "
    "Use an empty label and confidence below 0.5 when you cannot read a region. "
    "Do not invent fields that are not visible."
)

_SKETCH_PROMPT = (
    "Read this photographed sketch. List every labeled field as a region. "
    "Do not guess unlabeled boxes."
)

_NOT_CONNECTED = (
    "Gemini is not connected. Add GEMINI_API_KEY or set up Vertex AI to read a photographed sketch."
)


def _gemini_ready() -> bool:
    """Gemini through the shared AI client: a Studio key, or Vertex AI (project + ADC/service account)."""
    if settings.resolved_gemini_api_key():
        return True
    backend = (getattr(settings, "gemini_backend", "") or "").strip().lower()
    return backend == "vertex" and bool((getattr(settings, "vertex_project", "") or "").strip())


def selected_vision_provider() -> str:
    """Call site for the vision binding. Switching is one setting."""
    return vision_binding(vision_provider_name(settings.ai_vision_provider or None)).name


def get_vision_llm_provider() -> LLMProvider | None:
    from app.ai_client.shared_client import wrap

    """Same call site: Gemini unless the setting is FRONTIER_PROVIDER."""
    binding = vision_binding(vision_provider_name(settings.ai_vision_provider or None))
    if binding.name == FRONTIER_PROVIDER:
        if not (settings.anthropic_api_key or "").strip():
            return None
        return wrap(AnthropicProvider())
    if not _gemini_ready():
        return None
    return wrap(GeminiProvider())


def vision_status() -> dict[str, Any]:
    """Report today's Gemini connection. Does not activate Claude."""
    selected = selected_vision_provider()
    gemini_ok = bool(_gemini_ready())
    connected = gemini_ok if selected == DEFAULT_VISION_PROVIDER else _frontier_key_present()
    if selected == DEFAULT_VISION_PROVIDER:
        message = "Gemini is connected." if gemini_ok else _NOT_CONNECTED
    else:
        message = (
            "The frontier vision provider is selected but is not connected."
            if not connected
            else "Frontier vision provider is connected."
        )
    return {
        "provider": selected,
        "connected": connected,
        "message": message,
        "default_provider": DEFAULT_VISION_PROVIDER,
    }


def read_uploaded_photo(
    image_bytes: bytes,
    mime_type: str,
    *,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Send a photo to the selected vision provider. Never applies."""
    selected = selected_vision_provider()
    if provider is None:
        if selected == DEFAULT_VISION_PROVIDER and not _gemini_ready():
            return _not_connected(selected)
        if selected == FRONTIER_PROVIDER and not _frontier_key_present():
            return _not_connected(selected)
        provider = get_vision_llm_provider()
    if provider is None:
        return _not_connected(selected)
    raw = provider.generate_json(
        _SKETCH_PROMPT,
        system=_SKETCH_SYSTEM,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )
    try:
        payload = parse_llm_json_object(raw)
    except ValueError:
        return {
            "status": "error",
            "connected": True,
            "provider": selected,
            "message": "The vision model did not return a usable sketch. No regions were invented.",
            "clarification": None,
            "spec": None,
            "apply_ready": False,
            "sketch": None,
        }
    if not isinstance(payload.get("regions"), list) or not payload["regions"]:
        return {
            "status": "error",
            "connected": True,
            "provider": selected,
            "message": "The vision model returned no regions. No fields were invented.",
            "clarification": None,
            "spec": None,
            "apply_ready": False,
            "sketch": None,
        }
    payload.setdefault("source", "photograph")
    payload.setdefault("title", payload.get("title") or "Custom app")
    payload.setdefault("prompt", payload.get("prompt") or payload["title"])
    outcome = sketch_to_module_spec(payload)
    return _with_sketch(outcome, payload, selected)


def clarify_uploaded_sketch(
    sketch_payload: dict[str, Any],
    *,
    merge_key: str,
    answer_id: str,
    answer_text: str = "",
) -> dict[str, Any]:
    """Honor a clarify answer, then the existing sketch_to_module_spec path."""
    from app.wireframe.reader import read_sketch

    sketch = read_sketch(sketch_payload)
    apply_sketch_clarification(
        sketch,
        merge_key=merge_key,
        answer_id=answer_id,
        answer_text=answer_text,
    )
    outcome = sketch_to_module_spec(sketch)
    return _with_sketch(outcome, _sketch_payload(sketch), selected_vision_provider())


def _frontier_key_present() -> bool:
    return bool((settings.anthropic_api_key or "").strip())


def _not_connected(selected: str) -> dict[str, Any]:
    message = _NOT_CONNECTED
    if selected == FRONTIER_PROVIDER:
        message = "The frontier vision provider is selected but is not connected."
    return {
        "status": "not_connected",
        "connected": False,
        "provider": selected,
        "message": message,
        "clarification": None,
        "spec": None,
        "apply_ready": False,
        "sketch": None,
    }


def _sketch_payload(sketch: Sketch) -> dict[str, Any]:
    return {
        "title": sketch.title,
        "prompt": sketch.prompt,
        "source": sketch.source,
        "regions": [
            {
                "id": region.id,
                "label": region.label,
                "hint": region.hint,
                "widget": region.widget,
                "relation": region.relation,
                "confidence": region.confidence,
                "misread": region.misread,
                "box": list(region.box) if region.box else None,
            }
            for region in sketch.regions
        ],
    }


def _with_sketch(outcome: dict[str, Any], sketch: dict[str, Any], provider: str) -> dict[str, Any]:
    stamped = dict(outcome)
    stamped["sketch"] = sketch
    stamped["apply_ready"] = False
    stamped["connected"] = True
    stamped["provider"] = provider
    return stamped
