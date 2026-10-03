"""Live learning for Odoo 17–20 production databases.

JSON-2 databases use ``probe_json2``. XML-RPC and JSON-RPC databases (17, 18,
and self-hosted 19) use ``probe_legacy``. Both store one ``production_probe``
on the client. Neither probe inserts a row.
"""

from __future__ import annotations

from typing import Any, Callable

Execute = Callable[[str, str, list[Any] | None, dict[str, Any] | None], Any]


def probe_legacy(
    execute: Execute,
    *,
    protocol: str,
    major: int,
) -> dict[str, Any]:
    """Confirm the frozen ``execute_kw`` shapes on a legacy connection."""
    if protocol not in {"xmlrpc", "jsonrpc"}:
        raise ValueError(f"legacy probe protocol must be xmlrpc or jsonrpc, got {protocol}")
    calls: dict[str, Any] = {}
    parameters: dict[str, list[str]] = {}
    calls["search_read"] = _status(
        execute,
        "res.partner",
        "search_read",
        [[("id", "=", 0)]],
        {"fields": ["id"], "limit": 1},
    )
    if calls["search_read"] == 200:
        parameters["search_read"] = ["domain", "fields", "limit"]
    calls["fields_get"] = _status(
        execute,
        "res.partner",
        "fields_get",
        [],
        {"attributes": ["string", "type"]},
    )
    if calls["fields_get"] == 200:
        parameters["fields_get"] = ["attributes"]
    # Create stays on the positional vals shape. Do not call it.
    parameters["create"] = ["vals"]
    return {
        "protocol": protocol,
        "major": major,
        "doc_route": "not_applicable",
        "parameters": parameters,
        "calls": calls,
    }


def _status(
    execute: Execute,
    model: str,
    method: str,
    args: list[Any] | None,
    kwargs: dict[str, Any] | None,
) -> Any:
    try:
        execute(model, method, args, kwargs)
    except Exception as exc:  # noqa: BLE001 — the connection must still open
        return type(exc).__name__
    return 200
