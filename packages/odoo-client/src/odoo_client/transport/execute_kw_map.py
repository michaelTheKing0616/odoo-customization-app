"""Map ``execute_kw`` positional args+kwargs onto External JSON-2 named bodies.

Odoo 19 ``POST /json/2/<model>/<method>`` takes a single JSON object of named
kwargs — not the legacy ``execute_kw(db, uid, password, model, method, args, kw)``
shape. Callers of ``OdooClient.execute_kw`` stay unchanged; this module is the
only place that knows the mapping.
"""

from __future__ import annotations

from typing import Any

from odoo_client.compat.version_table import difference


def execute_kw_to_json2_body(
    method: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    *,
    major: int | None = None,
) -> dict[str, Any]:
    """Translate one ``execute_kw`` call into a JSON-2 request body.

    Raises ``ValueError`` when a known method cannot be mapped safely
    (mutant/regression gate — do not silently drop required keys).
    """
    positional = list(args or [])
    named = dict(kwargs or {})
    m = (method or "").strip()

    if m == "search_read":
        return _search_family(positional, named, domain_required=True)
    if m == "search":
        return _search_family(positional, named, domain_required=True)
    if m == "search_count":
        body = _search_family(positional, named, domain_required=True)
        # search_count only accepts domain (+ optional kwargs Odoo ignores harmlessly
        # if we strip unknowns — keep domain only for honesty).
        out: dict[str, Any] = {"domain": body["domain"]}
        return out
    if m == "read":
        return _read_body(positional, named)
    if m == "create":
        return _create_body(positional, named)
    if m == "write":
        return _write_body(positional, named)
    if m == "unlink":
        return _unlink_body(positional, named)
    if m == "fields_get":
        return _fields_get_body(positional, named)
    if m in {"button_immediate_install", "button_immediate_uninstall", "button_immediate_upgrade"}:
        return _ids_only_body(positional, named)
    if m == "name_search":
        return _name_search_body(positional, named, major=major)
    if m in {"read_group", "formatted_read_group"}:
        return _read_group_body(positional, named)
    if m == "update_list":
        # ir.module.module.update_list — no args
        if positional:
            raise ValueError(f"{m}: unexpected positional args {positional!r}")
        return dict(named)

    # Generic: kwargs win; if a single positional dict remains, merge it.
    if not positional:
        return named
    if len(positional) == 1 and isinstance(positional[0], dict) and not named:
        return dict(positional[0])
    if len(positional) == 1 and isinstance(positional[0], list) and "ids" not in named:
        # Common pattern: method([[id, ...]]) for recordset actions
        return {**named, "ids": _flatten_ids(positional[0])}
    raise ValueError(
        f"Cannot map execute_kw method {m!r} with args={positional!r} kwargs={named!r} "
        "to JSON-2 named body — add an explicit mapper"
    )


def _search_family(
    positional: list[Any],
    named: dict[str, Any],
    *,
    domain_required: bool,
) -> dict[str, Any]:
    body = dict(named)
    if positional:
        body["domain"] = positional[0]
        if len(positional) > 1:
            raise ValueError(f"search*: unexpected extra positional args {positional[1:]!r}")
    if domain_required and "domain" not in body:
        raise ValueError("search*: domain is required")
    return body


def _read_body(positional: list[Any], named: dict[str, Any]) -> dict[str, Any]:
    body = dict(named)
    if not positional:
        if "ids" not in body:
            raise ValueError("read: ids required")
        return body
    body["ids"] = _flatten_ids(positional[0])
    if len(positional) >= 2 and "fields" not in body:
        body["fields"] = positional[1]
    if len(positional) > 2:
        raise ValueError(f"read: unexpected extra positional args {positional[2:]!r}")
    return body


def _create_body(positional: list[Any], named: dict[str, Any]) -> dict[str, Any]:
    if "vals_list" in named:
        return dict(named)
    if not positional:
        raise ValueError("create: vals_list (or positional vals) required")
    raw = positional[0]
    # execute_kw convention in this repo: create([vals]) where vals is one dict.
    # JSON-2 wants vals_list: [dict, ...].
    if isinstance(raw, dict):
        vals_list: list[Any] = [raw]
    elif isinstance(raw, list):
        if raw and all(isinstance(x, dict) for x in raw):
            vals_list = raw
        elif len(raw) == 1 and isinstance(raw[0], dict):
            vals_list = [raw[0]]
        else:
            # create([[vals]]) should not happen; fail closed
            raise ValueError(f"create: cannot interpret positional vals {raw!r}")
    else:
        raise ValueError(f"create: expected dict or list of dicts, got {type(raw)!r}")
    if len(positional) > 1:
        raise ValueError(f"create: unexpected extra positional args {positional[1:]!r}")
    out = dict(named)
    out["vals_list"] = vals_list
    return out


