"""Worker Bot runtime: autonomy levels over validate / inbox / executor."""

from __future__ import annotations

from typing import Any

from odoo_client.schema_fingerprint import schema_fingerprint

from app.changeset.executor import apply, changeset_fingerprint, schema_drift_status
from app.changeset.inbox import Inbox
from app.changeset.validate import validate
from app.worker_bot.l3_policy import l3_staging_may_auto_apply

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

    def plan(
        self,
        changeset: list[dict[str, Any]],
        *,
        environment: str,
        requester_id: str,
        connection_id: str,
        known_models: set[str],
        goal: str,
        live_schema: dict[str, Any] | None = None,
        record_text: str = "",
    ) -> dict[str, Any]:
        """Validate and bind plan hash plus optional schema fingerprint at plan time."""
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

        binding: dict[str, Any] = {
            "action": "planned",
            "changeset": changeset,
            "report": report,
            "plan_hash": changeset_fingerprint(changeset),
            "environment": environment,
            "requester_id": requester_id,
            "connection_id": connection_id,
            "known_models": known_models,
            "goal": goal,
        }
        if isinstance(live_schema, dict):
            binding["schema_fingerprint"] = schema_fingerprint(live_schema)
        return finish(binding)

    def apply_planned(
        self,
        plan: dict[str, Any],
        *,
        live_schema: dict[str, Any] | None = None,
        port: Any | None = None,
        record_text: str = "",
    ) -> dict[str, Any]:
        """Apply a prior ``plan`` binding; abort with outcome STALE when the target drifted."""
        ignored = _ignored_untrusted_instruction(record_text)

        def finish(payload: dict[str, Any]) -> dict[str, Any]:
            if ignored:
                payload = {**payload, "ignored_instruction": True}
            return payload

        if plan.get("action") == "ask":
            return finish({"action": "ask", "applied": False})
        if plan.get("action") == "validate":
            return finish({"action": "validate", "report": plan.get("report"), "applied": False})
        if plan.get("ok") is False:
            return finish(dict(plan))

        changeset = plan.get("changeset")
        report = plan.get("report")
        if not isinstance(changeset, list) or not isinstance(report, dict):
            return finish({"ok": False, "applied": False, "error": "invalid_plan"})

        environment = str(plan.get("environment") or "")
        requester_id = str(plan.get("requester_id") or "")
        connection_id = str(plan.get("connection_id") or "")
        known_models = plan.get("known_models")
        goal = str(plan.get("goal") or "")
        if not isinstance(known_models, set):
            known_models = set(known_models) if known_models else set()

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

        schema_fp = plan.get("schema_fingerprint")
        if isinstance(schema_fp, str) and schema_fp:
            drift = schema_drift_status(schema_fp, live_schema)
            if drift == "STALE":
                return finish({"action": "aborted", "outcome": "STALE", "applied": False})

        if l3_staging_may_auto_apply(
            level=self.level,
            environment=environment,
            max_risk=max_risk,
            changeset=changeset,
        ):
            plan_hash = str(plan.get("plan_hash") or "")
            live_fp = schema_fingerprint(live_schema) if isinstance(live_schema, dict) else None
            apply_kwargs: dict[str, Any] = {
                "mode": "T",
                "approved_hash": plan_hash or None,
            }
            if port is not None:
                apply_kwargs["port"] = port
            if isinstance(schema_fp, str) and schema_fp:
                apply_kwargs["schema_fingerprint"] = schema_fp
                apply_kwargs["live_schema"] = live_schema
                apply_kwargs["expected_fingerprint"] = schema_fp
                apply_kwargs["live_fingerprint"] = live_fp
            result = apply(changeset, **apply_kwargs)
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

        if l3_staging_may_auto_apply(
            level=self.level,
            environment=environment,
            max_risk=max_risk,
            changeset=changeset,
        ):
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
