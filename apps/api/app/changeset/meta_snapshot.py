"""In-memory MetaSnapshot for order-independent metadata equality.

``metadata_snapshots`` (``MetadataSnapshot`` in ``db_models``) is one restore
row per resource: ``resource_type``, ``resource_key``, and a ``payload_json``
blob, written through a database session. That shape is a single rollback
payload. It is not this export, so it is not reused and nothing here is
persisted.

``build`` and ``from_memory`` take a caller-supplied mapping and do not call
Odoo. ``capture`` reads a port with public ``fields_get`` and ``search_read``
only. It never writes. It reads with the default ``active_test``, so archived
rows are not part of the export.

Equality ignores key order and list order at every level, using the same
comparison as undo (``snapshots_match``). Values such as ``sequence`` and
``priority`` are still compared. Config parameters are kept only when their
key is on the caller allowlist, and never when the key is protected or
secret-shaped. ``capture`` does not read any other key. Xmlids are kept only
for the ``ingenium`` module.
"""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Collection, Mapping
from typing import Any

from app.changeset.rollback import snapshots_match
from app.changeset.setting_ops import PROTECTED_CONFIG_KEYS
from app.config_packet.settings import is_secret_key

EXPORT_KEYS: tuple[str, ...] = (
    "models",
    "fields",
    "views",
    "actions",
    "menus",
    "acl",
    "rules",
    "groups",
    "automations",
    "crons",
    "templates",
    "sequences",
    "config_params",
    "filters",
    "xmlids",
)

# Odoo model names a payload may use in place of the export key.
_ALIASES: dict[str, str] = {
    "models": "models",
    "ir.model": "models",
    "fields": "fields",
    "ir.model.fields": "fields",
    "views": "views",
    "ir.ui.view": "views",
    "actions": "actions",
    "ir.actions.act_window": "actions",
    "ir.actions.server": "actions",
    "ir.actions.report": "actions",
    "menus": "menus",
    "ir.ui.menu": "menus",
    "acl": "acl",
    "ir.model.access": "acl",
    "ir.access": "acl",
    "rules": "rules",
    "ir.rule": "rules",
    "groups": "groups",
    "res.groups": "groups",
    "automations": "automations",
    "base.automation": "automations",
    "crons": "crons",
    "ir.cron": "crons",
    "templates": "templates",
    "mail.template": "templates",
    "sequences": "sequences",
    "ir.sequence": "sequences",
    "config_params": "config_params",
    "ir.config_parameter": "config_params",
    "filters": "filters",
    "ir.filters": "filters",
    "xmlids": "xmlids",
    "ir.model.data": "xmlids",
}

# In-memory op store (``apply_memory``) projected into the same export.
_MEMORY_BUCKETS: dict[str, str] = {
    "model.create": "models",
    "model.scaffold": "models",
    "constraint.sql": "models",
    "field.create": "fields",
    "field.update": "fields",
    "field.deprecate": "fields",
    "selection.update": "fields",
    "view.inherit.create": "views",
    "view.inherit.update": "views",
    "view.archive": "views",
    "view.create_base": "views",
    "report.inherit": "views",
    "action.window.create": "actions",
    "action.window.update": "actions",
    "server_action.create": "actions",
    "server_action.update": "actions",
    "report.action.create": "actions",
    "report.action.update": "actions",
    "menu.create": "menus",
    "menu.update": "menus",
    "menu.archive": "menus",
    "access.create": "acl",
    "access.update": "acl",
    "rule.create": "rules",
    "rule.update": "rules",
    "group.create": "groups",
    "automation.create": "automations",
    "automation.update": "automations",
    "automation.disable": "automations",
    "cron.create": "crons",
    "cron.update": "crons",
    "cron.disable": "crons",
    "mail_template.create": "templates",
    "mail_template.update": "templates",
    "sequence.create": "sequences",
    "sequence.update": "sequences",
    "config_param.set": "config_params",
    "filter.create": "filters",
    "filter.update": "filters",
}

