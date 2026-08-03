"""Inject Apps Store assets into export zips (TIER-3)."""

from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from typing import Any

from module_generator import ModuleSpec

from app.deploy_odoo_sh import inject_file_into_zip
from app.store_readiness import (
    PLACEHOLDER_ICON_PNG,
    STORE_REVIEW_DISCLAIMER,
    check_zip_store_readiness,
    parse_manifest_py,
)


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def listing_index_html(spec: ModuleSpec, *, description: str) -> str:
    name = _html_escape(spec.display_name or spec.technical_name)
    summary = _html_escape(getattr(spec, "summary", None) or spec.display_name or "")
    body = _html_escape(description)
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{name}</title>
</head>
<body>
  <section class="oe_container">
    <div class="oe_row oe_spaced">
      <h2 class="oe_slogan">{name}</h2>
      <h3 class="oe_slogan">{summary}</h3>
    </div>
    <div class="oe_row oe_spaced">
      <p>{body}</p>
      <p><em>{STORE_REVIEW_DISCLAIMER}</em></p>
    </div>
  </section>
</body>
</html>
"""


def _default_description(spec: ModuleSpec) -> str:
    models = len(spec.models)
    views = len(spec.views)
    reports = len(getattr(spec, "reports", []) or [])
    parts = [
        f"{spec.display_name} is a custom Odoo module exported from the Odoo Custom platform.",
        f"It includes {models} custom model(s), {views} view definition(s)",
    ]
    if reports:
        parts.append(f", and {reports} report(s)")
    parts.append(
        ". Install on a matching Odoo major, validate in sandbox, and review access rules "
        "before production use."
    )
    return "".join(parts)


def _patch_manifest_content(content: str, updates: dict[str, Any]) -> str:
    manifest = parse_manifest_py(content)
    manifest.update(updates)
    lines = ["# -*- coding: utf-8 -*-", "{"]
    for key, value in manifest.items():
        if isinstance(value, bool):
            rendered = "True" if value else "False"
        elif isinstance(value, str):
            rendered = repr(value)
        elif isinstance(value, list):
            inner = ", ".join(repr(v) for v in value)
            rendered = f"[{inner}]"
        else:
            rendered = repr(value)
        lines.append(f'    "{key}": {rendered},')
    lines.append("}")
    return "\n".join(lines) + "\n"


def apply_store_packaging(
    zip_bytes: bytes,
    spec: ModuleSpec,
    *,
    major: int | None,
    author: str | None = None,
    website: str | None = None,
) -> tuple[bytes, bool, dict[str, Any]]:
    """Enhance zip with store assets; return (zip, icon_is_placeholder, report_dict)."""
    root = spec.technical_name
    description = _default_description(spec)
    summary = spec.display_name or root.replace("_", " ").title()
    manifest_updates = {
        "name": spec.display_name,
        "summary": summary,
        "description": description,
        "category": "Customization",
        "author": author or spec.author or "Odoo Custom",
        "website": website or "https://www.odoo.com",
        "license": "LGPL-3",
    }
    if major is not None and not re.match(r"^\d+\.0\.", spec.version or ""):
        manifest_updates["version"] = f"{major}.0.1.0.0"

    manifest_path = f"{root}/__manifest__.py"
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zin:
        if manifest_path in zin.namelist():
            raw = zin.read(manifest_path).decode("utf-8")
            patched = _patch_manifest_content(raw, manifest_updates)
            zip_bytes = inject_file_into_zip(zip_bytes, manifest_path, patched)

    icon_path = f"{root}/static/description/icon.png"
    zip_bytes = inject_file_into_zip(zip_bytes, icon_path, PLACEHOLDER_ICON_PNG)
    index_path = f"{root}/static/description/index.html"
    zip_bytes = inject_file_into_zip(zip_bytes, index_path, listing_index_html(spec, description=description))

    report_path = f"{root}/STORE_READINESS.json"
    readiness = check_zip_store_readiness(
        zip_bytes,
        technical_name=root,
        major=major,
        icon_is_placeholder=True,
    )
    report_payload = {
        "disclaimer": readiness.disclaimer,
        "ok": readiness.ok,
        "fail_count": readiness.fail_count,
        "warn_count": readiness.warn_count,
        "message": readiness.message,
        "items": [
            {"key": i.key, "label": i.label, "status": i.status, "message": i.message}
            for i in readiness.items
        ],
    }
    zip_bytes = inject_file_into_zip(
        zip_bytes,
        report_path,
        json.dumps(report_payload, indent=2),
    )
    return zip_bytes, True, report_payload
