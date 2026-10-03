"""Model-facing tools. There is no apply tool. Results are untrusted data."""

from __future__ import annotations

import json
from typing import Any

INSPECTION = frozenset(
    {
        "env_info",
        "schema_search",
        "describe_model",
        "describe_field",
        "data_count",
        "find_usages",
        "ask_user",
        "skill_search",
    }
)

PLANNING = frozenset(
    {
        "changeset_create",
        "changeset_add_op",
        "changeset_update_op",
        "changeset_remove_op",
        "changeset_validate",
        "changeset_simulate",
        "changeset_render",
        "submit_changeset",
    }
)

REPORT = frozenset({"changeset_status", "verification_report_get", "propose_rollback"})

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
    "VALIDATE": frozenset({"changeset_validate", "changeset_update_op", "changeset_remove_op"}),
    "CRITIC": INSPECTION,
    "SIMULATE": frozenset({"changeset_simulate"}),
    "PRESENT": frozenset({"submit_changeset", "changeset_render"}),
    "AWAITING_APPROVAL": frozenset(),
    "EXECUTE": frozenset(),
    "VERIFY": frozenset(),
    "REPORT": REPORT,
    "CANCELLED": frozenset(),
    "ABORTED": frozenset(),
}


class ToolDenied(Exception):
    """The model asked for a tool the active phase does not expose."""


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