_VOLATILE = frozenset(
    {
        "write_date",
        "create_date",
        "write_uid",
        "create_uid",
        "__last_update",
        "display_name",
    }
)
_XMLID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INGENIUM_MODULE = "ingenium"

_GROUP_FIELDS = ("groups_id", "group_ids")

# Export key, Odoo model, and the fields asked for. ``capture`` keeps only
# the fields ``fields_get`` reports, so one list serves Odoo 16 to 20. A
# model that is not in ``ir.model`` is skipped (``ir.rule`` on 20, or
# ``base.automation`` when that module is not installed). Counters and run
# timestamps (``number_next``, ``nextcall``, ``last_run``) are not asked for.
CAPTURE_SOURCES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("models", "ir.model", ("model", "name", "state", "transient")),
    (
        "fields",
        "ir.model.fields",
        (
            "model",
            "name",
            "ttype",
            "relation",
            "relation_field",
            "required",
            "readonly",
            "store",
            "state",
            "field_description",
            "help",
            "related",
            "compute",
            "depends",
        ),
    ),
    (
        "views",
        "ir.ui.view",
        (
            "name",
            "model",
            "type",
            "mode",
            "priority",
            "inherit_id",
            "key",
            "arch_db",
            *_GROUP_FIELDS,
        ),
    ),
    (
        "actions",
        "ir.actions.act_window",
        ("name", "type", "res_model", "view_mode", "domain", "context", "target", *_GROUP_FIELDS),
    ),
    (
        "actions",
        "ir.actions.server",
        ("name", "type", "model_id", "state", "code", "binding_model_id", *_GROUP_FIELDS),
    ),
    (
        "actions",
        "ir.actions.report",
        ("name", "type", "model", "report_name", "report_type", "binding_model_id", *_GROUP_FIELDS),
    ),
    (
        "menus",
        "ir.ui.menu",
        ("name", "parent_id", "action", "sequence", "web_icon", *_GROUP_FIELDS),
    ),
    (
        "acl",
        "ir.model.access",
        ("name", "model_id", "group_id", "perm_read", "perm_write", "perm_create", "perm_unlink"),
    ),
    ("acl", "ir.access", ("name", "model_id", "group_id", "operation", "domain")),
    (
        "rules",
        "ir.rule",
        (
            "name",
            "model_id",
            "domain_force",
            "groups",
            "global",
            "perm_read",
            "perm_write",
            "perm_create",
            "perm_unlink",
        ),
    ),
    ("groups", "res.groups", ("name", "category_id", "privilege_id", "implied_ids", "share")),
    (
        "automations",
        "base.automation",
        (
            "name",
            "model_id",
            "trigger",
            "filter_domain",
            "filter_pre_domain",
            "trigger_field_ids",
            "action_server_id",
            "action_server_ids",
        ),
    ),
    (
        "crons",
        "ir.cron",
        (
            "name",
            "cron_name",
            "model_id",
            "ir_actions_server_id",
            "interval_number",
            "interval_type",
            "priority",
            "code",
            "user_id",
        ),
    ),
    (
        "templates",
        "mail.template",
        (
            "name",
            "model_id",
            "model",
            "subject",
            "email_from",
            "email_to",
            "partner_to",
            "body_html",
            "lang",
        ),
    ),
    (
        "sequences",
        "ir.sequence",
        (
            "name",
            "code",
            "prefix",
            "suffix",
            "padding",
            "number_increment",
            "implementation",
            "use_date_range",
            "company_id",
        ),
    ),
    ("config_params", "ir.config_parameter", ("key", "value")),
    (
        "filters",
        "ir.filters",
        ("name", "model_id", "domain", "context", "sort", "user_id", "is_default", "action_id"),
    ),
    ("xmlids", "ir.model.data", ("module", "name", "model", "res_id", "noupdate")),
)

