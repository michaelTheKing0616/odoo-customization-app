"""Parse Odoo domain strings (DomainBuilder-compatible)."""

from __future__ import annotations

import ast
import json
from typing import Any


class DomainParseError(ValueError):
    pass


def parse_domain(value: list[Any] | str | None) -> list[Any]:
    """Accept a domain list or JSON / Python-literal string."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        raise DomainParseError("domain must be a list or string")
    text = value.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError) as exc:
            raise DomainParseError(
                "Invalid domain — use Odoo domain list, e.g. [('state','=','draft')]"
            ) from exc
    if not isinstance(parsed, list):
        raise DomainParseError("domain must evaluate to a list")
    return parsed
