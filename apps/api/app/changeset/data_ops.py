"""Data-family sample, cap, and batch limits, and the delete gate.

The catalog in ``ops.py`` stays the source for base risk. This module checks
row samples, the row cap, and batch size, and it decides when ``data.delete``
must not be sent to a port. It does not call Odoo and it does not write.
"""

from __future__ import annotations

import re
from typing import Any

from app.changeset.policy import heavy_gate_refusal

SAMPLE_LIMIT = 20
ROW_CAP = 1000
BATCH_SIZE = 200
STOCK_QUANT = "stock.quant"

SAMPLE_OVER_LIMIT = "sample is at most 20 rows"
ROW_CAP_EXCEEDED = "row cap is 1000"
BATCH_NOT_200 = "batches are 200"
DELETE_DENIED = "data.delete is denied"
DELETE_NEEDS_TWO_APPROVERS = "data.delete requires two approvers who are not the requester"
STOCK_QUANT_REFUSED = "stock.quant is refused"

# Empty on purpose. A delete with no supplied allow-list is denied.
DATA_DELETE_ALLOW_LIST: frozenset[str] = frozenset()

LIMITED_DATA_OPS = frozenset(
    {
        "data.create_batch",
        "data.update_batch",
        "data.archive_batch",
        "data.import_upsert",
        "data.merge",
        "translation.upsert",
    }
)

_SAMPLE_LIST_KEYS = ("sample", "sample_rows")
_SAMPLE_COUNT_KEYS = ("sample_size",)
_ROW_LIST_KEYS = ("rows", "records", "ids", "record_ids", "lines")
_ROW_COUNT_KEYS = ("row_count",)
_MODEL_KEYS = ("model", "res_model")


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _list_len(params: dict[str, Any], key: str) -> int | None:
    value = params.get(key)
    if isinstance(value, list):
        return len(value)
    return None


def _max_count(params: dict[str, Any], list_keys: tuple[str, ...], count_keys: tuple[str, ...]) -> int:
    counts: list[int] = []
    for key in list_keys:
        listed = _list_len(params, key)
        if listed is not None:
            counts.append(listed)
    for key in count_keys:
        counted = _as_int(params.get(key))
        if counted is not None:
            counts.append(counted)
    if not counts:
        return 0
    return max(counts)


def sample_row_count(params: dict[str, Any] | None) -> int:
    """How many preview rows the op claims.

    Inputs: op params. A missing dict counts as no sample. List keys
    ``sample`` and ``sample_rows`` contribute their lengths. ``sample_size``
    contributes when it is a non-negative int. A bool is ignored.
    Outputs: the largest of those counts, or 0 when none are present.
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    return _max_count(body, _SAMPLE_LIST_KEYS, _SAMPLE_COUNT_KEYS)


def affected_row_count(params: dict[str, Any] | None) -> int:
    """How many rows the op would touch.

    Inputs: op params. List keys ``rows``, ``records``, ``ids``,
    ``record_ids``, and ``lines`` contribute their lengths. ``row_count``
    contributes when it is a non-negative int. Domain and ``values`` are
    not row lists.
    Outputs: the largest of those counts, or 0 when none are present.
    Side effects: none. Does not query Odoo.
    """
    body = params if isinstance(params, dict) else {}
    return _max_count(body, _ROW_LIST_KEYS, _ROW_COUNT_KEYS)


def data_limit_issues(params: dict[str, Any] | None) -> list[str]:
    """Issues for the sample, the row cap, and the batch size.

    Inputs: op params.
    Outputs: ``sample is at most 20 rows`` when the sample is larger than
    20, ``row cap is 1000`` when the row count is larger than 1000, and
    ``batches are 200`` when ``batch_size`` is present and is not 200.
    A missing ``batch_size`` is not an issue. An empty list when all three
    hold.
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    issues: list[str] = []
    if sample_row_count(body) > SAMPLE_LIMIT:
        issues.append(SAMPLE_OVER_LIMIT)
    if affected_row_count(body) > ROW_CAP:
        issues.append(ROW_CAP_EXCEEDED)
    if "batch_size" in body and _as_int(body.get("batch_size")) != BATCH_SIZE:
        issues.append(BATCH_NOT_200)
    return issues


