"""Lower the Ingenium schema profile for a provider, then validate against the canonical schema."""

from __future__ import annotations

import re
from typing import Any

# First character is a letter; two to forty more from the same class (length 3–41).
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_]{2,40}")
_MAX_DESCRIPTION_CHARS = 1024


def to_openai_strict(schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return schema
    schema = dict(schema)
    if isinstance(schema.get("items"), dict):
        schema["items"] = to_openai_strict(schema["items"])
    for key in ("anyOf", "oneOf", "allOf"):
        if isinstance(schema.get(key), list):
            schema[key] = [to_openai_strict(item) if isinstance(item, dict) else item for item in schema[key]]
    if schema.get("type") != "object":
        return schema
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    lowered: dict[str, Any] = {}
    for name, prop in properties.items():
        child = to_openai_strict(prop) if isinstance(prop, dict) else prop
        if name not in required:
            child = {"anyOf": [child, {"type": "null"}]}
        lowered[name] = child
    return {
        "type": "object",
        "properties": lowered,
        "required": list(properties),
        "additionalProperties": False,
    }


def to_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return schema
    if "const" in schema:
        copied = {key: value for key, value in schema.items() if key not in {"const", "pattern"}}
        copied["enum"] = [schema["const"]]
        return to_gemini(copied) if copied.keys() - {"enum", "type"} else copied
    out = {key: value for key, value in schema.items() if key not in {"pattern", "$ref"}}
    if isinstance(out.get("properties"), dict):
        out["properties"] = {name: to_gemini(prop) for name, prop in out["properties"].items()}
    if isinstance(out.get("items"), dict):
        out["items"] = to_gemini(out["items"])
    for key in ("anyOf", "oneOf", "allOf"):
        if isinstance(out.get(key), list):
            out[key] = [to_gemini(item) if isinstance(item, dict) else item for item in out[key]]
    return out


def canonical_issues(args: dict[str, Any] | None, schema: dict[str, Any]) -> list[str]:
    if not isinstance(args, dict):
        return ["args must be an object"]
    if schema.get("type") != "object":
        return []
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    issues: list[str] = []
    if schema.get("additionalProperties") is False:
        extra = [key for key in args if key not in properties]
        if extra:
            issues.append(f"unexpected {extra[0]}")
    for name in required:
        if name not in args or args[name] is None:
            issues.append(f"missing {name}")
    for name, prop in properties.items():
        if name not in args or args[name] is None:
            continue
        expected = prop.get("type")
        value = args[name]
        if expected == "string" and not isinstance(value, str):
            issues.append(f"{name} must be string")
        elif expected == "boolean" and not isinstance(value, bool):
            issues.append(f"{name} must be boolean")
        elif expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            issues.append(f"{name} must be integer")
        elif expected == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            issues.append(f"{name} must be number")
        elif expected == "object" and isinstance(value, dict):
            issues.extend(canonical_issues(value, prop))
        elif expected == "object":
            issues.append(f"{name} must be object")
        elif expected == "array":
            if not isinstance(value, list):
                issues.append(f"{name} must be array")
            elif isinstance(prop.get("items"), dict):
                for item in value:
                    if prop["items"].get("type") == "object" and isinstance(item, dict):
                        issues.extend(canonical_issues(item, prop["items"]))
                    elif prop["items"].get("type") == "string" and not isinstance(item, str):
                        issues.append(f"{name} items must be string")
        if "enum" in prop and value not in prop["enum"]:
            issues.append(f"{name} not in enum")
        if "const" in prop and value != prop["const"]:
            issues.append(f"{name} must equal const")
    return issues


def canonical_tool_issues(name: str, description: str) -> list[str]:
    """Return schema issues for a canonical tool name and description.

    ``name`` must match ``[a-z][a-z0-9_]{2,40}``. ``description`` must be a
    string of at most 1024 characters. No side effects.
    """
    issues: list[str] = []
    if not isinstance(name, str) or _TOOL_NAME.fullmatch(name) is None:
        issues.append("invalid tool name")
    if not isinstance(description, str) or len(description) > _MAX_DESCRIPTION_CHARS:
        issues.append("description exceeds 1024 characters")
    return issues
