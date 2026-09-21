"""Build component-grain ModuleSpec drafts (AI-8)."""

from __future__ import annotations

import re
from typing import Any

from odoo_client.client import OdooClient

from app.ai_connect_points import detect_field_collisions, propose_connect_points
from app.ai_grain import (
    HOST_LABELS,
    Grain,
    HostCandidate,
    classify_grain,
    discover_hosts,
    grain_display,
    module_for_model,
    named_host_from_prompt,
    parent_menu_xml_id_for_module,
)
from app.ai_senior_shape import finish_senior_component, infer_extension_fields
from app.component_gallery import get_gallery_seed, list_gallery


def inherit_only_display_name(prompt: str, host_label: str) -> str:
    """Grounded title for inherit-only ops — never residual slug or 'X extension'."""
    text = prompt or ""
    host = (host_label or "Host").strip() or "Host"
    prefer = bool(re.search(r"(?i)\bprefer(?:red)?\s+for\s+delivery\b", text))
    notes = bool(re.search(r"(?i)\bdelivery\s+notes?\b", text))
    if prefer or notes:
        return f"{host} delivery preferences"
    # Fall back to host + a brief noun that appears in the prompt.
    try:
        from app.ai_document_shape import naming_from_residual
        from app.ai_surface_invariants import title_is_grounded

        named, _slug = naming_from_residual(text)
        if named and title_is_grounded(named, text) and not re.search(
            r"(?i)\b(extras|extension)\b$", named.strip()
        ):
            return named
    except Exception:  # noqa: BLE001
        pass
    return f"{host} fields"




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

    # Extension arch is authored by ai_form_slots in finish_senior_component
    # (named slots, never a nested EXTENSION group).
    views: list[dict[str, Any]] = []

    menus: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    if grain == "feature_slice" and connect_points.get("menu_mode") == "sub":
        sub = connect_points.get("sub_menu_name") or "Extension"
        action_xml = f"action_{slug}_ext"
        menus.append(
            {
                "name": sub,
                "action_xml_id": action_xml,
                "parent_xml_id": parent_menu_xml_id_for_module(mod),
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
        else:
            actions.append(
                {
                    "name": sub,
                    "model": host_model,
                    "view_mode": "list,form",
                    "technical_name": action_xml,
                }
            )

    depends = [mod] if mod and mod != "base" else ["base"]

    def _generic_host_chrome_title(name: str | None) -> bool:
        return bool(
            re.search(r"(?i)^\w+\s+(?:extras|extension)$", (name or "").strip())
        )

    raw_sub = connect_points.get("sub_menu_name")
    if _generic_host_chrome_title(str(raw_sub or "")):
        raw_sub = None
    display = raw_sub or f"{host.label} extension"
    try:
        from app.ai_grain import is_inherit_only_ops

        inherit_only = is_inherit_only_ops(prompt or "")
    except Exception:  # noqa: BLE001
        inherit_only = False
    if grain == "field_pack" or inherit_only:
        low = (prompt or "").lower()
        if (
            not raw_sub
            and host.model == "account.move"
            and re.search(r"\b(vendor\s+bills?|supplier\s+bills?)\b", low)
        ):
            display = "Vendor bill fields"
        else:
            display = inherit_only_display_name(prompt or "", host.label)
        # Never keep a residual companion model on inherit-only / field_pack.
        models[:] = [
            row
            for row in models
            if isinstance(row, dict)
            and (
                str(row.get("mode") or "") == "inherit"
                or str(row.get("model") or "") == host.model
            )
        ]
        menus.clear()
        actions.clear()

    draft: dict[str, Any] = {
        "technical_name": technical,
        "display_name": display,
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
    named = named_host_from_prompt(prompt)
    extra_warnings: list[str] = []
    override_host = host_model_override or (
        str(connect_points_override.get("host_model") or "")
        if isinstance(connect_points_override, dict)
        else ""
    )
    if named and override_host and named != override_host:
        extra_warnings.append(
            f"Prompt names {named}; ignoring approved host {override_host}."
        )
        host_model_override = None
        connect_points_override = None
    hosts = discover_hosts(prompt, available_models=available_models)
    if host_model_override:
        hosts = [
            HostCandidate(
                model=host_model_override,
                label=HOST_LABELS.get(host_model_override, host_model_override),
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
        # Prefer Must-do / locked Diagnosis IR over polluted-prompt heuristics
        # (understanding_json / clarifications / status-hint prose as Char fields).
        from app.ai_field_ir import extract_field_ir

        fields = extract_field_ir(prompt)
        if not fields:
            fields = infer_extension_fields(
                prompt, pad=resolved_grain != "field_pack"
            )

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
    notes = finish_senior_component(draft, prompt=prompt, grain=resolved_grain)
    warnings.extend(extra_warnings)
    # Capability stamp notes are operator noise when the Option A callout exists;
    # keep only junk-drop lines so Apply honesty stays visible.
    for note in notes:
        if note.startswith("capability: dropped"):
            warnings.append(note)
        elif not note.startswith("capability:"):
            warnings.append(note)
    return draft, hosts, warnings


def preview_connect_points(
    prompt: str,
    *,
    grain: Grain | None = None,
    available_models: list[str] | None = None,
    gallery_id: str | None = None,
    host_model_override: str | None = None,
    connect_points_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wizard pre-draft step: classify grain + propose connect points without building spec."""
    resolved_grain: Grain = grain or classify_grain(prompt)
    if resolved_grain == "full_app":
        return {
            "grain": "full_app",
            "grain_label": grain_display("full_app", None),
            "connect_points": None,
            "host_candidates": [],
            "requires_review": False,
            "warnings": [],
            "gallery_id": gallery_id,
        }

    hosts = discover_hosts(prompt, available_models=available_models)
    if host_model_override:
        hosts = [
            HostCandidate(
                model=host_model_override,
                label=HOST_LABELS.get(host_model_override, host_model_override),
                score=1.0,
                module=module_for_model(host_model_override),
                reason="operator override",
            ),
            *hosts,
        ]

    gallery_seed = get_gallery_seed(gallery_id) if gallery_id else _match_gallery(prompt)
    resolved_gallery_id = gallery_id or (gallery_seed["id"] if gallery_seed else None)
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

    warnings: list[str] = []
    if not hosts:
        return {
            "grain": resolved_grain,
            "grain_label": grain_display(resolved_grain, None),
            "connect_points": None,
            "host_candidates": [],
            "requires_review": True,
            "warnings": [
                "No host model candidates — connect to Odoo or specify host in prompt."
            ],
            "gallery_id": resolved_gallery_id,
        }

    host = hosts[0]
    cp = connect_points_override or propose_connect_points(
        prompt, grain=resolved_grain, host=host, gallery_seed=gallery_seed
    )
    return {
        "grain": resolved_grain,
        "grain_label": grain_display(resolved_grain, host),
        "connect_points": cp,
        "host_candidates": [
            {"model": h.model, "label": h.label, "score": h.score, "reason": h.reason}
            for h in hosts
        ],
        "requires_review": True,
        "warnings": warnings,
        "gallery_id": resolved_gallery_id,
    }


__all__ = [
    "draft_component_from_prompt",
    "build_component_draft",
    "list_gallery",
    "preview_connect_points",
]
