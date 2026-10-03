"""Model-facing tools. There is no apply tool. Results are untrusted data."""

from __future__ import annotations

import json
from typing import Any

DATA_SAMPLE_MAX_ROWS = 5
ASK_USER_MAX_QUESTIONS = 3

INSPECTION = frozenset(
    {
        "env_info",
        "schema_search",
        "describe_model",
        "describe_field",
        "view_get",
        "view_test_xpath",
        "menu_action_find",
        "group_describe",
        "access_explain",
        "data_count",
        "data_sample",
        "data_aggregate",
        "domain_validate",
        "find_usages",
        "automation_list",
        "action_list",
        "cron_list",
        "template_list",
        "sequence_list",
        "report_list",
        "settings_describe",
        "module_list",
        "config_registry_describe",
        "search_docs",
        "skill_search",
        "skill_load",
        "skill_read",
        "ask_user",
        "memory_propose",
    }
)

PLANNING_CARD = frozenset(
    {
        "changeset_create",
        "changeset_add_op",
        "changeset_update_op",
        "changeset_remove_op",
        "changeset_reorder",
        "describe_op",
        "validate",
        "simulate",
        "render",
        "submit_changeset",
    }
)

# Already exposed on the phase profiles. The T8-TOOLS list does not include them.
# They stay callable. None of them apply a change-set.
LEGACY_PHASE_ALIASES = frozenset(
    {
        "changeset_validate",
        "changeset_simulate",
        "changeset_render",
    }
)

PLANNING = PLANNING_CARD | LEGACY_PHASE_ALIASES

REPORT = frozenset({"changeset_status", "verification_report_get", "propose_rollback"})

REGISTERED_TOOLS = INSPECTION | PLANNING_CARD | REPORT

# Names a jailbroken model might invent. None of these exist.
FORBIDDEN = frozenset(
    {
        "apply",
        "changeset_apply",
        "rpc.write",
        "execute_kw",
        "unlink",
        "sql",
    }
)

PHASE_TOOLS: dict[str, frozenset[str]] = {
    "INTAKE": frozenset(),
    "DISCOVER": INSPECTION,
    "CLARIFY": frozenset({"ask_user"}),
    "PLAN": INSPECTION | PLANNING,
    "VALIDATE": frozenset(
        {"changeset_validate", "validate", "changeset_update_op", "changeset_remove_op"}
    ),
    "CRITIC": INSPECTION,
    "SIMULATE": frozenset({"changeset_simulate", "simulate"}),
    "PRESENT": frozenset({"submit_changeset", "changeset_render", "render"}),
    "AWAITING_APPROVAL": frozenset(),
    "EXECUTE": frozenset(),
    "VERIFY": frozenset(),
    "REPORT": REPORT,
    "CANCELLED": frozenset(),
    "ABORTED": frozenset(),
}


class ToolDenied(Exception):
    """The model asked for a tool the active phase does not expose."""


def registered_tool_names() -> frozenset[str]:
    """Return the T8-TOOLS names.

    Inputs: none.
    Outputs: inspection, planning, and post-submit names from the card.
    Side effects: none. Legacy phase aliases are excluded.
    """
    return REGISTERED_TOOLS


def tools_for(phase: str) -> frozenset[str]:
    if phase not in PHASE_TOOLS:
        raise ToolDenied(f"unknown phase {phase!r}")
    exposed = PHASE_TOOLS[phase]
    overlap = exposed & FORBIDDEN
    if overlap:
        raise ToolDenied(f"phase {phase} exposes forbidden tools {sorted(overlap)}")
    return exposed


def assert_tool_allowed(phase: str, name: str) -> None:
    if name in FORBIDDEN or name not in tools_for(phase):
        raise ToolDenied(f"tool {name!r} is not available in phase {phase}")


def wrap_untrusted(
    *,
    name: str,
    evidence_id: str,
    payload: Any,
    tainted: bool,
) -> dict[str, Any]:
    """Tool results are data. They cannot become instructions or an approval."""
    body = json.dumps(payload, sort_keys=True, default=str)
    return {
        "name": name,
        "evidence_id": evidence_id,
        "tainted": tainted,
        "untrusted_data": body,
        "instruction": None,
    }


def data_sample_result(args: dict[str, Any]) -> dict[str, Any]:
    """Return a local row sample capped at five rows.

    Inputs: tool arguments. ``rows`` is an optional list.
    Outputs: ``rows`` (length at most 5), ``row_count``, and ``limit``.
    Side effects: none. Does not open a network connection or call Odoo.
    """
    raw_rows = args.get("rows")
    rows = list(raw_rows) if isinstance(raw_rows, list) else []
    capped = rows[:DATA_SAMPLE_MAX_ROWS]
    return {
        "rows": capped,
        "row_count": len(capped),
        "limit": DATA_SAMPLE_MAX_ROWS,
        "live": False,
    }


def ask_user_result(args: dict[str, Any]) -> dict[str, Any]:
    """Suspend for at most three questions.

    Inputs: tool arguments. ``questions`` is an optional list.
    Outputs: ``suspended`` true and at most three questions.
    Side effects: none.
    """
    raw = args.get("questions")
    questions = list(raw)[:ASK_USER_MAX_QUESTIONS] if isinstance(raw, list) else []
    return {"suspended": True, "questions": questions}


def memory_propose_result(args: dict[str, Any]) -> dict[str, Any]:
    """Return a pending memory proposal.

    Inputs: tool arguments. A confirmation flag in the arguments is ignored.
    Outputs: ``status`` pending and ``confirmed`` false.
    Side effects: none. Does not write memory and does not confirm the proposal.
    """
    return {
        "status": "pending",
        "confirmed": False,
        "proposal": args.get("proposal", args.get("text")),
    }
