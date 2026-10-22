"""BL-08 oracle. Locked: the Worker does not edit this file.

AC1: `git status --short` shows no untracked product module.
AC2: each commit's tests pass on their own.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

# One commit per track (card symbols). Cache, the pnpm store, patch files,
# and tests are not product modules.
_NAMED_TRACKS: tuple[str, ...] = (
    "apps/api/app/changeset",
    "apps/api/app/llm_gateway",
    "apps/api/app/agent_runtime",
    "apps/api/app/bots",
    "apps/api/app/worker_bot",
    "apps/api/app/bridge",
    "apps/api/app/config_as_code",
    "apps/api/app/odoo20",
    "apps/api/app/offline",
    "apps/api/app/skills",
    "apps/api/app/progress",
)

_ORACLE_FILE = "test_bl_08.py"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _git_status_short() -> str:
    """`git status --short` for product trees. Read-only."""
    completed = subprocess.run(
        ["git", "status", "--short", "--", "apps/api/app", "packages"],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _status_parts(line: str) -> tuple[str, str]:
    if len(line) < 4:
        return "", ""
    code = line[:2]
    path = line[3:].strip()
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        path = path[1:-1]
    return code, path.rstrip("/")


def _is_product_module_path(path: str) -> bool:
    """True for API app code and package source. Not tests, cache, or patches."""
    if not path or path.startswith(".cache/") or path.startswith(".pnpm-store/"):
        return False
    name = path.rsplit("/", 1)[-1]
    if name.startswith("0001-") and name.endswith(".patch"):
        return False
    if path.startswith("apps/api/tests/") or "/tests/" in path:
        return False
    if path.startswith("apps/api/app/"):
        return True
    return path.startswith("packages/") and "/src/" in path


def _product_module_id(path: str) -> str:
    if path.startswith("apps/api/app/"):
        head = path[len("apps/api/app/") :].split("/", 1)[0]
        return f"apps/api/app/{head}"
    if path.startswith("packages/"):
        parts = path.split("/")
        if len(parts) >= 2:
            return f"packages/{parts[1]}"
    return path


def _untracked_product_module_ids(status: str) -> list[str]:
    found: set[str] = set()
    for line in status.splitlines():
        code, path = _status_parts(line)
        if code != "??" or not _is_product_module_path(path):
            continue
        found.add(_product_module_id(path))
    return sorted(found)


def _ac1_holds(status: str) -> bool:
    return _untracked_product_module_ids(status) == []


def _dirty_named_tracks(status: str) -> list[str]:
    dirty: set[str] = set()
    for line in status.splitlines():
        _code, path = _status_parts(line)
        if not path:
            continue
        for track in _NAMED_TRACKS:
            if path == track or path.startswith(track + "/"):
                dirty.add(track)
                break
    return sorted(dirty)


def _commits_are_separate(module_to_commit: dict[str, str]) -> bool:
    """Unrelated tracks squashed into one commit are not on their own."""
    return len(set(module_to_commit.values())) == len(module_to_commit)


def _tests_importing(package: str) -> list[str]:
    """Test files that import this product package, relative to apps/api."""
    tests_root = _repo_root() / "apps" / "api" / "tests"
    api_root = _repo_root() / "apps" / "api"
    pattern = re.compile(rf"(?m)^(?:from|import) app\.{re.escape(package)}(?:\.|\s|$)")
    found: list[str] = []
    for path in sorted(tests_root.rglob("*.py")):
        if path.name == _ORACLE_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            found.append(str(path.relative_to(api_root)))
    return found


def _pytest_on_their_own(files: list[str]) -> int:
    api_root = _repo_root() / "apps" / "api"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "-q", "--tb=no"],
        cwd=api_root,
        check=False,
    )
    return completed.returncode


def _require_each_commit_tests_pass() -> None:
    status = _git_status_short()
    untracked = _untracked_product_module_ids(status)
    assert untracked == [], (
        "AC2: untracked product modules have no commit whose tests pass on their own: "
        + ", ".join(untracked)
    )
    dirty = _dirty_named_tracks(status)
    assert dirty == [], (
        "AC2: these tracks are still uncommitted, so their tests cannot pass on their own: "
        + ", ".join(dirty)
    )
    for track in _NAMED_TRACKS:
        package = track.rsplit("/", 1)[-1]
        files = _tests_importing(package)
        assert files, f"AC2: {track} has no tests that import app.{package}"
        exit_code = _pytest_on_their_own(files)
        assert exit_code == 0, (
            f"AC2: app.{package} tests failed on their own (exit {exit_code})"
        )


def test_ac1_positive_git_status_shows_no_untracked_product_module() -> None:
    status = _git_status_short()
    untracked = _untracked_product_module_ids(status)
    assert untracked == [], (
        "AC1: git status --short still shows untracked product modules: "
        + ", ".join(untracked)
    )


def test_ac1_negative_untracked_product_module_keeps_ac_open() -> None:
    worked = "?? apps/api/app/changeset/\n"
    assert _untracked_product_module_ids(worked) == ["apps/api/app/changeset"]
    assert _ac1_holds(worked) is False

    omitted = (
        "?? .cache/ai_ir_trace/x.json\n"
        "?? .pnpm-store/v3/files/00/ab\n"
        "?? 0001-example.patch\n"
        "?? apps/api/tests/test_bl_08.py\n"
    )
    assert _untracked_product_module_ids(omitted) == []
    assert _ac1_holds(omitted) is True

    assert _ac1_holds(_git_status_short()) is True


def test_ac2_positive_each_commits_tests_pass_on_their_own() -> None:
    _require_each_commit_tests_pass()


def test_ac2_negative_squashed_tracks_do_not_pass_on_their_own() -> None:
    squashed = {
        "apps/api/app/changeset": "abc111",
        "apps/api/app/llm_gateway": "abc111",
    }
    assert _commits_are_separate(squashed) is False
    _require_each_commit_tests_pass()
