"""PR-F.0: golden offline finish must use the Studio Generate wrapper."""

from __future__ import annotations

import inspect
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AI_DRAFT_JOBS = _REPO_ROOT / "apps" / "api" / "app" / "ai_draft_jobs.py"


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
