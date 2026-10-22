"""Twelve-part contract for the schema op family.

The catalog in ``ops.py`` stays the source for risk, reversibility, and DDL.
This module adds the other parts and the schema risk adjustments. It does not
call Odoo.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

TYPE_CHANGE_UNSUPPORTED = "field type change is unsupported"
CONSTRAINT_X_MODELS_ONLY = "constraint.sql is allowed on x_ models only"
CASCADE_FORBIDDEN = "on_delete cascade is forbidden"

SCHEMA_OP_TYPES: tuple[str, ...] = (
    "model.create",
    "model.scaffold",
    "field.create",
    "field.update",
    "field.deprecate",
    "field.delete",
    "selection.update",
    "constraint.sql",
)

TWELVE_PARTS: tuple[str, ...] = (
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

_TYPE_KEYS = ("ttype", "field_type", "new_type", "to_type")
_SENSITIVE_PREFIXES = ("account.", "hr.", "stock.")

_PARAMS_SCHEMAS: dict[str, dict[str, Any]] = {
    "model.create": {
        "type": "object",
        "required": ["model"],
        "properties": {"model": {"type": "string"}},
    },
    "model.scaffold": {
        "type": "object",
        "required": ["model"],
        "properties": {
            "model": {"type": "string"},
            "fields": {"type": "array"},
            "models": {"type": "array"},
        },
    },
    "field.create": {
        "type": "object",
        "required": ["model", "name"],
        "properties": {
            "model": {"type": "string"},
            "name": {"type": "string"},
            "ttype": {"type": "string"},
            "relation": {"type": "string"},
            "on_delete": {"type": "string"},
            "compute": {"type": "string"},
            "currency_field": {"type": "string"},
        },
    },
    "field.update": {
        "type": "object",
        "required": ["model", "name"],
        "properties": {
            "model": {"type": "string"},
            "name": {"type": "string"},
            "string": {"type": "string"},
            "help": {"type": "string"},
        },
    },
    "field.deprecate": {
        "type": "object",
        "required": ["model", "name"],
        "properties": {"model": {"type": "string"}, "name": {"type": "string"}},
    },
    "field.delete": {
        "type": "object",
        "required": ["model", "name"],
        "properties": {
            "model": {"type": "string"},
            "name": {"type": "string"},
            "record_count": {"type": "integer"},
        },
    },
    "selection.update": {
        "type": "object",
        "required": ["model", "name"],
        "properties": {
            "model": {"type": "string"},
            "name": {"type": "string"},
            "selection": {"type": "array"},
        },
    },
    "constraint.sql": {
        "type": "object",
        "required": ["model"],
        "properties": {
            "model": {"type": "string"},
            "name": {"type": "string"},
            "definition": {"type": "string"},
        },
    },
}

_POSTCONDITIONS: dict[str, tuple[str, ...]] = {
    "model.create": ("the model exists",),
    "model.scaffold": ("each scaffolded model and field exists",),
    "field.create": ("the field exists on the model",),
    "field.update": ("the field metadata matches the requested values",),
    "field.deprecate": ("the field is no longer offered on new views",),
    "field.delete": ("the field is absent",),
    "selection.update": ("the selection options match the request",),
    "constraint.sql": ("the constraint exists on the x_ model",),
}

IssuesFn = Callable[[dict[str, Any]], list[str]]
RiskFn = Callable[..., str]
PlanFn = Callable[[dict[str, Any]], str]
ApplyFn = Callable[[dict[str, dict[str, Any]], dict[str, Any]], None]
InverseFn = Callable[[dict[str, Any]], dict[str, Any] | None]


def is_x_model(model: str) -> bool:
    """True when ``model`` is a custom ``x_`` model.

    Inputs: technical model name.
    Outputs: True when the stripped name starts with ``x_``.
    Side effects: none.
    """
    return model.strip().startswith("x_")


def compute_requested(params: dict[str, Any]) -> bool:
    """True when params carry a non-empty compute method.

    Inputs: op params.
    Outputs: True for a non-blank ``compute`` string.
    Side effects: none.
    """
    value = params.get("compute")
    return isinstance(value, str) and bool(value.strip())


def type_change_requested(params: dict[str, Any]) -> bool:
    """True when a field update asks for a different type.

    Inputs: op params. A proposed type uses ``ttype``, ``field_type``,
    ``new_type``, or ``to_type``. ``current_type`` or ``from_type`` is the
    type already stored.
    Outputs: True when a proposed type is present and is not equal to the
    current type. A proposed type with no current type is a change.
    Side effects: none.
    """
    proposed = None
    for key in _TYPE_KEYS:
        value = params.get(key)
        if value not in (None, ""):
            proposed = value
            break
    if proposed is None:
        return False
    current = params.get("current_type", params.get("from_type"))
    if current is None:
        return True
    return str(current) != str(proposed)


def sensitive_model(model: str) -> bool:
    """True for financial (``account.``), HR (``hr.``), or stock (``stock.``) models.

    Inputs: technical model name.
    Outputs: True when the stripped name starts with one of those prefixes.
    Side effects: none.
    """
    name = model.strip()
    return name.startswith(_SENSITIVE_PREFIXES)


def record_count_of(params: dict[str, Any]) -> int | None:
    """Read a non-negative record count from params.

    Inputs: op params. Uses ``record_count`` when it is an int and not a bool.
    Outputs: the count, or None when it is missing or not an int.
    Side effects: none.
    """
    count = params.get("record_count")
    if isinstance(count, bool) or not isinstance(count, int):
        return None
    if count < 0:
        return None
    return count


def cascade_requested(params: dict[str, Any]) -> bool:
    """True when params ask for ``on_delete=cascade``.

    Inputs: op params, or one nested field dict. ``fields`` is walked when it
    is a list of dicts so a scaffold cannot hide cascade on a child.
    Outputs: True when this dict or a child field sets cascade.
    Side effects: none.
    """
    if str(params.get("on_delete") or "") == "cascade":
        return True
    fields = params.get("fields")
    if isinstance(fields, list):
        for field in fields:
            if isinstance(field, dict) and str(field.get("on_delete") or "") == "cascade":
                return True
    return False


def cascade_issues(params: dict[str, Any]) -> list[str]:
    """Issue list when cascade is requested.

    Inputs: op params.
    Outputs: one cascade issue, or an empty list. Cascade stays forbidden
    unless the caller names a different on_delete.
    Side effects: none.
    """
    if cascade_requested(params):
        return [CASCADE_FORBIDDEN]
    return []


def nonempty_sensitive_delete(params: dict[str, Any]) -> bool:
    """True when deleting a field from a non-empty financial, HR, or stock model.

    Inputs: ``field.delete`` params, including ``model`` and ``record_count``.
    Outputs: True only when the model is sensitive and ``record_count`` > 0.
    Side effects: none. Does not query Odoo.
    """
    if not sensitive_model(str(params.get("model") or "")):
        return False
    count = record_count_of(params)
    return count is not None and count > 0


def field_update_issues(params: dict[str, Any]) -> list[str]:
    """Preconditions for ``field.update``.

    Inputs: op params.
    Outputs: missing-key issues, plus a type-change issue when one is requested.
    Side effects: none.
    """
    issues = [f"missing {key}" for key in ("model", "name") if not params.get(key)]
    if type_change_requested(params):
        issues.append(TYPE_CHANGE_UNSUPPORTED)
    issues.extend(item for item in cascade_issues(params) if item not in issues)
    return issues


def scaffold_issues(params: dict[str, Any]) -> list[str]:
    """Preconditions for ``model.scaffold``.

    Inputs: op params, including optional nested ``fields``.
    Outputs: a cascade issue when the scaffold or a child field asks for it.
    Side effects: none.
    """
    return cascade_issues(params)


def constraint_sql_issues(params: dict[str, Any]) -> list[str]:
    """Preconditions for ``constraint.sql``.

    Inputs: op params.
    Outputs: one issue when the model is not an ``x_`` model, else an empty list.
    Side effects: none.
    """
    if is_x_model(str(params.get("model") or "")):
        return []
    return [CONSTRAINT_X_MODELS_ONLY]


def adjusted_schema_risk(
    op_type: str,
    params: dict[str, Any],
    *,
    counts: Mapping[str, int] | None = None,
) -> str:
    """Catalog risk after schema adjustments.

    Inputs: op type, params, and an optional fake ``model -> record_count`` map.
    When ``counts`` contains the model, that count is copied onto params before
    the field.delete rule runs.
    Outputs: an ``R0``–``R4`` string from ``op_base_risk``.
    Side effects: none. Does not call Odoo.
    """
    body = dict(params)
    if counts is not None:
        model = str(body.get("model") or "")
        if model in counts:
            body["record_count"] = counts[model]
    from app.changeset.ops import op_base_risk

    return op_base_risk(op_type, body)


@dataclass(frozen=True, slots=True)
class SchemaOpContract:
    """One schema op with the twelve engine parts."""

    type: str
    params_schema: dict[str, Any]
    risk_base: str
    reversible: str
    ddl: bool
    simulate_in_place: bool
    preconditions: IssuesFn
    risk_adjust: RiskFn
    plan: PlanFn
    apply: ApplyFn
    inverse: InverseFn
    postconditions: tuple[str, ...]

    def as_parts(self) -> dict[str, Any]:
        """Return the twelve parts in catalog order.

        Inputs: none.
        Outputs: a dict whose keys are ``TWELVE_PARTS``.
        Side effects: none.
        """
        return {name: getattr(self, name) for name in TWELVE_PARTS}


def schema_contracts() -> tuple[SchemaOpContract, ...]:
    """Build the schema-family contracts from the live catalog and handlers.

    Inputs: none.
    Outputs: one contract per schema op, in ``SCHEMA_OP_TYPES`` order.
    Side effects: imports the catalog and handlers. Does not call Odoo.
    """
    from app.changeset.handlers import apply_memory, handler_for
    from app.changeset.ops import OP_CATALOG

    contracts: list[SchemaOpContract] = []
    for op_type in SCHEMA_OP_TYPES:
        entry = OP_CATALOG[op_type]
        handler = handler_for(op_type)

        def preconditions(params: dict[str, Any], *, _handler: Any = handler) -> list[str]:
            return list(_handler.issues(params))

        def risk_adjust(
            params: dict[str, Any],
            counts: Mapping[str, int] | None = None,
            *,
            _op_type: str = op_type,
        ) -> str:
            return adjusted_schema_risk(_op_type, params, counts=counts)

        def plan(params: dict[str, Any], *, _handler: Any = handler) -> str:
            return _handler.describe(params)

        def apply(
            store: dict[str, dict[str, Any]],
            params: dict[str, Any],
            *,
            _op_type: str = op_type,
        ) -> None:
            apply_memory(store, {"type": _op_type, "params": params})

        def inverse(params: dict[str, Any], *, _handler: Any = handler) -> dict[str, Any] | None:
            return _handler.inverse(params)

        contracts.append(
            SchemaOpContract(
                type=op_type,
                params_schema=dict(_PARAMS_SCHEMAS[op_type]),
                risk_base=entry.risk_base,
                reversible=entry.reversible,
                ddl=entry.ddl,
                simulate_in_place=not entry.ddl,
                preconditions=preconditions,
                risk_adjust=risk_adjust,
                plan=plan,
                apply=apply,
                inverse=inverse,
                postconditions=_POSTCONDITIONS[op_type],
            )
        )
    return tuple(contracts)
