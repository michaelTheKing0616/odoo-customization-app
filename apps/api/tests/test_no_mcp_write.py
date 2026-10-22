"""Guardrail: no Odoo writes routed through MCP client helpers in product code."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCAN_ROOTS = (_REPO_ROOT / "apps", _REPO_ROOT / "packages")
_SKIP_DIR_NAMES = frozenset(
    {
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
_MCP_WRITE = re.compile(r"mcp.*execute_kw|call_model_method", re.IGNORECASE)
_THIS_FILE = Path(__file__).resolve()
_RPC_CLASSIFY = (_REPO_ROOT / "apps" / "api" / "app" / "rpc_classify.py").resolve()


def _skip_path(path: Path) -> bool:
    if any(part in _SKIP_DIR_NAMES for part in path.parts):
        return True
    try:
        rel = path.relative_to(_REPO_ROOT)
    except ValueError:
        return False
    if rel.parts and rel.parts[0] == "docs":
        return True
    if "docs" in rel.parts:
        return True
    return False


def _line_allowed(path: Path, line: str) -> bool:
    if path.resolve() == _THIS_FILE:
        return True
    stripped = line.strip()
    if path.resolve() == _RPC_CLASSIFY and stripped.startswith("#"):
        return True
    return False


def _collect_mcp_write_hits(
    roots: tuple[Path, ...], repo_root: Path
) -> list[str]:
    hits: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or _skip_path(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not _MCP_WRITE.search(line):
                    continue
                if _line_allowed(path, line):
                    continue
                try:
                    rel = path.relative_to(repo_root)
                except ValueError:
                    rel = path
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    return hits


def test_no_mcp_execute_kw_or_call_model_method_writes() -> None:
    hits = _collect_mcp_write_hits(_SCAN_ROOTS, _REPO_ROOT)
    assert hits == [], "MCP write patterns found:\n" + "\n".join(hits)


def test_mcp_scan_detects_planted_write_in_app_tree(tmp_path: Path) -> None:
    repo_root = tmp_path
    planted = repo_root / "apps" / "api" / "app" / "planted_mcp_write_probe.py"
    planted.parent.mkdir(parents=True)
    planted.write_text(
        'mcp.execute_kw("res.partner", "write", [1], {"name": "x"})\n',
        encoding="utf-8",
    )
    hits = _collect_mcp_write_hits((repo_root / "apps",), repo_root)
    assert hits, "expected planted MCP write pattern to be detected"
    assert "execute_kw" in hits[0]
