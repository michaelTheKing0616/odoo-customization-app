"""Stage H is mandatory for wireframe output. There is no apply here.

The sole sketch → app plan function is ``sketch_to_module_spec``. It
either returns a clarify step or a review-ready draft whose header form
was built by the existing Stage H helpers. Apply stays on the existing
ModuleSpec path and must call ``require_wireframe_stage_h``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai_conversation.clarify import apply_clarification_answer
from app.ai_generation_engine import attach_generation_engine, residual_form_preview
from app.wireframe.compile import regions_to_draft
from app.wireframe.reader import Sketch, SketchRegion, read_sketch

_HINT_FROM_ANSWER = {
    "name": "char",
    "date": "date",
    "email": "email",
    "phone": "phone",
    "host": "host",
    "photo": "image",
    "priority": "priority",
}


class WireframeReviewRequired(Exception):
    """Wireframe output cannot apply until Stage H has a form preview."""


def sketch_to_module_spec(source: Path | str | dict[str, Any] | Sketch) -> dict[str, Any]:
    """Sole path from a sketch toward a app plan. Never applies."""
    sketch = source if isinstance(source, Sketch) else read_sketch(source)
    clarification = _clarification_for(sketch)
    if clarification is not None:
        return {
            "status": "clarify",
            "clarification": clarification,
            "spec": None,
            "apply_ready": False,
        }
    draft = regions_to_draft(sketch)
    attach_stage_h(draft, prompt=sketch.prompt)
    return {
        "status": "review",
        "clarification": None,
        "spec": draft,
        "apply_ready": False,
        "form_preview": ((draft.get("_generation_engine") or {}).get("form_preview")),
    }


def attach_stage_h(draft: dict[str, Any], *, prompt: str) -> dict[str, Any]:
    """Run the existing header-form Stage H review. Fail closed."""
    preview = residual_form_preview(draft)
    if not preview:
        raise WireframeReviewRequired("Stage H form preview is required before apply")
    attach_generation_engine(draft, prompt, user_phase="review")
    ir = draft.get("_generation_engine")
    if not isinstance(ir, dict) or not ir.get("form_preview"):
        raise WireframeReviewRequired("Stage H form preview is required before apply")
    stamp = dict(draft.get("_wireframe") or {})
    stamp["source"] = stamp.get("source") or "sketch"
    stamp["stage_h"] = True
    draft["_wireframe"] = stamp
    return draft


def require_wireframe_stage_h(spec: dict[str, Any] | None) -> None:
    """Existing apply must call this. A missing Stage H stamp refuses apply."""
    if not isinstance(spec, dict):
        return
    stamp = spec.get("_wireframe")
    if not isinstance(stamp, dict):
        return
    if not stamp.get("stage_h"):
        raise WireframeReviewRequired(
            "Wireframe output must pass Stage H review before apply"
        )
    preview = residual_form_preview(spec)
    ir = spec.get("_generation_engine")
    ir_preview = ir.get("form_preview") if isinstance(ir, dict) else None
    if not preview or not ir_preview:
        raise WireframeReviewRequired("Stage H form preview is missing")


def apply_sketch_clarification(
    sketch: Sketch,
    *,
    merge_key: str,
    answer_id: str,
    answer_text: str = "",
) -> Sketch:
    """Honor an existing-clarify answer, then the caller re-runs sketch_to_module_spec."""
    region = sketch.first_unclear()
    if region is None:
        return sketch
    if answer_id == "drop":
        sketch.regions = [item for item in sketch.regions if item.id != region.id]
    else:
        _resolve_region(region, answer_id=answer_id, answer_text=answer_text)
    merged, _answers = apply_clarification_answer(
        sketch.prompt,
        merge_key=merge_key,
        answer_id=answer_id,
        answer_text=answer_text,
    )
    sketch.prompt = merged
    return sketch


def _clarification_for(sketch: Sketch) -> dict[str, Any] | None:
    region = sketch.first_unclear()
    if region is None:
        return None
    if region.is_unlabeled():
        question = "What is the unlabeled region on this sketch?"
        help_text = "We will not guess a field from a blank box. Name it or drop it."
        kind = "wireframe_unlabeled"
    else:
        question = "We could not read this region. What should it be?"
        help_text = "A vision misread is a question, not a silent apply."
        kind = "wireframe_misread"
    return {
        "id": kind,
        "merge_key": "wireframe_region",
        "question": question,
        "help": help_text,
        "region_id": region.id,
        "options": [
            {"id": "name", "label": "A name or title field"},
            {"id": "date", "label": "A date field"},
            {"id": "host", "label": "A host or user"},
            {"id": "drop", "label": "Ignore this region"},
            {"id": "other", "label": "Something else — I’ll type it"},
        ],
        "default_id": "name",
    }


def _resolve_region(region: SketchRegion, *, answer_id: str, answer_text: str) -> None:
    label = (answer_text or "").strip()
    if not label:
        labels = {
            "name": "Name",
            "date": "Date",
            "email": "Email",
            "phone": "Phone",
            "host": "Host",
            "photo": "Photo",
            "priority": "Priority",
            "other": "Notes",
        }
        label = labels.get(answer_id, answer_id.replace("_", " ").title() or "Field")
    region.label = label
    region.hint = _HINT_FROM_ANSWER.get(answer_id, region.hint or "char")
    region.confidence = 1.0
    region.misread = False
