"""One version-aware adapter for Odoo access rules (ir.access) and record rules (ir.rule).

Ingenium code speaks the original Odoo 20 ir.access shape: fields ``model`` (technical
name) and ``group``. Odoo 20 nightlies from 2026-09 renamed them to ``model_id`` and
``group_id`` and dropped ir.rule (row limits live as ir.access domains). Every
execute_kw call goes through :func:`adapt_call` / :func:`adapt_result`, so call sites
never patch field names themselves. Odoo 17-19 (ir.model.access / ir.rule) pass through.
"""
from __future__ import annotations

from typing import Any, Callable

Dispatch = Callable[[str, str, list[Any] | None, dict[str, Any] | None], Any]

_READS = {"search", "search_read", "search_count", "read", "read_group", "fields_get", "name_search", "web_search_read"}
_FIELD_MAP = {"model": "model_id", "group": "group_id"}


class IrAccessShape:
    """Detected once per client: does ir.access use model_id/group_id; does ir.rule exist."""

    def __init__(self, dispatch: Dispatch, major: int | None) -> None:
        self.major = int(major or 0)
        self.renamed = False
        self.rule_missing = False
        if self.major < 20:
            return
        try:
            f = dispatch("ir.access", "fields_get", [], {"attributes": ["type"]}) or {}
            self.renamed = "model" not in f and "model_id" in f
        except Exception:  # noqa: BLE001 - keep original names
            self.renamed = False
        try:
            self.rule_missing = not dispatch("ir.model", "search_count", [[("model", "=", "ir.rule")]], None)
        except Exception:  # noqa: BLE001
            self.rule_missing = False


def _map_field(name: str) -> str:
    head, dot, rest = name.partition(".")
    if head == "model":
        return "model_id.model" if not dot else f"model_id.{rest}"
    if head == "group":
        return "group_id" + (dot + rest if dot else "")
    return name


def _map_domain(domain: Any) -> Any:
    if not isinstance(domain, (list, tuple)):
        return domain
    out = []
    for leaf in domain:
        if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and isinstance(leaf[0], str):
            out.append((_map_field(leaf[0]), leaf[1], leaf[2]))
        else:
            out.append(leaf)
    return out


def _map_fields(fields: Any) -> Any:
    if not isinstance(fields, (list, tuple)):
        return fields
    mapped = [_FIELD_MAP.get(f, f) for f in fields]
    return list(dict.fromkeys(mapped))


def _map_vals(vals: Any, dispatch: Dispatch) -> Any:
    if isinstance(vals, list):
        return [_map_vals(v, dispatch) for v in vals]
    if not isinstance(vals, dict):
        return vals
    out = dict(vals)
    if "model" in out:
        m = out.pop("model")
        if isinstance(m, str):
            ids = dispatch("ir.model", "search", [[("model", "=", m)]], {"limit": 1}) or []
            if not ids:
                raise ValueError(f"Model {m!r} not found")
            m = ids[0]
        out["model_id"] = m
    if "group" in out:
        out["group_id"] = out.pop("group")
    return out


def adapt_call(shape: IrAccessShape, model: str, method: str, args: list[Any] | None,
               kwargs: dict[str, Any] | None, dispatch: Dispatch) -> tuple[list[Any] | None, dict[str, Any] | None]:
    if model != "ir.access" or not shape.renamed:
        return args, kwargs
    args = list(args or [])
    kwargs = dict(kwargs or {})
    if method in {"search", "search_read", "search_count", "read_group", "web_search_read"} and args:
        args[0] = _map_domain(args[0])
    if "domain" in kwargs:
        kwargs["domain"] = _map_domain(kwargs["domain"])
    if "fields" in kwargs:
        kwargs["fields"] = _map_fields(kwargs["fields"])
    if method == "read" and len(args) > 1:
        args[1] = _map_fields(args[1])
    if method == "create" and args:
        args[0] = _map_vals(args[0], dispatch)
    if method == "write" and len(args) > 1:
        args[1] = _map_vals(args[1], dispatch)
    return args, kwargs


def adapt_result(shape: IrAccessShape, model: str, method: str, result: Any, dispatch: Dispatch) -> Any:
    if model != "ir.access" or not shape.renamed or method not in {"read", "search_read"}:
        return result
    rows = result if isinstance(result, list) else []
    mids = sorted({r["model_id"][0] for r in rows if isinstance(r, dict)
                   and isinstance(r.get("model_id"), (list, tuple)) and r["model_id"]})
    tech: dict[int, str] = {}
    if mids:
        for m in dispatch("ir.model", "read", [mids], {"fields": ["model"]}) or []:
            tech[int(m["id"])] = str(m["model"])
    for r in rows:
        if not isinstance(r, dict):
            continue
        if "model_id" in r:
            mv = r["model_id"]
            r.setdefault("model", tech.get(mv[0], "") if isinstance(mv, (list, tuple)) and mv else (mv or ""))
        if "group_id" in r:
            r.setdefault("group", r["group_id"])
    return result


def missing_rule_result(shape: IrAccessShape, model: str, method: str) -> tuple[bool, Any]:
    """ir.rule on a v20 build without it: reads are empty; writes are refused plainly."""
    if model != "ir.rule" or not shape.rule_missing:
        return False, None
    if method == "search_count":
        return True, 0
    if method in _READS:
        return True, {} if method == "fields_get" else []
    raise RuntimeError(
        "This Odoo 20 database has no record rules (ir.rule); row limits are access-rule domains. "
        "Use the Access screen, which writes them as ir.access domains."
    )
