"""Import checks from the config-as-code spec. Blank cells are never keys."""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher


def normalize_ng_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("234"):
        rest = digits[3:]
    elif digits.startswith("0"):
        rest = digits[1:]
    else:
        rest = digits
    if len(rest) < 10:
        raise ValueError("phone too short")
    return "+234" + rest[:10]


def is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def dedupe_key(row: dict, fields: list[str]) -> str | None:
    parts: list[str] = []
    for field in fields:
        value = row.get(field)
        if is_blank(value):
            return None
        parts.append(str(value).strip().lower())
    return "|".join(parts)


def fuzzy_name_match(left: str, right: str) -> bool:
    if is_blank(left) or is_blank(right):
        return False
    return SequenceMatcher(None, left.casefold(), right.casefold()).ratio() >= 0.92