# Fields that name one record inside a category, for ``diff`` reports.
_KEY_FIELDS: dict[str, tuple[str, ...]] = {
    "models": ("model",),
    "fields": ("model", "name"),
    "views": ("model", "name", "type", "key"),
    "actions": ("type", "name", "res_model", "model_id", "model"),
    "menus": ("name", "parent_id"),
    "acl": ("name", "model_id", "group_id", "model", "group"),
    "rules": ("name", "model_id", "model"),
    "groups": ("name", "category_id"),
    "automations": ("name", "model_id", "model"),
    "crons": ("name", "cron_name", "model_id", "model"),
    "templates": ("name", "model_id", "model"),
    "sequences": ("code", "name"),
    "config_params": ("key",),
    "filters": ("name", "model_id", "model", "user_id"),
    "xmlids": ("module", "name"),
}
_RELATION_TYPES = frozenset({"many2many", "one2many"})


class MetaSnapshot:
    """Canonical export of the metadata categories T8-META compares.

    Inputs are accepted by ``build`` and ``from_memory``. The instance holds
    the canonical export only. It is not a ``MetadataSnapshot`` row.
    """

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    @classmethod
    def build(
        cls,
        payload: Mapping[str, Any],
        *,
        config_allowlist: Collection[str] = (),
    ) -> MetaSnapshot:
        """Build a snapshot from an in-memory payload.

        Inputs: a mapping whose keys are export names or Odoo model names,
        and the config-parameter allowlist. Keys outside the export are
        ignored. A string allowlist is rejected.
        Outputs: a snapshot whose ``to_dict`` lists every export key.
        Side effects: none. Does not read a database and does not call Odoo.
        """
        if not isinstance(payload, Mapping):
            raise TypeError("snapshot payload must be a mapping")
        allowlist = _allowlist(config_allowlist)
        buckets: dict[str, list[Any]] = {key: [] for key in EXPORT_KEYS}
        for raw_key, value in payload.items():
            bucket = _ALIASES.get(str(raw_key))
            if bucket is None:
                continue
            buckets[bucket].extend(_records_for(bucket, value))
        body = {
            key: _canonicalize(_export_bucket(key, buckets[key], allowlist)) for key in EXPORT_KEYS
        }
        return cls(body)

    @classmethod
    def from_memory(
        cls,
        store: Mapping[str, Mapping[str, Any]],
        *,
        config_allowlist: Collection[str] = (),
    ) -> MetaSnapshot:
        """Project an ``apply_memory`` store into a snapshot.

        Inputs: the in-memory op store and the config-parameter allowlist.
        Outputs: a snapshot of the ops that belong to the export. An
        ``ingenium`` xmlid on an op is also recorded under ``xmlids``.
        Side effects: none. Does not mutate ``store`` and does not call Odoo.
        """
        if not isinstance(store, Mapping):
            raise TypeError("memory store must be a mapping")
        payload: dict[str, list[Any]] = {key: [] for key in EXPORT_KEYS}
        for entry in store.values():
            if not isinstance(entry, Mapping):
                raise TypeError("memory entry must be a mapping")
            op_type = str(entry.get("type") or "")
            params = entry.get("params")
            if not isinstance(params, Mapping):
                raise TypeError(f"{op_type or 'op'} params must be a mapping")
            bucket = _MEMORY_BUCKETS.get(op_type)
            if bucket is not None:
                payload[bucket].append(dict(params))
            xmlid = params.get("xmlid")
            if xmlid is not None:
                payload["xmlids"].append(xmlid)
        return cls.build(payload, config_allowlist=config_allowlist)

    def to_dict(self) -> dict[str, Any]:
        """Copy of the canonical export.

        Inputs: none.
        Outputs: a new dict. Mutating it does not change the snapshot.
        Side effects: none.
        """
        return copy.deepcopy(self._body)

    def diff(self, other: MetaSnapshot) -> list[dict[str, Any]]:
        """Which category and record key differ from ``other``.

        Inputs: another snapshot.
        Outputs: one entry per differing key, in export order, with
        ``category``, ``key``, ``before`` (records here), and ``after``
        (records in ``other``). Empty when the snapshots are equal.
        Side effects: none.
        """
        if not isinstance(other, MetaSnapshot):
            raise TypeError("diff needs a MetaSnapshot")
        changes: list[dict[str, Any]] = []
        for category in EXPORT_KEYS:
            left = _keyed(category, self._body[category])
            right = _keyed(category, other._body[category])
            for key in sorted(set(left) | set(right)):
                before = left.get(key, [])
                after = right.get(key, [])
                if before == after:
                    continue
                changes.append(
                    {
                        "category": category,
                        "key": json.loads(key),
                        "before": copy.deepcopy(before),
                        "after": copy.deepcopy(after),
                    }
                )
        return changes

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MetaSnapshot):
            return NotImplemented
        return snapshots_match(self._body, other._body)

    def __repr__(self) -> str:
        counts = ", ".join(f"{key}={len(self._body[key])}" for key in EXPORT_KEYS)
        return f"MetaSnapshot({counts})"


