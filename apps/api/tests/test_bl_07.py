"""BL-07 acceptance tests for the MCP write scan.

AC1: a populated pytest cache is ignored.
AC2: a planted write under the API app tree is reported.
AC3: that planted write still fails the scan.
AC4: a second scan writes no file and opens no database.
"""

from __future__ import annotations

import importlib.util
import io
import os
import sqlite3
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


def _snapshot_tree(root: Path) -> dict[str, tuple[int, bytes | None]]:
    """Relative path → (mtime_ns, file bytes). Directories map to None bytes."""
    snap: dict[str, tuple[int, bytes | None]] = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if path.is_file():
            snap[rel] = (path.stat().st_mtime_ns, path.read_bytes())
        elif path.is_dir():
            snap[f"{rel}/"] = (path.stat().st_mtime_ns, None)
    return snap


def _opened_name(file: object) -> str:
    if isinstance(file, int):
        return ""
    if isinstance(file, bytes):
        return file.decode("utf-8", "replace")
    try:
        raw = os.fspath(file)  # type: ignore[arg-type]
    except TypeError:
        return str(file)
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return str(raw)


def _is_database_open(file: object) -> bool:
    text = _opened_name(file).lower()
    if text.startswith(("sqlite:", "file:", "postgres:", "postgresql:")):
        return True
    return Path(text).suffix in {".db", ".sqlite", ".sqlite3"}


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


def test_ac4_second_scan_writes_zero_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second scan creates no file, changes no file, and opens no database."""
    repo = tmp_path
    _write(
        repo,
        "apps",
        "api",
        "app",
        "second_run_probe.py",
        text=_planted_execute_line() + "\n",
    )
    roots = (repo / "apps",)
    first = _scan._collect_mcp_write_hits(roots, repo)
    before = _snapshot_tree(repo)
    db_opens: list[str] = []
    write_opens: list[str] = []
    real_open = io.open

    def _guard_open(file: object, mode: str = "r", *args: object, **kwargs: object):
        if _is_database_open(file):
            db_opens.append(_opened_name(file))
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            write_opens.append(_opened_name(file))
        return real_open(file, mode, *args, **kwargs)

    def _record_sqlite(database: object, *_args: object, **_kwargs: object) -> None:
        db_opens.append(str(database))

    monkeypatch.setattr(io, "open", _guard_open)
    monkeypatch.setattr("builtins.open", _guard_open)
    monkeypatch.setattr(sqlite3, "connect", _record_sqlite)
    second = _scan._collect_mcp_write_hits(roots, repo)
    after = _snapshot_tree(repo)
    created = sorted(set(after) - set(before))
    changed = sorted(key for key in before.keys() & after.keys() if before[key] != after[key])
    removed = sorted(set(before) - set(after))
    assert len(first) == 1
    assert second == first
    assert created == []
    assert changed == []
    assert removed == []
    assert write_opens == []
    assert db_opens == []
