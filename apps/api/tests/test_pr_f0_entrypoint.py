"""PR-F.0: golden offline finish must use the Studio Generate wrapper."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("AI_INTENT_LLM", "off")

pytestmark = pytest.mark.no_app_db

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AI_DRAFT_JOBS = _REPO_ROOT / "apps" / "api" / "app" / "ai_draft_jobs.py"

_MAINTENANCE_BRIEF = (
    "Build Maintenance tickets: checklist lines with done flags, parts used (product + qty), "
    "state Draft→Done; Online-honest on stock moves."
)


def _load_function_sources() -> tuple[str, str]:
    try:
        from app import ai_draft_jobs as mod

        finish_src = inspect.getsource(mod.studio_generate_offline_finish)
        seed_src = inspect.getsource(mod._finish_seed_draft)
        return finish_src, seed_src
    except Exception:
        text = _AI_DRAFT_JOBS.read_text(encoding="utf-8")
        finish_src = _extract_def_source(text, "studio_generate_offline_finish")
        seed_src = _extract_def_source(text, "_finish_seed_draft")
        return finish_src, seed_src


def _extract_def_source(module_text: str, name: str) -> str:
    marker = f"def {name}("
    start = module_text.index(marker)
    rest = module_text[start:]
    lines = rest.splitlines()
    block: list[str] = []
    for i, line in enumerate(lines):
        if i > 0 and line and not line[0].isspace() and line.startswith("def "):
            break
        block.append(line)
    return "\n".join(block)


def _draft_invent_counts(draft: dict[str, Any]) -> tuple[int, int, int]:
    field_total = o2m_total = 0
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            field_total += 1
            if field.get("ttype") == "one2many":
                o2m_total += 1
    menus = draft.get("menus")
    menu_total = len(menus) if isinstance(menus, list) else 0
    return field_total, o2m_total, menu_total


def _generate_ir_invent_counts(draft: dict[str, Any]) -> tuple[int, int, int]:
    ir = draft.get("_generate_ir")
    if not isinstance(ir, dict):
        return (-1, -1, -1)
    fields_by_model = ir.get("fields_by_model")
    field_total = (
        sum(len(rows) for rows in fields_by_model.values())
        if isinstance(fields_by_model, dict)
        else 0
    )
    o2m_total = len(ir.get("o2ms") or [])
    menu_total = len(ir.get("menus") or [])
    return field_total, o2m_total, menu_total


def assert_finish_seed_counts_match_generate_ir(draft: dict[str, Any]) -> None:
    """T1 invariant 2: draft invent counts must match stamped ``GenerateIR``."""
    ir_counts = _generate_ir_invent_counts(draft)
    assert ir_counts[0] >= 0, "expected _generate_ir on draft after _finish_seed_draft"
    assert _draft_invent_counts(draft) == ir_counts


def _maintenance_finish_seed_draft() -> dict[str, Any]:
    from app.ai_depth import apply_deterministic_depth
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_pipeline import seed_studio_draft
    from app.ai_schema_client import FakeSchemaClient

    draft = seed_studio_draft(_MAINTENANCE_BRIEF)
    draft["_schema_client"] = FakeSchemaClient(
        models={
            "res.partner",
            "res.users",
            "res.company",
            "product.product",
            "hr.employee",
            "purchase.order",
        },
        fields={
            "res.partner": {"name": {"ttype": "char", "readonly": False}},
            "product.product": {"name": {"ttype": "char", "readonly": False}},
        },
    )
    apply_deterministic_depth(draft, user_prompt=_MAINTENANCE_BRIEF)
    return _finish_seed_draft(_MAINTENANCE_BRIEF, draft, warnings=[])


def test_studio_generate_offline_finish_calls_seed_and_locked_craft() -> None:
    finish_src, _seed_src = _load_function_sources()
    assert "_finish_seed_draft" in finish_src
    assert "_apply_locked_craft_and_surface" in finish_src


def test_studio_generate_offline_finish_docstring_golden_entrypoint() -> None:
    try:
        from app import ai_draft_jobs as mod

        doc = mod.studio_generate_offline_finish.__doc__ or ""
    except Exception:
        finish_src, _ = _load_function_sources()
        doc_start = finish_src.index('"""') + 3
        doc_end = finish_src.index('"""', doc_start)
        doc = finish_src[doc_start:doc_end]

    assert "Goldens must call" in doc
    assert "studio_generate_offline_finish" in doc or "this wrapper" in doc
    assert "_finish_seed_draft" in doc
    assert "alone" in doc.lower()


def test_finish_seed_draft_invent_counts_match_generate_ir() -> None:
    draft = _maintenance_finish_seed_draft()
    assert_finish_seed_counts_match_generate_ir(draft)


def test_finish_seed_draft_post_entrypoint_invent_fails_count_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative: a node invented after ``stamp_generate_ir`` breaks invariant 2."""
    import app.ai_generation_engine as gen_engine

    real_attach = gen_engine.attach_generation_engine

    def _attach_with_post_invent(
        draft: dict[str, Any], prompt: str, *, user_phase: str = "review"
    ) -> None:
        models = draft.get("models") or []
        if models and isinstance(models[0], dict):
            fields = list(models[0].get("fields") or [])
            fields.append({"name": "x_post_entrypoint_spray", "ttype": "char"})
            models[0]["fields"] = fields
        real_attach(draft, prompt, user_phase=user_phase)

    monkeypatch.setattr(gen_engine, "attach_generation_engine", _attach_with_post_invent)
    draft = _maintenance_finish_seed_draft()
    with pytest.raises(AssertionError):
        assert_finish_seed_counts_match_generate_ir(draft)
