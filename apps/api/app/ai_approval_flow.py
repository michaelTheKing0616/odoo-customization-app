"""Community approval / execution flows on residual x_* drafts.

Enterprise Approvals and Studio button-gating are not available. Live Apply
executes this shape via ``ir.actions.server`` object_write (Submit / Approve /
Refuse) plus a ``base.automation`` activity when a record enters submitted.
Manager-only dests are enforced on the server action groups, not Python methods.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai_workflow import parse_selection_keys

_APPROVAL_RE = re.compile(
    r"(?i)\b("
    r"approval(?:s)?(?:\s+flow|\s+workflow|\s+chain|\s+process)?"
    r"|approver"
    r"|needs?\s+approval"
    r"|pending\s+approval"
    r"|submit(?:ted)?\s+for\s+approval"
    r"|manager\s+(?:must\s+|needs?\s+to\s+|to\s+)?approv"
    r"|require(?:s|d)?\s+(?:a\s+)?manager(?:\s+to\s+approv)?"
    r"|two[-\s]step\s+approval"
    r"|multi[-\s]level\s+approval"
    r"|approve\s+or\s+refuse"
    r"|approve\s+or\s+reject"
    r")\b"
)
_FALSE_POSITIVE_RE = re.compile(
    r"(?i)\b(approved host|connect points?|approval_requests template)\b"
)
_MANAGER_DESTS = frozenset({"approved", "refused", "rejected"})
_STATES = ["draft", "submitted", "approved", "refused"]
_TRANSITIONS = [
    ["draft", "submitted"],
    ["submitted", "approved"],
    ["submitted", "refused"],
]
_SELECTION = (
    "[('draft','Draft'),('submitted','Submitted'),"
    "('approved','Approved'),('refused','Refused')]"
)


def brief_wants_approval(text: str) -> bool:
    blob = str(text or "")
    if not blob or _FALSE_POSITIVE_RE.search(blob):
        return False
    if _APPROVAL_RE.search(blob):
        return True
    try:
        from app.ai_surface_invariants import extract_brief_slots

        return extract_brief_slots(blob).wants_approval
    except Exception:  # noqa: BLE001
        return False


def _header_model(draft: dict[str, Any]) -> dict[str, Any] | None:
    from app.ai_odoo_app_bar import looks_like_register
    from app.ai_model_quality import is_embedded_line_model

    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if is_embedded_line_model(mid) or looks_like_register(mid):
            continue
        if str(model.get("mode") or "new") == "inherit":
            continue
        return model
    return None


def _manager_group_id(draft: dict[str, Any]) -> str:
    tech = str(draft.get("technical_name") or "app").replace(".", "_")
    return f"group_{tech}_manager"


def _ensure_status_field(model: dict[str, Any], field_name: str) -> dict[str, Any]:
    fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
    row = next((f for f in fields if str(f.get("name") or "") == field_name), None)
    if row is None:
        row = {
            "name": field_name,
            "ttype": "selection",
            "string": "Status",
            "selection": _SELECTION,
            "required": True,
            "readonly": True,
            "tracking": True,
            "default": "draft",
        }
        fields.append(row)
        model["fields"] = fields
        return row
    row["ttype"] = "selection"
    row["selection"] = _SELECTION
    row["readonly"] = True
    row["tracking"] = True
    row.setdefault("string", "Status")
    row.setdefault("required", True)
    row.setdefault("default", "draft")
    return row


def _ensure_mail_mixins(model: dict[str, Any]) -> None:
    mixins = [str(x) for x in (model.get("mixins") or [])]
    for mixin in ("mail.thread", "mail.activity.mixin"):
        if mixin not in mixins:
            mixins.append(mixin)
    model["mixins"] = mixins
    model["is_mail_activity"] = True


def _manager_user_field_name(model: dict[str, Any]) -> str | None:
    """Best-effort heuristic: which field should receive the manager todo."""

    fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
    for f in fields:
        fttype = str(f.get("ttype") or "")
        if fttype not in {"many2one", "many2one_selection"}:
            continue
        relation = str(f.get("relation") or "")
        if relation != "res.users":
            continue
        name = str(f.get("name") or "")
        if not name.startswith("x_"):
            continue
        if "manager" in name.lower():
            return name
        string = str(f.get("string") or "")
        if "manager" in string.lower() or "approv" in string.lower():
            return name
    return None


def _ensure_activity_automation(
    draft: dict[str, Any],
    model_id: str,
    field_name: str,
    *,
    manager_user_field_name: str | None,
) -> None:
    autos = [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
    marker = "approval-notify-manager"
    existing = next(
        (a for a in autos if str(a.get("_approval_flow") or "") == marker),
        None,
    )
    row = {
        "name": "Notify manager to approve",
        "model": model_id,
        "trigger": "on_write",
        "filter_pre_domain": f"[('{field_name}', '!=', 'submitted')]",
        "filter_domain": f"[('{field_name}', '=', 'submitted')]",
        "trigger_field_names": [field_name],
        "safe_actions": [
            {
                "kind": "next_activity",
                "summary": "Approve this request",
                "activity_type_xml_id": "mail.mail_activity_data_todo",
            }
        ],
        "_approval_flow": marker,
    }
    # Assign the todo to the approving manager, when a suitable field exists.
    if manager_user_field_name:
        row["safe_actions"][0]["user_type"] = "specific"
        row["safe_actions"][0]["user_field_name"] = manager_user_field_name
    if existing:
        existing.update(row)
    else:
        autos.append(row)
        draft["automations"] = autos
    depends = [str(d) for d in (draft.get("depends") or [])]
    for mod in ("mail", "base_automation"):
        if mod not in depends:
            depends.append(mod)
    draft["depends"] = depends


def apply_approval_flow(
    draft: dict[str, Any],
    *,
    prompt: str = "",
    force: bool = False,
) -> list[str]:
    """Stamp Submit → Approve/Refuse on the residual header when the brief asks."""
    text = prompt or str(draft.get("_user_prompt") or "")
    if not force and not brief_wants_approval(text):
        return []
    if draft.get("grain") in {"stock_reuse", "field_pack"} and not force:
        return []
    model = _header_model(draft)
    if not model:
        return []
    mid = str(model.get("model") or "")
    field_name = "x_status"
    sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
    if str(sf.get("field") or "").startswith("x_"):
        field_name = str(sf["field"])
    _ensure_status_field(model, field_name)
    _ensure_mail_mixins(model)
    model["is_workflow"] = True
    model["state_field"] = {
        "field": field_name,
        "states": list(_STATES),
        "transitions": [list(edge) for edge in _TRANSITIONS],
        "statusbar_visible": list(_STATES),
        "approval": True,
    }
    _ensure_activity_automation(
        draft,
        mid,
        field_name,
        manager_user_field_name=_manager_user_field_name(model),
    )
    try:
        from app.ai_odoo_app_bar import sync_security_groups_to_technical_name

        sync_security_groups_to_technical_name(draft)
    except Exception:  # noqa: BLE001
        pass
    draft["_approval_flow"] = {
        "kind": "community_button_gate",
        "model": mid,
        "field": field_name,
        "states": list(_STATES),
        "transitions": [list(edge) for edge in _TRANSITIONS],
        "manager_dests": sorted(_MANAGER_DESTS),
        "manager_group": _manager_group_id(draft),
        "activity_on_submit": True,
        "note": (
            "Live Apply binds Submit/Approve/Refuse to object_write server actions. "
            "Approve/Refuse require the app Manager group. This is not Enterprise Approvals."
        ),
    }
    try:
        from app.ai_odoo_app_bar import rebuild_form_transition_headers
        from app.ai_enrich import sync_form_archs_to_models

        sync_form_archs_to_models(draft)
        rebuild_form_transition_headers(draft)
    except Exception:  # noqa: BLE001
        pass
    return [f"approval: {mid} draft→submitted→approved/refused (manager-gated)"]


def approval_manager_dests(draft: dict[str, Any]) -> set[str]:
    flow = draft.get("_approval_flow")
    if isinstance(flow, dict) and flow.get("manager_dests"):
        return {str(x) for x in flow["manager_dests"]}
    return set()


def dump_approval_stamp(draft: dict[str, Any]) -> str:
    flow = draft.get("_approval_flow")
    if not isinstance(flow, dict):
        return ""
    return json.dumps(flow, sort_keys=True)


__all__ = [
    "apply_approval_flow",
    "approval_manager_dests",
    "brief_wants_approval",
]
