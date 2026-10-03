"""Compile access rights for the Odoo major that will receive them.

Odoo 20 has ir.access and no ir.rule. Earlier majors keep ir.model.access plus ir.rule.
"""

from __future__ import annotations

from typing import Any


class AccessCompileError(ValueError):
    """The access spec cannot be applied on this major."""


def compile_access(
    major: int,
    access_rights: list[dict[str, Any]],
    record_rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rules = list(record_rules or [])
    if major >= 20:
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

    ops = []
    for right in access_rights:
        ops.append(
            {
                "model": "ir.model.access",
                "values": {
                    "name": right.get("name"),
                    "model": right.get("model"),
                    "group": right.get("group"),
                    "perm_read": right.get("perm_read", True),
                    "perm_write": right.get("perm_write", False),
                    "perm_create": right.get("perm_create", False),
                    "perm_unlink": right.get("perm_unlink", False),
                },
            }
        )
        if right.get("domain"):
            ops.append(
                {
                    "model": "ir.rule",
                    "values": {
                        "name": right.get("name"),
                        "model": right.get("model"),
                        "domain": right.get("domain"),
                        "groups": [right["group"]] if right.get("group") else [],
                    },
                }
            )
    for rule in rules:
        ops.append({"model": "ir.rule", "values": dict(rule)})
    return ops
