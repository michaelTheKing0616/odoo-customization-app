"""Run loop. Writes happen only after a hash-bound human approval, inside EXECUTE."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.agent_runtime.memory import MemoryBook, MemoryItem
from app.agent_runtime.phases import ENGINE_ONLY, PHASES, IllegalTransition, assert_transition
from app.agent_runtime.prompt import (
    AssembledContext,
    Exchange,
    PromptRejected,
    ToolExchange,
    assemble_context,
)
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
    _transcript: list[Exchange] = field(default_factory=list)

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
        tool_counts, and transcript. The transcript is the recorded
        exchanges. Nested values are copies. Pending memory, role notes,
        episodic memory, and global knowledge are not included.
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
            "transcript": _transcript_to_payload(self._transcript),
        }

    @classmethod
    def restore(cls, payload: dict[str, Any]) -> RunState:
        """Rebuild a run from an exported state dict.

        Inputs: the dict from export_state. Every existing export key is
        required. ``transcript`` may be omitted; that restores an empty
        transcript. A transcript list is copied onto the run as exchanges.
        Outputs: a new RunState. Nested lists are copies, so the payload
        and the restored run do not share objects.
        Side effects: none. Tools are not replayed. Nothing is written
        to disk or a database. The runtime that later uses this run binds
        the restored exchanges. A process kill still drops the run unless
        the caller kept this dict.
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
        transcript = _transcript_from_payload(payload)
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
            _transcript=transcript,
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


def _transcript_to_payload(exchanges: list[Exchange]) -> list[dict[str, Any]]:
    """Copy recorded exchanges into plain objects.

    Inputs: the run's exchange list.
    Outputs: a new list of dicts. Tool args and results are copies.
    Side effects: none.
    """
    copied: list[dict[str, Any]] = []
    for exchange in exchanges:
        copied.append(
            {
                "user": exchange.user,
                "assistant": exchange.assistant,
                "tools": [
                    {
                        "call_id": tool.call_id,
                        "name": tool.name,
                        "args": copy.deepcopy(tool.args),
                        "result": copy.deepcopy(tool.result),
                    }
                    for tool in exchange.tools
                ],
                "assumption": exchange.assumption,
                "evidence_id": exchange.evidence_id,
            }
        )
    return copied


def _transcript_from_payload(payload: Mapping[str, Any]) -> list[Exchange]:
    """Read exchanges from an exported state dict.

    Inputs: the export payload. A missing ``transcript`` key is an empty
    list. A present key must be a list of exchange objects.
    Outputs: new Exchange values. Tool args and results are copies.
    Side effects: none. Tools are not called.
    Raises ValueError when the transcript has the wrong shape.
    """
    if "transcript" not in payload:
        return []
    records = payload["transcript"]
    if not isinstance(records, list):
        raise ValueError("transcript must be a list")
    exchanges: list[Exchange] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        exchange = _exchange_from_record(record, index)
        for tool in exchange.tools:
            if tool.call_id in seen:
                raise ValueError(f"duplicate tool call id {tool.call_id}")
            seen.add(tool.call_id)
        exchanges.append(exchange)
    return exchanges


def _exchange_from_record(record: Any, index: int) -> Exchange:
    label = f"transcript[{index}]"
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an object")
    tools_raw = record.get("tools")
    if not isinstance(tools_raw, list):
        raise ValueError(f"{label}.tools must be a list")
    tools = [
        _tool_from_record(tool, f"{label}.tools[{tool_index}]")
        for tool_index, tool in enumerate(tools_raw)
    ]
    try:
        return Exchange(
            user=_require_str(record.get("user"), f"{label}.user"),
            assistant=_require_str(record.get("assistant"), f"{label}.assistant"),
            tools=tuple(tools),
            assumption=_require_str(record.get("assumption"), f"{label}.assumption"),
            evidence_id=_require_str(record.get("evidence_id"), f"{label}.evidence_id"),
        )
    except PromptRejected as exc:
        raise ValueError(f"{label} {exc}") from exc


def _tool_from_record(record: Any, label: str) -> ToolExchange:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an object")
    args = record.get("args")
    result = record.get("result")
    if not isinstance(args, dict):
        raise ValueError(f"{label}.args must be an object")
    if not isinstance(result, dict):
        raise ValueError(f"{label}.result must be an object")
    try:
        return ToolExchange(
            call_id=_require_str(record.get("call_id"), f"{label}.call_id"),
            name=_require_str(record.get("name"), f"{label}.name"),
            args=copy.deepcopy(args),
            result=copy.deepcopy(result),
        )
    except PromptRejected as exc:
        raise ValueError(f"{label} {exc}") from exc


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


