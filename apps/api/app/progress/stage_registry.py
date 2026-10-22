"""Named stages for live progress (T4-PROG). Unknown names are rejected at emit time."""

from __future__ import annotations

GENERATION_STAGES: tuple[str, ...] = (
    "retrieve_context",
    "extract_entities",
    "define_fields",
    "map_relationships",
    "build_workflow",
    "add_automations",
    "finalize_draft",
)

EXPERT_STAGES: tuple[str, ...] = (
    "expert_classify",
    "expert_retrieve",
    "expert_ground",
    "expert_answer",
)

BULK_STAGES: tuple[str, ...] = (
    "bulk_resolve",
    "bulk_sample",
    "bulk_execute",
    "bulk_report",
)

DASHBOARD_STAGES: tuple[str, ...] = (
    "dash_plan",
    "dash_query",
    "dash_render",
    "dash_save",
)

CONTROL_STAGES: tuple[str, ...] = ("tool_call_limit",)

KNOWN_STAGES: frozenset[str] = frozenset(
    (*GENERATION_STAGES, *EXPERT_STAGES, *BULK_STAGES, *DASHBOARD_STAGES, *CONTROL_STAGES)
)


def generation_stage_for_step(step: int) -> str:
    idx = max(0, min(step, len(GENERATION_STAGES) - 1))
    return GENERATION_STAGES[idx]