def _write_body(positional: list[Any], named: dict[str, Any]) -> dict[str, Any]:
    body = dict(named)
    if positional:
        body["ids"] = _flatten_ids(positional[0])
        if len(positional) < 2 and "vals" not in body:
            raise ValueError("write: vals required")
        if len(positional) >= 2:
            body["vals"] = positional[1]
        if len(positional) > 2:
            raise ValueError(f"write: unexpected extra positional args {positional[2:]!r}")
    if "ids" not in body or "vals" not in body:
        raise ValueError("write: ids and vals required")
    return body


def _unlink_body(positional: list[Any], named: dict[str, Any]) -> dict[str, Any]:
    body = dict(named)
    if positional:
        body["ids"] = _flatten_ids(positional[0])
        if len(positional) > 1:
            raise ValueError(f"unlink: unexpected extra positional args {positional[1:]!r}")
    if "ids" not in body:
        raise ValueError("unlink: ids required")
    return body


def _fields_get_body(positional: list[Any], named: dict[str, Any]) -> dict[str, Any]:
    body = dict(named)
    if positional:
        # fields_get(allfields=None, attributes=None) — first positional is allfields
        if "allfields" not in body and positional[0] is not None:
            body["allfields"] = positional[0]
        if len(positional) >= 2 and "attributes" not in body:
            body["attributes"] = positional[1]
        if len(positional) > 2:
            raise ValueError(f"fields_get: unexpected extra positional args {positional[2:]!r}")
    return body


def _ids_only_body(positional: list[Any], named: dict[str, Any]) -> dict[str, Any]:
    """Recordset button methods: execute_kw([[id]]) → {ids: [id]}."""
    body = dict(named)
    if positional:
        body["ids"] = _flatten_ids(positional[0])
        if len(positional) > 1:
            raise ValueError(f"ids-only method: unexpected extra args {positional[1:]!r}")
    if "ids" not in body:
        raise ValueError("ids-only method: ids required")
    return body


def _read_group_body(positional: list[Any], named: dict[str, Any]) -> dict[str, Any]:
    """read_group / formatted_read_group(domain, fields, groupby, **kwargs)."""
    body = dict(named)
    if positional:
        body["domain"] = positional[0]
        if len(positional) > 1 and "fields" not in body:
            body["fields"] = positional[1]
        if len(positional) > 2 and "groupby" not in body:
            body["groupby"] = positional[2]
        if len(positional) > 3:
            raise ValueError(
                f"read_group: unexpected extra positional args {positional[3:]!r}"
            )
    if "domain" not in body:
        raise ValueError("read_group: domain is required")
    return body


def _name_search_body(
    positional: list[Any],
    named: dict[str, Any],
    *,
    major: int | None = None,
) -> dict[str, Any]:
    body = dict(named)
    # name_search(name='', args|domain=None, operator='ilike', limit=100)
    filter_key = "args"
    if major is not None:
        filter_key = "domain" if difference("name_search_kw", major) == "domain" else "args"
    if positional and "name" not in body:
        body["name"] = positional[0]
    if len(positional) > 1:
        body.setdefault(filter_key, positional[1])
    if len(positional) > 2 and "operator" not in body:
        body["operator"] = positional[2]
    if len(positional) > 3 and "limit" not in body:
        body["limit"] = positional[3]
    if major is not None:
        other = "args" if filter_key == "domain" else "domain"
        if other in body and filter_key not in body:
            body[filter_key] = body.pop(other)
        elif other in body and filter_key in body:
            body.pop(other, None)
    return body


def _flatten_ids(raw: Any) -> list[int]:
    """Normalize execute_kw id forms: [1,2], [[1,2]], 1 → [1,2] / [1]."""
    if isinstance(raw, int):
        return [raw]
    if not isinstance(raw, list):
        raise ValueError(f"ids: expected list or int, got {type(raw)!r}")
    if len(raw) == 1 and isinstance(raw[0], list):
        raw = raw[0]
    out: list[int] = []
    for item in raw:
        if isinstance(item, bool):
            raise ValueError(f"ids: invalid id {item!r}")
        if isinstance(item, int):
            out.append(item)
        else:
            raise ValueError(f"ids: expected int elements, got {item!r}")
    return out
