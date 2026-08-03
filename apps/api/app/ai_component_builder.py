"""Build component-grain ModuleSpec drafts (AI-8)."""

from __future__ import annotations

import re
from typing import Any

from odoo_client.client import OdooClient

from app.ai_connect_points import detect_field_collisions, propose_connect_points
from app.ai_grain import Grain, HostCandidate, classify_grain, discover_hosts, grain_display, module_for_model, module_for_model
from app.component_gallery import get_gallery_seed, list_gallery


def _fields_from_prompt(prompt: str) -> list[dict[str, Any]]:
    text = (prompt or "").lower()
    fields: list[dict[str, Any]] = []
    if "warranty" in text:
        fields.extend(
            [
                {"name": "x_warranty_start", "ttype": "date", "string": "Warranty Start"},
                {"name": "x_warranty_end", "ttype": "date", "string": "Warranty End"},
                {
                    "name": "x_warranty_status",
                    "ttype": "selection",
                    "string": "Warranty Status",
                    "selection": "[('active','Active'),('expired','Expired')]",
                },
            ]
        )
    if "inspection" in text or "checklist" in text:
        fields.extend(
            [
                {
                    "name": "x_inspection_state",
                    "ttype": "selection",
                    "string": "Inspection",
                    "selection": "[('todo','To Do'),('pass','Pass'),('fail','Fail')]",
                },
                {"name": "x_inspection_due", "ttype": "date", "string": "Inspection Due"},
            ]
        )
    if "compliance" in text or "expiry" in text:
        fields.extend(
            [
                {
                    "name": "x_compliance_status",
                    "ttype": "selection",
                    "string": "Compliance Status",
                    "selection": "[('ok','OK'),('review','Review')]",
                },
                {"name": "x_compliance_expiry", "ttype": "date", "string": "Expiry Date"},
            ]
        )
    if not fields:
        fields.append({"name": "x_extension_note", "ttype": "text", "string": "Extension note"})
    return fields


def _match_gallery(prompt: str) -> dict[str, Any] | None:
    text = (prompt or "").lower()
    if "warranty" in text:
        return get_gallery_seed("warranty_tracker")
    if "inspection" in text or "checklist" in text:
        return get_gallery_seed("inspection_checklist")
    if "compliance" in text:
        return get_gallery_seed("compliance_status")
    if "document" in text and "expir" in text:
        return get_gallery_seed("document_expiry_pack")
    return None


