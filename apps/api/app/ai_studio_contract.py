"""Studio Contract Compiler — flagship Generate→Review→Apply spine.

LLM proposes intent; this module compiles a typed Studio Contract, drives
deterministic finishers, and gates Review/Apply on a scorecard. One IR feeds
placement, ops surfaces, preview honesty, and Expert structural repair.

Public ORM/RPC only — no private Odoo APIs.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from app.ai_grain import Grain, classify_grain, is_inherit_only_ops

_OPS_PICKING_RE = re.compile(
    r"(?i)\b(?:pickings?|transfers?|delivery\s*/\s*inventory|inventory\s+lists?)\b"
)
_OPS_FILTER_RE = re.compile(r"(?i)\b(?:filter|domain)\b")
_OPS_AUTO_RE = re.compile(
    r"(?i)\b(?:automation|automat(?:e|ed|ion)|when\s+(?:the\s+)?box\s+is\s+checked)\b"
)
_DELIVERY_PREF_RE = re.compile(
    r"(?i)\b(?:"
    r"prefer(?:red)?\s+for\s+delivery|"
    r"preferred[- ]delivery|"
    r"delivery\s+notes?"
    r")\b"
)
_NO_APP_RE = re.compile(
    r"(?i)\b(?:no\s+new\s+app|inherit[- ]only|still\s+inherit|do\s+not\s+create\s+a\s+new)\b"
)
_HOST_CONTACT_RE = re.compile(
    r"(?i)\b(?:res\.partner|contacts?|partners?)\b"
)

CONTRACT_VERSION = 1

SURFACE_PICKING_FILTER = "picking_search_filter"
SURFACE_TRANSFERS_BUTTON = "smart_button_transfers"
SURFACE_ON_WRITE = "on_write_activity"


def _constraints_blob(constraints: list[str] | None) -> str:
    return "\n".join(str(c) for c in (constraints or []) if c)


def _host_from_prompt(prompt: str, *, override: str | None = None) -> tuple[str, str]:
    """Resolve an inherit host. Empty string = no stock host (residual full_app)."""
    if override:
        return override, "Contacts" if override == "res.partner" else override
    text = prompt or ""
    if _HOST_CONTACT_RE.search(text) or _DELIVERY_PREF_RE.search(text):
        return "res.partner", "Contacts"
    from app.ai_grain import preferred_inherit_host

    named = preferred_inherit_host(text)
    if named:
        labels = {
            "res.partner": "Contacts",
            "stock.picking": "Transfers",
            "sale.order": "Sales",
            "project.task": "Tasks",
            "calendar.event": "Calendar",
            "hr.employee": "Employees",
        }
        return named, labels.get(named, named)
    # Do NOT invent Contacts — residual full_app briefs have no stock host.
    return "", ""


def _infer_surfaces(prompt: str, *, inherit_only: bool) -> list[str]:
    if not inherit_only:
        return []
    text = prompt or ""
    if not (
        _OPS_PICKING_RE.search(text)
        or _OPS_FILTER_RE.search(text)
        or _OPS_AUTO_RE.search(text)
    ):
        return []
    surfaces: list[str] = []
    if _OPS_PICKING_RE.search(text) or _OPS_FILTER_RE.search(text):
        surfaces.append(SURFACE_PICKING_FILTER)
    if _OPS_PICKING_RE.search(text):
        surfaces.append(SURFACE_TRANSFERS_BUTTON)
    if _OPS_AUTO_RE.search(text) or _OPS_PICKING_RE.search(text) or _OPS_FILTER_RE.search(text):
        surfaces.append(SURFACE_ON_WRITE)
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in surfaces:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _infer_fields(prompt: str, host: str) -> list[dict[str, Any]]:
    text = prompt or ""
    fields: list[dict[str, Any]] = []
    if host == "res.partner" and _DELIVERY_PREF_RE.search(text):
        if re.search(r"(?i)prefer", text):
            fields.append(
                {
                    "name": "x_preferred_for_delivery",
                    "ttype": "boolean",
                    "string": "Preferred for delivery",
                    "placement": "Delivery",
                    "slot": "new_tab",
                }
            )
        if re.search(r"(?i)delivery\s+notes?", text) or re.search(r"(?i)notes?", text):
            fields.append(
                {
                    "name": "x_delivery_notes",
                    "ttype": "text",
                    "string": "Delivery notes",
                    "placement": "Delivery",
                    "slot": "new_tab",
                }
            )
    return fields


def _app_title_from_prompt(prompt: str) -> str:
    """Residual app display name from Build…app / Title: / Title for our…"""
    text = prompt or ""
    m = re.search(
        r"(?i)\b(?:build|create|make)\s+(?:an?\s+)?(?:(?:tiny|simple|small|new|mini)\s+)*"
        r"(.+?)\s+app\b",
        text,
    )
    if m:
        nice = re.sub(r"\s+", " ", m.group(1)).strip(" .:,-")
        nice = re.sub(r"(?i)^(a|an|the)\s+", "", nice).strip()
        if nice:
            return nice.title() if nice.islower() else nice
    m = re.search(
        r"(?i)^([A-Z][\w][\w\s/-]{1,48}?)(?:\s+for\s+(?:our|the|a)\b|\s*[:—-])",
        text.strip(),
    )
    if m:
        nice = re.sub(r"\s+", " ", m.group(1)).strip(" .:,-")
        if nice:
            return nice.title() if nice.islower() else nice
    return "Custom app"


def _grounded_title(
    prompt: str,
    host_label: str,
    surfaces: list[str],
    *,
    grain: Grain | str = "field_pack",
) -> str:
    if grain == "full_app" and not host_label:
        return _app_title_from_prompt(prompt)
    if surfaces:
        return f"{host_label or 'Contacts'} delivery preferences"
    if _DELIVERY_PREF_RE.search(prompt or ""):
        return f"{host_label or 'Contacts'} delivery preferences"
    if host_label:
        return f"{host_label} field pack"
    return _app_title_from_prompt(prompt)


def build_studio_contract(
    prompt: str,
    *,
    constraints: list[str] | None = None,
    host_override: str | None = None,
    grain: Grain | None = None,
) -> dict[str, Any]:
    """Compile a typed Studio Contract from the operator brief (+ Must-do lines)."""
    blob = f"{prompt or ''}\n{_constraints_blob(constraints)}"
    inherit_only = is_inherit_only_ops(blob) or bool(_NO_APP_RE.search(blob))
    resolved_grain: Grain = grain or classify_grain(blob)
    if inherit_only:
        resolved_grain = "field_pack"
    # Residual full_app: never invent a stock host or «field pack» title.
    # Ignore host_override too — attach_studio_contract used to re-inject a stolen
    # inherit row (calendar.event) from the draft and bypass this clear.
    if resolved_grain == "full_app" and not inherit_only:
        host, host_label = "", ""
    else:
        host, host_label = _host_from_prompt(blob, override=host_override)
        # Prefer/inherit briefs with no named host still default Contacts.
        if inherit_only and not host:
            host, host_label = "res.partner", "Contacts"
    surfaces = _infer_surfaces(blob, inherit_only=inherit_only)
    fields = _infer_fields(blob, host) if host else []
    placement = None
    if any(str(f.get("placement") or "") == "Delivery" for f in fields):
        placement = "Delivery"
    elif host == "res.partner" and _DELIVERY_PREF_RE.search(blob):
        placement = "Delivery"
    reuse = bool(
        re.search(r"(?i)\balready\s+(?:persist|exist)|reuse\s+existing|do\s+not\s+recreate", blob)
    )
    title = _grounded_title(blob, host_label, surfaces, grain=resolved_grain)
    return {
        "version": CONTRACT_VERSION,
        "host_model": host or None,
        "host_label": host_label or None,
        "inherit_only": inherit_only,
        "no_new_app": inherit_only or bool(_NO_APP_RE.search(blob)),
        "reuse_fields": reuse,
        "grain": resolved_grain,
        "title": title,
        "placement_group": placement,
        "fields": fields,
        "surfaces": surfaces,
        "summary": contract_human_summary(
            {
                "host_label": host_label,
                "inherit_only": inherit_only,
                "placement_group": placement,
                "surfaces": surfaces,
                "fields": fields,
                "title": title,
            }
        ),
        "source_prompt": (prompt or "")[:2000],
    }


def contract_human_summary(contract: dict[str, Any]) -> str:
    host = str(contract.get("host_label") or contract.get("host_model") or "host")
    bits: list[str] = []
    if contract.get("inherit_only"):
        bits.append(f"Inherit-only on {host} (no new app tile)")
    elif host and host not in {"host", "None"}:
        bits.append(f"Host {host}")
    else:
        bits.append(f"New app: {contract.get('title') or 'custom'}")
    place = contract.get("placement_group")
    if place:
        bits.append(f"fields under {place} group")
    fields = contract.get("fields") or []
    if fields:
        labels = ", ".join(str(f.get("string") or f.get("name")) for f in fields if isinstance(f, dict))
        bits.append(f"fields: {labels}")
    surfaces = list(contract.get("surfaces") or [])
    if surfaces:
        nice = {
            SURFACE_PICKING_FILTER: "Transfers search filter",
            SURFACE_TRANSFERS_BUTTON: "Transfers smart button",
            SURFACE_ON_WRITE: "light on-write activity",
        }
        bits.append("wires " + ", ".join(nice.get(s, s) for s in surfaces))
    title = contract.get("title")
    if title:
        bits.append(f"title «{title}»")
    return "; ".join(bits)


def contract_diff(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    """Human lines for Refine — what the contract changed."""
    a = before or {}
    b = after or {}
    lines: list[str] = []
    for key, label in (
        ("title", "Title"),
        ("placement_group", "Placement"),
        ("grain", "Grain"),
        ("host_model", "Host"),
    ):
        if a.get(key) != b.get(key):
            lines.append(f"{label}: {a.get(key)!r} → {b.get(key)!r}")
    sa = set(a.get("surfaces") or [])
    sb = set(b.get("surfaces") or [])
    if sa != sb:
        lines.append(f"Surfaces: {sorted(sa)} → {sorted(sb)}")
    return lines


def attach_studio_contract(
    draft: dict[str, Any],
    prompt: str,
    *,
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    """Stamp ``_studio_contract`` on the draft (idempotent rebuild from prompt)."""
    from app.ai_grain import classify_grain

    grain = draft.get("grain")
    if not isinstance(grain, str) or grain not in {"field_pack", "feature_slice", "full_app"}:
        grain = classify_grain(prompt)
        draft["grain"] = grain

    host = None
    # Only feed draft inherit rows as host override for inherit grains.
    # Residual full_app drafts often carry a stolen calendar.event / hr.employee
    # inherit from alias noise — that must not become Contract host.
    if grain in {"field_pack", "feature_slice"}:
        for m in draft.get("models") or []:
            if isinstance(m, dict) and str(m.get("mode") or "") == "inherit":
                host = str(m.get("model") or "") or None
                break
    contract = build_studio_contract(
        prompt,
        constraints=constraints,
        host_override=host,
        grain=grain if isinstance(grain, str) else None,  # type: ignore[arg-type]
    )
    draft["_studio_contract"] = contract
    draft["_contract_summary"] = contract.get("summary")
    return contract


def _prefer_field_name(draft: dict[str, Any], contract: dict[str, Any]) -> str | None:
    for f in contract.get("fields") or []:
        if isinstance(f, dict) and str(f.get("ttype")) == "boolean":
            return str(f.get("name") or "") or None
    for m in draft.get("models") or []:
        if not isinstance(m, dict) or str(m.get("mode") or "") != "inherit":
            continue
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            if str(f.get("ttype") or "") != "boolean":
                continue
            blob = f"{f.get('name') or ''} {f.get('string') or ''}"
            if re.search(r"(?i)prefer", blob) and re.search(r"(?i)deliver", blob):
                return str(f.get("name") or "") or None
    return None


def fulfill_studio_contract(draft: dict[str, Any], prompt: str) -> list[str]:
    """Drive deterministic finishers from the stamped contract.

    Placement overrides feed ``apply_form_slots``; ops surfaces reuse senior ops
    wiring (already prompt-gated) and fill any remaining gaps from the contract.
    """
    notes: list[str] = []
    contract = draft.get("_studio_contract")
    if not isinstance(contract, dict):
        contract = attach_studio_contract(draft, prompt)

    # Title grounding
    title = str(contract.get("title") or "").strip()
    if title and contract.get("inherit_only"):
        cur = str(draft.get("display_name") or "")
        if (
            not cur
            or re.search(r"(?i)^\w+\s+(?:extras|extension)$", cur)
            or cur.lower() in {"prefer", "contact extras", "contacts extension"}
        ):
            draft["display_name"] = title
            notes.append(f"contract: grounded title → {title}")

    # Residual full_app: keep canvas residual — never reshape into stock inherit.
    if str(contract.get("grain") or draft.get("grain") or "") == "full_app" and not contract.get(
        "inherit_only"
    ):
        draft["grain"] = "full_app"
        if contract.get("title") and not str(draft.get("display_name") or "").strip():
            draft["display_name"] = str(contract["title"])
            notes.append(f"contract: residual title → {contract['title']}")

    # Grain lock for inherit-only
    if contract.get("inherit_only"):
        draft["grain"] = "field_pack"
        draft["menus"] = []
        # Drop residual x_* new models
        models = [m for m in (draft.get("models") or []) if isinstance(m, dict)]
        host = str(contract.get("host_model") or "res.partner")
        residual = [
            m
            for m in models
            if str(m.get("mode") or "new") != "inherit"
            and str(m.get("model") or "").startswith("x_")
        ]
        if residual:
            keep_fields: list[dict[str, Any]] = []
            for m in residual:
                for f in m.get("fields") or []:
                    if isinstance(f, dict):
                        keep_fields.append(deepcopy(f))
            for f in contract.get("fields") or []:
                if isinstance(f, dict) and not any(
                    str(k.get("name")) == str(f.get("name")) for k in keep_fields
                ):
                    keep_fields.append(deepcopy(f))
            draft["models"] = [
                {
                    "model": host,
                    "mode": "inherit",
                    "inherit": host,
                    "description": f"Extend {contract.get('host_label') or host}",
                    "fields": keep_fields
                    or [deepcopy(f) for f in (contract.get("fields") or []) if isinstance(f, dict)],
                }
            ]
            notes.append(f"contract: reshaped residual → inherit {host}")

    # Placement overrides for form slots
    placement = contract.get("placement_group")
    field_map: dict[str, str] = {}
    for f in contract.get("fields") or []:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "")
        slot = str(f.get("slot") or "new_tab")
        if name:
            field_map[name] = slot
    if placement or field_map:
        slots = draft.get("_form_slots") if isinstance(draft.get("_form_slots"), dict) else {}
        slots = dict(slots)
        if field_map:
            fields_ov = dict(slots.get("fields") or {})
            fields_ov.update(field_map)
            slots["fields"] = fields_ov
        if placement:
            slots["group_title"] = placement
            slots["tab_title"] = placement
        draft["_form_slots"] = slots
        notes.append(f"contract: placement overrides → {placement or 'slots'}")

    # Ensure ops surfaces via senior wiring when contract names them
    surfaces = set(contract.get("surfaces") or [])
    if surfaces:
        # Seed prompt themes if senior gate needs them (already true for ops briefs).
        from app.ai_senior_shape import _ensure_inherit_ops_wiring

        notes.extend(_ensure_inherit_ops_wiring(draft, prompt))
        # Gap-fill if senior skipped (e.g. missing prefer field name variants)
        fname = _prefer_field_name(draft, contract)
        if fname and SURFACE_PICKING_FILTER in surfaces:
            views = [v for v in (draft.get("views") or []) if isinstance(v, dict)]
            has_filter = any(
                str(v.get("model")) == "stock.picking"
                and str(v.get("type")) == "search"
                and "preferred" in str(v.get("arch") or "").lower()
                for v in views
            )
            if not has_filter:
                draft.setdefault("views", []).append(
                    {
                        "name": "stock.picking.search.preferred_delivery",
                        "model": "stock.picking",
                        "type": "search",
                        "mode": "extension",
                        "inherit_xml_id": "stock.view_picking_internal_search",
                        "arch": (
                            "<data>\n"
                            '  <xpath expr="//search" position="inside">\n'
                            f'    <filter string="Preferred delivery contact" '
                            f'name="ingenium_preferred_delivery_partner" '
                            f"domain=\"[('partner_id.{fname}', '=', True)]\"/>\n"
                            "  </xpath>\n"
                            "</data>"
                        ),
                        "source": "studio_contract",
                    }
                )
                deps = list(draft.get("depends") or [])
                if "stock" not in deps:
                    deps.append("stock")
                    draft["depends"] = deps
                notes.append("contract: authored picking search filter")
        if SURFACE_TRANSFERS_BUTTON in surfaces:
            buttons = draft.get("smart_buttons") or []
            has_btn = any(
                isinstance(b, dict)
                and str(b.get("on_model")) == "res.partner"
                and str(b.get("related_model")) == "stock.picking"
                for b in buttons
            )
            if not has_btn:
                draft.setdefault("smart_buttons", []).append(
                    {
                        "on_model": "res.partner",
                        "related_model": "stock.picking",
                        "relation_field": "partner_id",
                        "label": "Transfers",
                        "icon": "fa-truck",
                        "requires_inherit_view": True,
                        "source": "studio_contract",
                    }
                )
                notes.append("contract: authored Transfers smart button")
        if SURFACE_ON_WRITE in surfaces and fname:
            autos = draft.get("automations") or []
            has_auto = any(
                isinstance(a, dict)
                and str(a.get("model")) == "res.partner"
                and fname in str(a.get("filter_domain") or "")
                for a in autos
            )
            if not has_auto:
                draft.setdefault("automations", []).append(
                    {
                        "name": "Preferred for delivery — follow up",
                        "model": "res.partner",
                        "trigger": "on_write",
                        "trigger_field_names": [fname],
                        "filter_domain": f"[('{fname}', '=', True)]",
                        "description": "Contract light automation when Prefer for delivery is checked",
                        "safe_actions": [
                            {
                                "kind": "next_activity",
                                "summary": "Preferred for delivery: confirm delivery notes for logistics",
                                "activity_type_xml_id": "mail.mail_activity_data_todo",
                            }
                        ],
                        "source": "studio_contract",
                    }
                )
                notes.append("contract: authored on_write activity")

    sync_honesty_meta(draft)
    return notes


def sync_honesty_meta(draft: dict[str, Any]) -> None:
    """Keep Apply-count meta honest — never claim surfaces the draft lacks."""
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    meta = dict(meta)
    meta["smart_button_count"] = len(
        [b for b in (draft.get("smart_buttons") or []) if isinstance(b, dict)]
    )
    meta["automation_count"] = len(
        [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
    )
    search_filters = sum(
        1
        for v in (draft.get("views") or [])
        if isinstance(v, dict) and str(v.get("type")) == "search"
    )
    meta["search_filter_view_count"] = search_filters
    contract = draft.get("_studio_contract") if isinstance(draft.get("_studio_contract"), dict) else {}
    meta["contract_surfaces"] = list(contract.get("surfaces") or [])
    meta["contract_placement"] = contract.get("placement_group")
    draft["_meta"] = meta


def evaluate_studio_contract(draft: dict[str, Any]) -> dict[str, Any]:
    """Scorecard: pass only when authored draft satisfies the contract."""
    contract = draft.get("_studio_contract") if isinstance(draft.get("_studio_contract"), dict) else {}
    findings: list[dict[str, str]] = []
    repairs: list[str] = []

    if not contract:
        findings.append(
            {
                "severity": "error",
                "code": "contract_missing",
                "detail": "No Studio Contract on draft",
            }
        )
        repairs.append("Rebuild contract from the brief, then re-run finishers")
        return {
            "pass": False,
            "findings": findings,
            "repairs": repairs,
            "blocking": True,
        }

    if contract.get("inherit_only"):
        for m in draft.get("models") or []:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("model") or "")
            mode = str(m.get("mode") or "new")
            if mode != "inherit" and mid.startswith("x_"):
                findings.append(
                    {
                        "severity": "error",
                        "code": "residual_model",
                        "detail": f"Inherit-only contract but residual model {mid}",
                    }
                )
                repairs.append("Repair with Expert — reshape residual → inherit-only")
        if draft.get("menus"):
            findings.append(
                {
                    "severity": "error",
                    "code": "new_app_menu",
                    "detail": "Inherit-only contract forbids new menus/app tile",
                }
            )
            repairs.append("Clear menus; keep inherit-only on host")

    place = contract.get("placement_group")
    if place:
        slots = draft.get("_form_slots") if isinstance(draft.get("_form_slots"), dict) else {}
        got = slots.get("group_title")
        arch_blob = " ".join(
            str(v.get("arch") or "")
            for v in (draft.get("views") or [])
            if isinstance(v, dict) and str(v.get("type") or "form") == "form"
        )
        if got != place and f'string="{place}"' not in arch_blob:
            findings.append(
                {
                    "severity": "error",
                    "code": "placement_miss",
                    "detail": f"Expected {place} group placement; got {got!r}",
                }
            )
            repairs.append(f"Place fields under {place} group (not Other Info)")

    surfaces = set(contract.get("surfaces") or [])
    if SURFACE_PICKING_FILTER in surfaces:
        ok = any(
            isinstance(v, dict)
            and str(v.get("model")) == "stock.picking"
            and str(v.get("type")) == "search"
            for v in (draft.get("views") or [])
        )
        if not ok:
            findings.append(
                {
                    "severity": "error",
                    "code": "missing_picking_filter",
                    "detail": "Contract requires Transfers search filter",
                }
            )
            repairs.append("Author stock.picking Preferred delivery contact filter")
    if SURFACE_TRANSFERS_BUTTON in surfaces:
        ok = any(
            isinstance(b, dict)
            and str(b.get("on_model")) == "res.partner"
            and str(b.get("related_model")) == "stock.picking"
            for b in (draft.get("smart_buttons") or [])
        )
        if not ok:
            findings.append(
                {
                    "severity": "error",
                    "code": "missing_smart_button",
                    "detail": "Contract requires Transfers smart button",
                }
            )
            repairs.append("Author Contacts → Transfers smart button")
    if SURFACE_ON_WRITE in surfaces:
        ok = bool(draft.get("automations"))
        if not ok:
            findings.append(
                {
                    "severity": "error",
                    "code": "missing_automation",
                    "detail": "Contract requires light on-write automation",
                }
            )
            repairs.append("Author on_write activity when Prefer for delivery is set")

    # Honesty: meta counts must match
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    actual_btn = len([b for b in (draft.get("smart_buttons") or []) if isinstance(b, dict)])
    if meta.get("smart_button_count") not in (None, actual_btn):
        findings.append(
            {
                "severity": "warning",
                "code": "honesty_smart_buttons",
                "detail": "Meta smart_button_count disagrees with draft",
            }
        )

    errors = [f for f in findings if f.get("severity") == "error"]
    return {
        "pass": not errors,
        "findings": findings,
        "repairs": repairs,
        "blocking": bool(errors),
        "summary": contract.get("summary"),
        "surfaces_expected": sorted(surfaces),
        "smart_button_count": actual_btn,
        "automation_count": len(
            [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
        ),
    }


def stamp_studio_contract_pipeline(draft: dict[str, Any], prompt: str) -> list[str]:
    """Attach → fulfill → evaluate. Call after senior finish / form slots."""
    notes: list[str] = []
    attach_studio_contract(draft, prompt)
    notes.extend(fulfill_studio_contract(draft, prompt))
    # Re-apply form slots so placement overrides win
    try:
        from app.ai_form_slots import apply_form_slots

        notes.extend(apply_form_slots(draft, prompt=prompt))
    except Exception:  # noqa: BLE001
        pass
    score = evaluate_studio_contract(draft)
    draft["_contract_scorecard"] = score
    if score.get("pass"):
        notes.append("contract: scorecard pass")
    else:
        notes.append(
            "contract: scorecard blockers — "
            + "; ".join(score.get("repairs") or ["see findings"])
        )
    sync_honesty_meta(draft)
    return notes


__all__ = [
    "SURFACE_ON_WRITE",
    "SURFACE_PICKING_FILTER",
    "SURFACE_TRANSFERS_BUTTON",
    "attach_studio_contract",
    "build_studio_contract",
    "contract_diff",
    "contract_human_summary",
    "evaluate_studio_contract",
    "fulfill_studio_contract",
    "stamp_studio_contract_pipeline",
    "sync_honesty_meta",
]
