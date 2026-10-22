"""Report layout lite — QWeb PDF reports + paper formats via RPC."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.report_merge import ReportMergeError, run_merge_print
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)
from odoo_client.report_render import probe_report_render

router = APIRouter(
    prefix="/connections/{connection_id}/reports",
    tags=["reports"],
)

DEFAULT_QWEB = """\
<t t-name="{key}">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="doc">
            <t t-call="web.external_layout">
                <div class="page">
                    <h2 t-field="doc.display_name"/>
                    <p>Generated via Odoo Custom report lite.</p>
                </div>
            </t>
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



def _field_type_map(rows: list[Any]) -> dict[str, str]:
    """name → ttype from list_fields / fields_get rows (Table Inspector totals)."""
    out: dict[str, str] = {}
    for row in rows:
        if isinstance(row, dict):
            name = row.get("name")
            ttype = row.get("ttype") or row.get("type")
        else:
            name = getattr(row, "name", None)
            ttype = getattr(row, "ttype", None) or getattr(row, "type", None)
        if name and isinstance(ttype, str) and ttype:
            out[str(name)] = ttype
    return out


def _field_name_set(rows: list[Any]) -> set[str]:
    names: set[str] = set()
    for row in rows:
        name = getattr(row, "name", None)
        if name is None and isinstance(row, dict):
            name = row.get("name")
        if name:
            names.add(str(name))
    return names


