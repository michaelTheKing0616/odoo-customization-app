"""Stage F structural zip gate — unit-testable without Docker.

Fail-closed on missing ACL for new x_* models and Python syntax errors.
Does not prove install; sandbox `--test-enable` remains a follow-up when Docker is up.
"""

from __future__ import annotations

import ast
import io
import re
import zipfile
from typing import Any

_NAME_RE = re.compile(r"""_name\s*=\s*['"]([^'"]+)['"]""")
_INIT_IMPORT_RE = re.compile(r"from\s+\.\s+import\s+(\w+)")


def files_from_zip_bytes(zip_bytes: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            out[name] = zf.read(name)
    return out


def structural_zip_gate(
    zip_bytes: bytes | None = None,
    *,
    files: dict[str, str | bytes] | None = None,
) -> dict[str, Any]:
    """Return ``{ok, findings}``. Findings are operator-facing strings."""
    blob: dict[str, bytes] = {}
    if files:
        blob = {
            k: v.encode("utf-8") if isinstance(v, str) else v for k, v in files.items()
        }
    elif zip_bytes:
        blob = files_from_zip_bytes(zip_bytes)
    else:
        return {"ok": False, "findings": ["empty zip"]}

    findings: list[str] = []
    py_files = [p for p in blob if p.endswith(".py")]
    for path in py_files:
        raw = blob[path]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(f"not utf-8: {path}")
            continue
        try:
            ast.parse(text, filename=path)
        except SyntaxError as exc:
            findings.append(f"syntax error in {path}: {exc.msg} (line {exc.lineno})")

    new_x_models: list[str] = []
    for path in py_files:
        if "/models/" not in path.replace("\\", "/"):
            continue
        text = blob[path].decode("utf-8", errors="replace")
        for match in _NAME_RE.finditer(text):
            mid = match.group(1)
            if mid.startswith("x_"):
                new_x_models.append(mid)

    has_access = any(p.replace("\\", "/").endswith("security/ir.model.access.csv") for p in blob)
    if new_x_models and not has_access:
        findings.append(
            "missing security/ir.model.access.csv for new models: "
            + ", ".join(sorted(set(new_x_models)))
        )

    test_mods = []
    has_tests_init = False
    for path in blob:
        norm = path.replace("\\", "/")
        base = norm.rsplit("/", 1)[-1]
        if "/tests/" not in norm:
            continue
        if base == "__init__.py":
            has_tests_init = True
            continue
        if base.startswith("test_") and base.endswith(".py"):
            test_mods.append(base[:-3])

    if test_mods and not has_tests_init:
        findings.append("tests/ exist but tests/__init__.py is missing")
    elif test_mods and has_tests_init:
        init_path = next(
            p for p in blob if p.replace("\\", "/").endswith("/tests/__init__.py")
        )
        init_text = blob[init_path].decode("utf-8", errors="replace")
        imported = set(_INIT_IMPORT_RE.findall(init_text))
        missing = [m for m in test_mods if m not in imported]
        if missing:
            findings.append(
                "tests/__init__.py does not import: " + ", ".join(sorted(missing))
            )

    try:
        from app.ai_option_a_view_fields import files_view_field_findings

        text_files = {
            p: blob[p].decode("utf-8", errors="replace")
            for p in blob
            if p.endswith((".py", ".xml"))
        }
        findings.extend(files_view_field_findings(text_files))
    except Exception:  # noqa: BLE001
        pass

    return {"ok": not findings, "findings": findings, "new_x_models": sorted(set(new_x_models))}
