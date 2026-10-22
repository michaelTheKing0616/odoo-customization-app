"""BL-07 acceptance tests for the MCP write scan.

AC1: a populated pytest cache is ignored.
AC2: a planted write under the API app tree is reported.
AC3: that planted write still fails the scan.
AC4 is not covered here: this card does not run an Odoo plan.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

_SCAN_PATH = Path(__file__).with_name("test_no_mcp_write.py")
_spec = importlib.util.spec_from_file_location("bl07_no_mcp_write", _SCAN_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Could not load the MCP write scan test module")
_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_scan)

# Split so this file's own source does not match the scan pattern.
_MCP = "mc" + "p"
_EXEC = "execute_" + "kw"
_CALL = "call_" + "model_" + "method"

_CACHE_DIR_NAMES = (
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
)


def _planted_execute_line() -> str:
    return _MCP + "." + _EXEC + '("res.partner", "write", [1], {"name": "x"})'


def _cache_nodeid_line() -> str:
    return (
        "tests/test_no_"
        + _MCP
        + "_write.py::test_no_"
        + _MCP
        + "_"
        + _EXEC
        + "_or_"
        + _CALL
        + "_writes"
    )


def _write(repo: Path, *parts: str, text: str) -> Path:
    path = repo.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_ac1_positive_pytest_cache_text_is_not_a_hit(tmp_path: Path) -> None:
    """Cache directories that contain the guard test's name produce no hits."""
    repo = tmp_path
    noisy = _cache_nodeid_line() + "\n" + _planted_execute_line() + "\n"
    cache = _write(
        repo,
        "apps",
        "api",
        ".pytest_cache",
        "v",
        "cache",
        "nodeids",
        text=noisy,
    )
    assert _EXEC in cache.read_text(encoding="utf-8")
    assert _scan._skip_path(cache) is True
    for name in _CACHE_DIR_NAMES:
        cached = _write(repo, "apps", "api", name, "cached.txt", text=noisy)
        assert _scan._skip_path(cached) is True
    docs = _scan._REPO_ROOT / "docs" / "build-plan" / "FACTS.md"
    assert _scan._skip_path(docs) is True
    nested_docs = _scan._REPO_ROOT / "apps" / "api" / "docs" / "note.py"
    assert _scan._skip_path(nested_docs) is True
    real_cache = _scan._REPO_ROOT / "apps" / "api" / ".pytest_cache" / "v" / "cache" / "nodeids"
    assert _scan._skip_path(real_cache) is True
    hits = _scan._collect_mcp_write_hits((repo / "apps",), repo)
    assert hits == []


def test_ac1_negative_same_text_under_app_is_a_hit(tmp_path: Path) -> None:
    """The same cache text under apps/api/app is still a hit."""
    app_py = _scan._REPO_ROOT / "apps" / "api" / "app" / "rpc_classify.py"
    assert _scan._skip_path(app_py) is False
    repo = tmp_path
    planted = _write(
        repo,
        "apps",
        "api",
        "app",
        "cache_text_probe.py",
        text=_cache_nodeid_line() + "\n",
    )
    assert _scan._skip_path(planted) is False
    hits = _scan._collect_mcp_write_hits((repo / "apps",), repo)
    assert len(hits) == 1
    assert _EXEC in hits[0]
    assert _CALL in hits[0]


def test_ac2_positive_planted_write_under_app_is_a_hit(tmp_path: Path) -> None:
    """Worked example: a temp probe under apps/api/app is reported."""
    repo = tmp_path
    planted = _write(
        repo,
        "apps",
        "api",
        "app",
        "planted_mcp_write_probe.py",
        text=_planted_execute_line() + "\n",
    )
    assert _scan._skip_path(planted) is False
    hits = _scan._collect_mcp_write_hits((repo / "apps",), repo)
    assert len(hits) == 1
    assert "planted_mcp_write_probe.py" in hits[0]
    assert _EXEC in hits[0]
    assert "res.partner" in hits[0]
    assert '"write"' in hits[0]


def test_ac2_negative_same_planted_line_in_pytest_cache_is_not_a_hit(tmp_path: Path) -> None:
    """The planted line inside .pytest_cache does not fail the scan."""
    repo = tmp_path
    cached = _write(
        repo,
        "apps",
        "api",
        ".pytest_cache",
        "v",
        "cache",
        "nodeids",
        text=_planted_execute_line() + "\n",
    )
    assert _scan._skip_path(cached) is True
    hits = _scan._collect_mcp_write_hits((repo / "apps",), repo)
    assert hits == []


def test_ac3_positive_guard_file_and_classify_comment_are_allowed() -> None:
    """Only this scan file, and comment lines on the classify module, are allowed."""
    line = _planted_execute_line()
    assert _scan._line_allowed(_scan._THIS_FILE, line) is True
    assert _scan._line_allowed(_scan._RPC_CLASSIFY, "# " + line) is True
    assert _scan._line_allowed(_scan._RPC_CLASSIFY, line) is False
    other = _scan._REPO_ROOT / "apps" / "api" / "app" / "other.py"
    assert _scan._line_allowed(other, line) is False
    assert _scan._line_allowed(other, "# " + line) is False
    assert _scan._line_allowed(_scan._THIS_FILE, _CALL + "()") is True


def test_ac3_negative_planted_write_fails_the_scan(tmp_path: Path) -> None:
    """A planted write under apps/api/app still fails the scan."""
    repo = tmp_path
    _write(
        repo,
        "apps",
        "api",
        "app",
        "planted_mcp_write_probe.py",
        text=_planted_execute_line() + "\n" + _CALL + "()\n",
    )
    hits = _scan._collect_mcp_write_hits((repo / "apps",), repo)
    assert hits != []
    joined = "\n".join(hits)
    assert _EXEC in joined
    assert _CALL in joined
    assert "apps/api/app/planted_mcp_write_probe.py" in joined
