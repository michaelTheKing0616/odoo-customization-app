"""Emit field modifiers for view arch — Odoo 16 attrs= vs 17+ direct attributes."""

from __future__ import annotations

import ast
import re
from typing import Any


def _is_domain_literal(value: str) -> bool:
    s = value.strip()
    return s.startswith("[") and s.endswith("]")


def _parse_domain(value: str) -> Any:
    return ast.literal_eval(value.strip())


def _domain_to_expr(domain: str) -> str:
    """Best-effort domain → Odoo 17+ modifier expression."""
    s = domain.strip()
    if not _is_domain_literal(s):
        return s
    m = re.match(
        r"^\[\s*\(\s*['\"](\w+)['\"]\s*,\s*['\"]=(['\"]?)\s*,\s*['\"]([^'\"]*)['\"]\s*\)\s*\]$",
        s,
    )
    if m:
        field, _, val = m.group(1), m.group(2), m.group(3)
        if val.replace(".", "").replace("-", "").isdigit():
            return f"{field} == {val}"
        return f"{field} == '{val}'"
    return s


def _norm_modifier(val: bool | str | None) -> tuple[str | None, bool]:
    if val is None or val is False:
        return None, False
    if val is True:
        return "1", True
    if isinstance(val, str) and val.strip():
        stripped = val.strip()
        if stripped in {"1", "true", "True"}:
            return "1", True
        if stripped in {"0", "false", "False"}:
            return "0", True
        return stripped, False
    return None, False


def _attrs_literal(attrs: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in attrs.items():
        if isinstance(value, list):
            parts.append(f"'{key}': {value!r}")
        else:
            parts.append(f"'{key}': {value!r}")
    return "{" + ", ".join(parts) + "}"


def emit_field_modifiers(
    *,
    major: int,
    required: bool | str | None = None,
    readonly: bool | str | None = None,
    invisible: str | None = None,
) -> dict[str, str]:
    """Return XML attributes for a field node."""
    out: dict[str, str] = {}
    req_val, req_bool = _norm_modifier(required)
    ro_val, ro_bool = _norm_modifier(readonly)
    inv_val = invisible.strip() if isinstance(invisible, str) and invisible.strip() else None

    if major <= 16:
        attrs: dict[str, Any] = {}
        if req_val == "1":
            attrs["required"] = True
        elif req_val and not req_bool:
            attrs["required"] = _parse_domain(req_val) if _is_domain_literal(req_val) else req_val
        if ro_val == "1":
            attrs["readonly"] = True
        elif ro_val and not ro_bool:
            attrs["readonly"] = _parse_domain(ro_val) if _is_domain_literal(ro_val) else ro_val
        if inv_val:
            attrs["invisible"] = _parse_domain(inv_val) if _is_domain_literal(inv_val) else inv_val
        if attrs:
            out["attrs"] = _attrs_literal(attrs)
            return out
        if req_val == "1":
            out["required"] = "1"
        if ro_val == "1":
            out["readonly"] = "1"
        return out

    if req_val == "1":
        out["required"] = "1"
    elif req_val and not req_bool:
        out["required"] = _domain_to_expr(req_val)
    if ro_val == "1":
        out["readonly"] = "1"
    elif ro_val and not ro_bool:
        out["readonly"] = _domain_to_expr(ro_val)
    if inv_val:
        out["invisible"] = _domain_to_expr(inv_val)
    return out
