"""Run loop. Writes happen only after a hash-bound human approval, inside EXECUTE."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.agent_runtime.phases import ENGINE_ONLY, IllegalTransition, assert_transition
from app.agent_runtime.tools import ToolDenied, assert_tool_allowed, wrap_untrusted
from app.changeset.executor import apply as engine_apply
from app.changeset.executor import changeset_fingerprint
from app.changeset.policy import self_approval_allowed
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
            return {"ok": True, "mode": "static", "writes": 0}
        if name == "submit_changeset":
            return {"ok": True, "pending_approval": True, "writes": 0}
        if name == "describe_model":
            return {"model": args.get("model"), "fields": []}
        if name == "schema_search":
            return {"hits": []}
        if name == "env_info":
            return {"transport": "json2"}
        if name == "ask_user":
            return {"suspended": True, "questions": args.get("questions") or []}
        if name == "changeset_status":
            return {"phase": state.phase, "applied": state.applied, "status": state.status}
        if name == "verification_report_get":
            return {"report": state.report, "applied": state.applied}
        if name == "propose_rollback":
            return {"ok": True, "kind": "rollback_draft", "applied": False}
        return {"ok": True, "tool": name}
