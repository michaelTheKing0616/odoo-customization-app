"""Deterministic Odoo validation of an App design before it is compiled (stage 2 of the harness rework).

Evidence, not wording: every model, field, relation, write, app and automation in a design is checked
against the target database's schema (``ai_schema_client`` SchemaClient: Live / Catalog / Fake) plus the
Odoo version and hosting plan. Fail closed: each problem is a specific error; nothing is silently dropped.
Behind the flag ``INGENIUM_DESIGN_ADMISSION`` (off by default) so existing checks are unchanged.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

SUPPORTED_MAJORS = (17, 18, 19, 20)
_IDENT = re.compile(r"^x_[a-z0-9_]{1,60}$")
_BASE_TTYPES = {"char", "text", "html", "integer", "float", "monetary", "boolean", "date", "datetime",
                "selection", "many2one", "one2many", "many2many", "binary"}
_TTYPES_BY_MAJOR = {17: _BASE_TTYPES | {"properties"}, 18: _BASE_TTYPES | {"properties"},
                    19: _BASE_TTYPES | {"properties"}, 20: _BASE_TTYPES | {"properties"}}
_WHEN = {"on_create", "on_write", "on_time", "untouched"}
_ACTIONS = {"activity", "set_fields", "notify"}
# Odoo's base.automation trigger values per major (17+ share these).
_TRIGGERS_BY_MAJOR = {m: {"on_create", "on_write", "on_create_or_write", "on_time", "on_change", "on_unlink"}
                      for m in SUPPORTED_MAJORS}
ENTERPRISE_ONLY = {"sale_renting", "helpdesk", "planning", "documents", "sign", "quality_control",
                   "field_service", "industry_fsm", "appointment", "knowledge", "web_studio"}
_ALWAYS_PRESENT = {"res.partner", "res.users", "res.company", "res.currency", "res.groups", "ir.attachment",
                   "uom.uom", "product.product", "product.template"}


def admission_enabled() -> bool:
    return os.environ.get("INGENIUM_DESIGN_ADMISSION", "").strip().lower() in {"1", "true", "on", "yes"}


@dataclass
class AdmissionError:
    code: str
    item: str
    message: str


@dataclass
class AdmissionResult:
    ok: bool
    errors: list[AdmissionError] = field(default_factory=list)
    checked: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": [asdict(e) for e in self.errors], "checked": self.checked}


def view_tag_for(major: int) -> str:
    from app.compat.odoo_versions import list_view_tag

    return list_view_tag(major)


def validate_design(design: dict[str, Any], schema: Any, *, major: int, hosting: str = "unknown",
                    edition: str = "unknown", installed: set[str] | None = None) -> AdmissionResult:
    """``schema``: SchemaClient (model_exists, fields_get, relation_ok, field_is_writable).
    ``hosting``: online | sh | onpremise | unknown. ``edition``: enterprise | community | unknown."""
    errs: list[AdmissionError] = []
    add = lambda code, item, msg: errs.append(AdmissionError(code, item, msg))  # noqa: E731
    checked = {"models": 0, "fields": 0, "relations": 0, "extensions": 0, "apps": 0, "automations": 0}
    if major not in SUPPORTED_MAJORS:
        add("version_unsupported", str(major), f"Odoo {major} is not supported; supported: {', '.join(map(str, SUPPORTED_MAJORS))}.")
        return AdmissionResult(False, errs, checked)
    ttypes = _TTYPES_BY_MAJOR[major]
    installed = installed or set()
    new = [m for m in design.get("new_models") or [] if isinstance(m, dict)]
    new_names = {str(m.get("name") or "") for m in new}

    # Stock apps the design asks to install first (code-verified installable): their models are known.
    # Planned installs: the design suggests installing the app (installed is not True) and the
    # database can install it (code-verified when the schema knows installable modules).
    from app.compat.odoo_versions import module_for_model

    can_install = getattr(schema, "module_installable", None)
    suggested = {str(i.get("module") or "") for i in design.get("integrations") or []
                 if isinstance(i, dict) and i.get("installed") is not True}
    planned_models = {m for i in design.get("integrations") or [] if isinstance(i, dict)
                      and i.get("installed") is False and i.get("status") == "available" for m in i.get("models") or []}
    for ext in design.get("stock_extensions") or []:
        mdl = str((ext or {}).get("model") or "") if isinstance(ext, dict) else ""
        mod = module_for_model(mdl, major)
        if mdl and not schema.model_exists(mdl) and mod in suggested and can_install is not None and can_install(mod):  # fail closed when unknown
            planned_models.add(mdl)

    def model_known(name: str) -> bool:
        return (name in new_names or name in _ALWAYS_PRESENT or name in planned_models
                or bool(schema.model_exists(name)))

    seen: set[str] = set()
    for m in new:
        name = str(m.get("name") or "")
        checked["models"] += 1
        if not _IDENT.match(name):
            add("model_name_invalid", name, f"Record name '{name}' must start with x_ and use a-z, 0-9, _.")
        if name in seen:
            add("model_duplicate", name, f"Record '{name}' is defined twice.")
        seen.add(name)
        if schema.model_exists(name):
            add("model_exists", name, f"'{name}' already exists in this database; extend it instead of creating it.")
        fnames: set[str] = set()
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            checked["fields"] += 1
            fn, tt = str(f.get("name") or ""), str(f.get("ttype") or "")
            item = f"{name}.{fn}"
            if fn in fnames:
                add("field_duplicate", item, f"Field '{fn}' appears twice on '{name}'.")
            fnames.add(fn)
            if not _IDENT.match(fn):
                add("field_name_invalid", item, f"Field '{fn}' must start with x_.")
            if tt not in ttypes:
                add("field_type_invalid", item, f"Field type '{tt}' does not exist in Odoo {major}.")
            if tt == "selection" and not f.get("selection"):
                add("selection_empty", item, f"Choice field '{fn}' has no choices.")
            if tt in {"many2one", "one2many", "many2many"}:
                checked["relations"] += 1
                rel = str(f.get("relation") or "")
                if not rel or not model_known(rel):
                    add("relation_target_missing", item, f"'{fn}' links to '{rel or '?'}', which is not in this database or the design.")
                if tt == "one2many":
                    inv = str(f.get("inverse_name") or "")
                    child = next((c for c in new if c.get("name") == rel), None)
                    if child is not None:
                        back = next((g for g in child.get("fields") or [] if isinstance(g, dict) and g.get("name") == inv), None)
                        if back is None or back.get("ttype") != "many2one" or back.get("relation") != name:
                            add("one2many_inverse_missing", item, f"'{fn}' needs a link back from '{rel}' (field '{inv or '?'}') to '{name}'.")
                    elif rel and not schema.relation_ok(rel, inv, name) and not any(
                            isinstance(g, dict) and g.get("name") == inv and g.get("ttype") == "many2one" and g.get("relation") == name
                            for e in design.get("stock_extensions") or [] if isinstance(e, dict) and e.get("model") == rel
                            for g in e.get("fields") or []):
                        add("one2many_inverse_missing", item, f"'{rel}.{inv or '?'}' does not link back to '{name}'.")
            if tt == "monetary" and not any(str(g.get("ttype")) == "many2one" and g.get("relation") == "res.currency"
                                            for g in m.get("fields") or [] if isinstance(g, dict)):
                add("monetary_without_currency", item, f"Money field '{fn}' needs a currency field on '{name}'.")
    for ext in design.get("stock_extensions") or []:
        if not isinstance(ext, dict):
            continue
        model = str(ext.get("model") or "")
        checked["extensions"] += 1
        if model in planned_models:
            continue  # fields checked after the planned install
        if not schema.model_exists(model):
            add("extension_model_missing", model, f"'{model}' is not installed in this database, so it cannot be extended.")
            continue
        existing = schema.fields_get(model) or {}
        for f in ext.get("fields") or []:
            fn = str((f or {}).get("name") or "")
            if fn in existing:
                add("extension_field_exists", f"{model}.{fn}", f"'{model}' already has '{fn}'.")
            elif not _IDENT.match(fn):
                add("field_name_invalid", f"{model}.{fn}", f"Field '{fn}' must start with x_.")
    for integ in design.get("integrations") or []:
        if not isinstance(integ, dict) or not integ.get("module") or integ.get("status") == "deferred":
            continue
        mod = str(integ["module"])
        checked["apps"] += 1
        if mod in ENTERPRISE_ONLY and edition == "community" and hosting != "online":
            add("app_enterprise_only", mod, f"'{mod}' needs Odoo Enterprise; this database is Community.")
        elif installed and mod not in installed and integ.get("required"):
            add("app_not_installed", mod, f"'{mod}' is required but not installed.")
    known_fields: dict[str, dict[str, Any]] = {}
    for m in new:
        known_fields[str(m.get("name"))] = {str(f.get("name")): f for f in m.get("fields") or [] if isinstance(f, dict)}
    groups = {str(g.get("name")) for g in design.get("security_groups") or [] if isinstance(g, dict)}
    ext_fields: dict[str, dict[str, Any]] = {}  # fields the design adds to stock models exist after apply
    for ext in design.get("stock_extensions") or []:
        if isinstance(ext, dict):
            ext_fields.setdefault(str(ext.get("model") or ""), {}).update(
                {str(f.get("name")): f for f in ext.get("fields") or [] if isinstance(f, dict)})
    for a in design.get("automations") or []:
        if not isinstance(a, dict):
            continue
        checked["automations"] += 1
        spec, target, label = a.get("automation") or {}, str(a.get("target_model") or ""), str(a.get("label") or "automation")
        when, action = str(spec.get("when") or ""), str(spec.get("action") or "")
        if when not in _WHEN or action not in _ACTIONS:
            add("automation_type_unsupported", label, f"'{label}': '{when}/{action}' is not an automation App Studio can create.")
            continue
        trig = "on_time" if when == "untouched" else when
        if trig not in _TRIGGERS_BY_MAJOR[major]:
            add("automation_trigger_unsupported", label, f"Odoo {major} has no '{trig}' trigger.")
        if not target or not model_known(target):
            add("automation_target_missing", label, f"'{label}' acts on '{target or '?'}', which does not exist.")
            continue
        if target in planned_models:
            continue  # planned install: fields checked after install
        fields_of = known_fields.get(target) or {**(schema.fields_get(target) or {}), **ext_fields.get(target, {})}
        if when == "on_time":
            df = str(spec.get("date_field") or "")
            if df not in fields_of or str((fields_of.get(df) or {}).get("ttype") or (fields_of.get(df) or {}).get("type")) not in {"date", "datetime"}:
                add("automation_date_field_missing", label, f"'{label}' counts from '{df or '?'}', which is not a date field on '{target}'.")
        if when == "untouched" and int(spec.get("offset_days") or 0) <= 0:
            add("automation_days_missing", label, f"'{label}' needs a number of days.")
        for k in (spec.get("values") or {}):
            if target in known_fields:
                if k not in fields_of:
                    add("automation_write_field_missing", f"{label}:{k}", f"'{label}' writes '{k}', which '{target}' does not have.")
            elif not schema.field_is_writable(target, k):
                add("automation_write_not_writable", f"{label}:{k}", f"'{label}' writes '{target}.{k}', which cannot be written.")
        for t in spec.get("condition") or []:
            if t and t[0] not in fields_of and t[0] not in {"write_date", "create_date", "id"}:
                add("automation_condition_field_missing", f"{label}:{t[0]}", f"'{label}' checks '{t[0]}', which '{target}' does not have.")
        if action == "notify" and spec.get("group") and spec["group"] not in groups:
            add("automation_group_missing", label, f"'{label}' notifies '{spec['group']}', a role this app does not define.")
    for p in design.get("python_needed") or []:
        if isinstance(p, dict) and hosting == "online" and p.get("delivery_lane") not in {"online_scheduled_action", None, ""} \
                and str(p.get("online_blocked")).lower() == "true":
            add("online_custom_code_blocked", str(p.get("label") or "custom code"),
                f"'{p.get('label')}' needs a custom Python module, which Odoo Online does not allow.")
    return AdmissionResult(not errs, errs, checked)


class SnapshotSchemaClient:
    """SchemaClient over the existing live snapshot (odoo_snapshot.Snapshot) when no RPC client is at hand."""

    def __init__(self, snap: Any) -> None:
        self._s = snap

    def model_exists(self, model: str) -> bool:
        return model in (getattr(self._s, "index", {}) or {}) or model in (getattr(self._s, "models", {}) or {})

    def fields_get(self, model: str) -> dict[str, dict[str, Any]]:
        info = (getattr(self._s, "models", {}) or {}).get(model)
        if info is None:
            return {}
        return {n: {"type": f.type, "relation": f.relation, "readonly": f.readonly, "store": f.stored}
                for n, f in (info.fields or {}).items()}

    def relation_ok(self, model: str, field: str, relation: str) -> bool:
        meta = self.fields_get(model).get(field) or {}
        return meta.get("type") in {"many2one", "one2many", "many2many"} and meta.get("relation") == relation

    def field_is_writable(self, model: str, field: str) -> bool:
        meta = self.fields_get(model).get(field)
        return bool(meta) and not meta.get("readonly")

    def module_installable(self, module: str) -> bool:
        return bool(module) and module in (getattr(self._s, "installable", None) or {})

    def view_has_field(self, model: str, field: str) -> bool:
        return field in self.fields_get(model)


def validate_compiled_views(draft: dict[str, Any], major: int) -> list[AdmissionError]:
    """Version grammar of the compiled views (e.g. Odoo 17 lists are <tree>, kanban cards are kanban-box)."""
    from app.compat.odoo_versions import kanban_card_template, list_view_tag

    out: list[AdmissionError] = []
    for v in draft.get("views") or []:
        arch, name = str(v.get("arch") or ""), str(v.get("name") or "view")
        tag, card = list_view_tag(major), kanban_card_template(major)
        if tag == "tree" and arch.startswith("<list"):
            out.append(AdmissionError("view_tag_version", name, "Odoo 17 list views must use <tree>, not <list>."))
        if card == "kanban-box" and 't-name="card"' in arch:
            out.append(AdmissionError("kanban_template_version", name, "Odoo 17 kanban cards use t-name=\"kanban-box\"."))
        if tag == "list" and arch.startswith("<tree"):
            out.append(AdmissionError("view_tag_version", name, f"Odoo {major} list views use <list>, not <tree>."))
    return out


def _merge_snapshot_checks(design: dict[str, Any], snap: Any, res: AdmissionResult) -> AdmissionResult:
    """Extend, don't duplicate: the existing odoo_snapshot.validate_design errors come first."""
    from app.odoo_snapshot import validate_design as snapshot_validate

    base = [AdmissionError("snapshot_" + str(x.get("scope") or "design"), str(x.get("where") or ""), str(x.get("message") or ""))
            for x in snapshot_validate(design, snap) if x.get("severity") == "error"]
    have = {(e.item, e.message) for e in res.errors}
    res.errors = base + [e for e in res.errors if (e.item, e.message) not in have]
    res.ok = not res.errors
    return res