def equal(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    config_allowlist: Collection[str] = (),
) -> bool:
    """Whether two in-memory payloads export the same metadata.

    Inputs: two payloads and one allowlist applied to both.
    Outputs: True when the built snapshots match. List order is ignored.
    Side effects: none.
    """
    return MetaSnapshot.build(left, config_allowlist=config_allowlist) == MetaSnapshot.build(
        right, config_allowlist=config_allowlist
    )


def capture(port: Any, *, config_allowlist: Collection[str] = ()) -> MetaSnapshot:
    """Read every export category from a port into a snapshot.

    Inputs: a port with ``execute_kw(model, method, args, kwargs)`` and the
    config-parameter allowlist.
    Outputs: the snapshot. Many2one values become the id. A model that is not
    in ``ir.model`` contributes no records.
    Side effects: public ``fields_get`` and ``search_read`` calls only, with
    the default ``active_test``. Config parameters are read by allowlisted
    key only. Xmlids are read for the ``ingenium`` module only. No write.
    A port error is raised to the caller.
    """
    if not callable(getattr(port, "execute_kw", None)):
        raise TypeError("capture needs a port with execute_kw")
    allowlist = _allowlist(config_allowlist)
    payload: dict[str, list[Any]] = {key: [] for key in EXPORT_KEYS}
    installed: frozenset[str] | None = None
    for category, model, wanted in CAPTURE_SOURCES:
        if installed is not None and model not in installed:
            continue
        domain = _capture_domain(category, allowlist)
        if domain is None:
            continue
        rows = _search_read(port, model, wanted, domain)
        payload[category].extend(rows)
        if model == "ir.model":
            installed = frozenset(
                str(row["model"]) for row in rows if isinstance(row.get("model"), str)
            )
    return MetaSnapshot.build(payload, config_allowlist=allowlist)


def _capture_domain(category: str, allowlist: frozenset[str]) -> list[list[Any]] | None:
    if category == "config_params":
        keys = sorted(key for key in allowlist if _config_kept({"key": key}, allowlist))
        return [["key", "in", keys]] if keys else None
    if category == "xmlids":
        return [["module", "=", _INGENIUM_MODULE]]
    return []


def _search_read(
    port: Any, model: str, wanted: tuple[str, ...], domain: list[list[Any]]
) -> list[dict[str, Any]]:
    described = port.execute_kw(model, "fields_get", [], {"attributes": ["type"]})
    if not isinstance(described, Mapping):
        raise TypeError(f"{model} fields_get did not return a mapping")
    fields = [name for name in wanted if name in described]
    if not fields:
        return []
    rows = port.execute_kw(model, "search_read", [domain], {"fields": fields})
    if not isinstance(rows, list):
        raise TypeError(f"{model} search_read did not return a list")
    types = {
        name: str(meta.get("type") or "") if isinstance(meta, Mapping) else ""
        for name, meta in described.items()
    }
    return [_read_row(model, row, fields, types) for row in rows]


