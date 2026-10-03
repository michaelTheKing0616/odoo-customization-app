"""Learn JSON-2 from the connected database.

``GET /doc`` is used when it is the API page. A website page at that path is
recorded and ignored. Live calls decide the parameter names on every host:
Online, Odoo.sh, Enterprise, and on-prem.
"""

from __future__ import annotations

import json
from typing import Any

from odoo_client.transport.json2 import Json2Transport, Json2TransportError

_METHODS = ("search_read", "create", "fields_get")
_PARAM_TOKENS = (
    "domain",
    "fields",
    "offset",
    "limit",
    "order",
    "context",
    "vals_list",
    "attributes",
    "allfields",
    "specification",
)


def probe_json2(transport: Json2Transport) -> dict[str, Any]:
    """Read-only confirmation. ``create`` is sent with an empty body so no row is written."""
    doc_status, doc_text = _safe_get(transport, "/doc")
    doc_route, doc_parameters = _read_doc(doc_status, doc_text)
    calls: dict[str, int | None] = {"doc": doc_status}
    live: dict[str, list[str]] = {}

    search_status = _safe_call(
        transport,
        "res.partner",
        "search_read",
        {"domain": [["id", "=", 0]], "fields": ["id"], "limit": 1},
    )
    calls["search_read"] = search_status
    if search_status == 200:
        live["search_read"] = ["domain", "fields", "limit"]

    fields_status = _safe_call(
        transport,
        "res.partner",
        "fields_get",
        {"attributes": ["string", "type"]},
    )
    calls["fields_get"] = fields_status
    if fields_status == 200:
        live["fields_get"] = ["attributes"]

    create_status, create_message = _safe_call_message(transport, "res.partner", "create", {})
    calls["create"] = create_status
    if create_status == 422 and "vals_list" in create_message:
        live["create"] = ["vals_list"]

    disagreements = _disagreements(doc_parameters, live)
    return {
        "origin": transport.base_url,
        "doc_route": doc_route,
        "doc_parameters": doc_parameters,
        "live_parameters": live,
        "parameters": dict(live),
        "disagreements": disagreements,
        "calls": calls,
    }


def _safe_get(transport: Json2Transport, path: str) -> tuple[int | None, str]:
    try:
        return transport.request("GET", path)
    except Json2TransportError:
        return None, ""


def _safe_call(
    transport: Json2Transport,
    model: str,
    method: str,
    body: dict[str, Any],
) -> int | None:
    status, _message = _safe_call_message(transport, model, method, body)
    return status


def _safe_call_message(
    transport: Json2Transport,
    model: str,
    method: str,
    body: dict[str, Any],
) -> tuple[int | None, str]:
    try:
        transport.call(model, method, body)
        return 200, ""
    except Json2TransportError as exc:
        message = ""
        if isinstance(exc.body, dict):
            message = str(exc.body.get("message") or "")
        return exc.status, message


def _read_doc(status: int | None, text: str) -> tuple[str, dict[str, list[str]]]:
    if status != 200 or not text:
        return "unavailable", {}
    lowered = text.lstrip().lower()
    if lowered.startswith("<!doctype html") or lowered.startswith("<html") or "data-website-id" in text:
        return "website", {}
    found = [token for token in _PARAM_TOKENS if token in text]
    if not any(method in text for method in _METHODS):
        return "unavailable", {}
    return "api", {method: found for method in _METHODS if method in text}


def _disagreements(doc: dict[str, list[str]], live: dict[str, list[str]]) -> list[str]:
    notes: list[str] = []
    for method, live_names in live.items():
        doc_names = doc.get(method) or []
        missing = [name for name in live_names if name not in doc_names and doc_names]
        if missing:
            notes.append(f"{method} live parameters {missing} are absent from /doc")
    return notes


def loads_probe(raw: str) -> dict[str, Any]:
    """Parse a stored probe. Rejects any payload that contains an API key field."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("probe must be an object")
    if "api_key" in data or "authorization" in data:
        raise ValueError("probe must not store credentials")
    return data