def planned_batch_sizes(params: dict[str, Any] | None) -> list[int] | None:
    """Batch sizes for a payload that already passes the data limits.

    Inputs: op params.
    Outputs: ``None`` when ``data_limit_issues`` is non-empty. Otherwise the
    row count split into chunks of 200, with a shorter final chunk when the
    count is not a multiple of 200. An empty payload is an empty list.
    Side effects: none. Does not call a port.
    """
    body = params if isinstance(params, dict) else {}
    if data_limit_issues(body):
        return None
    remaining = affected_row_count(body)
    sizes: list[int] = []
    while remaining > 0:
        take = BATCH_SIZE if remaining > BATCH_SIZE else remaining
        sizes.append(take)
        remaining -= take
    return sizes


def targets_stock_quant(params: dict[str, Any] | None) -> bool:
    """True when the op names ``stock.quant``.

    Inputs: op params. Reads ``model``, ``res_model``, and a ``models`` list.
    Outputs: True when one of those values is ``stock.quant`` after stripping.
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    for key in _MODEL_KEYS:
        value = body.get(key)
        if isinstance(value, str) and value.strip() == STOCK_QUANT:
            return True
    models = body.get("models")
    if isinstance(models, list):
        for item in models:
            if isinstance(item, str) and item.strip() == STOCK_QUANT:
                return True
    return False


def _text(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def _approvers(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    found: list[str] = []
    for item in value:
        if isinstance(item, dict):
            token = _text(item.get("id", item.get("user")))
        else:
            token = _text(item)
        if token and token not in found:
            found.append(token)
    return found


def _allow_names(value: Any) -> frozenset[str]:
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    names: set[str] = set()
    for item in value:
        token = _text(item)
        if token:
            names.add(token)
    return frozenset(names)


def _pick(op: dict[str, Any], params: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in op:
            return op[key]
    for key in keys:
        if key in params:
            return params[key]
    return None


def delete_port_reason(op: dict[str, Any] | None) -> str | None:
    """Why a ``data.delete`` must not be sent to a port.

    Inputs: the op dict, including params. Approvers may sit on the op or
    in params under ``approvals``, ``approvers``, or ``approved_by``. The
    requester may sit under ``requester_id``, ``requester``, or
    ``requested_by``. ``allow_list`` may sit on the op or in params. When
    that key is absent, the allow-list is the empty ``DATA_DELETE_ALLOW_LIST``.
    Heavy-gate facts (simulation, backup, window, authenticated ``user_id``)
    use the same shapes as the approval store.
    Outputs: ``stock.quant is refused`` when the model is ``stock.quant``.
    ``data.delete is denied`` when the model is not on the allow-list,
    which is the default. A named heavy-gate reason when the production
    heavy-R4 gate is not met. ``None`` only when the model is allow-listed
    and the heavy gate has passed.
    Side effects: none.
    """
    body = op if isinstance(op, dict) else {}
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    if targets_stock_quant(params):
        return STOCK_QUANT_REFUSED
    model = _text(params.get("model"))
    if "allow_list" in body or "allow_list" in params:
        allow = _allow_names(_pick(body, params, "allow_list"))
    else:
        allow = DATA_DELETE_ALLOW_LIST
    if not model or model not in allow:
        return DELETE_DENIED
    gated = dict(body)
    gated.setdefault("type", "data.delete")
    if "params" not in gated or not isinstance(gated.get("params"), dict):
        gated["params"] = dict(params)
    return heavy_gate_refusal(gated)


# --- T8-OP-DATA apply payloads -------------------------------------------
# The dispatcher in ``dispatch.py`` calls these. They build public ORM calls
# and never call a port themselves.

DATA_OP_TYPES: tuple[str, ...] = (
    "data.create_batch",
    "data.update_batch",
    "data.archive_batch",
    "data.import_upsert",
    "data.merge",
    "data.delete",
    "translation.upsert",
)
# data.delete applies only when delete_port_reason returns None (allow-list + heavy gate).
DATA_APPLY_OPS = frozenset(DATA_OP_TYPES)

PARTNER_MODEL = "res.partner"
PARTNER_MERGE_WIZARD = "base.partner.merge.automatic.wizard"
MERGE_PARTNER_ONLY = "data.merge only runs Odoo's partner merge wizard on res.partner"
MERGE_NEEDS_TWO_IDS = "data.merge needs at least two distinct record ids"
MERGE_NEEDS_DESTINATION = "data.merge needs dst_id, one of the merged ids"
MODEL_REQUIRED = "model is required"
ROWS_REQUIRED = "rows must be a non-empty list of field dicts"
CREATE_ROW_HAS_ID = "data.create_batch rows must not carry an id"
VALUES_REQUIRED = "values must be a non-empty dict"
TARGET_REQUIRED = "ids or a non-empty domain is required"
UNBOUNDED_DOMAIN = "unbounded domain is forbidden"
UPSERT_KEY_REQUIRED = "data.import_upsert needs key, a field name to match rows on"
UPSERT_ROW_UNKEYED = "every upsert row needs an id or a value for key"
LANG_REQUIRED = "translation.upsert needs lang, for example fr_FR"
TRANSLATION_FIELD_REQUIRED = "translation.upsert needs field and value, or values"
IDS_REQUIRED = "ids are required"
BAD_FIELD_NAME = "field names must be lowercase identifiers"
WRITE_SETS_ID = "values must not set id"

_FIELD_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_LANG_RE = re.compile(r"^[a-z]{2,3}(_[A-Za-z0-9]{2,8})?(@[a-z]+)?$")


def data_model(params: dict[str, Any] | None) -> str:
    """Target model of a data op. ``model`` wins over ``res_model``; else ''."""
    body = params if isinstance(params, dict) else {}
    for key in _MODEL_KEYS:
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def data_ids(params: dict[str, Any] | None) -> list[int]:
    """Explicit record ids from ``ids``, ``record_ids``, or ``id``.

    Inputs: op params. Bools and non-positive ints are not ids.
    Outputs: distinct ids in order. An empty list when none, or when a list
    holds a non-id item (fail closed rather than drop it).
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    for key in ("ids", "record_ids"):
        raw = body.get(key)
        if isinstance(raw, list) and raw:
            found: list[int] = []
            for item in raw:
                if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
                    return []
                if item not in found:
                    found.append(item)
            return found
    item = body.get("id")
    if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
        return []
    return [item]


