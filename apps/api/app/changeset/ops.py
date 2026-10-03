"""Frozen op catalog for the change-set engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

RiskBase = str  # R0 .. R4
Reversible = str  # E | S | N


@dataclass(frozen=True, slots=True)
class OpDef:
    type: str
    risk_base: RiskBase
    reversible: Reversible
    ddl: bool


OP_CATALOG: Final[dict[str, OpDef]] = {
    "model.create": OpDef("model.create", "R2", "E", True),
    "model.scaffold": OpDef("model.scaffold", "R2", "E", True),
    "field.create": OpDef("field.create", "R2", "E", True),
    "field.update": OpDef("field.update", "R1", "E", False),
    "field.deprecate": OpDef("field.deprecate", "R1", "E", False),
    "field.delete": OpDef("field.delete", "R3", "N", True),
    "selection.update": OpDef("selection.update", "R1", "E", False),
    "constraint.sql": OpDef("constraint.sql", "R3", "E", True),
    "view.inherit.create": OpDef("view.inherit.create", "R1", "E", False),
    "view.inherit.update": OpDef("view.inherit.update", "R1", "E", False),
    "view.archive": OpDef("view.archive", "R1", "E", False),
    "view.create_base": OpDef("view.create_base", "R1", "E", False),
    "action.window.create": OpDef("action.window.create", "R1", "E", False),
    "action.window.update": OpDef("action.window.update", "R1", "E", False),
    "menu.create": OpDef("menu.create", "R1", "E", False),
    "menu.update": OpDef("menu.update", "R1", "E", False),
    "menu.archive": OpDef("menu.archive", "R1", "E", False),
    "filter.create": OpDef("filter.create", "R1", "E", False),
    "filter.update": OpDef("filter.update", "R1", "E", False),
    "report.inherit": OpDef("report.inherit", "R2", "E", False),
    "report.action.create": OpDef("report.action.create", "R2", "E", False),
    "report.action.update": OpDef("report.action.update", "R2", "E", False),
    "server_action.create": OpDef("server_action.create", "R2", "E", False),
    "server_action.update": OpDef("server_action.update", "R2", "E", False),
    "automation.create": OpDef("automation.create", "R2", "E", False),
    "automation.update": OpDef("automation.update", "R2", "E", False),
    "automation.disable": OpDef("automation.disable", "R2", "E", False),
    "cron.create": OpDef("cron.create", "R3", "E", False),
    "cron.update": OpDef("cron.update", "R3", "E", False),
    "cron.disable": OpDef("cron.disable", "R3", "E", False),
    "sequence.create": OpDef("sequence.create", "R2", "S", False),
    "sequence.update": OpDef("sequence.update", "R2", "S", False),
    "mail_template.create": OpDef("mail_template.create", "R1", "E", False),
    "mail_template.update": OpDef("mail_template.update", "R1", "E", False),
    "activity_type.create": OpDef("activity_type.create", "R1", "E", False),
    "activity_type.update": OpDef("activity_type.update", "R1", "E", False),
    "stage.upsert": OpDef("stage.upsert", "R1", "E", False),
    "stage.reorder": OpDef("stage.reorder", "R1", "E", False),
    "stage.archive": OpDef("stage.archive", "R1", "E", False),
    "config_record.upsert": OpDef("config_record.upsert", "R2", "E", False),
    "group.create": OpDef("group.create", "R3", "E", False),
    "access.create": OpDef("access.create", "R3", "E", False),
    "access.update": OpDef("access.update", "R3", "E", False),
    "rule.create": OpDef("rule.create", "R3", "E", False),
    "rule.update": OpDef("rule.update", "R3", "E", False),
    "field.groups.set": OpDef("field.groups.set", "R2", "E", False),
    "user.groups.assign": OpDef("user.groups.assign", "R3", "E", False),
    "user.create": OpDef("user.create", "R3", "E", False),
    "user.archive": OpDef("user.archive", "R3", "E", False),
    "setting.set": OpDef("setting.set", "R2", "E", False),
    "config_param.set": OpDef("config_param.set", "R2", "E", False),
    "company.update": OpDef("company.update", "R2", "E", False),
    "module.install": OpDef("module.install", "R3", "S", False),
    "module.upgrade": OpDef("module.upgrade", "R3", "S", False),
    "module.uninstall": OpDef("module.uninstall", "R4", "N", False),
    "data.create_batch": OpDef("data.create_batch", "R2", "E", False),
    "data.update_batch": OpDef("data.update_batch", "R2", "E", False),
    "data.archive_batch": OpDef("data.archive_batch", "R2", "E", False),
    "data.import_upsert": OpDef("data.import_upsert", "R2", "E", False),
    "data.merge": OpDef("data.merge", "R3", "N", False),
    "data.delete": OpDef("data.delete", "R4", "N", False),
    "translation.upsert": OpDef("translation.upsert", "R1", "E", False),
}

_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset({"rpc.write"})


def is_known_op(op_type: str) -> bool:
    return op_type in OP_CATALOG


def get_op(op_type: str) -> OpDef | None:
    if op_type in _FORBIDDEN_TYPES:
        return None
    return OP_CATALOG.get(op_type)


def op_base_risk(op_type: str, params: dict | None) -> RiskBase:
    """Base risk before policy bumps (flag params on select ops)."""
    entry = get_op(op_type)
    if entry is None:
        return "R4"
    base = entry.risk_base
    p = params or {}
    if op_type == "server_action.create":
        if p.get("code") or p.get("email") or p.get("webhook"):
            base = _max_risk(base, "R3")
    elif op_type == "company.update":
        if p.get("lock_date"):
            base = "R4"
    elif op_type == "user.groups.assign":
        if p.get("admin"):
            base = "R4"
    return base


def _max_risk(a: RiskBase, b: RiskBase) -> RiskBase:
    order = ("R0", "R1", "R2", "R3", "R4")
    return a if order.index(a) >= order.index(b) else b
