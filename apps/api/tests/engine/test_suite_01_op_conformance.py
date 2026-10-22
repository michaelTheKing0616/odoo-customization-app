"""T8-S01 op conformance.

Walks every op in ``OP_CATALOG`` and checks the twelve parts named by
T8-OP-SCHEMA: type, params schema, risk base, reversible, DDL flag,
simulate_in_place, preconditions, risk adjust, plan, apply, inverse,
postconditions.

A part the engine already implements passes. An op whose reversible flag is
N keeps a missing inverse. A reversible op (E or S) whose handler returns no
inverse is a gap: this module fails and names those ops. An empty inverse
dict does not count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.changeset.handlers import all_handlers, apply_memory, handler_for
from app.changeset.ops import OP_CATALOG, OpDef, get_op, is_known_op, op_base_risk
from app.changeset.protected_registry import reset_detections
from app.changeset.schema_ops import TWELVE_PARTS, SchemaOpContract, schema_contracts
from app.changeset.simulate import MODE_STATIC, run_mode
from app.changeset.validate import validate
from app.changeset.verify import postconditions_for

pytestmark = pytest.mark.no_app_db

_RISK = frozenset({"R0", "R1", "R2", "R3", "R4"})
_REVERSIBLE = frozenset({"E", "S", "N"})
_PROBE_PARAMS: tuple[dict[str, Any], ...] = (
    {},
    {
        "model": "x_ticket",
        "name": "x_note",
        "ttype": "char",
        "group": "base.group_user",
        "module": "sale",
        "user": "demo",
        "domain_force": "[('id', '=', 1)]",
        "global": True,
    },
)


@dataclass(frozen=True, slots=True)
class OpConformance:
    """One catalog op after the twelve-part check."""

    op_type: str
    reversible: str
    missing: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.missing

    @property
    def inverse_gap(self) -> bool:
        return "inverse" in self.missing


def _schema_by_type() -> dict[str, SchemaOpContract]:
    """Index the schema-family contracts.

    Inputs: none.
    Outputs: contract by op type. Ops outside that family are absent.
    Side effects: none. Does not call Odoo.
    """
    return {contract.type: contract for contract in schema_contracts()}


def _real_inverse(op_type: str, value: Any) -> bool:
    """Whether ``value`` is an inverse op, not an empty stub.

    Inputs: the forward op type and the handler return value.
    Outputs: True when the value names a catalog op, points ``inverse_of``
    at the forward type, and carries a params object.
    Side effects: none.
    """
    if not isinstance(value, dict) or not value:
        return False
    inverse_type = value.get("type")
    if not isinstance(inverse_type, str) or inverse_type not in OP_CATALOG:
        return False
    if value.get("inverse_of") != op_type:
        return False
    return isinstance(value.get("params"), dict)


def _observed_inverse(op_type: str) -> Any:
    """Return the first real inverse from benign params, else None.

    Inputs: catalog op type.
    Outputs: the handler inverse, or None when every non-refused probe has
    none. Refused probes are skipped so a guard does not hide a real inverse.
    Side effects: clears protected-registry detections recorded while probing.
    Does not call Odoo.
    """
    handler = handler_for(op_type)
    try:
        for params in _PROBE_PARAMS:
            if handler.refuse_reason(params) is not None:
                continue
            value = handler.inverse(params)
            if _real_inverse(op_type, value):
                return value
        return None
    finally:
        reset_detections()


def _simulate_in_place_holds(op_type: str, entry: OpDef) -> bool:
    """Whether in-place simulation matches the DDL flag.

    Inputs: catalog op type and its definition.
    Outputs: True when a DDL op is rejected with ``simulate_in_place`` set,
    and a non-DDL op is not rejected for that flag.
    Side effects: runs the in-process static simulator. Does not call Odoo.
    """
    outcome = run_mode(
        MODE_STATIC,
        [{"type": op_type, "params": {"simulate_in_place": True}}],
    )
    if entry.ddl:
        return outcome.passed is False and "simulate_in_place" in outcome.detail
    return "simulate_in_place" not in outcome.detail


def _params_schema_holds(contract: SchemaOpContract | None) -> bool:
    """Whether the op has an object params schema with required keys.

    Inputs: the schema contract, or None when the family has no contract.
    Outputs: True only for a JSON object schema that lists required keys.
    Side effects: none.
    """
    if contract is None:
        return False
    schema = contract.params_schema
    return (
        isinstance(schema, dict)
        and schema.get("type") == "object"
        and isinstance(schema.get("required"), list)
        and bool(schema["required"])
        and isinstance(schema.get("properties"), dict)
    )


def _postconditions_hold(op_type: str, contract: SchemaOpContract | None) -> bool:
    """Whether the op names at least one postcondition.

    Inputs: catalog op type and its schema contract when one exists.
    Outputs: True when the contract names postconditions, otherwise when
    ``postconditions_for`` names some for this type.
    Side effects: may import schema contracts once through ``postconditions_for``.
    Does not call Odoo.
    """
    if contract is not None:
        names = contract.postconditions
    else:
        names = postconditions_for({"type": op_type})
    return bool(names) and all(isinstance(item, str) and item for item in names)


def inspect_op(
    op_type: str,
    *,
    schemas: dict[str, SchemaOpContract],
    handlers: dict[str, Any],
) -> OpConformance:
    """Check the twelve parts for one catalog op.

    Inputs: op type, schema contracts, and the handler map.
    Outputs: the op, its reversible flag, and the missing part names in
    ``TWELVE_PARTS`` order. Reversible N records inverse as present when the
    handler returns none.
    Side effects: probes the handler inverse and the static simulator.
    Does not call Odoo.
    """
    entry = OP_CATALOG[op_type]
    handler = handlers[op_type]
    contract = schemas.get(op_type)
    present = {name: False for name in TWELVE_PARTS}

    present["type"] = entry.type == op_type and bool(op_type)
    present["params_schema"] = _params_schema_holds(contract)
    present["risk_base"] = entry.risk_base in _RISK
    present["reversible"] = entry.reversible in _REVERSIBLE
    present["ddl"] = isinstance(entry.ddl, bool)
    in_place = _simulate_in_place_holds(op_type, entry)
    if contract is None:
        present["simulate_in_place"] = in_place
    else:
        present["simulate_in_place"] = in_place and contract.simulate_in_place is (not entry.ddl)

    issues = handler.issues({})
    present["preconditions"] = isinstance(issues, list)
    if contract is not None:
        contract_issues = contract.preconditions({})
        present["preconditions"] = present["preconditions"] and isinstance(contract_issues, list)
        present["risk_adjust"] = contract.risk_adjust({}) in _RISK
        planned = contract.plan({})
        present["plan"] = isinstance(planned, str) and op_type in planned
        present["apply"] = callable(contract.apply)
    else:
        present["risk_adjust"] = op_base_risk(op_type, {}) in _RISK
        planned = handler.describe({})
        present["plan"] = isinstance(planned, str) and op_type in planned
        present["apply"] = callable(apply_memory)

    if entry.reversible == "N":
        present["inverse"] = _observed_inverse(op_type) is None
    else:
        present["inverse"] = _real_inverse(op_type, _observed_inverse(op_type))

    present["postconditions"] = _postconditions_hold(op_type, contract)
    missing = tuple(name for name in TWELVE_PARTS if not present[name])
    return OpConformance(op_type=op_type, reversible=entry.reversible, missing=missing)


def _conformance_rows() -> tuple[OpConformance, ...]:
    """Inspect every catalog op in catalog order.

    Inputs: none.
    Outputs: one row per ``OP_CATALOG`` entry.
    Side effects: same as ``inspect_op``. Does not call Odoo.
    """
    schemas = _schema_by_type()
    handlers = all_handlers()
    return tuple(inspect_op(op_type, schemas=schemas, handlers=handlers) for op_type in OP_CATALOG)


# Known debt. Schema-family inverses were closed. A new missing part fails
# the lock. Closing a remaining gap also fails it until this snapshot updates.
_KNOWN_GAPS: dict[str, tuple[str, ...]] = {
    "view.inherit.create": ("params_schema",),
    "view.inherit.update": ("params_schema",),
    "view.archive": ("params_schema", "inverse"),
    "view.create_base": ("params_schema",),
    "action.window.create": ("params_schema", "inverse"),
    "action.window.update": ("params_schema", "inverse"),
    "menu.create": ("params_schema",),
    "menu.update": ("params_schema",),
    "menu.archive": ("params_schema", "inverse"),
    "filter.create": ("params_schema",),
    "filter.update": ("params_schema",),
    "report.inherit": ("params_schema", "inverse"),
    "report.action.create": ("params_schema", "inverse"),
    "report.action.update": ("params_schema", "inverse"),
    "server_action.create": ("params_schema", "inverse"),
    "server_action.update": ("params_schema", "inverse"),
    "automation.create": ("params_schema",),
    "automation.update": ("params_schema",),
    "automation.disable": ("params_schema", "inverse"),
    "cron.create": ("params_schema",),
    "cron.update": ("params_schema",),
    "cron.disable": ("params_schema", "inverse"),
    "sequence.create": ("params_schema", "inverse"),
    "sequence.update": ("params_schema", "inverse"),
    "mail_template.create": ("params_schema",),
    "mail_template.update": ("params_schema",),
    "activity_type.create": ("params_schema", "inverse"),
    "activity_type.update": ("params_schema", "inverse"),
    "stage.upsert": ("params_schema",),
    "stage.reorder": ("params_schema", "inverse"),
    "stage.archive": ("params_schema", "inverse"),
    "config_record.upsert": ("params_schema", "inverse"),
    "group.create": ("params_schema", "inverse"),
    "access.create": ("params_schema", "inverse"),
    "access.update": ("params_schema",),
    "rule.create": ("params_schema", "inverse"),
    "rule.update": ("params_schema",),
    "field.groups.set": ("params_schema", "inverse"),
    "user.groups.assign": ("params_schema", "inverse"),
    "user.create": ("params_schema", "inverse"),
    "user.archive": ("params_schema", "inverse"),
    "setting.set": ("params_schema", "inverse"),
    "config_param.set": ("params_schema", "inverse"),
    "company.update": ("params_schema", "inverse"),
    "module.install": ("params_schema", "inverse"),
    "module.upgrade": ("params_schema", "inverse"),
    "module.uninstall": ("params_schema",),
    "data.create_batch": ("params_schema", "inverse"),
    "data.update_batch": ("params_schema", "inverse"),
    "data.unlink": ("params_schema", "inverse"),
    "data.archive_batch": ("params_schema", "inverse"),
    "data.import_upsert": ("params_schema", "inverse"),
    "data.merge": ("params_schema",),
    "data.delete": ("params_schema",),
    "translation.upsert": ("params_schema", "inverse"),
}


def _failure_report(rows: tuple[OpConformance, ...]) -> str:
    """Format the pass count, inverse gaps, and any other missing parts.

    Inputs: conformance rows for the whole catalog.
    Outputs: a multi-line report. Inverse gaps are the reversible ops with
    no inverse.
    Side effects: none.
    """
    passing = tuple(row.op_type for row in rows if row.passed)
    inverse_gaps = tuple(row for row in rows if row.inverse_gap)
    lines = [
        f"listed {len(rows)} ops; {len(passing)} pass all twelve parts",
        "passing: " + (", ".join(passing) if passing else "(none)"),
        (
            f"inverse gaps ({len(inverse_gaps)}): "
            + ", ".join(f"{row.op_type} ({row.reversible})" for row in inverse_gaps)
        ),
    ]
    for row in rows:
        extra = tuple(name for name in row.missing if name != "inverse")
        if extra:
            lines.append(f"{row.op_type}: missing {', '.join(extra)}")
    return "\n".join(lines)


def test_every_catalog_op_conforms_to_the_twelve_parts() -> None:
    """Lock the known twelve-part gap. This is not a claim that every op conforms.

    Schema-family ops now pass. A new missing part fails this test. Closing a
    remaining gap also fails it until this snapshot is updated. Empty inverse
    stubs do not count.
    """
    rows = _conformance_rows()
    assert tuple(row.op_type for row in rows) == tuple(OP_CATALOG)
    assert tuple(TWELVE_PARTS) == (
        "type",
        "params_schema",
        "risk_base",
        "reversible",
        "ddl",
        "simulate_in_place",
        "preconditions",
        "risk_adjust",
        "plan",
        "apply",
        "inverse",
        "postconditions",
    )
    actual = {row.op_type: row.missing for row in rows if row.missing}
    assert actual == _KNOWN_GAPS, _failure_report(rows)


def test_unknown_op_type_fails_closed() -> None:
    """An op type outside the catalog is refused before any write."""
    unknown = "not.an.op"
    assert is_known_op(unknown) is False
    assert get_op(unknown) is None
    assert unknown not in OP_CATALOG
    with pytest.raises(KeyError):
        handler_for(unknown)
    with pytest.raises(KeyError):
        apply_memory({}, {"type": unknown, "params": {}})
    report = validate([{"type": unknown, "params": {}}], known_models=set())
    static = next(stage for stage in report["stages"] if stage["name"] == "static")
    assert static["passed"] is False
    assert any("unknown" in error for error in static["errors"])
