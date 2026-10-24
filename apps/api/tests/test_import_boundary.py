"""Import-boundary scanners for T8-P0-LINT.

GATE-P0-05 is not clean: apps/api/app still compares Odoo majors to
version literals outside a compat/ directory. The baseline test records
that count. It does not allowlist the files.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

_APP_ROOT = Path(__file__).resolve().parents[1] / "app"
_FORBIDDEN_IMPORT_SEGMENTS = frozenset({"llm_gateway", "agent_runtime"})
_PROVIDER_SDK_MODULES = (
    "openai",
    "anthropic",
    "google.generativeai",
    "google.genai",
)
_VERSION_LITERALS = frozenset({15, 16, 17, 18, 19, 20})
# Measured against apps/api/app on 2026-10-03. A new hit must fail.
_VERSION_BRANCH_BASELINE = 22

_PLANTED_CHANGESET_IMPORTS = (
    "from app.llm_gateway import Gateway\n",
    "import app.agent_runtime\n",
)
_PLANTED_PROVIDER_IMPORTS = (
    ("import openai\n", "openai"),
    ("from anthropic import Anthropic\n", "anthropic"),
    ("import google.generativeai\n", "google.generativeai"),
    ("from google.genai import Client\n", "google.genai"),
)


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    )


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _parse(path: Path) -> ast.AST:
    """Parse one Python file.

    Inputs: source path.
    Outputs: AST.
    Side effects: reads the file. Raises SyntaxError with that path.
    """
    text = path.read_text(encoding="utf-8")
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise SyntaxError(f"{path}: {exc.msg}") from exc


def _module_segments(module: str) -> list[str]:
    return [part for part in module.split(".") if part]


def _imports_forbidden_module(module: str) -> bool:
    return any(part in _FORBIDDEN_IMPORT_SEGMENTS for part in _module_segments(module))


def _is_provider_sdk(module: str) -> bool:
    return any(
        module == sdk or module.startswith(sdk + ".") for sdk in _PROVIDER_SDK_MODULES
    )


def _under_llm_gateway_adapters(path: Path) -> bool:
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        if part == "llm_gateway" and parts[index + 1] == "adapters":
            return True
    return False


def _under_compat_directory(path: Path) -> bool:
    return "compat" in path.parts


def forbidden_llm_imports(root: Path) -> list[str]:
    """Find imports of llm_gateway or agent_runtime under ``root``.

    Inputs: directory to scan.
    Outputs: sorted ``path:line: module`` hits. Empty when none exist.
    Side effects: reads Python files. Does not import them.
    """
    hits: list[str] = []
    for path in _python_files(root):
        tree = _parse(path)
        rel = _relative(root, path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module] if node.module else []
                modules.extend(
                    alias.name
                    for alias in node.names
                    if alias.name in _FORBIDDEN_IMPORT_SEGMENTS
                )
            else:
                continue
            for module in modules:
                if module and _imports_forbidden_module(module):
                    hits.append(f"{rel}:{node.lineno}: {module}")
    hits.sort()
    return hits


def provider_sdk_imports(root: Path) -> list[str]:
    """Find provider SDK imports outside llm_gateway/adapters/.

    SDKs: openai, anthropic, google.generativeai, google.genai.
    Inputs: directory to scan.
    Outputs: sorted ``path:line: module`` hits. Files under
    llm_gateway/adapters/ are skipped.
    Side effects: reads Python files. Does not import them.
    """
    hits: list[str] = []
    for path in _python_files(root):
        if _under_llm_gateway_adapters(path):
            continue
        tree = _parse(path)
        rel = _relative(root, path)
        for node in ast.walk(tree):
            labels: list[str] = []
            if isinstance(node, ast.Import):
                labels = [alias.name for alias in node.names if _is_provider_sdk(alias.name)]
            elif isinstance(node, ast.ImportFrom) and node.module:
                if _is_provider_sdk(node.module):
                    labels = [node.module]
                elif node.module == "google":
                    labels = [
                        f"google.{alias.name}"
                        for alias in node.names
                        if alias.name in {"genai", "generativeai"}
                    ]
            for label in labels:
                hits.append(f"{rel}:{node.lineno}: {label}")
    hits.sort()
    return hits


def _is_major_name(name: str) -> bool:
    return name == "major" or name.endswith("_major")


def _is_major_expr(node: ast.AST) -> bool:
    """True when ``node`` is a major, ``obj.major``, ``int(major)``, or ``major_of(...)``."""
    if isinstance(node, ast.Name):
        return _is_major_name(node.id)
    if isinstance(node, ast.Attribute):
        return node.attr == "major"
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    func_name = func.id if isinstance(func, ast.Name) else None
    if func_name is None and isinstance(func, ast.Attribute):
        func_name = func.attr
    if func_name == "major_of":
        return True
    if func_name == "int" and len(node.args) == 1 and not node.keywords:
        return _is_major_expr(node.args[0])
    return False


def _is_version_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value in _VERSION_LITERALS
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)) and node.elts:
        values: list[object] = []
        for elt in node.elts:
            if not isinstance(elt, ast.Constant) or type(elt.value) is not int:
                return False
            values.append(elt.value)
        return any(value in _VERSION_LITERALS for value in values)
    return False


def _snippet(path: Path, node: ast.AST) -> str:
    text = path.read_text(encoding="utf-8")
    raw = ast.get_source_segment(text, node) or ""
    compact = " ".join(raw.split())
    if len(compact) > 120:
        return compact[:117] + "..."
    return compact or "version branch"


def odoo_version_branches(root: Path) -> list[str]:
    """Find comparisons of a major against literal 15, 16, 17, 18, 19, or 20.

    A major is a name ``major`` or ``*_major``, an attribute ``.major``,
    ``int(...)`` of one of those, or a call to ``major_of``. A collection
    counts only when every element is an int literal and one of them is a
    version. Files inside a compat/ directory are skipped.
    Inputs: directory to scan.
    Outputs: sorted ``path:line: snippet`` hits.
    Side effects: reads Python files. Does not import them.
    """
    hits: list[str] = []
    for path in _python_files(root):
        if _under_compat_directory(path):
            continue
        tree = _parse(path)
        rel = _relative(root, path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            if not any(_is_major_expr(operand) for operand in operands):
                continue
            if not any(_is_version_literal(operand) for operand in operands):
                continue
            hits.append(f"{rel}:{node.lineno}: {_snippet(path, node)}")
    hits.sort()
    return hits


def test_changeset_package_does_not_import_llm_gateway_or_agent_runtime() -> None:
    hits = forbidden_llm_imports(_APP_ROOT / "changeset")
    assert hits == [], "changeset imports an LLM package:\n" + "\n".join(hits)


@pytest.mark.parametrize("source", _PLANTED_CHANGESET_IMPORTS)
def test_planted_changeset_import_of_llm_gateway_or_agent_runtime_is_rejected(
    tmp_path: Path,
    source: str,
) -> None:
    planted = tmp_path / "planted_changeset.py"
    planted.write_text(source, encoding="utf-8")
    hits = forbidden_llm_imports(tmp_path)
    assert hits, "planted changeset import was not rejected"
    assert planted.name in hits[0]


def test_provider_sdks_are_not_imported_outside_llm_gateway_adapters() -> None:
    hits = provider_sdk_imports(_APP_ROOT)
    assert hits == [], "provider SDK import outside adapters:\n" + "\n".join(hits)


@pytest.mark.parametrize(("source", "label"), _PLANTED_PROVIDER_IMPORTS)
def test_planted_provider_sdk_import_outside_adapters_is_rejected(
    tmp_path: Path,
    source: str,
    label: str,
) -> None:
    outside = tmp_path / "vendor.py"
    outside.write_text(source, encoding="utf-8")
    allowed = tmp_path / "llm_gateway" / "adapters" / "vendor.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text(source, encoding="utf-8")
    hits = provider_sdk_imports(tmp_path)
    assert hits == [f"vendor.py:1: {label}"]


def test_planted_odoo_version_branch_outside_compat_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "route.py"
    outside.write_text(
        "def route(major: int) -> str:\n"
        "    if major >= 19:\n"
        "        return 'new'\n"
        "    return 'old'\n",
        encoding="utf-8",
    )
    allowed = tmp_path / "compat" / "route.py"
    allowed.parent.mkdir()
    allowed.write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    noise = tmp_path / "noise.py"
    noise.write_text(
        "def noise(risk: int, raw: bytes) -> bool:\n"
        "    return risk <= 15 or len(raw) > 15 * 1024\n",
        encoding="utf-8",
    )
    hits = odoo_version_branches(tmp_path)
    assert hits == ["route.py:2: major >= 19"]


@pytest.mark.xfail(
    strict=True,
    reason="P0-2-CL2: the app tree has 38 version branches and the constant stays 22",
)
def test_real_app_tree_odoo_version_branch_count_matches_measured_baseline() -> None:
    """Measured baseline: 22 Odoo-version branches outside compat/ in apps/api/app.

    Each hit is a comparison of a major against a literal 15, 16, 17, 18, 19,
    or 20. A new hit changes this count and fails the test. The count is not
    a file allowlist, and the branches are still present in the product tree.
    """
    hits = odoo_version_branches(_APP_ROOT)
    assert len(hits) == _VERSION_BRANCH_BASELINE, (
        f"expected {_VERSION_BRANCH_BASELINE} version branches, found {len(hits)}:\n"
        + "\n".join(hits)
    )
