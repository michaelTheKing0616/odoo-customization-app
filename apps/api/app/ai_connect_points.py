"""Connect-points proposal + collision detection (AI-8)."""

from __future__ import annotations

import re
from typing import Any

from odoo_client.client import OdooClient, OdooClientError

from app.ai_grain import Grain, HostCandidate, INHERIT_FORM_XML, module_for_model


def propose_connect_points(
    prompt: str,
    *,
    grain: Grain,
    host: HostCandidate,
    gallery_seed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic connect-points plan (reasoning-model step can refine later)."""
    host_model = host.model
    if gallery_seed:
        from app.component_gallery import gallery_seed_to_connect_points

        cp = gallery_seed_to_connect_points(gallery_seed, host_model=host_model)
        cp["grain"] = grain
        cp["prompt_excerpt"] = (prompt or "")[:120]
        return cp

    cp: dict[str, Any] = {
        "grain": grain,
        "host_model": host_model,
        "host_module": host.module or module_for_model(host_model),
        "host_label": host.label,
        "form_inherit_xml_id": INHERIT_FORM_XML.get(host_model),
        "form_xpath": "//sheet",
        "form_position": "inside",
        "menu_mode": "none" if grain == "field_pack" else "sub",
        "sub_menu_name": _infer_sub_menu(prompt, host_model),
        "fk_direction": "component_to_host",
        "prompt_excerpt": (prompt or "")[:120],
    }
    if grain == "feature_slice" and host_model == "sale.order":
        cp["smart_button"] = {
            "label": "Warranties",
            "relation_field": "order_id",
            "target_model": "x_warranty_claim",
        }
    return cp


def _infer_sub_menu(prompt: str, host_model: str) -> str | None:
    text = (prompt or "").lower()
    if "warranty" in text:
        return "Warranty"
    if "inspection" in text or "checklist" in text:
        return "Inspections"
    if "compliance" in text:
        return "Compliance"
    if host_model == "sale.order":
        return "Extensions"
    if host_model == "project.task":
        return "Task extras"
    return None


def detect_field_collisions(
    client: OdooClient | None,
    *,
    host_model: str,
    field_names: list[str],
) -> list[dict[str, str]]:
    """Return collisions with rename suggestions — never silent rename."""
    if client is None or not field_names:
        return []
    existing: set[str] = set()
    try:
        rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", host_model)]],
            {"fields": ["name"], "limit": 500},
        )
        existing = {str(r.get("name") or "") for r in rows}
    except OdooClientError:
        return []

    out: list[dict[str, str]] = []
    for name in field_names:
        if name in existing:
            slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
            out.append(
                {
                    "field": name,
                    "collision": "exists_on_host",
                    "suggested_rename": f"x_cmp_{slug[:40]}",
                    "message": f"Field {name!r} already exists on {host_model}",
                }
            )
    return out


def unique_inherit_view_name(host_model: str, suffix: str) -> str:
    slug = host_model.replace(".", "_")
    safe = re.sub(r"[^a-z0-9_]+", "_", suffix.lower()).strip("_")[:32]
    return f"{host_model}.custom.ai8_{slug}_{safe}"
