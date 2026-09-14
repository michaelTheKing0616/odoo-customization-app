"""Structured Failure IR — interface between sandbox/static tools and repair."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

FailureCategory = Literal[
    "install", "xml", "python", "security", "smoke", "scorecard", "static", "unknown"
]
Severity = Literal["critical", "high", "medium", "low"]


def make_failure(
    *,
    category: FailureCategory,
    message: str,
    severity: Severity = "high",
    file: str | None = None,
    line: int | None = None,
    repair_constraints: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    digest = hashlib.sha1(f"{category}:{file}:{message}".encode()).hexdigest()[:10]
    out: dict[str, Any] = {
        "failure_id": f"{category.upper()}-{digest}",
        "category": category,
        "severity": severity,
        "message": (message or "")[:2000],
        "repair_constraints": repair_constraints
        or [
            "max_files:2",
            "do_not_touch_locked",
            "preserve_architecture_plan",
        ],
    }
    if file:
        out["file"] = file
    if line is not None:
        out["line"] = line
    if extra:
        out.update(extra)
    return out


_TRACE_FILE_RE = re.compile(
    r'File "([^"]+/(?:models|views|security|controllers|static|report|wizard|data)[^"]+)", line (\d+)',
)
_PARSE_WHILE_RE = re.compile(
    r"while parsing\s+(\S+?):(\d+)",
    re.I,
)
_FILE_KV_RE = re.compile(r"""['"]file['"]\s*:\s*['"]([^'"]+)['"]""")
_XPATH_EXPR_RE = re.compile(r"""<xpath\s+expr=["']([^"']+)["']""", re.I)
_XPATH_ENTITY_RE = re.compile(
    r"xpath expr=.*?@name=(?:'|&#39;)([^'&]+)(?:'|&#39;)",
    re.I,
)
_XMLID_RE = re.compile(r"""['"]xmlid['"]\s*:\s*['"]([^'"]+)['"]""")
_XPATH_RE = re.compile(r"xpath|XPath|view validation|ParseError", re.I)
_IMPORT_RE = re.compile(r"ModuleNotFoundError|ImportError|depends", re.I)
_JUNK_TRACE_RE = re.compile(
    r"(?i)(xmlrpc\.py$|/rpc/controllers/|/dist-packages/odoo/addons/rpc|"
    r"/odoo/tools/convert|/odoo/addons/base/)"
)


def _module_relative_path(path: str) -> str:
    path = (path or "").replace("\\", "/")
    for marker in ("/mnt/extra-addons/", "/addons/"):
        if marker in path:
            path = path.split(marker, 1)[-1]
            if "/" in path:
                path = "/".join(path.split("/")[1:])
            break
    return path.lstrip("/")


def _is_junk_traceback_path(path: str) -> bool:
    p = (path or "").replace("\\", "/")
    if _JUNK_TRACE_RE.search(p):
        return True
    if "extra-addons" in p:
        return False
    return bool(p.endswith(".py") and "/odoo/" in p)


def _xpath_from_log(text: str) -> str | None:
    m = _XPATH_EXPR_RE.search(text or "")
    if m:
        return m.group(1)
    m = _XPATH_ENTITY_RE.search(text or "")
    if m:
        return f"//field[@name='{m.group(1)}']"
    return None


def failures_from_sandbox_log(
    log_tail: str,
    *,
    ok: bool,
    message: str = "",
) -> list[dict[str, Any]]:
    """Best-effort Failure IR from Odoo install / sandbox log."""
    if ok:
        return []
    text = (log_tail or "") + "\n" + (message or "")
    xpath = _xpath_from_log(text)
    xmlid_m = _XMLID_RE.search(text)
    xmlid = xmlid_m.group(1) if xmlid_m else None
    extra: dict[str, Any] = {}
    if xpath:
        extra["xpath"] = xpath
    if xmlid:
        extra["xmlid"] = xmlid

    hits: list[tuple[str, int]] = []
    seen: set[str] = set()

    def _add_hit(raw_path: str, line: int) -> None:
        if _is_junk_traceback_path(raw_path):
            return
        path = _module_relative_path(raw_path)
        if not path or path in seen:
            return
        seen.add(path)
        hits.append((path, line))

    for m in _TRACE_FILE_RE.finditer(text):
        _add_hit(m.group(1), int(m.group(2)))
    for m in _PARSE_WHILE_RE.finditer(text):
        _add_hit(m.group(1), int(m.group(2)))
    for m in _FILE_KV_RE.finditer(text):
        _add_hit(m.group(1), 0)

    failures: list[dict[str, Any]] = []
    for path, line in hits:
        failures.append(
            make_failure(
                category="python" if path.endswith(".py") else "xml",
                message=message or "traceback in sandbox install",
                severity="critical",
                file=path,
                line=line or None,
                extra=extra or None,
            )
        )
    if not failures:
        cat: FailureCategory = "install"
        if _XPATH_RE.search(text):
            cat = "xml"
        elif _IMPORT_RE.search(text):
            cat = "install"
        failures.append(
            make_failure(
                category=cat,
                message=(message or text[-500:] or "sandbox install failed"),
                severity="critical",
                extra=extra or None,
            )
        )
    return failures


def failures_from_smoke(smoke: dict[str, Any]) -> list[dict[str, Any]]:
    if smoke.get("ok"):
        return []
    return [
        make_failure(
            category="smoke",
            message=str(smoke.get("message") or "option A smoke failed"),
            severity="critical",
            extra={"assertions": smoke.get("assertions") or smoke.get("checks")},
        )
    ]


def failures_from_static(static: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in static.get("findings") or []:
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity") or "medium").lower()
        if sev not in {"critical", "high", "medium", "low"}:
            sev = "medium"
        out.append(
            make_failure(
                category="static",
                message=str(f.get("message") or f.get("rule") or "static finding"),
                severity=sev,  # type: ignore[arg-type]
                file=f.get("file"),
                line=f.get("line"),
                extra={"rule": f.get("rule")},
            )
        )
    return out


def stamp_failures(draft: dict[str, Any], failures: list[dict[str, Any]]) -> None:
    existing = draft.get("_failures") if isinstance(draft.get("_failures"), list) else []
    # merge by failure_id
    by_id = {
        str(f.get("failure_id")): f
        for f in existing
        if isinstance(f, dict) and f.get("failure_id")
    }
    for f in failures:
        if isinstance(f, dict) and f.get("failure_id"):
            by_id[str(f["failure_id"])] = f
    draft["_failures"] = list(by_id.values())


__all__ = [
    "failures_from_sandbox_log",
    "failures_from_smoke",
    "failures_from_static",
    "make_failure",
    "stamp_failures",
]
