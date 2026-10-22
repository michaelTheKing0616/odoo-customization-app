"""Code inspection: Stage H cannot be bypassed on the wireframe path."""

from __future__ import annotations

import ast
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
_APP_ROOT = _API_ROOT / "app"
_WIREFRAME = _APP_ROOT / "wireframe"
_PREPARE = _APP_ROOT / "ai_apply_readiness.py"
_APPLY_UI = _APP_ROOT / "spec_apply_ui.py"

_APPLY_NAMES = frozenset(
    {
        "apply_module_spec_ui",
        "apply_module_spec",
        "apply_session_route",
        "apply_project_spec",
        "apply_project",
        "apply_queued_flush",
    }
)
_LLM_ROOTS = frozenset({"llm_provider", "llm_gateway"})


def _call_names(fn: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _module_imports(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def _top_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def _named(tree: ast.Module, name: str) -> ast.FunctionDef:
    for fn in _top_functions(tree):
        if fn.name == name:
            return fn
    raise AssertionError(f"missing function {name}")


def test_wireframe_package_never_applies_or_calls_a_live_model() -> None:
    for path in sorted(_WIREFRAME.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _module_imports(tree):
            root = module.split(".", 1)[0]
            assert root not in _LLM_ROOTS, f"{path.name} imports {module}"
            assert "changeset" not in module
            assert "agent_runtime" not in module
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                hits = _call_names(fn) & _APPLY_NAMES
                assert hits == set(), f"{path.name}:{fn.name} calls {sorted(hits)}"


def test_exactly_one_sketch_to_spec_path_runs_stage_h() -> None:
    from app import wireframe as public

    assert public.sketch_to_module_spec is not None
    assert "sketch_to_module_spec" in public.__all__
    assert "regions_to_draft" not in public.__all__

    producers: list[str] = []
    for path in sorted(_WIREFRAME.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fn in _top_functions(tree):
            calls = _call_names(fn)
            if "regions_to_draft" in calls and (
                "attach_stage_h" in calls or "residual_form_preview" in calls
            ):
                producers.append(fn.name)
    assert producers == ["sketch_to_module_spec"]

    review = ast.parse(
        (_WIREFRAME / "review.py").read_text(encoding="utf-8"),
        filename="review.py",
    )
    sole = _named(review, "sketch_to_module_spec")
    assert "attach_stage_h" in _call_names(sole)
    attach = _named(review, "attach_stage_h")
    assert "residual_form_preview" in _call_names(attach)
    assert "attach_generation_engine" in _call_names(attach)


def test_existing_apply_must_pass_stage_h() -> None:
    prepare_tree = ast.parse(_PREPARE.read_text(encoding="utf-8"), filename=str(_PREPARE))
    prepare = _named(prepare_tree, "prepare_spec_for_live_apply")
    assert "require_wireframe_stage_h" in _call_names(prepare)

    apply_tree = ast.parse(_APPLY_UI.read_text(encoding="utf-8"), filename=str(_APPLY_UI))
    apply_ui = _named(apply_tree, "apply_module_spec_ui")
    assert "require_wireframe_stage_h" in _call_names(apply_ui)


def test_no_second_wireframe_apply_route() -> None:
    hits: list[str] = []
    for path in _APP_ROOT.rglob("*.py"):
        if "wireframe" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "sketch_to_module_spec" in text and any(
            token in text for token in ("apply_module_spec_ui", "apply_session_route")
        ):
            hits.append(str(path.relative_to(_API_ROOT)))
    assert hits == []
