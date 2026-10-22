"""SCAN-01: scan routes (contract only).

Each handler calls exactly one injected engine function. The default engines say
plainly that scans are not available yet; engine cards replace them. Nothing here
calls Odoo. Every error leaves as the B5 envelope.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Coroutine
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.db import get_db
from app.scans.contract import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CancelScanFn,
    FindingsFn,
    FindingsPage,
    FindingsQuery,
    GetScanFn,
    PlanDraftRef,
    PlanFindingFn,
    ScanError,
    ScanErrorEnvelope,
    ScanRun,
    ScanScope,
    StartScanFn,
    StartScanRequest,
)
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth

_HTTP_TO_CODE = {
    403: "ROLE_DENIED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION",
    429: "RATE_LIMITED",
    503: "ODOO_UNREACHABLE",
}
_PLAIN = {
    "ROLE_DENIED": "Your role can't do this.",
    "NOT_FOUND": "We couldn't find that.",
    "CONFLICT": "That can't be done right now.",
    "VALIDATION": "Some of what was sent isn't right.",
    "RATE_LIMITED": "Too many requests. Try again shortly.",
    "ODOO_UNREACHABLE": "We can't reach this database right now.",
}


def _envelope(err: ScanError) -> JSONResponse:
    headers = {"Retry-After": str(err.retry_after_s)} if err.retry_after_s else None
    return JSONResponse(status_code=err.status_code, content=err.body(), headers=headers)


def _from_http(exc: HTTPException) -> ScanError | None:
    code = _HTTP_TO_CODE.get(exc.status_code)
    if code is None:
        return None
    d = exc.detail
    message = d if isinstance(d, str) and d else _PLAIN[code]
    if isinstance(d, dict) and isinstance(d.get("message"), str):
        message = d["message"]
    detail = d if isinstance(d, dict) else None
    retry = None
    if exc.headers and str(exc.headers.get("Retry-After", "")).isdigit():
        retry = int(exc.headers["Retry-After"])
    return ScanError(code, message, detail, retry)


class ScanEnvelopeRoute(APIRoute):
    """Renders every error on this router as the B5 envelope (incl. auth deps)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except ScanError as err:
                return _envelope(err)
            except RequestValidationError as exc:
                fields = [
                    {"field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"),
                     "problem": e.get("msg", "")}
                    for e in exc.errors()
                ]
                names = ", ".join(f["field"] for f in fields if f["field"])
                return _envelope(ScanError(
                    "VALIDATION",
                    f"Check these fields: {names}." if names else _PLAIN["VALIDATION"],
                    {"fields": fields},
                ))
            except HTTPException as exc:
                mapped = _from_http(exc)
                if mapped is None:
                    raise
                return _envelope(mapped)

        return wrapped


_ERRORS: dict[int | str, dict[str, Any]] = {
    s: {"model": ScanErrorEnvelope} for s in (403, 404, 409, 422, 429, 503)
}

router = APIRouter(
    prefix="/connections/{connection_id}",
    tags=["scans"],
    route_class=ScanEnvelopeRoute,
    responses=_ERRORS,
)


# Tenancy ---------------------------------------------------------------------
def scan_scope(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ScanScope:
    """404 unless the connection belongs to the caller's workspace (or client grant)."""
    auth: WorkspaceAuth = get_workspace_auth(request)
    row = get_scoped_connection_or_404(db, connection_id, auth)
    return ScanScope(workspace_id=getattr(row, "workspace_id", None), connection_id=row.id)


# Default engines (replaced by engine cards) -----------------------------------
def _not_ready(*_a: Any) -> Any:
    raise ScanError("NOT_FOUND", "Scans aren't available on this server yet.")


def start_engine() -> StartScanFn:
    return _not_ready


def get_engine() -> GetScanFn:
    return _not_ready


def findings_engine() -> FindingsFn:
    return _not_ready


def cancel_engine() -> CancelScanFn:
    return _not_ready


def plan_engine() -> PlanFindingFn:
    return _not_ready


# Opaque cursor: bound to the filters it was issued for --------------------------
def _encode_cursor(offset: int, severity: str | None, area: str | None) -> str:
    raw = json.dumps({"v": 1, "o": offset, "s": severity, "a": area}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, severity: str | None, area: str | None) -> int:
    bad = ScanError("VALIDATION", "This page link is no longer valid. Start from the first page.",
                    {"fields": [{"field": "cursor", "problem": "invalid"}]})
    try:
        pad = "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(cursor + pad))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise bad from None
    if (
        not isinstance(data, dict)
        or data.get("v") != 1
        or not isinstance(data.get("o"), int)
        or data["o"] < 0
        or data.get("s") != severity
        or data.get("a") != area
    ):
        raise bad
    return data["o"]


# Routes ----------------------------------------------------------------------
@router.post("/scans", response_model=ScanRun, status_code=202)
def start_scan(
    body: StartScanRequest,
    response: Response,
    scope: ScanScope = Depends(scan_scope),
    engine: StartScanFn = Depends(start_engine),
) -> ScanRun:
    run, created = engine(scope, body)
    if not created:
        response.status_code = 200  # idempotent: the matching run already exists
    return run


@router.get("/scans/{run_id}", response_model=ScanRun)
def get_scan(
    run_id: str,
    scope: ScanScope = Depends(scan_scope),
    engine: GetScanFn = Depends(get_engine),
) -> ScanRun:
    return engine(scope, run_id)


@router.get("/scans/{run_id}/findings", response_model=FindingsPage)
def list_findings(
    run_id: str,
    severity: Literal["info", "low", "medium", "high", "critical"] | None = None,
    area: str | None = Query(None, max_length=64),
    cursor: str | None = Query(None, max_length=512),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    scope: ScanScope = Depends(scan_scope),
    engine: FindingsFn = Depends(findings_engine),
) -> FindingsPage:
    offset = _decode_cursor(cursor, severity, area) if cursor else 0
    items, has_more = engine(scope, run_id, FindingsQuery(severity, area, offset, limit))
    items = items[:limit]
    nxt = _encode_cursor(offset + len(items), severity, area) if has_more and items else None
    return FindingsPage(items=items, next_cursor=nxt)


@router.post("/scans/{run_id}/cancel", response_model=ScanRun)
def cancel_scan(
    run_id: str,
    scope: ScanScope = Depends(scan_scope),
    engine: CancelScanFn = Depends(cancel_engine),
) -> ScanRun:
    return engine(scope, run_id)


@router.post("/findings/{fid}/plan", response_model=PlanDraftRef)
def plan_finding(
    fid: str,
    scope: ScanScope = Depends(scan_scope),
    engine: PlanFindingFn = Depends(plan_engine),
) -> PlanDraftRef:
    return engine(scope, fid)
