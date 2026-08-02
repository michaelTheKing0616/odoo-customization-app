"""Report layout lite — QWeb PDF reports + paper formats via RPC."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(
    prefix="/connections/{connection_id}/reports",
    tags=["reports"],
)

DEFAULT_QWEB = """\
<t t-name="{key}">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="doc">
            <div class="page">
                <h2 t-field="doc.display_name"/>
                <p>Generated via Odoo Custom report lite.</p>
            </div>
        </t>
    </t>
</t>
"""


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _confirm_http(exc: ConfirmationRequired) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "requires_confirmation": True,
            "confirm_phrase": CONFIRM_PHRASE,
            "warning": exc.warning,
            "risks": exc.risks,
        },
    )


class PaperFormatOut(BaseModel):
    id: int
    name: str
    format: str | None = None
    orientation: str | None = None
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None


class ReportOut(BaseModel):
    id: int
    name: str
    model: str | None = None
    report_type: str | None = None
    report_name: str | None = None
    paperformat_id: int | None = None
    paperformat_name: str | None = None
    arch: str | None = None
    view_id: int | None = None


class CreateReportBody(BaseModel):
    name: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    report_key: str = Field(
        ...,
        min_length=3,
        description="QWeb key, e.g. custom.report_x_rent_contract",
        pattern=r"^[a-zA-Z0-9_.]+$",
    )
    arch: str | None = None
    paperformat_id: int | None = None
    report_type: str = "qweb-pdf"


class UpdateReportBody(BaseModel):
    name: str | None = None
    arch: str | None = None
    paperformat_id: int | None = None
    clear_paperformat: bool = False


@router.get("/paperformats", response_model=list[PaperFormatOut])
def list_paperformats(
    connection_id: str, db: Session = Depends(get_db)
) -> list[PaperFormatOut]:
    client = _client(connection_id, db)
    try:
        rows = client.execute_kw(
            "report.paperformat",
            "search_read",
            [[]],
            {
                "fields": [
                    "name",
                    "format",
                    "orientation",
                    "margin_top",
                    "margin_bottom",
                    "margin_left",
                    "margin_right",
                ],
                "limit": 50,
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        PaperFormatOut(
            id=int(r["id"]),
            name=str(r.get("name") or ""),
            format=r.get("format") or None,
            orientation=r.get("orientation") or None,
            margin_top=float(r["margin_top"]) if r.get("margin_top") is not None else None,
            margin_bottom=(
                float(r["margin_bottom"]) if r.get("margin_bottom") is not None else None
            ),
            margin_left=float(r["margin_left"]) if r.get("margin_left") is not None else None,
            margin_right=(
                float(r["margin_right"]) if r.get("margin_right") is not None else None
            ),
        )
        for r in rows
    ]


def _find_qweb_view(client: Any, key: str) -> dict[str, Any] | None:
    rows = client.execute_kw(
        "ir.ui.view",
        "search_read",
        [[("key", "=", key), ("type", "=", "qweb")]],
        {"fields": ["id", "name", "arch", "key"], "limit": 1},
    )
    return rows[0] if rows else None


def _report_out(client: Any, row: dict[str, Any]) -> ReportOut:
    pf = row.get("paperformat_id")
    paperformat_id = int(pf[0]) if isinstance(pf, (list, tuple)) and pf else None
    paperformat_name = (
        str(pf[1]) if isinstance(pf, (list, tuple)) and len(pf) > 1 else None
    )
    report_name = row.get("report_name") or None
    arch = None
    view_id = None
    if report_name:
        view = _find_qweb_view(client, str(report_name))
        if view:
            arch = view.get("arch") or None
            view_id = int(view["id"])
    return ReportOut(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        model=row.get("model") or None,
        report_type=row.get("report_type") or None,
        report_name=report_name,
        paperformat_id=paperformat_id,
        paperformat_name=paperformat_name,
        arch=arch,
        view_id=view_id,
    )


@router.get("", response_model=list[ReportOut])
def list_reports(
    connection_id: str,
    model: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ReportOut]:
    client = _client(connection_id, db)
    domain: list[Any] = []
    if model:
        domain.append(("model", "=", model))
    try:
        rows = client.execute_kw(
            "ir.actions.report",
            "search_read",
            [domain],
            {
                "fields": [
                    "name",
                    "model",
                    "report_type",
                    "report_name",
                    "paperformat_id",
                ],
                "limit": 100,
                "order": "name",
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_report_out(client, r) for r in rows]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    connection_id: str, report_id: int, db: Session = Depends(get_db)
) -> ReportOut:
    client = _client(connection_id, db)
    try:
        rows = client.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {
                "fields": [
                    "name",
                    "model",
                    "report_type",
                    "report_name",
                    "paperformat_id",
                ]
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_out(client, rows[0])


@router.post("", response_model=ReportOut, status_code=201)
def create_report(
    connection_id: str, body: CreateReportBody, db: Session = Depends(get_db)
) -> ReportOut:
    client = _client(connection_id, db)
    if not client.model_exists(body.model):
        raise HTTPException(status_code=400, detail=f"Model {body.model} not found")
    arch = body.arch or DEFAULT_QWEB.format(key=body.report_key)
    if body.report_key not in arch and 't-name="' not in arch:
        raise HTTPException(
            status_code=422,
            detail="QWeb arch must include a t-name matching report_key",
        )
    try:
        existing = _find_qweb_view(client, body.report_key)
        if existing:
            view_id = int(existing["id"])
            client.execute_kw("ir.ui.view", "write", [[view_id], {"arch": arch}])
        else:
            view_id = int(
                client.execute_kw(
                    "ir.ui.view",
                    "create",
                    [
                        {
                            "name": body.report_key,
                            "type": "qweb",
                            "key": body.report_key,
                            "arch": arch,
                        }
                    ],
                )
            )
        vals: dict[str, Any] = {
            "name": body.name,
            "model": body.model,
            "report_type": body.report_type,
            "report_name": body.report_key,
        }
        if body.paperformat_id:
            vals["paperformat_id"] = body.paperformat_id
        report_id = int(client.execute_kw("ir.actions.report", "create", [vals]))
        try:
            from app.snapshots import snapshot_created_report

            snapshot_created_report(db, connection_id, client, report_id)
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
        rows = client.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {
                "fields": [
                    "name",
                    "model",
                    "report_type",
                    "report_name",
                    "paperformat_id",
                ]
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out = _report_out(client, rows[0])
    out.view_id = view_id
    out.arch = arch
    return out


@router.patch("/{report_id}", response_model=ReportOut)
def update_report(
    connection_id: str,
    report_id: int,
    body: UpdateReportBody,
    db: Session = Depends(get_db),
) -> ReportOut:
    client = _client(connection_id, db)
    from app.snapshots import snapshot_report

    try:
        snapshot_report(db, connection_id, client, report_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        rows = client.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {
                "fields": [
                    "name",
                    "model",
                    "report_type",
                    "report_name",
                    "paperformat_id",
                ]
            },
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Report not found")
        vals: dict[str, Any] = {}
        if body.name is not None:
            vals["name"] = body.name
        if body.clear_paperformat:
            vals["paperformat_id"] = False
        elif body.paperformat_id is not None:
            vals["paperformat_id"] = body.paperformat_id
        if vals:
            client.execute_kw("ir.actions.report", "write", [[report_id], vals])
        if body.arch is not None:
            key = rows[0].get("report_name")
            if not key:
                raise HTTPException(status_code=400, detail="Report has no report_name/key")
            view = _find_qweb_view(client, str(key))
            if not view:
                raise HTTPException(status_code=404, detail="QWeb view not found for report")
            client.execute_kw(
                "ir.ui.view", "write", [[int(view["id"])], {"arch": body.arch}]
            )
        refreshed = client.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {
                "fields": [
                    "name",
                    "model",
                    "report_type",
                    "report_name",
                    "paperformat_id",
                ]
            },
        )
    except HTTPException:
        raise
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _report_out(client, refreshed[0])


@router.delete("/{report_id}")
def delete_report(
    connection_id: str,
    report_id: int,
    body: ConfirmAdvancedBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Deleting a report removes the print action from the model.",
            risks=[
                "Users lose Print menu entry for this report",
                "QWeb view may remain orphaned — clean manually if needed",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    client = _client(connection_id, db)
    import json

    from app.snapshots import snapshot_report

    try:
        snap = snapshot_report(db, connection_id, client, report_id)
        payload = json.loads(snap.payload_json)
        payload["deleted"] = True
        snap.payload_json = json.dumps(payload)
        snap.reversible = "partial"  # QWeb view may remain orphaned
        db.add(snap)
        db.commit()
    except Exception:  # noqa: BLE001 — snapshot best-effort before delete
        pass
    try:
        client.execute_kw("ir.actions.report", "unlink", [[report_id]])
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "report_id": report_id}