def _slug_from_host(host_model: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", host_model.replace(".", "_"))


def build_component_draft(
    *,
    prompt: str,
    grain: Grain,
    host: HostCandidate,
    connect_points: dict[str, Any],
    fields: list[dict[str, Any]],
    gallery_seed: dict[str, Any] | None = None,
    collisions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    host_model = host.model
    mod = connect_points.get("host_module") or host.module
    slug = _slug_from_host(host_model)
    technical = f"ext_{slug}"

    models: list[dict[str, Any]] = [
        {
            "model": host_model,
            "mode": "inherit",
            "inherit": host_model,
            "description": f"Extend {host.label}",
            "fields": fields,
        }
    ]

    if gallery_seed and gallery_seed.get("companion_model"):
        cm = gallery_seed["companion_model"]
        companion_fields = list(cm.get("fields") or [])
        host_o2m = gallery_seed.get("host_o2m")
        if host_o2m:
            models[0]["fields"].append(host_o2m)
        models.append(
            {
                "model": cm["model"],
                "mode": "new",
                "description": cm.get("description") or cm["model"],
                "fields": companion_fields,
            }
        )

    inherit_xml = connect_points.get("form_inherit_xml_id")
    views: list[dict[str, Any]] = []
    if inherit_xml:
        field_xml = "\n".join(
            f'                <field name="{f["name"]}"/>'
            for f in fields
            if isinstance(f, dict) and f.get("name")
        )
        views.append(
            {
                "name": f"{host_model}.form.extension",
                "model": host_model,
                "type": "form",
                "mode": "extension",
                "inherit_xml_id": inherit_xml,
                "arch": (
                    "<data>\n"
                    f'  <xpath expr="{connect_points.get("form_xpath", "//sheet")}" '
                    f'position="{connect_points.get("form_position", "inside")}">\n'
                    f"{field_xml}\n"
                    f"  </xpath>\n"
                    f"</data>"
                ),
            }
        )

    menus: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    if grain == "feature_slice" and connect_points.get("menu_mode") == "sub":
        sub = connect_points.get("sub_menu_name") or "Extension"
        action_xml = f"action_{slug}_ext"
        menus.append(
            {
                "name": sub,
                "action_xml_id": action_xml,
                "parent_xml_id": f"{mod}.menu_{mod}_root" if mod != "base" else None,
                "sequence": 90,
            }
        )
        if gallery_seed and gallery_seed.get("companion_model"):
            cm = gallery_seed["companion_model"]
            actions.append(
                {
                    "name": sub,
                    "model": cm["model"],
                    "view_mode": "list,form",
                    "technical_name": action_xml,
                }
            )

    depends = [mod] if mod and mod != "base" else ["base"]

    draft: dict[str, Any] = {
        "technical_name": technical,
        "display_name": connect_points.get("sub_menu_name") or f"{host.label} extension",
        "depends": depends,
        "grain": grain,
        "connect_points": connect_points,
        "host_candidates": [{"model": host.model, "label": host.label, "score": host.score}],
        "models": models,
        "views": views,
        "menus": menus,
        "actions": actions,
        "automations": list((gallery_seed or {}).get("automations") or []),
        "smart_buttons": [],
        "_ambition": "thin",
        "_component": True,
    }

    warnings: list[str] = []
    if collisions:
        for c in collisions:
            warnings.append(
                f"Field collision on {host_model}: {c.get('message')} — "
                f"suggest rename to {c.get('suggested_rename')}"
            )
        draft["field_collisions"] = collisions

    if gallery_seed:
        draft["gallery_id"] = gallery_seed["id"]
        draft["review_notes"] = [
            f"Component from gallery seed {gallery_seed['id']!r} — inherit-only on {host_model}."
        ]

    return draft, warnings


def draft_component_from_prompt(
    prompt: str,
    *,
    grain: Grain | None = None,
    available_models: list[str] | None = None,
    connect_points_override: dict[str, Any] | None = None,
    gallery_id: str | None = None,
    host_model_override: str | None = None,
    client: OdooClient | None = None,
) -> tuple[dict[str, Any], list[HostCandidate], list[str]]:
    """Build a component draft without running the full-app pipeline."""
    resolved_grain = grain or classify_grain(prompt)
    hosts = discover_hosts(prompt, available_models=available_models)
    if host_model_override:
        hosts = [
            HostCandidate(
                model=host_model_override,
                label=host_model_override,
                score=1.0,
                module=module_for_model(host_model_override),
                reason="operator override",
            ),
            *hosts,
        ]

    gallery_seed = get_gallery_seed(gallery_id) if gallery_id else _match_gallery(prompt)
    if gallery_seed and gallery_seed.get("host_slot") not in ("any", None):
        slot = str(gallery_seed["host_slot"])
        hosts = [
            HostCandidate(
                model=slot,
                label=slot,
                score=1.0,
                module=module_for_model(slot),
                reason="gallery host slot",
            ),
            *hosts,
        ]

    if not hosts:
        return (
            {
                "technical_name": "component_needs_host",
                "display_name": "Select a host model",
                "depends": ["base"],
                "models": [],
                "grain": resolved_grain,
                "connect_points": None,
                "host_candidates": [],
                "_needs_host_selection": True,
            },
            [],
            ["No host model candidates — connect to Odoo or specify host in prompt."],
        )

    host = hosts[0]
    if gallery_seed:
        fields = list(gallery_seed.get("fields") or [])
    else:
        fields = _fields_from_prompt(prompt)

    cp = connect_points_override or propose_connect_points(
        prompt, grain=resolved_grain, host=host, gallery_seed=gallery_seed
    )
    field_names = [str(f["name"]) for f in fields if isinstance(f, dict) and f.get("name")]
    collisions = detect_field_collisions(client, host_model=host.model, field_names=field_names)

    draft, warnings = build_component_draft(
        prompt=prompt,
        grain=resolved_grain,
        host=host,
        connect_points=cp,
        fields=fields,
        gallery_seed=gallery_seed,
        collisions=collisions,
    )
    draft["grain_label"] = grain_display(resolved_grain, host)
    draft["host_candidates"] = [
        {"model": h.model, "label": h.label, "score": h.score, "reason": h.reason}
        for h in hosts
    ]
    return draft, hosts, warnings


__all__ = ["draft_component_from_prompt", "build_component_draft", "list_gallery"]