def _admit(design: dict[str, Any], snap: Any, draft: dict[str, Any] | None) -> AdmissionResult:
    if snap is None or not getattr(snap, "ok", False):
        return AdmissionResult(False, [AdmissionError("schema_unavailable", "database",
                                                      "Unchecked: could not read this database's structure, so the design was not admitted.")],
                               {"status": "unchecked"})  # type: ignore[dict-item]
    major = int(getattr(snap, "major", 0) or 0)
    hosting = "online" if str(getattr(snap, "series", "")).startswith("saas") else "unknown"
    res = validate_design(design, SnapshotSchemaClient(snap), major=major, hosting=hosting,
                          edition=str(getattr(snap, "edition", "unknown")), installed=set(getattr(snap, "modules", {}) or {}))
    res = _merge_snapshot_checks(design, snap, res)
    if draft is not None:
        res.errors += validate_compiled_views(draft, major)
        res.ok = not res.errors
    return res


def admit_design_for_connection(design: dict[str, Any], draft: dict[str, Any] | None = None) -> AdmissionResult | None:
    """Flagged check at generate time on the request's snapshot. None when the flag is off."""
    if not admission_enabled():
        return None
    from app.odoo_snapshot import current_snapshot

    return _admit(design, current_snapshot(), draft)


def admit_before_apply(client: Any, spec: dict[str, Any]) -> AdmissionResult | None:
    """Re-validate against a FRESH snapshot immediately before apply (one reader/cache: odoo_snapshot),
    then clear that cache entry so the next read sees what apply changed. None when the flag is off."""
    if not admission_enabled():
        return None
    design = spec.get("_app_design") if isinstance(spec.get("_app_design"), dict) else None
    if design is None:
        return None
    from app.odoo_snapshot import clear_snapshot_cache, get_snapshot

    key = f"apply:{getattr(client, 'url', '') or getattr(client, 'base_url', '') or id(client)}"

    def call(model: str, method: str, args: list, kwargs: dict) -> Any:
        return client.execute_kw(model, method, args, kwargs)

    clear_snapshot_cache(key)
    try:
        snap = get_snapshot(call, key, "", [m.get("name") for m in design.get("new_models") or [] if isinstance(m, dict)]
                            + [e.get("model") for e in design.get("stock_extensions") or [] if isinstance(e, dict)], ttl=0.0)
    except Exception:  # noqa: BLE001
        snap = None
    try:
        return _admit(design, snap, spec)
    finally:
        clear_snapshot_cache(key)


