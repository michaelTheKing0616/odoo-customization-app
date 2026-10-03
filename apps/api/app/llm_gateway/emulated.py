"""Emulated tool calls. A partial or ambiguous action is never executed."""

from __future__ import annotations

from app.llm_gateway.normalize import ArgsRejected, parse_tool_args


class EmulatedRejected(Exception):
    pass


def parse_emulated_json(text: str) -> dict[str, object]:
    try:
        payload = parse_tool_args(text)
    except ArgsRejected as exc:
        raise EmulatedRejected(exc.reason) from exc
    action = payload.get("action")
    if not isinstance(action, dict):
        raise EmulatedRejected("missing action")
    if "final" in action and "tool" in action:
        raise EmulatedRejected("ambiguous")
    if "final" in action:
        if not isinstance(action["final"], str):
            raise EmulatedRejected("final must be text")
        return {"final": action["final"]}
    tool = action.get("tool")
    args = action.get("args")
    if not isinstance(tool, str) or not isinstance(args, dict):
        raise EmulatedRejected("partial")
    return {"tool": tool, "args": args}
