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
        if rules:
            # A record rule is not an ir.access grant, with or without a group.
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


def major_of(obj: Any, default: int = 19) -> int:
    """Connection major on a client or port. Missing major stays on the ≤19 path."""
    caps = getattr(obj, "capabilities", None)
    major = getattr(caps, "major", None) if caps is not None else None
    if major is None:
        major = getattr(obj, "major", None)
    if major is None:
        return default
    try:
        return int(major)
    except (TypeError, ValueError):
        return default


def access_rights_from_perms(
    *,
    name: Any,
    model: Any,
    group: Any,
    perms: dict[str, Any],
    domain: Any = None,
) -> list[dict[str, Any]]:
    """One compiler right per enabled perm. The compiler emits one ir.access row each."""
    rights: list[dict[str, Any]] = []
    for operation, key in (
        ("read", "perm_read"),
        ("write", "perm_write"),
        ("create", "perm_create"),
        ("unlink", "perm_unlink"),
    ):
        if not bool(perms.get(key, True)):
            continue
        row: dict[str, Any] = {
            "name": name,
            "model": model,
            "group": group,
            "operation": operation,
        }
        if domain not in (None, False, ""):
            row["domain"] = domain
        if "kind" in perms:
            row["kind"] = perms["kind"]
        rights.append(row)
    return rights


def record_rule_for_compiler(rule: dict[str, Any]) -> dict[str, Any]:
    """Map draft rule keys onto the compiler's ``group`` field."""
    payload: dict[str, Any] = {
        "name": rule.get("name"),
        "model": rule.get("model"),
        "domain": rule.get("domain") if rule.get("domain") not in (None, False, "") else rule.get("domain_force"),
    }
    group = rule.get("group") or rule.get("group_xml_id")
    if not group and rule.get("group_ids"):
        group = rule.get("group_ids")
    if not group and rule.get("groups"):
        group = rule.get("groups")
    if group:
        payload["group"] = group
    return payload


def apply_compiled_access(
    create: Any,
    major: int,
    access_rights: list[dict[str, Any]],
    record_rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Create compiler ops via ``create(model, values)``.

    Major 20 never calls ``create`` for ``ir.rule``. ``kind`` is never written.
    """
    ops = compile_access(int(major), access_rights, record_rules)
    if int(major) >= 20:
        for op in ops:
            values = dict(op.get("values") or {})
            if op.get("model") == "ir.rule":
                raise AccessCompileError(
                    "Odoo 20 has no ir.rule. Rewrite the group record rule as an access right with a domain."
                )
            if "kind" in values:
                raise AccessCompileError("ir.access.kind is computed; do not write it")
    for op in ops:
        create(str(op["model"]), dict(op.get("values") or {}))
    return ops
