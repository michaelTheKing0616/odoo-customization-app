"""Browser-testing sub-agent for Stage F.

Walks a generated Odoo tour (open each ``ir.ui.view``) against the zip
without Docker. Catches view-arch defects that Python syntax, ACL, and
``view_field_undefined`` do not: unparseable arch XML, nameless field
widgets, empty inherit xpath. QWeb templates and security/data records
are skipped (ERRORS.md implied_ids).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_DEFECT_UNPARSEABLE = "view_arch_unparseable"
_DEFECT_FIELD_NAME = "view_arch_field_missing_name"
_DEFECT_XPATH_EMPTY = "view_arch_xpath_empty"

_WEB_AGENT = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "web"
    / "src"
    / "testing"
    / "browserAgent"
    / "inspect.mjs"
)


def run_browser_agent(files: dict[str, str]) -> dict[str, Any]:
    """Inspect module files and invoke the web agent when Node is present.

    Stage F always uses this report. The web CLI is invoked from here; it
    is not a second compiler.
    """
    report = inspect_module_files(files)
    web = _invoke_web_agent(files)
    report["invoked_web_agent"] = web is not None
    if web is not None:
        report["web_agent_ok"] = bool(web.get("ok"))
        report["web_agent_caught"] = list(web.get("caught") or [])
        report["web_agent_views_checked"] = int(web.get("views_checked") or 0)
    return report


def inspect_module_files(files: dict[str, str]) -> dict[str, Any]:
    """Return a tour report for ``ir.ui.view`` arches in ``files``."""
    module = _module_name(files)
    findings: list[str] = []
    caught: list[dict[str, str]] = []
    tour: list[dict[str, str]] = []
    views_checked = 0

    for path in sorted(files):
        norm = path.replace("\\", "/")
        if not norm.endswith(".xml"):
            continue
        if "/security/" in f"/{norm}":
            continue
        content = files[path] or ""
        if _is_qweb_only(content):
            continue
        if "ir.ui.view" not in content:
            continue

        parsed = _parse_xml(content)
        if parsed is None:
            views_checked += 1
            view_id = _hint_view_id(content) or norm
            _record(
                findings,
                caught,
                module=module,
                view=view_id,
                defect=_DEFECT_UNPARSEABLE,
                detail="ir.ui.view XML is not well-formed",
                file=norm,
            )
            tour.append(
                {
                    "action": "open_view",
                    "view_id": view_id,
                    "model": "",
                    "file": norm,
                    "result": "fail",
                }
            )
            continue

        for rec in parsed.iter():
            if _local(rec.tag) != "record":
                continue
            if (rec.get("model") or "").strip() != "ir.ui.view":
                continue
            view_id = (rec.get("id") or "").strip() or norm
            model = _record_model_field(rec)
            views_checked += 1
            arch_el = _arch_element(rec)
            step = {
                "action": "open_view",
                "view_id": view_id,
                "model": model,
                "file": norm,
                "result": "ok",
            }
            if arch_el is None or (
                not list(arch_el) and not (arch_el.text or "").strip()
            ):
                _record(
                    findings,
                    caught,
                    module=module,
                    view=view_id,
                    defect=_DEFECT_UNPARSEABLE,
                    detail="ir.ui.view arch is empty",
                    file=norm,
                )
                step["result"] = "fail"
                tour.append(step)
                continue
            for el in arch_el.iter():
                if el is arch_el:
                    continue
                tag = _local(el.tag).lower()
                if tag == "field" and not (el.get("name") or "").strip():
                    _record(
                        findings,
                        caught,
                        module=module,
                        view=view_id,
                        defect=_DEFECT_FIELD_NAME,
                        detail="OWL field widget is missing name",
                        file=norm,
                    )
                    step["result"] = "fail"
                if tag == "xpath" and not (el.get("expr") or "").strip():
                    _record(
                        findings,
                        caught,
                        module=module,
                        view=view_id,
                        defect=_DEFECT_XPATH_EMPTY,
                        detail="extension xpath expression is empty",
                        file=norm,
                    )
                    step["result"] = "fail"
            tour.append(step)

    return {
        "ran": True,
        "ok": not findings,
        "module": module,
        "views_checked": views_checked,
        "tour": tour,
        "findings": findings,
        "caught": caught,
        "false_positive_rate": _rate(len(findings), views_checked),
        "invoked_web_agent": False,
    }


def _invoke_web_agent(files: dict[str, str]) -> dict[str, Any] | None:
    script = _WEB_AGENT
    node = shutil.which("node")
    if node is None or not script.is_file():
        return None
    try:
        proc = subprocess.run(
            [node, str(script)],
            input=json.dumps({"files": files}),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _module_name(files: dict[str, str]) -> str:
    for path in files:
        norm = path.replace("\\", "/")
        if norm.endswith("__manifest__.py"):
            parts = [p for p in norm.split("/") if p]
            if len(parts) >= 2:
                return parts[-2]
            return parts[0] if parts else "unknown"
    for path in files:
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if parts:
            return parts[0]
    return "unknown"


def _is_qweb_only(content: str) -> bool:
    if "ir.ui.view" in content:
        return False
    return "<templates" in content or "t-name=" in content


def _parse_xml(content: str) -> ET.Element | None:
    body = (content or "").lstrip()
    if not body:
        return None
    try:
        return ET.fromstring(body)
    except ET.ParseError:
        try:
            return ET.fromstring(f"<data>{body}</data>")
        except ET.ParseError:
            return None


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _record_model_field(rec: ET.Element) -> str:
    for child in rec:
        if _local(child.tag) == "field" and child.get("name") == "model":
            return (child.text or "").strip()
    return ""


def _arch_element(rec: ET.Element) -> ET.Element | None:
    for child in rec:
        if _local(child.tag) == "field" and child.get("name") == "arch":
            return child
    return None


def _hint_view_id(content: str) -> str:
    marker = 'id="'
    start = content.find(marker)
    if start == -1:
        start = content.find("id='")
        if start == -1:
            return ""
        marker = "id='"
    start += len(marker)
    end = content.find(marker[-1], start)
    if end == -1:
        return ""
    return content[start:end]


def _record(
    findings: list[str],
    caught: list[dict[str, str]],
    *,
    module: str,
    view: str,
    defect: str,
    detail: str,
    file: str,
) -> None:
    findings.append(
        f"browser_agent: module={module} view={view} defect={defect}: {detail} [{file}]"
    )
    row = {"module": module, "view": view, "defect": defect, "file": file}
    if row not in caught:
        caught.append(row)


def _rate(finding_count: int, views_checked: int) -> float:
    if views_checked <= 0:
        return 0.0
    return finding_count / views_checked


__all__ = ["inspect_module_files", "run_browser_agent"]
