"""Pre-transport RPC guard: refuse classify-forbidden calls before they hit Odoo."""

from __future__ import annotations

from typing import Any

from app.rpc_classify import classify_rpc
from odoo_client.client import OdooClientError


def refuse_if_forbidden(
    model: str,
    method: str,
    args: list[Any],
    kwargs: dict[str, Any],
) -> None:
    ids: list[int] | None = None
    if args and isinstance(args[0], list) and args[0] and all(isinstance(x, int) for x in args[0]):
        ids = list(args[0])

    values: dict[str, Any] | None = None
    if len(args) > 1 and isinstance(args[1], dict):
        values = args[1]
    else:
        candidate = kwargs.get("vals") or kwargs.get("values")
        if isinstance(candidate, dict):
            values = candidate

    classification = classify_rpc(
        model,
        method,
        ids=ids,
        values=values,
        args=(args, kwargs),
        approved=False,
    )
    if classification.forbidden:
        raise OdooClientError(f"forbidden {model}.{method}: {classification.reason}")