# ------------------------------------------------------------------ stable external ids (idempotent re-apply)
XMLID_MODULE = "ingenium"


def requirement_xmlid(external_id: str, idx: int = 0) -> str:
    """module.name for a requirement-derived record; idx>0 for the 2nd+ action of one automation."""
    name = re.sub(r"[^a-z0-9_]", "_", str(external_id or "").lower()).strip("_")[:120]
    if not name:
        return ""
    return f"{XMLID_MODULE}.{name}" + (f"_{idx + 1}" if idx else "")


def find_by_xmlid(client: Any, xmlid: str, model: str) -> int | None:
    """res_id of a live record tagged with ``xmlid`` (and still existing), else None."""
    if not xmlid:
        return None
    module, name = xmlid.split(".", 1)
    rows = client.execute_kw("ir.model.data", "search_read", [[("module", "=", module), ("name", "=", name),
                             ("model", "=", model)]], {"fields": ["res_id"], "limit": 1})
    if not rows:
        return None
    rid = int(rows[0]["res_id"])
    return rid if client.execute_kw(model, "search", [[("id", "=", rid)]], {"limit": 1}) else None


def tag_xmlid(client: Any, xmlid: str, model: str, res_id: int) -> None:
    """Record ``xmlid`` -> res_id (replacing a dangling tag) so re-apply updates instead of duplicating."""
    if not xmlid or not res_id:
        return
    module, name = xmlid.split(".", 1)
    stale = client.execute_kw("ir.model.data", "search", [[("module", "=", module), ("name", "=", name)]], {})
    if stale:
        client.execute_kw("ir.model.data", "unlink", [stale], {})
    client.execute_kw("ir.model.data", "create", [{"module": module, "name": name, "model": model,
                                                    "res_id": int(res_id), "noupdate": True}], {})
