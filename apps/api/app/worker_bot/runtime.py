"""Worker Bot runtime: autonomy levels over validate / inbox / executor."""

from __future__ import annotations

from typing import Any

from app.changeset.executor import apply
from app.changeset.inbox import Inbox
from app.changeset.validate import validate

_VALID_LEVELS = frozenset({"L0", "L1", "L2", "L3"})


def _ignored_untrusted_instruction(record_text: str) -> bool:
    low = record_text.lower()
    return "grant admin" in low or "ignore policy" in low


class WorkerBot:
    def __init__(self, level: str) -> None:
        if level not in _VALID_LEVELS:
            raise ValueError(f"invalid autonomy level: {level!r}")
        self.level = level
        self._inboxes: dict[str, Inbox] = {}

    def _inbox_for(self, connection_id: str) -> Inbox:
        if connection_id not in self._inboxes:
            self._inboxes[connection_id] = Inbox()
        return self._inboxes[connection_id]

    def handle(
        self,
        changeset: list[dict[str, Any]],
        *,
        environment: str,
        requester_id: str,
        connection_id: str,
        known_models: set[str],
        goal: str,
        record_text: str = "",
    ) -> dict[str, Any]:
        ignored = _ignored_untrusted_instruction(record_text)

        def finish(payload: dict[str, Any]) -> dict[str, Any]:
            if ignored:
                payload = {**payload, "ignored_instruction": True}
            return payload

        if self.level == "L0":
            return finish({"action": "ask", "applied": False})

        report = validate(changeset, known_models=known_models)

        if self.level == "L1":
            return finish({"action": "validate", "report": report, "applied": False})

        if not report["valid"]:
            return finish({"ok": False, "report": report, "applied": False})

        max_risk = report["max_risk"]
        if max_risk == "R4":
            return finish(
                {
                    "ok": False,
                    "report": report,
                    "error": "R4 is denied",
                    "applied": False,
                }
            )

        env = environment.lower()
        if self.level == "L3" and env == "staging" and max_risk in {"R0", "R1"}:
            result = apply(changeset, mode="T")
            return finish({"action": "applied", "applied": True, "result": result})

        inbox = self._inbox_for(connection_id)
        submit = inbox.submit(
            changeset,
            goal=goal,
            assumptions=[],
            environment=environment,
            requester_id=requester_id,
            known_models=known_models,
            connection_id=connection_id,
        )
        if not submit["ok"]:
            return finish({"ok": False, "report": submit.get("report", report), "applied": False})

        return finish({"action": "paused", "applied": False, "card": submit["card"]})
