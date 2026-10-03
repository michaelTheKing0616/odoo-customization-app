"""Guardrail: no direct xmlrpc.client / ServerProxy transport outside the legacy adapter and sandbox."""

from __future__ import annotations

import re
from pathlib import Path

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
_DIRECT_XMLRPC = re.compile(r"import xmlrpc|xmlrpc\.client|ServerProxy")
_THIS_FILE = Path(__file__).resolve()
_LEGACY_ADAPTER_ROOT = (_REPO_ROOT / "packages" / "odoo-client").resolve()
_SANDBOX_MODULE = (_REPO_ROOT / "apps" / "api" / "app" / "sandbox.py").resolve()


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
    if "tests" in rel.parts:
        return True
    return False


def _path_allowed(path: Path) -> bool:
    resolved = path.resolve()
    if resolved == _THIS_FILE:
        return True
    if resolved == _SANDBOX_MODULE:
        return True
    try:
        resolved.relative_to(_LEGACY_ADAPTER_ROOT)
    except ValueError:
        return False
    else:
        return True


def _collect_direct_xmlrpc_hits(
    roots: tuple[Path, ...], repo_root: Path
) -> list[str]:
    hits: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or _skip_path(path):
                continue
            if _path_allowed(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not _DIRECT_XMLRPC.search(line):
                    continue
                try:
                    rel = path.relative_to(repo_root)
                except ValueError:
                    rel = path
                hits.append(f"{rel}:{lineno}: {line.strip()}")
    return hits


def test_no_direct_xmlrpc_outside_legacy_adapter_and_sandbox() -> None:
    hits = _collect_direct_xmlrpc_hits(_SCAN_ROOTS, _REPO_ROOT)
    assert hits == [], "Direct XML-RPC transport patterns found:\n" + "\n".join(hits)


def test_direct_xmlrpc_scan_detects_planted_server_proxy_in_app_tree(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    planted = repo_root / "apps" / "api" / "app" / "planted_xmlrpc_probe.py"
    planted.parent.mkdir(parents=True)
    planted.write_text(
        'proxy = xmlrpc.client.ServerProxy("http://127.0.0.1:8069/xmlrpc/2/common")\n',
        encoding="utf-8",
    )
    hits = _collect_direct_xmlrpc_hits((repo_root / "apps",), repo_root)
    assert hits, "expected planted ServerProxy pattern to be detected"
    assert "ServerProxy" in hits[0]
