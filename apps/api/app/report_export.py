"""Helpers to map live ir.actions.report + QWeb views into ReportSpec."""

from __future__ import annotations

import re
from typing import Any

from module_generator import ReportSpec


def should_export_report(*, model: str, report_name: str | None) -> bool:
    """Prefer custom / x_* reports; skip stock PDF actions on extended models."""
    if model.startswith("x_"):
        return True
    key = (report_name or "").lower()
    if key.startswith("custom."):
        return True
    if ".studio." in key or key.startswith("custom_"):
        return True
    return False


def template_xml_id_from_key(report_key: str, *, report_id: int) -> str:
    """Last segment of report key → safe xml id."""
    raw = (report_key or "").strip()
    segment = raw.rsplit(".", 1)[-1] if raw else f"report_{report_id}"
    slug = re.sub(r"[^a-z0-9_]+", "_", segment.lower()).strip("_")
    if not slug:
        slug = f"report_{report_id}"
    if slug[0].isdigit():
        slug = f"r_{slug}"
    return slug[:60]


def qweb_arch_to_body_html(arch: str) -> str:
    """Strip live QWeb shell into inner page HTML for reports.xml.j2 (uses ``o``)."""
    text = (arch or "").strip()
    if not text:
        return "<p t-field=\"o.display_name\"/>"
    text = text.replace("doc.", "o.")
    # Prefer content inside <div class="page">…</div>
    page = re.search(
        r"<div[^>]*\bclass=['\"][^'\"]*\bpage\b[^'\"]*['\"][^>]*>(.*?)</div>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if page:
        inner = page.group(1).strip()
        if inner:
            return inner
    # Else content of docs foreach
    foreach = re.search(
        r"<t[^>]*t-foreach=['\"]docs['\"][^>]*>(.*?)</t>\s*</t>\s*</t>\s*$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if foreach:
        inner = foreach.group(1).strip()
        # Drop nested page wrapper if present
        page2 = re.search(
            r"<div[^>]*\bclass=['\"][^'\"]*\bpage\b[^'\"]*['\"][^>]*>(.*?)</div>",
            inner,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if page2 and page2.group(1).strip():
            return page2.group(1).strip()
        if inner:
            return inner
    # Last resort: strip outer <t t-name>…</t>
    stripped = re.sub(
        r"^<t[^>]*t-name=['\"][^'\"]+['\"][^>]*>\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    stripped = re.sub(r"</t>\s*$", "", stripped, count=1, flags=re.IGNORECASE)
    stripped = stripped.strip()
    return stripped or "<p t-field=\"o.display_name\"/>"


def report_row_to_spec(row: dict[str, Any], *, arch: str) -> ReportSpec:
    report_id = int(row["id"])
    model = str(row.get("model") or "")
    report_key = str(row.get("report_name") or f"custom.report_{report_id}")
    template_id = template_xml_id_from_key(report_key, report_id=report_id)
    name = str(row.get("name") or template_id)
    print_name = row.get("print_report_name") or None
    if print_name is False:
        print_name = None
    return ReportSpec(
        name=name,
        model=model,
        report_name=report_key,
        template_xml_id=template_id,
        body_html=qweb_arch_to_body_html(arch),
        print_report_name=str(print_name) if print_name else None,
        technical_name=f"rpt_{report_id}_{template_id}"[:50],
    )


def find_qweb_arch(client: Any, report_key: str) -> str | None:
    rows = client.execute_kw(
        "ir.ui.view",
        "search_read",
        [[("key", "=", report_key), ("type", "=", "qweb")]],
        {"fields": ["arch", "key"], "limit": 1},
    )
    if not rows:
        return None
    arch = rows[0].get("arch")
    return arch if isinstance(arch, str) else None
