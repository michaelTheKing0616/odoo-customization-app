"""In-memory MetaSnapshot for order-independent metadata equality.

``metadata_snapshots`` (``MetadataSnapshot`` in ``db_models``) is one restore
row per resource: ``resource_type``, ``resource_key``, and a ``payload_json``
blob, written through a database session. That shape is a single rollback
payload. It is not this export, so it is not reused and nothing here is
persisted.

The snapshot is built from a caller-supplied mapping. It does not open a
database connection and it does not call Odoo.

Equality ignores key order and list order at every level, using the same
comparison as undo (``snapshots_match``). Config parameters are kept only
when their key is on the caller allowlist, and never when the key is
protected or secret-shaped. Xmlids are kept only for the ``ingenium`` module.
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
            key: _canonicalize(_export_bucket(key, buckets[key], allowlist))
            for key in EXPORT_KEYS
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
