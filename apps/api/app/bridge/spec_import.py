"""Bridge B2 (spec item 2): any app from OpenAPI / Swagger / Postman / a sample payload.

Code builds and checks the connector descriptor. An AI step may later suggest names or
entity picks, but it can only choose among what this parser found (AI proposes, code authorizes).
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import yaml

MAX_BYTES = 5_000_000
_TYPE = {
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "string": "char",
    "array": "list",
    "object": "dict",
}
_FMT = {"date": "date", "date-time": "datetime", "email": "char", "uri": "char"}


class SpecError(ValueError):
    pass


def _load(text: str) -> Any:
    if len(text.encode()) > MAX_BYTES:
        raise SpecError("File is too large (5 MB limit).")
    try:
        return json.loads(text)
    except ValueError:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SpecError("Not JSON or YAML.") from exc


def _check_url(u: str) -> str:
    p = urlparse(u or "")
    if not p.scheme:
        return ""
    if p.scheme != "https":
        raise SpecError("Base URL must use https.")
    host = (p.hostname or "").lower()
    if (
        host in ("localhost",)
        or host.endswith(".local")
        or re.match(r"^(127\.|10\.|192\.168\.|169\.254\.|0\.)", host)
    ):
        raise SpecError("Base URL points to a private address.")
    return u.rstrip("/")


def _fields(schema: dict, comps: dict, depth: int = 0) -> dict[str, str]:
    if not isinstance(schema, dict) or depth > 4:
        return {}
    if "$ref" in schema:
        return _fields(_ref(schema["$ref"], comps), comps, depth + 1)
    if schema.get("type") == "array":
        return _fields(schema.get("items") or {}, comps, depth + 1)
    for k in ("allOf",):
        if k in schema:
            out: dict[str, str] = {}
            for s in schema[k]:
                out |= _fields(s, comps, depth + 1)
            return out
    out = {}
    for name, p in (schema.get("properties") or {}).items():
        if isinstance(p, dict) and "$ref" in p:
            out[name] = "many2one"
        elif isinstance(p, dict):
            out[name] = _FMT.get(p.get("format", ""), _TYPE.get(p.get("type", ""), "char"))
    return out


def _ref(ref: str, comps: dict) -> dict:
    node: Any = comps
    for part in ref.lstrip("#/").split("/"):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, dict) else {}


def _entity(path: str) -> str:
    segs = [
        s
        for s in path.strip("/").split("/")
        if s and not s.startswith("{") and not re.match(r"^v\d+$", s)
    ]
    return re.sub(r"\.json$", "", segs[-1]) if segs else ""


def from_openapi(doc: dict) -> dict[str, Any]:
    comps = doc
    if "openapi" in doc:
        base = (doc.get("servers") or [{}])[0].get("url", "")
        schemes = (doc.get("components") or {}).get("securitySchemes") or {}
    else:  # swagger 2
        base = f"https://{doc.get('host', '')}{doc.get('basePath', '')}" if doc.get("host") else ""
        schemes = doc.get("securityDefinitions") or {}
    auth = sorted({_auth_kind(s) for s in schemes.values() if isinstance(s, dict)} - {""})
    entities: dict[str, dict[str, Any]] = {}
    for path, ops in (doc.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        ent = _entity(path)
        if not ent:
            continue
        e = entities.setdefault(ent, {"read": None, "create": None, "update": None, "fields": {}})
        for method, op in ops.items():
            if not isinstance(op, dict):
                continue
            m = method.lower()
            if m == "get" and "{" not in path.rstrip("/").split("/")[-1]:
                e["read"] = path
                resp = (op.get("responses") or {}).get("200") or {}
                sch = (
                    resp.get("schema")
                    or ((resp.get("content") or {}).get("application/json") or {}).get("schema")
                    or {}
                )
                e["fields"] |= _fields(sch, comps)
            elif m == "post":
                e["create"] = path
                body = ((op.get("requestBody") or {}).get("content") or {}).get(
                    "application/json", {}
                ).get("schema") or {}
                e["fields"] |= _fields(body, comps)
            elif m in ("put", "patch"):
                e["update"] = path
    return {
        "source": "openapi",
        "name": (doc.get("info") or {}).get("title", "Custom app"),
        "base_url": _check_url(base),
        "auth": auth or ["api_key"],
        "entities": entities,
    }


def _auth_kind(s: dict) -> str:
    t = (s.get("type") or "").lower()
    if t == "oauth2" or t == "openidconnect":
        return "oauth2"
    if t == "apikey":
        return "api_key"
    if t == "http":
        return "basic" if (s.get("scheme") or "").lower() == "basic" else "api_key"
    if t == "basic":
        return "basic"
    return ""


def from_postman(doc: dict) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = {}
    base = ""

    def walk(items: list) -> None:
        nonlocal base
        for it in items or []:
            if "item" in it:
                walk(it["item"])
                continue
            req = it.get("request") or {}
            url = req.get("url") or {}
            raw = url if isinstance(url, str) else url.get("raw", "")
            p = urlparse(raw.replace("{{", "").replace("}}", ""))
            if not base and p.scheme:
                base = f"{p.scheme}://{p.netloc}"
            path = (
                "/" + "/".join(url.get("path", []))
                if isinstance(url, dict) and url.get("path")
                else p.path
            )
            ent = _entity(re.sub(r":\w+", "{id}", path))
            if not ent:
                continue
            e = entities.setdefault(
                ent, {"read": None, "create": None, "update": None, "fields": {}}
            )
            m = (req.get("method") or "GET").upper()
            if m == "GET":
                e["read"] = path
            elif m == "POST":
                e["create"] = path
                try:
                    e["fields"] |= sample_fields(
                        json.loads((req.get("body") or {}).get("raw") or "{}")
                    )
                except ValueError:
                    pass
            elif m in ("PUT", "PATCH"):
                e["update"] = path

    walk(doc.get("item") or [])
    a = ((doc.get("auth") or {}).get("type") or "").lower()
    auth = {"oauth2": "oauth2", "basic": "basic", "apikey": "api_key", "bearer": "api_key"}.get(
        a, "api_key"
    )
    return {
        "source": "postman",
        "name": (doc.get("info") or {}).get("name", "Custom app"),
        "base_url": _check_url(base),
        "auth": [auth],
        "entities": entities,
    }


def sample_fields(obj: Any) -> dict[str, str]:
    if isinstance(obj, list):
        obj = obj[0] if obj and isinstance(obj[0], dict) else {}
    if not isinstance(obj, dict):
        return {}
    out = {}
    for k, v in obj.items():
        if isinstance(v, bool):
            out[k] = "boolean"
        elif isinstance(v, int):
            out[k] = "integer"
        elif isinstance(v, float):
            out[k] = "float"
        elif isinstance(v, dict):
            out[k] = "many2one" if "id" in v else "dict"
        elif isinstance(v, list):
            out[k] = "list"
        elif isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", v):
            out[k] = "datetime"
        elif isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            out[k] = "date"
        else:
            out[k] = "char"
    return out


def from_sample(obj: Any, entity: str = "records") -> dict[str, Any]:
    if (
        isinstance(obj, dict)
        and len(obj) == 1
        and isinstance(next(iter(obj.values())), (list, dict))
    ):
        entity, obj = next(iter(obj.items()))
    return {
        "source": "sample",
        "name": "Custom app",
        "base_url": "",
        "auth": ["api_key"],
        "entities": {
            entity: {"read": None, "create": None, "update": None, "fields": sample_fields(obj)}
        },
    }


def import_spec(text: str, hint: str | None = None) -> dict[str, Any]:
    doc = _load(text)
    if isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc):
        out = from_openapi(doc)
    elif isinstance(doc, dict) and "item" in doc and "info" in doc:
        out = from_postman(doc)
    elif isinstance(doc, (dict, list)):
        out = from_sample(doc, hint or "records")
    else:
        raise SpecError("Could not read this file as an API description or a sample.")
    out["entities"] = {
        k: v for k, v in out["entities"].items() if v["read"] or v["create"] or v["fields"]
    }
    if not out["entities"]:
        raise SpecError("No data types found in this file.")
    out["checks"] = _checks(out)
    return out


def _checks(d: dict) -> list[str]:
    notes = []
    if d["source"] != "sample" and not d["base_url"]:
        notes.append("No base URL found; add it before connecting.")
    for k, e in d["entities"].items():
        if not e["read"] and d["source"] != "sample":
            notes.append(f"{k}: no list endpoint, so it can only be pushed to, not read from.")
        if not e["fields"]:
            notes.append(f"{k}: no fields described; send a sample record to map it.")
    return notes