def data_rows(params: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Copies of the row dicts in ``rows`` or ``records``.

    Outputs: ``None`` when the list is missing, empty, or holds a non-dict
    or empty dict. Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    for key in ("rows", "records"):
        raw = body.get(key)
        if isinstance(raw, list):
            if not raw or not all(isinstance(row, dict) and row for row in raw):
                return None
            return [dict(row) for row in raw]
    return None


def data_domain(params: dict[str, Any] | None) -> list[Any] | None:
    """The ``domain`` list, or ``None`` when absent or not a list."""
    body = params if isinstance(params, dict) else {}
    domain = body.get("domain")
    return domain if isinstance(domain, list) else None


def chunk_ids(ids: list[int]) -> list[list[int]]:
    """Split ids into batches of ``BATCH_SIZE`` (200), in order."""
    return [ids[start : start + BATCH_SIZE] for start in range(0, len(ids), BATCH_SIZE)]


def chunk_rows(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split rows into batches of ``BATCH_SIZE`` (200), in order."""
    return [rows[start : start + BATCH_SIZE] for start in range(0, len(rows), BATCH_SIZE)]


def translation_values(params: dict[str, Any] | None) -> dict[str, Any]:
    """Values for ``translation.upsert``: ``values`` dict, else ``{field: value}``."""
    body = params if isinstance(params, dict) else {}
    values = body.get("values")
    if isinstance(values, dict) and values:
        return dict(values)
    field = body.get("field")
    if isinstance(field, str) and field and isinstance(body.get("value"), str):
        return {field: body["value"]}
    return {}


def merge_destination(params: dict[str, Any] | None) -> int | None:
    """Destination partner id from ``dst_id`` or ``target_id``."""
    body = params if isinstance(params, dict) else {}
    for key in ("dst_id", "target_id"):
        item = body.get(key)
        if isinstance(item, int) and not isinstance(item, bool) and item > 0:
            return item
    return None


def _bad_names(values: dict[str, Any]) -> bool:
    return any(not isinstance(key, str) or not _FIELD_NAME_RE.match(key) for key in values)


def _target_issues(params: dict[str, Any]) -> list[str]:
    if data_ids(params):
        return []
    domain = data_domain(params)
    if domain is None:
        return [TARGET_REQUIRED]
    if domain == []:
        return [UNBOUNDED_DOMAIN]
    return []


def data_payload_issues(op_type: str, params: dict[str, Any] | None) -> list[str]:
    """Apply-time payload issues for one data op, before any port call.

    Inputs: op type and resolved params.
    Outputs: issue strings. ``stock.quant`` is refused for every data op.
    ``data.delete`` requires a model and a target (ids or domain); the
    allow-list and heavy gate are checked by ``delete_port_reason``.
    Side effects: none. Does not call Odoo.
    """
    body = params if isinstance(params, dict) else {}
    if targets_stock_quant(body):
        return [STOCK_QUANT_REFUSED]
    issues: list[str] = []
    if op_type == "data.delete":
        if not data_model(body):
            issues.append(MODEL_REQUIRED)
        else:
            issues.extend(_target_issues(body))
        return issues
    if not data_model(body):
        issues.append(MODEL_REQUIRED)
    if op_type == "data.create_batch":
        rows = data_rows(body)
        if rows is None:
            issues.append(ROWS_REQUIRED)
        else:
            if any("id" in row for row in rows):
                issues.append(CREATE_ROW_HAS_ID)
            if any(_bad_names(row) for row in rows):
                issues.append(BAD_FIELD_NAME)
    elif op_type in {"data.update_batch", "data.archive_batch"}:
        issues.extend(_target_issues(body))
        if op_type == "data.update_batch":
            values = body.get("values")
            if not isinstance(values, dict) or not values:
                issues.append(VALUES_REQUIRED)
            elif "id" in values:
                issues.append(WRITE_SETS_ID)
            elif _bad_names(values):
                issues.append(BAD_FIELD_NAME)
    elif op_type == "data.import_upsert":
        rows = data_rows(body)
        key = body.get("key")
        keyed_ok = isinstance(key, str) and bool(_FIELD_NAME_RE.match(key))
        if rows is None:
            issues.append(ROWS_REQUIRED)
        else:
            if not keyed_ok and any("id" not in row for row in rows):
                issues.append(UPSERT_KEY_REQUIRED)
            for row in rows:
                row_id = row.get("id")
                has_id = isinstance(row_id, int) and not isinstance(row_id, bool) and row_id > 0
                keyed = keyed_ok and row.get(key) not in (None, "", False)
                if not has_id and not keyed:
                    issues.append(UPSERT_ROW_UNKEYED)
                    break
            if any(_bad_names({k: v for k, v in row.items() if k != "id"}) for row in rows):
                issues.append(BAD_FIELD_NAME)
    elif op_type == "data.merge":
        if data_model(body) and data_model(body) != PARTNER_MODEL:
            issues.append(MERGE_PARTNER_ONLY)
        ids = data_ids(body)
        if len(ids) < 2:
            issues.append(MERGE_NEEDS_TWO_IDS)
        dst = merge_destination(body)
        if dst is None or dst not in ids:
            issues.append(MERGE_NEEDS_DESTINATION)
    elif op_type == "translation.upsert":
        lang = body.get("lang")
        if not isinstance(lang, str) or not _LANG_RE.match(lang):
            issues.append(LANG_REQUIRED)
        if not data_ids(body):
            issues.append(IDS_REQUIRED)
        values = translation_values(body)
        if not values:
            issues.append(TRANSLATION_FIELD_REQUIRED)
        elif _bad_names(values) or not all(isinstance(v, str) for v in values.values()):
            issues.append(BAD_FIELD_NAME)
    return issues
