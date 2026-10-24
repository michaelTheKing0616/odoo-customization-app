"""NF BV-02: per-op read-back of live Odoo state (read-only RPC).

Each function takes a connection-scoped port and one change-set op and
returns ``{postcondition_name: bool, "evidence": {...}}``. Only
search_read / read / fields_get / get_views / search_count are called.
Success claims on the op (status, verified, success) are never read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.bridge.ops import mask_pii
from app.changeset.data_ops import SAMPLE_LIMIT
from app.changeset.ops import OP_CATALOG
from app.changeset.verify import postconditions_for

READ_METHODS: frozenset[str] = frozenset(
    {"search_read", "read", "fields_get", "get_views", "search_count"}
)
PII_PREFIXES: tuple[str, ...] = ("email", "phone", "mobile", "street")
PII_EXACT: frozenset[str] = frozenset(
    {
        "name",
        "display_name",
        "login",
        "contact_address",
        "city",
        "zip",
        "vat",
        "iban",
        "acc_number",
        "website",
    }
)
MASK = "***"
# AC5 (BV-LIVE): free-text fields are masked whatever their content.
FREE_TEXT_KEYS: frozenset[str] = frozenset(
    {"function", "comment", "description", "note", "notes", "body", "body_html", "message"}
)
FREE_TEXT_TYPES: frozenset[str] = frozenset({"text", "html"})


class PortUnavailable(Exception):
    """Port saw HTTP 429/503 from Odoo; ``retry_after`` is the raw header."""

    def __init__(self, status: int, retry_after: str | None = None) -> None:
        super().__init__(f"odoo unavailable ({status})")
        self.status = status
        self.retry_after = retry_after


def rpc(
    port: Any,
    model: str,
    method: str,
    args: Any = (),
    kwargs: dict | None = None,
    *,
    as_uid: int | None = None,
) -> Any:
    """The only way this package talks to the port; refuses non-read methods."""
    if method not in READ_METHODS:
        raise PermissionError(f"read-back may not call {method}")
    return port.call(model, method, args, kwargs or {}, as_uid=as_uid)


def is_pii_key(key: Any) -> bool:
    k = str(key).lower()
    return k in PII_EXACT or k.endswith("_name") or k.startswith(PII_PREFIXES)


def _is_m2o(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], str)
    )


def mask(value: Any, free_text: frozenset[str] | set[str] = frozenset()) -> Any:
    """DEC-023 masking: PII keys, free-text keys/fields, m2o labels, then bridge.ops regex."""
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            if _is_m2o(v):
                out[k] = [v[0], MASK]
            elif (is_pii_key(k) or k in FREE_TEXT_KEYS or k in free_text) and v not in (
                None,
                False,
                "",
            ):
                out[k] = MASK
            else:
                out[k] = mask(v, free_text)
        return out
    if _is_m2o(value):
        return [value[0], MASK]
    if isinstance(value, (list, tuple)):
        return [mask(x, free_text) for x in value]
    return mask_pii(value)


def free_text_fields(port: Any, model: str) -> set[str]:
    """Text/Html field names of ``model`` (fields_get); empty when unreadable."""
    try:
        meta = rpc(port, model, "fields_get", (), {"attributes": ["type"]}) or {}
    except PortUnavailable:
        raise
    except Exception:  # noqa: BLE001 - masking falls back to key patterns
        return set()
    return {
        k for k, v in meta.items() if isinstance(v, Mapping) and v.get("type") in FREE_TEXT_TYPES
    }


def target_model(changeset: Any) -> str | None:
    """First model named by the change-set; None (never a fallback) when none is named."""
    for op in changeset or []:
        p = op.get("params") if isinstance(op, Mapping) else None
        if isinstance(p, Mapping) and isinstance(p.get("model"), str) and p["model"]:
            return p["model"]
    return None


def sample_fields(op: Mapping[str, Any]) -> list[str]:
    """``id`` plus only the fields the op names (params.fields, record/value keys)."""
    p = _params(op)
    names: list[str] = ["id"]
    sources: list[Any] = [p.get("fields") or []]
    if isinstance(p.get("values"), Mapping):
        sources.append(list(p["values"]))
    for rec in p.get("records") or []:
        if isinstance(rec, Mapping):
            sources.append(list(rec))
    for src in sources:
        for name in src if isinstance(src, list) else []:
            if isinstance(name, str) and name and name not in names:
                names.append(name)
    return names


Readback = Callable[[Any, Mapping[str, Any]], dict[str, Any]]


def _params(op: Mapping[str, Any]) -> Mapping[str, Any]:
    p = op.get("params")
    return p if isinstance(p, Mapping) else {}


def _slot(op: Mapping[str, Any], ok: bool, evidence: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {name: bool(ok) for name in postconditions_for(op)}
    out["evidence"] = mask(dict(evidence))
    return out


def _find(port: Any, model: str, p: Mapping[str, Any]) -> dict | None:
    if isinstance(p.get("id"), int):
        rows = rpc(port, model, "read", ([p["id"]],))
    else:
        domain: list = []
        for key in ("key", "name", "model", "res_model"):
            if (
                key in p
                and isinstance(p[key], str)
                and not (key == "model" and model != "ir.model")
            ):
                domain.append((key, "=", p[key]))
                break
        if not domain:
            return None
        rows = rpc(
            port,
            model,
            "search_read",
            (domain,),
            {"limit": 1, "context": {"active_test": False, "ir.ui.menu.full_list": True}},
        )
    return dict(rows[0]) if rows else None


def _values_match(row: Mapping[str, Any], values: Any) -> bool:
    if not isinstance(values, Mapping):
        return True
    return all(row.get(k) == v for k, v in values.items())


def _field_rb(op: Mapping[str, Any], port: Any) -> dict[str, Any]:
    p = _params(op)
    model, name = str(p.get("model") or ""), str(p.get("name") or p.get("field") or "")
    fields = (
        rpc(port, model, "fields_get", (), {"attributes": ["type", "string", "selection"]}) or {}
    )
    meta = fields.get(name)
    kind = str(op.get("type"))
    if kind == "field.delete":
        return _slot(op, meta is None, {"model": model, "field": name, "present": meta is not None})
    ok = isinstance(meta, Mapping)
    if ok and p.get("field_type"):
        ok = meta.get("type") == p["field_type"]
    if ok and kind == "field.update":
        ok = _values_match(meta, p.get("values"))
    if ok and kind == "selection.update":
        want = [str(k) for k, *_ in (p.get("selection") or [])]
        ok = [str(k) for k, *_ in (meta.get("selection") or [])] == want
    return _slot(op, ok, {"model": model, "field": name, "type": (meta or {}).get("type")})


def _model_rb(op: Mapping[str, Any], port: Any) -> dict[str, Any]:
    p = _params(op)
    models = p.get("models") or [p.get("model")]
    names = [str(m.get("model") if isinstance(m, Mapping) else m) for m in models if m]
    rows = rpc(port, "ir.model", "search_read", ([("model", "in", names)],), {"fields": ["model"]})
    found = {r.get("model") for r in rows}
    return _slot(op, bool(names) and set(names) <= found, {"models": sorted(found)})


def _constraint_rb(op: Mapping[str, Any], port: Any) -> dict[str, Any]:
    p = _params(op)
    rows = rpc(
        port, "ir.model.constraint", "search_read", ([("name", "=", p.get("name"))],), {"limit": 1}
    )
    return _slot(op, bool(rows), {"name": p.get("name"), "present": bool(rows)})


def _record_rb(model: str) -> Readback:
    def run(port: Any, op: Mapping[str, Any]) -> dict[str, Any]:
        p = _params(op)
        kind = str(op.get("type"))
        row = _find(port, model, p)
        ok = row is not None
        if ok and kind.endswith((".archive", ".disable")):
            ok = row.get("active") is False
        elif ok:
            ok = _values_match(row, p.get("values"))
            if ok and "active" in row and kind.startswith("automation."):
                ok = row.get("active") is True
            if ok and model == "ir.ui.view" and p.get("node"):
                ok = str(p["node"]) in str(row.get("arch_db") or row.get("arch") or "")
            if ok and kind == "user.groups.assign":
                have = set(row.get("groups_id") or row.get("group_ids") or [])
                ok = set(p.get("group_ids") or []) <= have
        return _slot(
            op, ok, {"model": model, "found": row is not None, "id": (row or {}).get("id")}
        )

    return run


def _stage_rb(port: Any, op: Mapping[str, Any]) -> dict[str, Any]:
    """Stage model comes from the op params; none named = skipped, never crm.stage."""
    model = _params(op).get("model")
    if not isinstance(model, str) or not model:
        out = _slot(op, False, {"reason": "no_stage_model"})
        out["evidence"]["skipped"] = True
        return out
    return _record_rb(model)(port, op)


def _company_id(port: Any, p: Mapping[str, Any]) -> int | None:
    if isinstance(p.get("company_id"), int):
        return p["company_id"]
    rows = rpc(
        port, "res.company", "search_read", ([],), {"fields": ["id"], "limit": 1, "order": "id"}
    )
    return rows[0]["id"] if rows else None


def _xmlid_res(port: Any, module: str | None, name: str) -> list[int]:
    domain: list = [("model", "=", "res.groups"), ("name", "=", name)]
    if module:
        domain.append(("module", "=", module))
    rows = rpc(port, "ir.model.data", "search_read", (domain,), {"fields": ["res_id"], "limit": 2})
    return [int(r["res_id"]) for r in rows]


def _setting_rb(op: Mapping[str, Any], port: Any) -> dict[str, Any]:
    """AC4: company-related settings read res.company; group_* settings read res.groups."""
    p = _params(op)
    key = str(p.get("key") or "")
    meta = (
        rpc(port, "res.config.settings", "fields_get", (), {"attributes": ["type", "related"]})
        or {}
    ).get(key)
    related = str((meta or {}).get("related") or "")
    if related.startswith("company_id.") and related.count(".") == 1:
        fname = related.split(".", 1)[1]
        cid = _company_id(port, p)
        rows = rpc(port, "res.company", "read", ([cid], [fname])) if cid else []
        got = rows[0].get(fname) if rows else None
        return _slot(op, got == p.get("value"), {"source": "res.company", "field": fname})
    if meta is not None and key.startswith("group_"):
        implied = str(p.get("implied_group") or "")
        module, _, name = implied.rpartition(".") if implied else ("", "", key)
        gids = _xmlid_res(port, module or None, name)
        base = _xmlid_res(port, "base", "group_user")
        if len(gids) != 1 or not base:
            out = _slot(op, False, {"source": "res.groups", "reason": "group_unknown"})
            out["evidence"]["skipped"] = True
            return out
        rows = rpc(port, "res.groups", "read", (base, ["implied_ids"]))
        on = bool(rows) and gids[0] in (rows[0].get("implied_ids") or [])
        return _slot(op, on is bool(p.get("value")), {"source": "res.groups", "group": gids[0]})
    out = _param_rb(op, port)
    out["evidence"]["source"] = "ir.config_parameter"
    return out


def _param_rb(op: Mapping[str, Any], port: Any) -> dict[str, Any]:
    p = _params(op)
    row = _find(port, "ir.config_parameter", {"key": p.get("key") or p.get("name")})
    ok = row is not None and str(row.get("value")) == str(p.get("value"))
    return _slot(op, ok, {"key": p.get("key"), "matches": ok})


def _module_rb(op: Mapping[str, Any], port: Any) -> dict[str, Any]:
    p = _params(op)
    rows = rpc(
        port,
        "ir.module.module",
        "search_read",
        ([("name", "=", p.get("name"))],),
        {"fields": ["name", "state"], "limit": 1},
    )
    state = rows[0].get("state") if rows else None
    want = "uninstalled" if op.get("type") == "module.uninstall" else "installed"
    return _slot(op, state == want, {"module": p.get("name"), "state": state})


def data_domain(op: Mapping[str, Any]) -> list:
    p = _params(op)
    if isinstance(p.get("domain"), list):
        return list(p["domain"])
    if isinstance(p.get("ids"), list):
        return [("id", "in", list(p["ids"]))]
    return []


def expected_count(op: Mapping[str, Any], port: Any) -> int:
    """Rows that must match ``data_domain`` after the op."""
    p = _params(op)
    kind = str(op.get("type"))
    if kind in ("data.unlink", "data.delete", "data.archive_batch", "data.merge"):
        return 0 if kind != "data.merge" else 1
    if isinstance(p.get("records"), list):
        return len(p["records"])
    if isinstance(p.get("ids"), list):
        return len(p["ids"])
    return int(p.get("expected_count") or 0)


def _data_rb(op: Mapping[str, Any], port: Any) -> dict[str, Any]:
    p = _params(op)
    model = str(p.get("model") or "")
    domain = data_domain(op)
    actual = rpc(port, model, "search_count", (domain,))
    want = expected_count(op, port)
    ok = actual == want
    return _slot(op, ok, {"model": model, "expected": want, "actual": actual})


def data_sample(port: Any, op: Mapping[str, Any]) -> tuple[str, int, int, list]:
    p = _params(op)
    model = str(p.get("model") or "")
    domain = data_domain(op)
    actual = rpc(port, model, "search_count", (domain,))
    rows = rpc(
        port, model, "search_read", (domain,), {"limit": SAMPLE_LIMIT, "fields": sample_fields(op)}
    )
    hidden = free_text_fields(port, model) if model else set()
    return model, expected_count(op, port), actual, mask(list(rows)[:SAMPLE_LIMIT], hidden)


def _bind(fn: Callable[[Mapping[str, Any], Any], dict[str, Any]]) -> Readback:
    return lambda port, op: fn(op, port)


# Odoo 20 merged ir.model.access + ir.rule into ir.access (for_* booleans, domain).
_ACL20_KEYS: dict[str, str] = {
    "perm_read": "for_read",
    "perm_write": "for_write",
    "perm_create": "for_create",
    "perm_unlink": "for_unlink",
    "domain_force": "domain",
}


def _has_ir_access(port: Any) -> bool:
    return bool(rpc(port, "ir.model", "search_count", ([("model", "=", "ir.access")],)))


def _acl_rb(legacy: str) -> Readback:
    def run(port: Any, op: Mapping[str, Any]) -> dict[str, Any]:
        if not _has_ir_access(port):
            return _record_rb(legacy)(port, op)
        p = dict(_params(op))
        if isinstance(p.get("values"), Mapping):
            p["values"] = {_ACL20_KEYS.get(k, k): v for k, v in p["values"].items()}
        out = _record_rb("ir.access")(port, {**op, "params": p})
        out["evidence"]["source"] = "ir.access"
        return out

    return run


def family_of(kind: str) -> str:
    """Op family key in ``FAMILY_READBACK`` (two-level for action.window / report.action)."""
    for two in ("action.window", "report.action"):
        if kind.startswith(two + "."):
            return two
    if kind in ("field.groups.set", "selection.update", "constraint.sql", "config_param.set"):
        return kind
    return kind.split(".", 1)[0]


def _field_family(kind: str) -> Readback:
    return _bind(_field_rb)


# Explicit read-back per op family (BV-LIVE pin). Unknown family = KeyError at import.
FAMILY_READBACK: dict[str, Callable[[str], Readback]] = {
    "model": lambda k: _bind(_model_rb),
    "field": _field_family,
    "selection.update": _field_family,
    "field.groups.set": lambda k: _record_rb("ir.model.fields"),
    "constraint.sql": lambda k: _bind(_constraint_rb),
    "setting": lambda k: _bind(_setting_rb),
    "config_param.set": lambda k: _bind(_param_rb),
    "module": lambda k: _bind(_module_rb),
    "data": lambda k: _bind(_data_rb),
    "stage": lambda k: _stage_rb,
    "view": lambda k: _record_rb("ir.ui.view"),
    "action.window": lambda k: _record_rb("ir.actions.act_window"),
    "report.action": lambda k: _record_rb("ir.actions.report"),
    "report": lambda k: _record_rb("ir.actions.report"),
    "menu": lambda k: _record_rb("ir.ui.menu"),
    "filter": lambda k: _record_rb("ir.filters"),
    "server_action": lambda k: _record_rb("ir.actions.server"),
    "automation": lambda k: _record_rb("base.automation"),
    "cron": lambda k: _record_rb("ir.cron"),
    "sequence": lambda k: _record_rb("ir.sequence"),
    "mail_template": lambda k: _record_rb("mail.template"),
    "activity_type": lambda k: _record_rb("mail.activity.type"),
    "config_record": lambda k: _record_rb("ir.model.data"),
    "group": lambda k: _record_rb("res.groups"),
    "access": lambda k: _acl_rb("ir.model.access"),
    "rule": lambda k: _acl_rb("ir.rule"),
    "user": lambda k: _record_rb("res.users"),
    "company": lambda k: _record_rb("res.company"),
    "translation": lambda k: _record_rb("ir.model.fields"),
}


def build_table(kinds: Any) -> dict[str, Readback]:
    return {kind: FAMILY_READBACK[family_of(kind)](kind) for kind in kinds}


READBACKS: dict[str, Readback] = build_table(OP_CATALOG)