def _combine_memory(book_text: str, supplied: str) -> str:
    """Join confirmed book text with a caller-supplied memory string.

    Inputs: confirmed tenant or database lines, and the optional caller
    string. Either may be empty.
    Outputs: book text, then the caller string, separated by a newline
    when both are present. Empty when both are empty.
    Side effects: none.
    """
    if book_text and supplied:
        return f"{book_text}\n{supplied}"
    return book_text or supplied


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
        self._transcripts: dict[int, list[Exchange]] = {}
        self._memory: dict[int, MemoryBook] = {}

    def start(self) -> RunState:
        state = RunState()
        state.events.append({"kind": "phase", "phase": "INTAKE"})
        return state

    def record_exchange(self, state: RunState, exchange: Exchange) -> None:
        """Append one turn to this run's transcript.

        Inputs: the run state and one exchange.
        Outputs: none.
        Side effects: stores a deep copy on this run. ``export_state``
        includes that copy. The runtime that uses the run reads the same
        list. Does not call a model and does not write to disk or a database.
        A process kill still drops the run unless the caller kept the
        exported dict.
        """
        if not isinstance(exchange, Exchange):
            raise TypeError("exchange must be an Exchange")
        stored = copy.deepcopy(exchange)
        bucket = self._bind_transcript(state)
        seen = {tool.call_id for item in bucket for tool in item.tools}
        for tool in stored.tools:
            if tool.call_id in seen:
                raise PromptRejected(f"duplicate tool call id {tool.call_id}")
            seen.add(tool.call_id)
        bucket.append(stored)

    def memory_book(self, state: RunState) -> MemoryBook:
        """Return the in-process memory book for this run object.

        Inputs: the run state.
        Outputs: the book created for that object. A new run gets an empty
        book. Working notes and pending proposals live here, not in
        ``state.facts``. Confirmed tenant and database facts are read by
        ``build_context``. Pending items, episodic memory, and global
        knowledge are not.
        Side effects: stores the book on this runtime, keyed by the state
        object. A restored run is a new object and starts with an empty
        book. Nothing is written to disk or a database.
        """
        return self._memory.setdefault(id(state), MemoryBook())

    def confirm_memory(self, state: RunState, item_id: str, *, confirmed_by: str) -> MemoryItem:
        """Confirm one pending item. This is not a model tool.

        Inputs: the run, the item id from ``memory_propose``, and the
        human identity.
        Outputs: the confirmed item. A role note cannot be confirmed.
        Side effects: updates that item on the run book. Does not change
        ``state.facts``. Does not write global knowledge. Does not call
        a model. Does not count as a tool call.
        """
        return self.memory_book(state).confirm(item_id, confirmed_by=confirmed_by)

    def record_working(self, state: RunState, text: str) -> MemoryItem:
        """Record engine-trusted working memory. This is not a model tool.

        Inputs: the run and the note text.
        Outputs: a confirmed working item. It is not a tenant fact.
        Side effects: appends the note on the run book. Does not call a
        model. Does not write global knowledge.
        """
        return self.memory_book(state).record_working(text)

    def build_context(
        self,
        state: RunState,
        *,
        window_tokens: int,
        count_tokens: Callable[[str], int],
        tools: Sequence[Mapping[str, str]] = (),
        skills: str = "",
        memory: str = "",
        overlay: str = "",
        overlay_runtime_edited: bool = False,
        core_runtime_edited: bool = False,
        core: str | None = None,
        production: bool = False,
        explorer: bool = False,
        tier: str | None = None,
        secrets: Sequence[str] = (),
    ) -> AssembledContext:
        """Assemble the model context for turns recorded on this run.

        Inputs: run state, window size, and a local token counter. Layers and
        budgets are applied by ``assemble_context``. The transcript is the
        one recorded with ``record_exchange`` for this state object. After
        restore, this runtime binds the exchanges carried on the run. The
        memory layer is confirmed tenant and database text from this run's
        book, then any caller-supplied memory string. Pending items, refused
        role notes, episodic memory, and global knowledge are omitted.
        Outputs: messages, the scrubbed cacheable prefix, and budget counts.
        The memory layer is fitted to 5 percent of the window.
        Side effects: binds the run's exchange list onto this runtime.
        Does not mutate the exchanges, the book, or the run fields.
        Does not replay tools. Does not call a model provider.
        """
        exchanges = tuple(self._bind_transcript(state))
        book = self._memory.get(id(state))
        book_text = book.prompt_text() if book is not None else ""
        return assemble_context(
            state,
            exchanges,
            window_tokens=window_tokens,
            count_tokens=count_tokens,
            tools=tools,
            skills=skills,
            memory=_combine_memory(book_text, memory),
            overlay=overlay,
            overlay_runtime_edited=overlay_runtime_edited,
            core_runtime_edited=core_runtime_edited,
            core=core,
            production=production,
            explorer=explorer,
            tier=tier,
            secrets=secrets,
        )

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

    def _bind_transcript(self, state: RunState) -> list[Exchange]:
        """Attach this run's exchanges to the runtime that uses it.

        Inputs: the run state. Recorded and restored exchanges already sit
        on that object.
        Outputs: the list ``build_context`` reads for this object.
        Side effects: stores that list on this runtime, keyed by the state
        object. Does not replay tools. Does not write to disk or a database.
        """
        bound = self._transcripts.get(id(state))
        if bound is None:
            bound = state._transcript
            self._transcripts[id(state)] = bound
        return bound

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
            return memory_propose_result(args, self.memory_book(state))
        if name == "changeset_status":
            return {"phase": state.phase, "applied": state.applied, "status": state.status}
        if name == "verification_report_get":
            return {"report": state.report, "applied": state.applied}
        if name == "propose_rollback":
            return {"ok": True, "kind": "rollback_draft", "applied": False}
        if name == "skill_load":
            if self.grant is None:
                return {"ok": False, "code": "GRANT_REQUIRED", "loaded": []}
            from app.skills.router import route_skills

            phrase = str(args.get("phrase") or args.get("query") or "")
            route = route_skills(phrase, self.grant)
            return {
                "ok": True,
                "loaded": list(route.skill_ids),
                "refused": list(route.refused),
                "dropped": list(route.dropped),
                "ops": sorted(route.grant.ops_allowed),
            }
        return {"ok": True, "tool": name}
