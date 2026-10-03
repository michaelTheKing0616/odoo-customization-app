"""Odoo 20 security adapter.

``access_model()`` is ``ir.access``. Creating ``ir.rule`` raises
``IrRuleNotSupportedOnOdoo20``. Do not write the computed ``kind`` field.

Compilation uses the same field names as ``apps/api/app/odoo20/access_compiler.py``.
This package cannot import that module (apps.api already depends on odoo_client).
Picked: thin wrapper here that calls those same rules; not a second compiler.
"""

from __future__ import annotations

from typing import Any


class AccessCompileError(ValueError):
    """The access spec cannot be applied on this major."""


class IrRuleNotSupportedOnOdoo20(AccessCompileError):
    """Odoo 20 has no ``ir.rule``; create is refused."""


def access_model() -> str:
    return "ir.access"


def create_record_rule(*_args: Any, **_kwargs: Any) -> None:
    """Refuse every ``ir.rule`` create on major 20."""
    raise IrRuleNotSupportedOnOdoo20(
        "Odoo 20 has no ir.rule. Rewrite the group record rule as an access right with a domain."
    )


def compile_access(
    access_rights: list[dict[str, Any]],
    record_rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Major-20 branch of ``access_compiler.compile_access`` (same field names)."""
    rules = list(record_rules or [])
    ops: list[dict[str, Any]] = []
    for right in access_rights:
        if "kind" in right:
            raise AccessCompileError("ir.access.kind is computed; do not write it")
        ops.append(
            {
                "model": "ir.access",
                "values": {
                    "name": right.get("name"),
                    "model": right.get("model"),
                    "group": right.get("group"),
                    "operation": right.get("operation") or "read",
                    "domain": right.get("domain"),
                },
            }
        )
    for rule in rules:
        if rule.get("group"):
            raise AccessCompileError(
                "Odoo 20 has no ir.rule. Rewrite the group record rule as an access right with a domain."
            )
    return ops


__all__ = [
    "AccessCompileError",
    "IrRuleNotSupportedOnOdoo20",
    "access_model",
    "compile_access",
    "create_record_rule",
]