def _ground_design_spec(
    client: Any,
    spec: dict[str, Any],
    *,
    require_blocks: bool = False,
) -> dict[str, Any]:
    """model_exists + fields_get (via list_fields) before compile writes arch.

    Inputs: live Odoo client and a designer spec.
    Outputs: the same spec after gates pass; line-table column ``ttype`` hints
    are re-annotated from the related model's fields_get (PDF-07).
    Side effects: raises HTTPException 400/422 on missing model, empty design,
    unknown field tokens, or totals on non-numeric columns — never writes into
    the arch. Rebinds ``spec["blocks"]`` on the caller's request-local dict.
    """
    from app.report_design import (
        annotate_column_types,
        ground_design_against_schema,
        relational_line_fields,
        collect_field_tokens,
    )

    model = str(spec.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail="design model is required for grounding")
    if not client.model_exists(model):
        raise HTTPException(status_code=400, detail=f"Model {model} not found")
    try:
        parent_rows = client.list_fields(model)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    parent_names = _field_name_set(parent_rows)
    line_map = relational_line_fields(parent_rows)
    related: dict[str, set[str]] = {}
    related_types: dict[str, dict[str, str]] = {}
    tokens = collect_field_tokens(
        [b for b in (spec.get("blocks") or []) if isinstance(b, dict)]
    )
    needed_o2m = {
        t.get("o2m_field") or ""
        for t in tokens
        if t.get("scope") == "column" and t.get("o2m_field")
    }
    # Also load comodel when an o2m parent token is present so the picker gate matches.
    for t in tokens:
        if t.get("scope") == "parent" and t["field"] in line_map:
            needed_o2m.add(t["field"])
    for o2m in needed_o2m:
        comodel = line_map.get(o2m)
        if not comodel:
            # validate_grounded_fields will refuse columns; still surface clearly
            related[o2m] = set()
            continue
        if not client.model_exists(comodel):
            raise HTTPException(
                status_code=400,
                detail=f"Related model {comodel} for {o2m} not found",
            )
        try:
            related_rows = client.list_fields(comodel)
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        related[o2m] = _field_name_set(related_rows)
        related_types[o2m] = _field_type_map(related_rows)
    try:
        ground_design_against_schema(
            spec,
            parent_field_names=parent_names,
            related_field_names=related,
            require_blocks=require_blocks,
            related_field_types=related_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return annotate_column_types(spec, related_types)



def _gate_report_arch_or_422(arch: str | None) -> None:
    """PDF-05: refuse unsafe pasted/compiled arch before any ir.ui.view write."""
    if not arch:
        return
    from app.qweb_unsafe_gate import gate_report_arch

    try:
        gate_report_arch(arch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    # PDF-04: optional visual design — grounded then compiled to arch.
    # Empty blocks are refused (do not create). use_external_layout defaults on.
    spec: dict[str, Any] | None = None


class UpdateReportBody(BaseModel):
    name: str | None = None
    arch: str | None = None
    paperformat_id: int | None = None
    clear_paperformat: bool = False
    # PDF-03: optional report.inherit payload from the designer (one anchor).
    inherit_op: dict[str, Any] | None = None


class ReportRenderProbeOut(BaseModel):
    major: int
    rpc_methods: dict[str, str]
    http_report_pdf: bool
    primary_path: str
    message: str


class MergePrintItemIn(BaseModel):
    report_id: int
    record_ids: list[int] = Field(..., min_length=1)


class MergePrintBody(BaseModel):
    items: list[MergePrintItemIn] = Field(..., min_length=1)
    order: list[int] | None = None
    filename: str | None = Field(None, max_length=120)


class ReportDesignCompileBody(BaseModel):
    spec: dict[str, Any] = Field(default_factory=dict)


class ReportDesignCompileOut(BaseModel):
    ok: bool
    arch: str
    body_html: str


class ReportDesignModuleSpecOut(BaseModel):
    ok: bool
    fragment: dict[str, Any]


class ReportDesignPreviewBody(BaseModel):
    spec: dict[str, Any] = Field(default_factory=dict)
    report_id: int
    record_id: int


class ReportDesignPreviewOut(BaseModel):
    ok: bool
    content_base64: str
    render_path: str
    message: str


class ReportDesignAnchorsBody(BaseModel):
    arch: str = Field(..., min_length=1)


class ReportDesignAnchorOut(BaseModel):
    xpath: str
    label: str


@router.get("/design/palette")
def report_design_palette() -> list[dict[str, str]]:
    from app.report_design import BLOCK_PALETTE

    return list(BLOCK_PALETTE)


@router.post("/design/compile", response_model=ReportDesignCompileOut)
def compile_report_design_route(
    connection_id: str,
    body: ReportDesignCompileBody,
    db: Session = Depends(get_db),
) -> ReportDesignCompileOut:
    from app.report_design import compile_report_design as compile_design

    spec = dict(body.spec or {})
    if str(spec.get("model") or "").strip():
        client = _client(connection_id, db)
        _ground_design_spec(client, spec, require_blocks=False)
    try:
        out = compile_design(spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ReportDesignCompileOut(ok=True, arch=out["arch"], body_html=out["body_html"])


@router.post("/design/to-module-spec", response_model=ReportDesignModuleSpecOut)
def report_design_to_module_spec(body: ReportDesignCompileBody) -> ReportDesignModuleSpecOut:
    from app.report_design import design_to_module_report

    try:
        fragment = design_to_module_report(body.spec or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ReportDesignModuleSpecOut(ok=True, fragment=fragment)


@router.post("/design/anchors", response_model=list[ReportDesignAnchorOut])
def report_design_anchors(body: ReportDesignAnchorsBody) -> list[ReportDesignAnchorOut]:
    from app.report_design import parse_qweb_anchors

    return [ReportDesignAnchorOut(**a) for a in parse_qweb_anchors(body.arch)]


@router.post("/design/preview", response_model=ReportDesignPreviewOut)
def report_design_preview(
    connection_id: str,
    body: ReportDesignPreviewBody,
    db: Session = Depends(get_db),
) -> ReportDesignPreviewOut:
    import base64

    from app.report_design import compile_report_design as compile_design
    from odoo_client.report_render import probe_report_render, render_report_pdf

    client = _client(connection_id, db)
    spec = dict(body.spec or {})
    if str(spec.get("model") or "").strip():
        _ground_design_spec(client, spec, require_blocks=False)
    try:
        compiled = compile_design(spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    arch = compiled["arch"]
    _gate_report_arch_or_422(arch)
    try:
        rows = client.execute_kw(
            "ir.actions.report",
            "read",
            [[int(body.report_id)]],
            {"fields": ["report_name"]},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Report not found")
    key = rows[0].get("report_name")
    if not key:
        raise HTTPException(status_code=400, detail="Report has no QWeb key")
    view = _find_qweb_view(client, str(key))
    if not view:
        raise HTTPException(status_code=404, detail="QWeb view not found")
    prior_arch = view.get("arch") or ""
    view_id = int(view["id"])
    try:
        client.execute_kw("ir.ui.view", "write", [[view_id], {"arch": arch}])
        probe = probe_report_render(
            client,
            sample_report_id=int(body.report_id),
            sample_res_id=int(body.record_id),
        )
        pdf = render_report_pdf(
            client,
            int(body.report_id),
            [int(body.record_id)],
            probe=probe,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        try:
            client.execute_kw("ir.ui.view", "write", [[view_id], {"arch": prior_arch}])
        except OdooClientError:
            pass
    return ReportDesignPreviewOut(
        ok=True,
        content_base64=base64.b64encode(pdf).decode("ascii"),
        render_path=probe.primary_path,
        message=probe.message or "Preview rendered",
    )



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


@router.get("/render-probe", response_model=ReportRenderProbeOut)
def report_render_probe(
    connection_id: str,
    report_id: int | None = Query(None),
    res_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> ReportRenderProbeOut:
    client = _client(connection_id, db)
    probe = probe_report_render(
        client,
        sample_report_id=report_id,
        sample_res_id=res_id,
    )
    return ReportRenderProbeOut.model_validate(probe.to_dict())


@router.post("/merge-print")
def merge_print_reports(
    connection_id: str,
    body: MergePrintBody,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    client = _client(connection_id, db)
    try:
        pdf_bytes, meta = run_merge_print(
            client,
            items=[item.model_dump() for item in body.items],
            order=body.order,
        )
    except ReportMergeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = (body.filename or meta.filename).strip() or "merged-report.pdf"
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Total-Pages": str(meta.total_pages),
        "X-Render-Path": meta.probe.primary_path if meta.probe else "unknown",
    }
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers=headers,
    )


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
    """Create ir.actions.report (report.action.create shape) bound to a real model.

    When ``spec`` is provided it must be non-empty and every field token must
    exist via model_exists + list_fields (fields_get equivalent). Unknown
    fields are refused and never written into the arch. New primary designs
    default to web.external_layout.
    """
    from app.report_design import compile_report_design as compile_design

    client = _client(connection_id, db)
    if not client.model_exists(body.model):
        raise HTTPException(status_code=400, detail=f"Model {body.model} not found")
    arch = body.arch
    if body.spec is not None:
        spec = dict(body.spec)
        spec.setdefault("model", body.model)
        spec.setdefault("report_key", body.report_key)
        spec.setdefault("name", body.name)
        spec.setdefault("mode", "primary")
        spec.setdefault("use_external_layout", True)
        _ground_design_spec(client, spec, require_blocks=True)
        try:
            arch = compile_design(spec)["arch"]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not arch:
        # Minimal grounded default — display_name exists on every model; external layout on.
        arch = DEFAULT_QWEB.format(key=body.report_key)
    if body.report_key not in arch and 't-name="' not in arch:
        raise HTTPException(
            status_code=422,
            detail="QWeb arch must include a t-name matching report_key",
        )
    _gate_report_arch_or_422(arch)
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
    if body.inherit_op is not None:
        from app.changeset.ui_ops import report_inherit_issues

        op = body.inherit_op
        params = op.get("params") if isinstance(op, dict) else None
        if not isinstance(op, dict) or op.get("type") != "report.inherit" or not isinstance(params, dict):
            raise HTTPException(status_code=400, detail="Report extension (inherit_op) must be type report.inherit with params")
        issues = report_inherit_issues(params)
        if issues:
            raise HTTPException(status_code=400, detail="; ".join(issues))
        # Exactly one anchor — expect_matches defaults to 1 in report_inherit_issues.
        if params.get("expect_matches", 1) != 1:
            raise HTTPException(status_code=400, detail="report extension requires exactly one anchor")
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
            _gate_report_arch_or_422(body.arch)
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
