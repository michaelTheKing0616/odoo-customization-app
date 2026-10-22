"""LLM-free change-set CLI.

``python -m app.changeset.cli plan|validate|simulate|apply|rollback <file.json>``
runs the file on an in-process fake port. Apply and rollback call that port.
They do not open a socket and they do not call Odoo.

This module does not import an LLM package.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.changeset.dispatch import dispatch_op
from app.changeset.executor import apply, reset_journal
from app.changeset.handlers import apply_memory
from app.changeset.plan_card import render_plan_card
from app.changeset.rollback import undo
from app.changeset.simulate import simulate
from app.changeset.validate import validate

COMMANDS = ("plan", "validate", "simulate", "apply", "rollback")
_USAGE = "usage: python -m app.changeset.cli plan|validate|simulate|apply|rollback <file.json>"
_FILE_KEYS = frozenset(
    {
        "ops",
        "changeset",
        "goal",
        "assumptions",
        "environment",
        "known_models",
        "requester_id",
        "connection_id",
        "approvals",
    }
)


class ChangeSetCLIError(ValueError):
    """The JSON file is not a change-set this CLI can run."""


@dataclass(frozen=True, slots=True)
class ChangeSetFile:
    """One change-set file and the fields the five commands share.

    Inputs: produced by ``load_changeset``.
    Outputs: ops plus plan, validation, and rollback fields.
    Side effects: none. The object does not hold a connection.
    """

    ops: list[dict[str, Any]]
    goal: str
    assumptions: tuple[str, ...]
    environment: str
    known_models: frozenset[str]
    requester_id: str
    connection_id: str
    approvals: tuple[dict[str, str], ...]


class FakePort:
    """In-memory stand-in for an Odoo port.

    ``create`` and ``write`` append to lists on this object. There is no host,
    URL, or socket.
    """

    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.writes: list[tuple[str, list[int], dict[str, Any]]] = []

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create.

        Inputs: model name and values.
        Outputs: a 1-based id local to this object.
        Side effects: appends a copy of ``values``. Does not open a socket.
        """
        self.created.append((model, dict(values)))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Record one write.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: appends copies. Does not open a socket.
        """
        self.writes.append((model, list(ids), dict(values)))

    def calls(self) -> int:
        """How many create and write calls this port has seen.

        Inputs: none.
        Outputs: the call count.
        Side effects: none.
        """
        return len(self.created) + len(self.writes)

    def drop_replayed(self) -> None:
        """Forget rows this command replayed.

        Inputs: none.
        Outputs: none.
        Side effects: clears the in-memory lists. Does not open a socket.
        """
        self.created.clear()
        self.writes.clear()


def load_changeset(path: Path) -> ChangeSetFile:
    """Read a change-set JSON file.

    Inputs: path to a JSON array of ops, or an object with ``ops`` or
    ``changeset``. A connection URL is not a recognized key.
    Outputs: the loaded file.
    Side effects: reads the file. Does not open a socket.
    Raises ChangeSetCLIError when the document is not a change-set.
    """
    body = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(body, list):
        ops = _ops(body)
        return _file(ops, {})
    if not isinstance(body, dict):
        raise ChangeSetCLIError("change-set JSON must be an object or an array")
    unknown = sorted(set(body) - _FILE_KEYS)
    if unknown:
        raise ChangeSetCLIError(f"unknown keys: {unknown}")
    if "ops" in body and "changeset" in body and body["ops"] != body["changeset"]:
        raise ChangeSetCLIError("ops and changeset disagree")
    raw_ops = body["ops"] if "ops" in body else body.get("changeset")
    return _file(_ops(raw_ops), body)


def run_command(command: str, loaded: ChangeSetFile, port: FakePort) -> dict[str, Any]:
    """Run one command against ``port``.

    Inputs: command name, the loaded file, and a fake port.
    Outputs: a JSON-ready object. ``ok`` is true only when that command's
    engine result succeeded. ``live_odoo`` is false.
    Side effects: apply writes the ops through ``port``. Rollback replays the
    ops onto ``port``, runs the in-memory inverse, then drops the replayed
    rows. Plan, validate, and simulate do not call the port. None of the
    commands open a socket.
    Raises ValueError from the engine when a command cannot run.
    """
    if command not in COMMANDS:
        raise ChangeSetCLIError(f"unknown command: {command}")
    if command == "plan":
        return _plan(loaded, port)
    if command == "validate":
        return _validate(loaded, port)
    if command == "simulate":
        return _simulate(loaded, port)
    if command == "apply":
        return _apply(loaded, port)
    return _rollback(loaded, port)


def main(argv: list[str] | None = None) -> int:
    """Run one CLI command.

    Inputs: argv without the program name. None uses ``sys.argv[1:]``.
    Outputs: 0 when the command succeeded, 2 for usage, 1 when the file or
    the engine rejected the run.
    Side effects: writes one JSON object to stdout, or usage text to stderr.
    A rejected file or engine run also writes one ``error: ...`` line to
    stderr. Does not open a socket and does not call Odoo.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in COMMANDS:
        print(_USAGE, file=sys.stderr)
        return 2
    command, raw_path = args
    try:
        loaded = load_changeset(Path(raw_path))
        payload = run_command(command, loaded, FakePort())
    except ChangeSetCLIError as exc:
        return _reject(command, exc)
    except Exception as exc:
        if not _engine_error(exc):
            raise
        return _reject(command, exc)
    _emit(payload)
    return 0 if payload.get("ok") else 1