def _read_row(model: str, row: Any, fields: list[str], types: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise TypeError(f"{model} search_read row is not a mapping")
    record: dict[str, Any] = {}
    for name in fields:
        if name not in row:
            continue
        value = row[name]
        kind = types.get(name, "")
        if kind == "many2one" and isinstance(value, (list, tuple)) and value:
            value = value[0]
        elif kind in _RELATION_TYPES and isinstance(value, (list, tuple)):
            value = list(value)
        record[name] = value
    return record


def _keyed(category: str, records: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for record in records:
        if isinstance(record, Mapping):
            key = {name: record[name] for name in _KEY_FIELDS[category] if name in record}
            if not key:
                key = {"record": record}
        else:
            key = {"record": record}
        grouped.setdefault(_sort_key(key), []).append(record)
    return grouped


def _allowlist(values: Collection[str]) -> frozenset[str]:
    if isinstance(values, str) or not isinstance(values, Collection):
        raise TypeError("config allowlist must be a collection of keys")
    keys = frozenset(values)
    if any(not isinstance(key, str) or not key for key in keys):
        raise TypeError("config allowlist keys must be non-empty strings")
    return keys


def _records_for(bucket: str, value: Any) -> list[Any]:
    if bucket == "config_params" and isinstance(value, Mapping):
        if isinstance(value.get("key"), str):
            return [value]
        if value and all(not isinstance(item, Mapping) for item in value.values()):
            return [{"key": str(key), "value": item} for key, item in value.items()]
    return _as_records(value)


def _as_records(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str) or _is_scalar(value):
        return [value]
    if isinstance(value, Mapping):
        if value and all(isinstance(item, Mapping) for item in value.values()):
            return list(value.values())
        return [value]
    raise TypeError(f"snapshot value is not JSON: {type(value).__name__}")


def _export_bucket(bucket: str, records: list[Any], allowlist: frozenset[str]) -> list[Any]:
    if bucket == "config_params":
        return [record for record in records if _config_kept(record, allowlist)]
    if bucket == "xmlids":
        kept = [_xmlid_record(record) for record in records]
        return [record for record in kept if record is not None]
    return records


def _config_kept(record: Any, allowlist: frozenset[str]) -> bool:
    if not isinstance(record, Mapping):
        return False
    key = record.get("key")
    if not isinstance(key, str) or not key:
        return False
    if key not in allowlist:
        return False
    if key in PROTECTED_CONFIG_KEYS:
        return False
    if is_secret_key(key):
        return False
    return True


def _xmlid_record(record: Any) -> dict[str, Any] | None:
    module, name, extra = _xmlid_parts(record)
    if module != _INGENIUM_MODULE or not _XMLID_NAME.match(name):
        return None
    if name.startswith("x_studio_"):
        return None
    body: dict[str, Any] = {"module": module, "name": name}
    body.update(extra)
    return body


def _xmlid_parts(record: Any) -> tuple[str, str, dict[str, Any]]:
    if isinstance(record, str):
        module, separator, name = record.partition(".")
        if not separator:
            return "", "", {}
        return module, name, {}
    if not isinstance(record, Mapping):
        return "", "", {}
    extra = {
        str(key): value
        for key, value in record.items()
        if str(key) not in {"module", "name", "xmlid"} and str(key) not in _VOLATILE
    }
    xmlid = record.get("xmlid")
    if isinstance(xmlid, str):
        module, separator, name = xmlid.partition(".")
        if separator:
            return module, name, extra
    module = record.get("module")
    name = record.get("name")
    if isinstance(module, str) and isinstance(name, str):
        return module, name, extra
    return "", "", {}


def _canonicalize(value: Any) -> Any:
    return _sort(_json_value(value))


def _sort(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sort(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        items = [_sort(item) for item in value]
        return sorted(items, key=_sort_key)
    return value


def _sort_key(item: Any) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if type(value) is int:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("snapshot value is not JSON")
        return value
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("snapshot key is not a string")
            if key in _VOLATILE:
                continue
            cleaned[key] = _json_value(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"snapshot value is not JSON: {type(value).__name__}")


def _is_scalar(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if type(value) is int:
        return True
    return isinstance(value, float)
