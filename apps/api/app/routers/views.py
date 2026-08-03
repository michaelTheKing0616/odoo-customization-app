"""View designer endpoints — render, parse, inherit-save, and polish forms."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odoo_client import CreateViewRequest, parse_arch, render_arch, render_inherit_replace_arch
from odoo_client.blueprint import apply_form_layout, auto_form_layout_for_model
from odoo_client.view_arch import (
    render_inherit_xpath_arch,
    render_xpath_wrap_arch,
    validate_xpath_arch,
)

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody, ViewOut
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(prefix="/connections/{connection_id}/views", tags=["view-designer"])


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


def _ensure_act_window_view_mode(client: Any, model: str, view_type: str) -> None:
    """Append view_type to every act_window for model so Open-in-Odoo can switch to it."""
    vt = "list" if view_type == "tree" else view_type
    if vt in {"search", "qweb"}:
        return
    try:
        actions = client.execute_kw(
            "ir.actions.act_window",
            "search_read",
            [[("res_model", "=", model)]],
            {"fields": ["id", "view_mode"], "limit": 80},
        )
    except Exception:
        return
    for act in actions or []:
        raw = str(act.get("view_mode") or "")
        modes = [m.strip() for m in raw.split(",") if m.strip()]
        if vt in modes:
            continue
        modes.append(vt)
        try:
            client.execute_kw(
                "ir.actions.act_window",
                "write",
                [[int(act["id"])], {"view_mode": ",".join(modes)}],
            )
        except Exception:
            continue


def _is_stock_model(model: str) -> bool:
    return not model.startswith("x_")


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _connection_major(db: Session, connection_id: str) -> int:
    from odoo_client.compat import UnsupportedOdooMajorError, parse_major

    row = get_connection_or_404(db, connection_id)
    try:
        return parse_major(str(row.server_version or "19"))
    except UnsupportedOdooMajorError:
        return 19


def _spec_with_major(spec: dict[str, Any], major: int) -> dict[str, Any]:
    merged = dict(spec)
    merged.setdefault("major", major)
    return merged


class PreviewArchBody(BaseModel):
    view_type: str = Field(..., examples=["form", "list"])
    spec: dict[str, Any]


class PreviewArchOut(BaseModel):
    arch: str


class ParseArchBody(BaseModel):
    view_type: str
    arch: str


class ParseArchOut(BaseModel):
    view_type: str
    spec: dict[str, Any]


class SaveViewBody(ConfirmAdvancedBody):
    model: str
    view_type: str = Field(..., examples=["form", "list"])
    name: str | None = None
    view_id: int | None = None
    spec: dict[str, Any] | None = None
    arch: str | None = None
    create_if_missing: bool = True
    # inherit (default): write extension view — safer for installed modules
    # overwrite: mutate primary / target view_id arch directly
    strategy: Literal["inherit", "overwrite"] = "inherit"


class PolishFormBody(ConfirmAdvancedBody):
    model: str
    string: str | None = None


class PolishFormOut(BaseModel):
    model: str
    view_id: int | None = None
    applied: bool
    detail: dict[str, Any] = Field(default_factory=dict)
    snapshot_id: str | None = None


class XPathPreviewBody(BaseModel):
    expr: str
    position: Literal[
        "inside", "after", "before", "replace", "attributes", "move"
    ] = "inside"
    body_xml: str = ""
    wrapper_xml: str | None = None
    wrapper_xml: str | None = None


class XPathPreviewOut(BaseModel):
    arch: str
    issues: list[str] = Field(default_factory=list)


@router.post("/preview", response_model=PreviewArchOut)
def preview_arch(
    connection_id: str, body: PreviewArchBody, db: Session = Depends(get_db)
) -> PreviewArchOut:
    major = _connection_major(db, connection_id)
    try:
        arch = render_arch(body.view_type, _spec_with_major(body.spec, major))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PreviewArchOut(arch=arch)


@router.post("/parse", response_model=ParseArchOut)
def parse_view_arch(connection_id: str, body: ParseArchBody) -> ParseArchOut:
    """Round-trip: Odoo arch XML → designer canvas spec."""
    _ = connection_id
    try:
        spec = parse_arch(body.view_type, body.arch)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ParseArchOut(view_type=body.view_type, spec=spec)


@router.post("/polish-form", response_model=PolishFormOut)
def polish_form(
    connection_id: str, body: PolishFormBody, db: Session = Depends(get_db)
) -> PolishFormOut:
    """Apply Identity/Details/Lines labeled form layout for any model (Builder polish)."""
    if _is_stock_model(body.model):
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Polish will rewrite the primary form layout for stock model "
                    f"{body.model}. Prefer inherit Designer saves unless you intend this."
                ),
                risks=[
                    "Can break stock xpath inherits (e.g. Contacts phone field)",
                    "Harder to reverse than inherit child views",
                    "Snapshot taken when possible — Undo from Snapshots if reversible",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    client = _client(connection_id, db)
    layout = auto_form_layout_for_model(client, body.model, string=body.string)
    if layout is None:
        return PolishFormOut(model=body.model, applied=False, detail={"reason": "no_fields"})
    from app.snapshots import snapshot_view

    snapshot_id: str | None = None
    try:
        primary = client.find_view(body.model, "form", primary_only=True) or client.find_view(
            body.model, "form"
        )
        if primary is not None:
            snap = snapshot_view(db, connection_id, client, primary.id)
            snapshot_id = snap.id
    except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
        pass
    try:
        detail = apply_form_layout(client, layout)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if snapshot_id:
        detail = {**detail, "snapshot_id": snapshot_id}
    return PolishFormOut(
        model=body.model,
        view_id=detail.get("view_id"),
        applied=not detail.get("skipped", False),
        detail=detail,
        snapshot_id=snapshot_id,
    )


@router.post("/xpath/preview", response_model=XPathPreviewOut)
def xpath_preview(connection_id: str, body: XPathPreviewBody) -> XPathPreviewOut:
    """Build + validate a single-xpath inherit arch (Designer power editor)."""
    _ = connection_id
    try:
        if body.wrapper_xml:
            arch = render_xpath_wrap_arch(expr=body.expr, wrapper_xml=body.wrapper_xml)
        else:
            arch = render_inherit_xpath_arch(
                expr=body.expr, position=body.position, body_xml=body.body_xml
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return XPathPreviewOut(arch=arch, issues=validate_xpath_arch(arch))


@router.get("/{view_id}", response_model=ViewOut)
def get_view(connection_id: str, view_id: int, db: Session = Depends(get_db)) -> ViewOut:
    client = _client(connection_id, db)
    try:
        view = client.get_view(view_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ViewOut.model_validate(view.model_dump())


@router.post("/save", response_model=ViewOut, status_code=200)
def save_view(
    connection_id: str, body: SaveViewBody, db: Session = Depends(get_db)
) -> ViewOut:
    from app.snapshots import snapshot_view
    from app.ee_drivers import EE_VIEW_TYPES
    from app.tier_matrix import build_tier_context

    row = get_connection_or_404(db, connection_id)
    vt_check = "list" if body.view_type == "tree" else body.view_type
    if vt_check in EE_VIEW_TYPES:
        ctx = build_tier_context(url=row.url, server_version=row.server_version)
        if not ctx.is_enterprise:
            raise HTTPException(
                status_code=409,
                detail={
                    "capability": "views_enterprise_types",
                    "message": (
                        f"View type {vt_check!r} is Enterprise-only — "
                        "matrix row views_enterprise_types is not available on Community."
                    ),
                },
            )

    client = _client(connection_id, db)
    major = _connection_major(db, connection_id)
    try:
        if body.arch:
            arch = body.arch
        elif body.spec is not None:
            arch = render_arch(body.view_type, _spec_with_major(body.spec, major))
        else:
            raise HTTPException(status_code=422, detail="Provide spec or arch")

        vt = "list" if body.view_type == "tree" else body.view_type
        snapshot_id: str | None = None
        overwrite = body.strategy == "overwrite" or body.view_id is not None

        if overwrite:
            # Stock primary overwrite always needs advanced confirm; any overwrite too.
            try:
                require_advanced_confirmation(
                    confirm_advanced=body.confirm_advanced,
                    confirm_phrase=body.confirm_phrase,
                    warning=(
                        f"Overwrite will mutate the live form/list arch for {body.model} "
                        "(not an inherit child). Prefer inherit unless you need a primary rewrite."
                    ),
                    risks=[
                        "Can break stock module xpath inherits",
                        "Upgrade / module update may conflict with mutated arches",
                        "Snapshot is taken — use Undo when reversible",
                        "On Odoo Online this is the same class of power as Odoo.sh view edits via RPC",
                    ],
                )
            except ConfirmationRequired as exc:
                raise _confirm_http(exc) from exc

        if overwrite:
            target_id = body.view_id
            if target_id is None:
                existing = client.find_view(body.model, vt)
                if existing is None:
                    if not body.create_if_missing:
                        raise HTTPException(status_code=404, detail="View not found")
                    view = client.create_view(
                        CreateViewRequest(
                            name=body.name or f"{body.model}.{vt}",
                            model=body.model,
                            type=vt,
                            arch=arch,
                        )
                    )
                    _ensure_act_window_view_mode(client, body.model, vt)
                    return ViewOut.model_validate(view.model_dump())
                target_id = existing.id
            snap = snapshot_view(db, connection_id, client, target_id)
            snapshot_id = snap.id
            view = client.update_view_arch(target_id, arch)
            _ensure_act_window_view_mode(client, body.model, vt)
            data = view.model_dump()
            data["snapshot_id"] = snapshot_id
            return ViewOut.model_validate(data)

        # inherit strategy (default) — force inherit for stock when caller asked overwrite
        # (overwrite already handled above)
        primary = client.find_view(body.model, vt, primary_only=True)
        if primary is None:
            primary = client.find_view(body.model, vt)
        if primary is None:
            if not body.create_if_missing:
                raise HTTPException(status_code=404, detail="View not found")
            view = client.create_view(
                CreateViewRequest(
                    name=body.name or f"{body.model}.{vt}",
                    model=body.model,
                    type=vt,
                    arch=arch,
                )
            )
            _ensure_act_window_view_mode(client, body.model, vt)
            return ViewOut.model_validate(view.model_dump())

        child_name = body.name or f"{body.model}.designer.{vt}"
        existing_child = client.execute_kw(
            "ir.ui.view",
            "search",
            [[("name", "=", child_name), ("model", "=", body.model)]],
            {"limit": 1},
        )
        # First inherit-save on a model with no view creates a *primary* under the
        # designer name. A later save must not write <data><xpath> onto that primary —
        # Odoo validates typed roots (<activity>, <form>, …) and rejects <data>.
        designer_owns_primary = (
            (existing_child and int(existing_child[0]) == primary.id)
            or getattr(primary, "name", None) == child_name
        )
        snap = snapshot_view(db, connection_id, client, primary.id)
        snapshot_id = snap.id
        if designer_owns_primary:
            view = client.update_view_arch(primary.id, arch)
        elif existing_child:
            inherit_arch = render_inherit_replace_arch(vt, arch)
            view = client.update_view_arch(int(existing_child[0]), inherit_arch)
        else:
            inherit_arch = render_inherit_replace_arch(vt, arch)
            view = client.create_inherit_view(
                model=body.model,
                name=child_name,
                view_type=vt,
                inherit_id=primary.id,
                arch=inherit_arch,
            )
        _ensure_act_window_view_mode(client, body.model, vt)
        data = view.model_dump()
        data["snapshot_id"] = snapshot_id
        return ViewOut.model_validate(data)
    except HTTPException:
        raise
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
