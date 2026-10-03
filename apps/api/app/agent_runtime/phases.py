"""Phase machine. The model cannot skip a phase or call a tool outside the active profile."""

from __future__ import annotations

PHASES = (
    "INTAKE",
    "DISCOVER",
    "CLARIFY",
    "PLAN",
    "VALIDATE",
    "CRITIC",
    "SIMULATE",
    "PRESENT",
    "AWAITING_APPROVAL",
    "EXECUTE",
    "VERIFY",
    "REPORT",
    "CANCELLED",
    "ABORTED",
)

# Engine-only destinations. A model "end" turn may not name these.
ENGINE_ONLY = frozenset({"EXECUTE", "VERIFY", "AWAITING_APPROVAL"})

_LEGAL: dict[str, frozenset[str]] = {
    "INTAKE": frozenset({"DISCOVER", "CANCELLED"}),
    "DISCOVER": frozenset({"CLARIFY", "PLAN", "CANCELLED", "ABORTED"}),
    "CLARIFY": frozenset({"PLAN", "DISCOVER", "CANCELLED"}),
    "PLAN": frozenset({"VALIDATE", "CANCELLED", "ABORTED"}),
    "VALIDATE": frozenset({"CRITIC", "SIMULATE", "PLAN", "ABORTED"}),
    "CRITIC": frozenset({"PLAN", "SIMULATE"}),
    "SIMULATE": frozenset({"PRESENT", "PLAN"}),
    "PRESENT": frozenset({"AWAITING_APPROVAL"}),
    "AWAITING_APPROVAL": frozenset({"EXECUTE", "PLAN", "CANCELLED"}),
    "EXECUTE": frozenset({"VERIFY"}),
    "VERIFY": frozenset({"REPORT"}),
    "REPORT": frozenset(),
    "CANCELLED": frozenset(),
    "ABORTED": frozenset(),
}


class IllegalTransition(Exception):
    """Raised when a phase change is not in the legal table."""


def legal_targets(phase: str) -> frozenset[str]:
    if phase not in _LEGAL:
        raise IllegalTransition(f"unknown phase {phase!r}")
    return _LEGAL[phase]


def assert_transition(current: str, nxt: str) -> None:
    allowed = legal_targets(current)
    if nxt not in allowed:
        raise IllegalTransition(f"{current} -> {nxt} is not a legal transition")
