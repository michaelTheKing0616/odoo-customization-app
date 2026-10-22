"""T4-WIRE: a sketch becomes a ModuleSpec; ambiguity asks; apply is not silent."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai_apply_readiness import prepare_spec_for_live_apply
from app.module_spec_codec import draft_dict_to_module_spec
from app.wireframe import (
    WireframeReviewRequired,
    apply_sketch_clarification,
    read_sketch,
    require_wireframe_stage_h,
    sketch_to_module_spec,
)
from app.wireframe.compile import regions_to_draft

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "wireframe"
_PHOTO = _FIXTURES / "visitor_log_photo.json"
_UNLABELED = _FIXTURES / "unlabeled_region.json"
_MISREAD = _FIXTURES / "vision_misread.json"


def test_photographed_sketch_becomes_module_spec() -> None:
    outcome = sketch_to_module_spec(_PHOTO)
    assert outcome["status"] == "review"
    assert outcome["clarification"] is None
    assert outcome["apply_ready"] is False
    spec = outcome["spec"]
    assert spec["technical_name"] == "visitor_log"
    models = {row["model"] for row in spec["models"]}
    assert "x_visitor_log" in models
    fields = {f["name"]: f for f in spec["models"][0]["fields"]}
    assert "x_visitor_name" in fields
    assert fields["x_host"]["ttype"] == "many2one"
    assert fields["x_host"]["widget"] == "many2one_avatar_user"
    assert fields["x_photo"]["widget"] == "image"
    assert spec["_wireframe"]["source"] == "sketch"
    assert spec["_wireframe"]["stage_h"] is True
    assert outcome["form_preview"]["model"] == "x_visitor_log"
    assert outcome["form_preview"]["type"] == "form"
    module = draft_dict_to_module_spec(spec)
    assert module.technical_name == "visitor_log"
    assert any(model.model == "x_visitor_log" for model in module.models)
    prepared, _notes = prepare_spec_for_live_apply(spec)
    assert prepared["_wireframe"]["stage_h"] is True


def test_unlabeled_region_asks_and_does_not_apply() -> None:
    outcome = sketch_to_module_spec(_UNLABELED)
    assert outcome["status"] == "clarify"
    assert outcome["spec"] is None
    assert outcome["apply_ready"] is False
    clarify = outcome["clarification"]
    assert clarify["id"] == "wireframe_unlabeled"
    assert clarify["merge_key"] == "wireframe_region"
    assert "unlabeled" in clarify["question"].lower()
    with pytest.raises(WireframeReviewRequired):
        require_wireframe_stage_h({"_wireframe": {"source": "sketch", "stage_h": False}})


def test_vision_misread_is_a_question() -> None:
    outcome = sketch_to_module_spec(_MISREAD)
    assert outcome["status"] == "clarify"
    assert outcome["spec"] is None
    assert outcome["apply_ready"] is False
    assert outcome["clarification"]["id"] == "wireframe_misread"
    assert "silent" in (outcome["clarification"].get("help") or "").lower() or "read" in (
        outcome["clarification"].get("question") or ""
    ).lower()


def test_clarification_then_review() -> None:
    sketch = read_sketch(_UNLABELED)
    apply_sketch_clarification(
        sketch,
        merge_key="wireframe_region",
        answer_id="date",
        answer_text="Visit date",
    )
    outcome = sketch_to_module_spec(sketch)
    assert outcome["status"] == "review"
    names = {f["name"] for f in outcome["spec"]["models"][0]["fields"]}
    assert "x_visit_date" in names
    assert outcome["spec"]["_wireframe"]["stage_h"] is True


def test_unsigned_wireframe_spec_is_refused_at_apply() -> None:
    sketch = read_sketch(_PHOTO)
    raw = regions_to_draft(sketch)
    assert raw["_wireframe"]["stage_h"] is False
    with pytest.raises(WireframeReviewRequired):
        prepare_spec_for_live_apply(raw)
    with pytest.raises(WireframeReviewRequired):
        require_wireframe_stage_h(raw)
