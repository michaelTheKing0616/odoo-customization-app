"""Data-family sample, cap, and batch limits, and the delete gate.

The catalog in ``ops.py`` stays the source for base risk. This module checks
row samples, the row cap, and batch size, and it decides when ``data.delete``
must not be sent to a port. It does not call Odoo and it does not write.
"""

from __future__ import annotations

from typing import Any

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
    in params under ``approvers`` or ``approved_by``. The requester may sit
    under ``requester`` or ``requested_by``. ``allow_list`` may sit on the
    op or in params. When that key is absent, the allow-list is the empty
    ``DATA_DELETE_ALLOW_LIST``.
    Outputs: ``stock.quant is refused`` when the model is ``stock.quant``.
    ``data.delete is denied`` when the model is not on the allow-list,
    which is the default. ``data.delete requires two approvers who are not
    the requester`` when the requester is missing, or fewer than two distinct
    approvers remain after the requester is removed. ``None`` only when the
    model is allow-listed and two approvers are neither the named requester.
    ``None`` does not authorize a write; ``data.delete`` stays prohibited.
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
    requester = _text(_pick(body, params, "requester", "requested_by"))
    approvers = _approvers(_pick(body, params, "approvers", "approved_by"))
    outsiders = [person for person in approvers if person != requester]
    if not requester or len(outsiders) < 2:
        return DELETE_NEEDS_TWO_APPROVERS
    return None