def _file(ops: list[dict[str, Any]], body: dict[str, Any]) -> ChangeSetFile:
    requester = _text(body.get("requester_id"), default="operator", field="requester_id")
    return ChangeSetFile(
        ops=ops,
        goal=_text(body.get("goal"), default="Hand-written change-set", field="goal"),
        assumptions=_assumptions(body.get("assumptions")),
        environment=_text(body.get("environment"), default="staging", field="environment"),
        known_models=_known_models(body.get("known_models"), ops),
        requester_id=requester,
        connection_id=_text(body.get("connection_id"), default="fake", field="connection_id"),
        approvals=_approvals(body.get("approvals"), requester),
    )


def _ops(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ChangeSetCLIError("change-set must be a non-empty list of ops")
    ops: list[dict[str, Any]] = []
    for index, op in enumerate(raw):
        if not isinstance(op, dict) or not isinstance(op.get("type"), str) or not op["type"]:
            raise ChangeSetCLIError(f"op[{index}] needs a type string")
        ops.append(dict(op))
    return ops


def _text(value: Any, *, default: str, field: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ChangeSetCLIError(f"{field} must be a non-empty string")
    return value


def _assumptions(value: Any) -> tuple[str, ...]:
    if value is None:
        return ("The change-set was supplied as a file.",)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ChangeSetCLIError("assumptions must be a list of strings")
    return tuple(value)


def _known_models(value: Any, ops: list[dict[str, Any]]) -> frozenset[str]:
    found: set[str] = set()
    if value is not None:
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ChangeSetCLIError("known_models must be a list of strings")
        found.update(value)
    for op in ops:
        params = op.get("params")
        if isinstance(params, dict) and isinstance(params.get("model"), str) and params["model"]:
            found.add(params["model"])
    return frozenset(found)


def _approvals(value: Any, requester_id: str) -> tuple[dict[str, str], ...]:
    if value is None:
        return ({"approver_id": requester_id, "decision": "approve"},)
    if not isinstance(value, list) or not value:
        raise ChangeSetCLIError("approvals must be a non-empty list")
    approvals: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ChangeSetCLIError(f"approvals[{index}] must be an object")
        approver = item.get("approver_id")
        decision = item.get("decision")
        if not isinstance(approver, str) or not approver:
            raise ChangeSetCLIError(f"approvals[{index}].approver_id must be a string")
        if not isinstance(decision, str) or not decision:
            raise ChangeSetCLIError(f"approvals[{index}].decision must be a string")
        approvals.append({"approver_id": approver, "decision": decision})
    return tuple(approvals)


def _envelope(command: str, loaded: ChangeSetFile, port: FakePort, **fields: Any) -> dict[str, Any]:
    return {
        "ok": fields.pop("ok"),
        "command": command,
        "op_count": len(loaded.ops),
        "port": "fake",
        "port_calls": port.calls(),
        "socket_opened": False,
        "live_odoo": False,
        **fields,
    }


def _plan(loaded: ChangeSetFile, port: FakePort) -> dict[str, Any]:
    card = render_plan_card(
        loaded.ops,
        goal=loaded.goal,
        assumptions=loaded.assumptions,
        environment=loaded.environment,
    )
    return _envelope("plan", loaded, port, ok=True, result=card)


def _validate(loaded: ChangeSetFile, port: FakePort) -> dict[str, Any]:
    report = validate(loaded.ops, known_models=set(loaded.known_models))
    return _envelope("validate", loaded, port, ok=bool(report["valid"]), result=report)


def _simulate(loaded: ChangeSetFile, port: FakePort) -> dict[str, Any]:
    report = simulate(loaded.ops)
    body = asdict(report)
    return _envelope(
        "simulate",
        loaded,
        port,
        ok=bool(report.passed and not report.socket_opened and not report.live),
        result=body,
    )


def _apply(loaded: ChangeSetFile, port: FakePort) -> dict[str, Any]:
    reset_journal()
    result = apply(
        loaded.ops,
        mode="C",
        port=port,
        environment=loaded.environment,
        max_risk="R3",
        groups={"operator"},
    )
    created = [{"model": model, "values": values} for model, values in port.created]
    verified = result.get("status") == "VERIFIED" and port.calls() >= len(loaded.ops)
    return _envelope(
        "apply",
        loaded,
        port,
        ok=verified,
        status=result.get("status"),
        created=created,
        result=result,
    )


def _rollback(loaded: ChangeSetFile, port: FakePort) -> dict[str, Any]:
    reset_journal()
    for op in loaded.ops:
        dispatch_op(port, op, document=loaded.ops)
    store: dict[str, dict[str, Any]] = {}
    for op in loaded.ops:
        apply_memory(store, op)
    snapshot = {"models": sorted(loaded.known_models), "fields": [], "source": "fake_port"}
    result = undo(
        loaded.ops,
        known_models=set(loaded.known_models),
        environment=loaded.environment,
        requester_id=loaded.requester_id,
        connection_id=loaded.connection_id,
        store=store,
        approvals=[dict(item) for item in loaded.approvals],
        expected_snapshot=snapshot,
        observed_snapshot=snapshot,
        goal=f"Undo: {loaded.goal}",
        assumptions=list(loaded.assumptions),
    )
    calls = port.calls()
    rolled_back = result.get("status") == "ROLLED_BACK" and result.get("snapshot_match") is True
    if rolled_back:
        port.drop_replayed()
    rows_after = len(port.created)
    return {
        "ok": rolled_back and calls >= len(loaded.ops) and rows_after == 0,
        "command": "rollback",
        "op_count": len(loaded.ops),
        "port": "fake",
        "port_calls": calls,
        "port_rows_after": rows_after,
        "socket_opened": False,
        "live_odoo": False,
        "replayed_on_fake_port": True,
        "status": result.get("status"),
        "snapshot_match": result.get("snapshot_match"),
        "result": result,
    }


def _failure(command: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": command,
        "port": "fake",
        "socket_opened": False,
        "live_odoo": False,
        "error": message,
    }


def _reject(command: str, exc: Exception) -> int:
    message = " ".join(str(exc).split()) or type(exc).__name__
    _emit(_failure(command, message))
    print(f"error: {message}", file=sys.stderr)
    return 1


def _engine_error(exc: Exception) -> bool:
    return isinstance(exc, (OSError, ValueError, PermissionError)) or hasattr(exc, "code")


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True, default=str))
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
