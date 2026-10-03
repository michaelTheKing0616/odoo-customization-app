"""Run loop. Writes happen only after a hash-bound human approval, inside EXECUTE."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from app.agent_runtime.phases import ENGINE_ONLY, PHASES, IllegalTransition, assert_transition
from app.agent_runtime.tools import (
    ToolDenied,
    ask_user_result,
    assert_tool_allowed,
    data_sample_result,
    memory_propose_result,
    wrap_untrusted,
)
from app.changeset.executor import apply as engine_apply
from app.changeset.executor import changeset_fingerprint
from app.changeset.policy import self_approval_allowed
from app.changeset.simulate import simulate
from app.changeset.validate import validate

MAX_STEPS = 40
MAX_TOOL_CALLS = 120
REPEAT_WARN = 3
REPEAT_ABORT = 4


@dataclass
class RunState:
    phase: str = "INTAKE"
    step: int = 0
    tool_calls: int = 0
    changeset: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    plan_hash: str | None = None
    approved_hash: str | None = None
    applied: bool = False
    report: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "running"
    loop_warnings: int = 0
    _tool_counts: dict[str, int] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "step": self.step,
            "applied": self.applied,
            "status": self.status,
            "plan_hash": self.plan_hash,
            "approved_hash": self.approved_hash,
            "op_count": len(self.changeset),
            "tool_calls": self.tool_calls,
        }

    def export_state(self) -> dict[str, Any]:
        """Copy the fields this run already holds.

        Inputs: this RunState.
        Outputs: phase, step, tool_calls, changeset, facts, plan_hash,
        approved_hash, applied, report, events, status, loop_warnings,
        and tool_counts. Nested values are copies.
        Side effects: none. Nothing is written to disk or a database.
        A process kill still drops the run unless the caller kept this dict.
        """
        return {
            "phase": self.phase,
            "step": self.step,
            "tool_calls": self.tool_calls,
            "changeset": copy.deepcopy(self.changeset),
            "facts": copy.deepcopy(self.facts),
            "plan_hash": self.plan_hash,
            "approved_hash": self.approved_hash,
            "applied": self.applied,
            "report": copy.deepcopy(self.report),
            "events": copy.deepcopy(self.events),
            "status": self.status,
            "loop_warnings": self.loop_warnings,
            "tool_counts": dict(self._tool_counts),
        }

    @classmethod
    def restore(cls, payload: dict[str, Any]) -> RunState:
        """Rebuild a run from an exported state dict.

        Inputs: the dict from export_state. Every key is required.
        Outputs: a new RunState. Nested lists are copies, so the payload
        and the restored run do not share objects.
        Side effects: none. Tools are not replayed. Nothing is written
        to disk or a database.
        Raises ValueError when the payload is incomplete or the wrong shape.
        Raises IllegalTransition when phase is not in the machine.
        """
        if not isinstance(payload, dict):
            raise ValueError("exported state must be an object")
        missing = [key for key in _EXPORT_KEYS if key not in payload]
        if missing:
            raise ValueError(f"exported state is missing {missing}")
        phase = payload["phase"]
        if not isinstance(phase, str) or phase not in PHASES:
            raise IllegalTransition(f"unknown phase {phase!r}")
        report = payload["report"]
        if report is not None and not isinstance(report, dict):
            raise ValueError("report must be an object or null")
        raw_counts = payload["tool_counts"]
        if not isinstance(raw_counts, dict):
            raise ValueError("tool_counts must be an object")
        tool_counts: dict[str, int] = {}
        for key, count in raw_counts.items():
            if not isinstance(key, str):
                raise ValueError("tool_counts keys must be strings")
            tool_counts[key] = _require_int(count, "tool_counts value")
        return cls(
            phase=phase,
            step=_require_int(payload["step"], "step"),
            tool_calls=_require_int(payload["tool_calls"], "tool_calls"),
            changeset=_copy_records(payload["changeset"], label="changeset"),
            facts=_copy_records(payload["facts"], label="facts"),
            plan_hash=_optional_str(payload["plan_hash"], "plan_hash"),
            approved_hash=_optional_str(payload["approved_hash"], "approved_hash"),
            applied=_require_bool(payload["applied"], "applied"),
            report=copy.deepcopy(report) if report is not None else None,
            events=_copy_records(payload["events"], label="events"),
            status=_require_str(payload["status"], "status"),
            loop_warnings=_require_int(payload["loop_warnings"], "loop_warnings"),
            _tool_counts=tool_counts,
        )


_EXPORT_KEYS = (
    "phase",
    "step",
    "tool_calls",
    "changeset",
    "facts",
    "plan_hash",
    "approved_hash",
    "applied",
    "report",
    "events",
    "status",
    "loop_warnings",
    "tool_counts",
)


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an int")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a bool")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _optional_str(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, label)


def _copy_records(records: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError(f"{label} must be a list")
    copied: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        copied.append(copy.deepcopy(record))
    return copied


class BudgetExceeded(Exception):
    pass


class LoopDetected(Exception):
    pass


def _canonical_call(name: str, args: dict[str, Any]) -> str:
    return name + ":" + json.dumps(args, sort_keys=True, default=str)


def _args_tainted(args: dict[str, Any]) -> bool:
    blob = json.dumps(args, default=str)
    return _looks_like_instruction(blob)


def _looks_like_instruction(text: str) -> bool:
    low = text.lower()
    markers = (
        "ignore previous",
        "ignore policy",
        "grant admin",
        "system:",
        "you are now",
    )
    return any(marker in low for marker in markers)


class AgentRuntime:
    """Scripted or live models both enter through call_tool / complete_phase.

    Neither method can apply a change-set. Approval is a separate method the
    HTTP approval service calls after a human decision.
    """

    def __init__(
        self,
        grant: Any | None = None,
        requester_ops: frozenset[str] | None = None,
    ) -> None:
        self.grant = grant
        self.requester_ops = requester_ops

    def start(self) -> RunState:
        state = RunState()
        state.events.append({"kind": "phase", "phase": "INTAKE"})
        return state

    def complete_phase(self, state: RunState, nxt: str) -> RunState:
        self._guard(state)
        if nxt in ENGINE_ONLY:
            raise IllegalTransition(f"the model cannot enter {nxt}")
        assert_transition(state.phase, nxt)
        state.phase = nxt
        state.step += 1
        state.events.append({"kind": "phase", "phase": nxt})
        if nxt == "PRESENT":
            state.plan_hash = changeset_fingerprint(state.changeset)
            assert_transition("PRESENT", "AWAITING_APPROVAL")
            state.phase = "AWAITING_APPROVAL"
            state.status = "awaiting_approval"
            state.events.append({"kind": "phase", "phase": "AWAITING_APPROVAL"})
        return state

    def call_tool(self, state: RunState, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        self._guard(state)
        payload = dict(args or {})
        assert_tool_allowed(state.phase, name)
        key = _canonical_call(name, payload)
        state._tool_counts[key] = state._tool_counts.get(key, 0) + 1
        count = state._tool_counts[key]
        state.tool_calls += 1
        if count == REPEAT_WARN:
            state.loop_warnings += 1
            state.events.append({"kind": "loop_detected", "tool": name, "count": count})
            return wrap_untrusted(
                name=name,
                evidence_id=f"E{state.tool_calls}",
                payload={"code": "LOOP_DETECTED", "message": "Change approach. Do not repeat this call."},
                tainted=False,
            )
        if count >= REPEAT_ABORT or state.loop_warnings >= 2:
            state.phase = "ABORTED"
            state.status = "aborted_loop"
            state.events.append({"kind": "aborted", "reason": "loop"})
            raise LoopDetected(name)

        tainted = _args_tainted(payload)
        result = self._dispatch(state, name, payload)
        wrapped = wrap_untrusted(
            name=name,
            evidence_id=f"E{state.tool_calls}",
            payload=result,
            tainted=tainted,
        )
        state.events.append({"kind": "tool", "name": name, "tainted": tainted})
        return wrapped

    def approve(
        self,
        state: RunState,
        *,
        plan_hash: str,
        approver_id: str,
        requester_id: str,
        known_models: set[str],
    ) -> dict[str, Any]:
        """Human approval. This is the only path into EXECUTE."""
        if state.phase != "AWAITING_APPROVAL":
            raise IllegalTransition("approval is only valid while awaiting approval")
        if state.plan_hash is None or plan_hash != state.plan_hash:
            state.events.append({"kind": "approval_rejected", "reason": "hash_mismatch"})
            return {"ok": False, "error": "APPROVAL_HASH_MISMATCH", "applied": False}
        if changeset_fingerprint(state.changeset) != plan_hash:
            state.events.append({"kind": "approval_rejected", "reason": "hash_mismatch"})
            return {"ok": False, "error": "APPROVAL_HASH_MISMATCH", "applied": False}

        report = validate(state.changeset, known_models=known_models)
        state.report = report
        if not report["valid"]:
            return {"ok": False, "error": "INVALID", "applied": False, "report": report}
        risk = str(report["max_risk"])
        if risk == "R4":
            state.events.append({"kind": "approval_rejected", "reason": "R4"})
            return {"ok": False, "error": "RISK_R4", "applied": False}
        if not self_approval_allowed(risk) and approver_id == requester_id:
            state.events.append({"kind": "approval_rejected", "reason": "self_approval"})
            return {"ok": False, "error": "SELF_APPROVAL", "applied": False}

        state.approved_hash = plan_hash
        assert_transition("AWAITING_APPROVAL", "EXECUTE")
        state.phase = "EXECUTE"
        state.events.append({"kind": "phase", "phase": "EXECUTE"})
        result = engine_apply(state.changeset, mode="T")
        verified = result.get("status") == "VERIFIED"
        state.applied = verified
        assert_transition("EXECUTE", "VERIFY")
        state.phase = "VERIFY"
        state.events.append({"kind": "phase", "phase": "VERIFY"})
        state.events.append({"kind": "verified", "ok": verified})
        assert_transition("VERIFY", "REPORT")
        state.phase = "REPORT"
        state.status = "verified" if verified else "verify_failed"
        state.events.append({"kind": "phase", "phase": "REPORT"})
        return {"ok": verified, "applied": verified, "result": result, "status": state.status}

    def _guard(self, state: RunState) -> None:
        if state.status in {"aborted_loop", "cancelled"}:
            raise BudgetExceeded(state.status)
        if state.step >= MAX_STEPS:
            state.phase = "ABORTED"
            state.status = "aborted_budget"
            raise BudgetExceeded("max steps")
        if state.tool_calls >= MAX_TOOL_CALLS:
            state.phase = "ABORTED"
            state.status = "aborted_budget"
            raise BudgetExceeded("max tool calls")
        if state.phase in {"EXECUTE", "VERIFY"}:
            raise ToolDenied("the model has no tools during execute or verify")

    def _dispatch(self, state: RunState, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "changeset_add_op":
            op = args.get("op")
            if not isinstance(op, dict) or "type" not in op:
                return {"ok": False, "code": "SCHEMA_INVALID"}
            record_text = str(args.get("record_text") or "")
            if _looks_like_instruction(record_text):
                state.events.append({"kind": "injection_ignored"})
                return {"ok": False, "code": "IGNORED_INSTRUCTION", "added": False}
            if self.grant is not None:
                from app.bots.grant import decide

                denied = decide(self.grant, op, requester_ops=self.requester_ops)
                if denied:
                    state.events.append({"kind": "grant_denied", "reason": denied})
                    return {"ok": False, "code": "GRANT_DENIED", "reason": denied, "added": False}
            state.changeset.append(op)
            return {"ok": True, "index": len(state.changeset) - 1, "added": True}
        if name == "changeset_create":
            state.changeset = []
            return {"ok": True, "created": True}
        if name == "changeset_remove_op":
            index = int(args.get("index", -1))
            if 0 <= index < len(state.changeset):
                state.changeset.pop(index)
                return {"ok": True}
            return {"ok": False, "code": "UNKNOWN_OP"}
        if name == "changeset_validate":
            return validate(state.changeset, known_models=set(args.get("known_models") or []))
        if name == "changeset_simulate":
            report = simulate(list(state.changeset))
            return {
                "ok": report.passed,
                "mode": "static",
                "writes": 0,
                "phase": report.phase,
                "live": False,
                "recorded": report.recorded,
            }
        if name == "submit_changeset":
            return {"ok": True, "pending_approval": True, "writes": 0}
        if name == "describe_model":
            return {"model": args.get("model"), "fields": []}
        if name == "schema_search":
            return {"hits": []}
        if name == "env_info":
            return {"transport": "json2"}
        if name == "ask_user":
            return ask_user_result(args)
        if name == "data_sample":
            return data_sample_result(args)
        if name == "memory_propose":
            return memory_propose_result(args)
        if name == "changeset_status":
            return {"phase": state.phase, "applied": state.applied, "status": state.status}
        if name == "verification_report_get":
            return {"report": state.report, "applied": state.applied}
        if name == "propose_rollback":
            return {"ok": True, "kind": "rollback_draft", "applied": False}
        return {"ok": True, "tool": name}
