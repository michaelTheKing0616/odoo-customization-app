"""Build Odoo automation records (data, not Python) from a contract automation.

Version-agnostic by construction: nothing is assumed about Odoo 16-20. Field
names and selection values are probed on the live instance; if the instance
cannot do what the spec asks, the builder returns a plain-language problem and
builds nothing. Pure function: no RPC here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_SERVER = "@server"  # placeholder replaced with the created ir.actions.server id
_RESPONSIBLE = ("user_id", "x_user_id", "x_owner_id", "x_responsible_id")


def _keep(vals: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {k: v for k, v in vals.items() if k in allowed}


def build_automation_records(
    auto: dict[str, Any],
    *,
    model_ids: dict[str, int],
    field_ids: dict[tuple[str, str], int],
    fields_of: Callable[[str], set[str]],
    selection_of: Callable[[str, str], set[str]],
    responsible_field: str = "",
    activity_type_id: int | None = None,
) -> tuple[list[tuple[str, dict[str, Any], str]], str]:
    """Return ([(odoo_model, vals, ref)], problem). A problem means: skip and tell the user."""
    spec = auto.get("automation") or {}
    target = auto.get("target_model") or ""
    label = (auto.get("label") or "Automation")[:80]
    if not spec:
        return [], "App Studio cannot build this kind of automation yet."
    model_id = model_ids.get(target)
    if not model_id:
        return [], f"{target or 'The target record'} was not found in this database."

    rule_fields = fields_of("base.automation")
    server_fields = fields_of("ir.actions.server")
    target_fields = fields_of(target)
    if not rule_fields:
        return [], "Automated actions are not installed in this database (base_automation)."
    if "activity_summary" not in server_fields:
        return [], "To-do automations need the Discuss app (mail) installed."
    if "next_activity" not in selection_of("ir.actions.server", "state"):
        return [], "This Odoo version has no 'schedule a to-do' action type."
    if spec["when"] not in selection_of("base.automation", "trigger"):
        return [], f"This Odoo version does not offer the '{spec['when']}' trigger."
    if "activity_ids" not in target_fields:
        return [], f"{target} cannot hold to-dos yet (it needs chatter and activities)."
    responsible = responsible_field or next((f for f in _RESPONSIBLE if f in target_fields), "")
    if not responsible:
        return [], f"{target} has no responsible-user field to assign the to-do to."

    server: dict[str, Any] = {
        "name": f"{label} (action)",
        "model_id": model_id,
        "state": "next_activity",
        "activity_summary": spec.get("summary") or label,
        "activity_user_type": "generic",
        "activity_user_field_name": responsible,
    }
    if activity_type_id:
        server["activity_type_id"] = activity_type_id

    rule: dict[str, Any] = {"name": label, "model_id": model_id, "trigger": spec["when"]}
    if spec["when"] == "on_time":
        date_field = spec.get("date_field") or ""
        field_id = field_ids.get((target, date_field))
        if not field_id or "trg_date_id" not in rule_fields:
            return [], "The date field this automation depends on was not found."
        if "day" not in selection_of("base.automation", "trg_date_range_type"):
            return [], "This Odoo version cannot delay an automation by days."
        offset = int(spec.get("offset_days") or 0)
        rule.update(trg_date_id=field_id, trg_date_range_type="day")
        if "trg_date_range_mode" in rule_fields:
            rule.update(
                trg_date_range=abs(offset),
                trg_date_range_mode="before" if offset < 0 else "after",
            )
        else:
            rule["trg_date_range"] = offset  # older versions: negative means before
    if "action_server_ids" in rule_fields:
        rule["action_server_ids"] = [(6, 0, [_SERVER])]
    elif "action_server_id" in rule_fields:
        rule["action_server_id"] = _SERVER
    else:
        return [], "Could not link the action to the automation on this Odoo version."
    return [
        ("ir.actions.server", _keep(server, server_fields), "server"),
        ("base.automation", _keep(rule, rule_fields), "automation"),
    ], ""


def substitute_refs(vals: dict[str, Any], created: dict[str, int]) -> dict[str, Any]:
    """Replace the '@server' placeholder with the id created in the previous step."""
    sid = created.get("server")

    def fix(v: Any) -> Any:
        if v == _SERVER:
            return sid
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, tuple):
            return tuple(fix(x) for x in v)
        return v

    return {k: fix(v) for k, v in vals.items()}