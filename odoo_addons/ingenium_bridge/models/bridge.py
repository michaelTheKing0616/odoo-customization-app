"""Odoo entrypoints. Security decisions live in protocol.py and are tested without Odoo."""

from odoo import api, models

from ..protocol import KILL_SWITCH_PARAM, authorize, enabled_from_param, ping_payload


class IngeniumBridge(models.AbstractModel):
    _name = "ingenium.bridge"
    _description = "Ingenium bridge"

    def _gate(self, method: str, user_id: int | None = None) -> None:
        parameter = self.env["ir.config_parameter"].sudo().get_param(KILL_SWITCH_PARAM, "1")
        groups = set()
        if self.env.user.has_group("ingenium_bridge.group_ingenium_reader"):
            groups.add("reader")
        if self.env.user.has_group("ingenium_bridge.group_ingenium_operator"):
            groups.add("operator")
        authorize(
            method=method,
            protocol_version=1,
            enabled=enabled_from_param(parameter),
            groups=groups,
            caller_id=self.env.uid,
            user_id=user_id,
            escalated=bool(self.env.su),
        )

    @api.model
    def ping(self) -> dict:
        self._gate("ping")
        return ping_payload(
            server_version=self.env["ir.module.module"]._get("base").latest_version or "",
            edition="community",
            module_hash="",
            capabilities={},
        )

    @api.model
    def introspect(self, batch_spec: dict) -> dict:
        self._gate("introspect")
        if not isinstance(batch_spec, dict):
            raise ValueError("batch_spec must be an object")
        return {"requested": sorted(batch_spec)}

    @api.model
    def combined_view(self, model: str, view_type: str, user_id: int | None = None) -> dict:
        self._gate("combined_view", user_id=user_id)
        return {"model": model, "view_type": view_type}

    @api.model
    def effective_access(self, model: str, user_ids: list) -> dict:
        self._gate("effective_access")
        return {"model": model, "users": list(user_ids)[:20]}

    @api.model
    def render_check(self, kind: str, ref: str) -> dict:
        self._gate("render_check")
        if kind not in {"view", "report", "template"}:
            raise ValueError("unknown render kind")
        return {"kind": kind, "ref": ref, "writes": 0}
