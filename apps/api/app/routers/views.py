"""View designer endpoints — render, parse, inherit-save, and polish forms."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odoo_client import CreateModelRequest, CreateViewRequest, parse_arch, render_arch, render_inherit_replace_arch
from odoo_client.blueprint import apply_form_layout, auto_form_layout_for_model
from odoo_client.view_arch import (
    build_additive_form_inherit_arch,
    extract_replaced_form_arch,
    field_names_in_arch,
    form_spec_for_additive_repair,
    inherit_arch_looks_like_full_form_replace,
    list_x_field_names_in_form_spec,
    merge_inherit_data_arch,
    render_inherit_xpath_arch,
    render_overlay_operation_arch,
    render_xpath_wrap_arch,
)
from odoo_client.xpath_locator import (
    blocking_issues,
    classify_xpath_arch,
    count_xpath_matches,
    looks_like_xpath_inherit,
    semantic_field_candidates,
    semantic_inject_expr,
    semantic_structure_candidates,
    suggested_expr_from_issues,
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


def _locator_issue_out(issues: list[Any]) -> list[LocatorIssueOut]:
    return [LocatorIssueOut.model_validate(item.as_dict()) for item in issues]


def _xpath_preview_fields(
    arch: str,
    *,
    expr: str,
    parent_arch: str | None,
    view_type: str = "form",
) -> tuple[list[Any], str | None, int | None, bool, str | None]:
    classified = classify_xpath_arch(arch, parent_arch=parent_arch)
    suggested = suggested_expr_from_issues(classified, expr)
    match_count = count_xpath_matches(parent_arch, expr) if parent_arch else None
    default_inject = semantic_inject_expr(parent_arch, view_type)
    return (
        classified,
        suggested,
        match_count,
        bool(blocking_issues(classified)),
        default_inject,
    )


def _raise_if_blocking_xpath(arch: str, parent_arch: str | None) -> None:
    """Refuse inherit writes whose operator xpath misses or is ambiguous."""
    if not parent_arch or not looks_like_xpath_inherit(arch):
        return
    classified = classify_xpath_arch(arch, parent_arch=parent_arch)
    blocking = blocking_issues(classified)
    if not blocking:
        return
    first = blocking[0]
    raise HTTPException(
        status_code=422,
        detail={
            "message": first.as_text(),
            "code": first.code,
            "expr": first.expr,
            "suggestion": first.suggestion,
            "issues": [item.as_dict() for item in classified],
        },
    )


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


class DesignerInheritBody(ConfirmAdvancedBody):
    model: str
    view_type: str = Field("form", examples=["form", "list"])


class DesignerInheritOut(BaseModel):
    action: Literal["repaired", "already_additive", "unlinked", "missing"]
    model: str
    view_type: str
    view_id: int | None = None
    view_name: str | None = None
    snapshot_id: str | None = None
    kept_custom_fields: list[str] = Field(default_factory=list)
    remaining_custom_injects: list[str] = Field(default_factory=list)
    detail: str = ""


def _designer_child_name(model: str, view_type: str) -> str:
    vt = "list" if view_type == "tree" else view_type
    return f"{model}.designer.{vt}"


def _inherit_id_int(raw: Any) -> int | None:
    if raw in (False, None, 0, "0"):
        return None
    if isinstance(raw, (list, tuple)) and raw:
        return int(raw[0])
    return int(raw)


def _existing_names_for_repair(client: Any, model: str, view_type: str, dumped_arch: str) -> set[str]:
    """Stock + already-injected fields — keep only truly new x_* in the repair arch."""
    existing = {n for n in field_names_in_arch(dumped_arch) if not n.startswith("x_")}
    try:
        for inject_name in client.list_custom_field_inject_names(model, view_type):
            # account.move.custom.x_demo_note.form → x_demo_note
            parts = inject_name.split(".")
            if len(parts) >= 4 and parts[-1] in {"form", "list", "tree", "search", "kanban"}:
                field_leaf = parts[-2]
                if field_leaf.startswith("x_"):
                    existing.add(field_leaf)
    except Exception:  # noqa: BLE001
        pass
    try:
        primary = client.find_view(model, view_type, primary_only=True) or client.find_view(
            model, view_type
        )
        if primary and primary.arch:
            existing |= {n for n in field_names_in_arch(primary.arch) if not n.startswith("x_")}
    except Exception:  # noqa: BLE001
        pass
    return existing


@router.post("/designer-inherit/repair", response_model=DesignerInheritOut)
def repair_designer_inherit(
    connection_id: str, body: DesignerInheritBody, db: Session = Depends(get_db)
) -> DesignerInheritOut:
    """Rewrite a full-form-replace Designer inherit to additive ``x_*`` only.

    Fixes duplicate Send/Print/Pay and Other Info on stock forms (e.g. Bills)
    while keeping TEST GROUP / custom fields when possible. If nothing additive
    remains, unlinks the broken inherit (chrome restored; inject views may still
    show ``x_*`` fields).
    """
    from app.snapshots import save_snapshot, snapshot_view

    if body.model.startswith("x_"):
        raise HTTPException(
            status_code=422,
            detail="Repair is for stock models with a Designer inherit child — custom x_* models own their primary.",
        )
    vt = "list" if body.view_type == "tree" else body.view_type
    if vt != "form":
        raise HTTPException(status_code=422, detail="Repair is only implemented for form views")

    client = _client(connection_id, db)
    major = _connection_major(db, connection_id)
    rows = client.find_designer_inherit_rows(body.model, vt)
    injects = client.list_custom_field_inject_names(body.model, vt)
    child_name = _designer_child_name(body.model, vt)

    if not rows:
        return DesignerInheritOut(
            action="missing",
            model=body.model,
            view_type=vt,
            view_name=child_name,
            remaining_custom_injects=injects,
            detail=f"No view named {child_name!r} — chrome may already be stock, or the inherit used another name.",
        )

    row = rows[0]
    view_id = int(row["id"])
    inherit_id = _inherit_id_int(row.get("inherit_id"))
    if inherit_id is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{child_name!r} is a primary view, not an inherit child — "
                "refusing repair/unlink. Fix manually in Odoo Technical → Views."
            ),
        )

    arch = row.get("arch") or ""
    snap = snapshot_view(db, connection_id, client, view_id)
    snapshot_id = snap.id

    if not inherit_arch_looks_like_full_form_replace(arch):
        return DesignerInheritOut(
            action="already_additive",
            model=body.model,
            view_type=vt,
            view_id=view_id,
            view_name=str(row.get("name") or child_name),
            snapshot_id=snapshot_id,
            remaining_custom_injects=injects,
            detail="Designer inherit is already additive (no full form replace) — hard-refresh Odoo if duplicates persist.",
        )

    dumped = extract_replaced_form_arch(arch) or arch
    existing = _existing_names_for_repair(client, body.model, vt, dumped)
    spec = form_spec_for_additive_repair(arch)
    try:
        new_arch = build_additive_form_inherit_arch(
            spec, existing_field_names=existing, major=major
        )
    except ValueError:
        # Nothing left to inject — drop the chrome-duplicating inherit.
        client.unlink_view(view_id)
        save_snapshot(
            db,
            connection_id=connection_id,
            resource_type="view",
            resource_key=f"view:{view_id}:unlinked",
            label=f"Unlinked {child_name} (repair had no additive fields)",
            payload={"view": row, "deleted": True},
            reversible="no",
        )
        return DesignerInheritOut(
            action="unlinked",
            model=body.model,
            view_type=vt,
            view_id=view_id,
            view_name=child_name,
            snapshot_id=snapshot_id,
            remaining_custom_injects=injects,
            detail=(
                "Full-replace inherit removed (no leftover x_* to keep). "
                "Hard-refresh the Bill/Invoice. Custom inject views listed in remaining_custom_injects may still show fields."
            ),
        )

    kept = [n for n in field_names_in_arch(new_arch) if n.startswith("x_")]
    client.update_view_arch(view_id, new_arch)
    return DesignerInheritOut(
        action="repaired",
        model=body.model,
        view_type=vt,
        view_id=view_id,
        view_name=child_name,
        snapshot_id=snapshot_id,
        kept_custom_fields=kept,
        remaining_custom_injects=injects,
        detail=(
            "Rewrote Designer inherit to additive sheet inject — duplicates gone; "
            f"kept custom fields: {', '.join(kept) or '(none)'}."
        ),
    )


@router.post("/designer-inherit/unlink", response_model=DesignerInheritOut)
def unlink_designer_inherit(
    connection_id: str, body: DesignerInheritBody, db: Session = Depends(get_db)
) -> DesignerInheritOut:
    """Unlink ``{model}.designer.{view_type}`` after confirm — restores stock chrome.

    Does not delete ``ir.model.fields`` or ``{model}.custom.*`` inject views.
    """
    from app.snapshots import save_snapshot, snapshot_view

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                f"Unlink will delete the Designer inherit view "
                f"{_designer_child_name(body.model, body.view_type)!r}. "
                "Stock Send/Print/Pay / Other Info duplicates clear; custom groups "
                "that lived only in that inherit disappear (fields may remain via inject views)."
            ),
            risks=[
                "Deletes the extension view row (not the primary stock form)",
                "TEST GROUP / layout that existed only in that inherit is removed",
                "Undo cannot recreate a deleted view from a normal arch snapshot",
                "Prefer Fix duplicate chrome (repair) when you want to keep x_* groups",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    vt = "list" if body.view_type == "tree" else body.view_type
    child_name = _designer_child_name(body.model, vt)
    rows = client.find_designer_inherit_rows(body.model, vt)
    injects = client.list_custom_field_inject_names(body.model, vt)

    if not rows:
        return DesignerInheritOut(
            action="missing",
            model=body.model,
            view_type=vt,
            view_name=child_name,
            remaining_custom_injects=injects,
            detail=f"No view named {child_name!r} to unlink.",
        )

    row = rows[0]
    view_id = int(row["id"])
    if _inherit_id_int(row.get("inherit_id")) is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{child_name!r} is a primary view — refusing unlink. "
                "Use Odoo Technical → Views and inspect carefully."
            ),
        )

    snap = snapshot_view(db, connection_id, client, view_id)
    client.unlink_view(view_id)
    save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="view",
        resource_key=f"view:{view_id}:unlinked",
        label=f"Unlinked {child_name}",
        payload={"view": row, "deleted": True},
        reversible="no",
    )
    return DesignerInheritOut(
        action="unlinked",
        model=body.model,
        view_type=vt,
        view_id=view_id,
        view_name=child_name,
        snapshot_id=snap.id,
        remaining_custom_injects=injects,
        detail=(
            f"Unlinked {child_name}. Hard-refresh Odoo. "
            "To put custom fields back without duplicates: Load existing view → Save Inherit."
        ),
    )


class XPathPreviewBody(BaseModel):
    expr: str
    position: Literal[
        "inside", "after", "before", "replace", "attributes", "move"
    ] = "inside"
    body_xml: str = ""
    wrapper_xml: str | None = None
    parent_arch: str | None = None
    view_type: str = "form"


class OverlayApplyBody(BaseModel):
    model: str
    view_type: str = Field(..., examples=["form", "list"])
    operation: Literal[
        "hide",
        "move",
        "relabel",
        "add_field",
        "set_widget",
        "group_label",
        "add_page",
        "add_group",
    ]
    expr: str = ""
    field_name: str | None = None
    anchor_expr: str | None = None
    move_position: Literal["before", "after", "inside"] | None = None
    add_field_name: str | None = None
    add_position: Literal["before", "after", "inside"] = "after"
    string: str | None = None
    placeholder: str | None = None
    help_text: str | None = None
    widget: str | None = None
    label_target: Literal["field", "group", "page"] = "field"
    preview_only: bool = False
    parent_arch: str | None = None


class LocatorIssueOut(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    expr: str | None = None
    suggestion: str | None = None


class OverlayApplyOut(BaseModel):
    xpath_arch: str
    issues: list[str] = Field(default_factory=list)
    locator_issues: list[LocatorIssueOut] = Field(default_factory=list)
    suggested_expr: str | None = None
    view_id: int | None = None
    snapshot_id: str | None = None
    inherit_name: str | None = None


class XPathPreviewOut(BaseModel):
    arch: str
    issues: list[str] = Field(default_factory=list)
    locator_issues: list[LocatorIssueOut] = Field(default_factory=list)
    suggested_expr: str | None = None
    default_inject_expr: str | None = None
    match_count: int | None = None
    blocking: bool = False


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
    classified, suggested, match_count, blocking, default_inject = _xpath_preview_fields(
        arch,
        expr=body.expr,
        parent_arch=body.parent_arch,
        view_type=body.view_type,
    )
    return XPathPreviewOut(
        arch=arch,
        issues=[item.as_text() for item in classified],
        locator_issues=_locator_issue_out(classified),
        suggested_expr=suggested,
        default_inject_expr=default_inject,
        match_count=match_count,
        blocking=blocking,
    )


class ResolveFieldBody(BaseModel):
    view_type: str
    arch: str
    field_name: str


@router.post("/resolve-field")
def resolve_field_node(body: ResolveFieldBody) -> dict[str, object]:
    """Map overlay field descriptor → ranked semantic arch nodes (UIX-6)."""
    name = body.field_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="field_name required")
    ranked = semantic_field_candidates(body.arch, name)
    candidates = [
        {
            "xpath": item.xpath,
            "match": item.match,
            "score": item.score,
            "fragile": item.fragile,
            "match_count": item.match_count,
        }
        for item in ranked
    ]
    if not candidates:
        try:
            spec = parse_arch(body.view_type, body.arch)
            fields = []
            if isinstance(spec, dict):
                for key in ("fields", "columns", "children"):
                    val = spec.get(key)
                    if isinstance(val, list):
                        fields.extend(val)
            for f in fields:
                if isinstance(f, dict) and f.get("name") == name:
                    xpath = f"//field[@name='{name}']"
                    candidates.append(
                        {
                            "xpath": xpath,
                            "from_spec": True,
                            "score": 0,
                            "fragile": True,
                            "match_count": None,
                        }
                    )
        except Exception:  # noqa: BLE001
            pass
    return {
        "field_name": name,
        "candidates": candidates,
        "ambiguous": len(candidates) > 1,
    }


class ResolveStructureBody(BaseModel):
    arch: str
    tags: list[str] | None = None


@router.post("/resolve-structure")
def resolve_structure_nodes(body: ResolveStructureBody) -> dict[str, object]:
    """Map overlay containers (notebook/page/group/sheet) → ranked semantic locators."""
    tags = tuple(body.tags) if body.tags else None
    ranked = semantic_structure_candidates(body.arch, tags=tags)
    candidates = [
        {
            "xpath": item.xpath,
            "tag": item.tag,
            "label": item.label,
            "score": item.score,
            "fragile": item.fragile,
            "match_count": item.match_count,
        }
        for item in ranked
    ]
    return {"candidates": candidates, "ambiguous": len(candidates) > 1}


def _overlay_child_name(model: str, view_type: str) -> str:
    vt = "list" if view_type == "tree" else view_type
    return f"{model}.overlay.{vt}"


def _build_overlay_fragment(body: OverlayApplyBody) -> str:
    return render_overlay_operation_arch(
        body.operation,
        expr=body.expr,
        view_type=body.view_type,
        field_name=body.field_name,
        anchor_expr=body.anchor_expr,
        move_position=body.move_position,
        add_field_name=body.add_field_name,
        add_position=body.add_position,
        string=body.string,
        placeholder=body.placeholder,
        help_text=body.help_text,
        widget=body.widget,
        label_target=body.label_target,
        parent_arch=body.parent_arch,
    )


def _stock_field_names_only(names: set[str] | list[str]) -> set[str]:
    return {n for n in names if n and not str(n).startswith("x_")}


def _unlink_redundant_field_injects(
    client: Any, model: str, view_type: str, field_names: list[str]
) -> list[str]:
    """Remove ``{model}.custom.{field}.{view_type}`` injects now covered by Designer inherit.

    Create-field defaults to inject-into-views; Form layout Save then owns placement.
    Leaving both produces duplicate widgets (or a false 'already on form' Save refusal).
    """
    vt = "list" if view_type == "tree" else view_type
    removed: list[str] = []
    for fname in field_names:
        if not fname.startswith("x_"):
            continue
        inject_name = f"{model}.custom.{fname}.{vt}"
        try:
            ids = client.execute_kw(
                "ir.ui.view",
                "search",
                [[("name", "=", inject_name), ("model", "=", model)]],
                {"limit": 1},
            )
            if not ids:
                continue
            client.unlink_view(int(ids[0]))
            removed.append(inject_name)
        except Exception:  # noqa: BLE001 — best-effort cleanup
            continue
    return removed


def _existing_names_for_designer_additive(
    client: Any, model: str, primary_arch: str | None
) -> set[str]:
    """Stock field names only — canvas ``x_*`` must be free to rewrite the designer inherit."""
    existing = _stock_field_names_only(field_names_in_arch(primary_arch or ""))
    try:
        combined = client.get_combined_view_arch(model, "form")
        existing |= _stock_field_names_only(field_names_in_arch(combined))
    except Exception:  # noqa: BLE001
        pass
    return existing


@router.get("/primary", response_model=ViewOut)
def get_primary_view(
    connection_id: str,
    model: str,
    view_type: str = "form",
    db: Session = Depends(get_db),
) -> ViewOut:
    """Return the primary (non-extension) view arch for overlay mapping."""
    client = _client(connection_id, db)
    vt = "list" if view_type == "tree" else view_type
    try:
        primary = client.find_view(model, vt, primary_only=True) or client.find_view(model, vt)
    except OdooClientError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if primary is None:
        raise HTTPException(status_code=404, detail=f"No {vt} view for {model}")
    return ViewOut.model_validate(primary.model_dump())


@router.post("/overlay/preview", response_model=OverlayApplyOut)
def overlay_preview(connection_id: str, body: OverlayApplyBody) -> OverlayApplyOut:
    """Build xpath inherit fragment for an overlay operation (no Odoo write)."""
    _ = connection_id
    try:
        arch = _build_overlay_fragment(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    classified = classify_xpath_arch(arch, parent_arch=body.parent_arch)
    return OverlayApplyOut(
        xpath_arch=arch,
        issues=[item.as_text() for item in classified],
        locator_issues=_locator_issue_out(classified),
        suggested_expr=suggested_expr_from_issues(classified, body.expr),
    )


@router.post("/overlay/apply", response_model=OverlayApplyOut)
def overlay_apply(
    connection_id: str, body: OverlayApplyBody, db: Session = Depends(get_db)
) -> OverlayApplyOut:
    """Apply one overlay operation as an appended xpath on ``{model}.overlay.{type}`` inherit."""
    from app.snapshots import snapshot_view

    if body.preview_only:
        return overlay_preview(connection_id, body)

    client = _client(connection_id, db)
    vt = "list" if body.view_type == "tree" else body.view_type
    try:
        fragment = _build_overlay_fragment(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    primary = client.find_view(body.model, vt, primary_only=True) or client.find_view(
        body.model, vt
    )
    if primary is None:
        raise HTTPException(status_code=404, detail=f"No {vt} view for {body.model}")

    parent_arch = body.parent_arch or getattr(primary, "arch", None)
    _raise_if_blocking_xpath(fragment, parent_arch)
    classified = classify_xpath_arch(fragment, parent_arch=parent_arch)

    snap = snapshot_view(db, connection_id, client, primary.id)
    child_name = _overlay_child_name(body.model, vt)
    existing = client._find_view_by_exact_name(child_name)
    if existing is not None and existing.arch:
        merged = merge_inherit_data_arch(existing.arch, fragment)
        view = client.update_view_arch(existing.id, merged)
    else:
        view = client.create_inherit_view(
            model=body.model,
            name=child_name,
            view_type=vt,
            inherit_id=primary.id,
            arch=fragment,
        )
    return OverlayApplyOut(
        xpath_arch=fragment,
        issues=[item.as_text() for item in classified],
        locator_issues=_locator_issue_out(classified),
        suggested_expr=suggested_expr_from_issues(classified, body.expr),
        view_id=view.id,
        snapshot_id=snap.id,
        inherit_name=child_name,
    )


@router.get("/{view_id}", response_model=ViewOut)
def get_view(connection_id: str, view_id: int, db: Session = Depends(get_db)) -> ViewOut:
    client = _client(connection_id, db)
    try:
        view = client.get_view(view_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ViewOut.model_validate(view.model_dump())


def _humanize_model_name(model: str) -> str:
    stem = model.split(".")[-1]
    if stem.startswith("x_"):
        stem = stem[2:]
    return stem.replace("_", " ").strip().title() or model


def _ensure_custom_model_for_view(client, model: str) -> bool:
    """Create a stub x_* ir.model when Designer saves before Models & Fields.

    Returns True when a new model was created.
    """
    if not model.startswith("x_") or client.model_exists(model):
        return False
    client.create_model(
        CreateModelRequest(
            name=_humanize_model_name(model),
            model=model,
            transient=False,
        ),
        with_defaults=True,
    )
    return True


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
        _ensure_custom_model_for_view(client, body.model)

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
        if body.arch and looks_like_xpath_inherit(arch) and not designer_owns_primary:
            _raise_if_blocking_xpath(arch, getattr(primary, "arch", None))
        snap = snapshot_view(db, connection_id, client, primary.id)
        snapshot_id = snap.id

        stock_model = not body.model.startswith("x_")
        use_additive_form = (
            stock_model
            and vt == "form"
            and body.spec is not None
            and not body.arch
        )

        if designer_owns_primary:
            # Custom models that own the primary still get a full typed arch.
            view = client.update_view_arch(primary.id, arch)
        elif use_additive_form:
            # Stock forms: never replace //form with a re-emitted combined dump —
            # that duplicates Send/Print/Pay and notebook pages from module inherits.
            # existing = stock fields only so canvas x_* always rewrite designer.form
            # (create-field inject already put x_* on the combined form — must not
            # treat that as "nothing to save").
            existing_names = _existing_names_for_designer_additive(
                client, body.model, primary.arch
            )
            try:
                inherit_arch = build_additive_form_inherit_arch(
                    body.spec,
                    existing_field_names=existing_names,
                    major=major,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if existing_child:
                child_id = int(existing_child[0])
                view = client.update_view_arch(child_id, inherit_arch)
            else:
                view = client.create_inherit_view(
                    model=body.model,
                    name=child_name,
                    view_type=vt,
                    inherit_id=primary.id,
                    arch=inherit_arch,
                )
            placed = list_x_field_names_in_form_spec(body.spec)
            _unlink_redundant_field_injects(client, body.model, vt, placed)
        elif existing_child:
            inherit_arch = (
                arch
                if body.arch and arch.lstrip().startswith("<data")
                else render_inherit_replace_arch(vt, arch)
            )
            # Guard: stock + accidental full replace body still gets rewritten if we
            # can see form chrome in a raw arch override path — leave raw xpath alone.
            if (
                stock_model
                and vt == "form"
                and inherit_arch_looks_like_full_form_replace(inherit_arch)
                and body.spec is not None
            ):
                inherit_arch = build_additive_form_inherit_arch(
                    body.spec,
                    existing_field_names=_existing_names_for_designer_additive(
                        client, body.model, primary.arch
                    ),
                    major=major,
                )
            view = client.update_view_arch(int(existing_child[0]), inherit_arch)
        else:
            inherit_arch = (
                arch
                if body.arch and arch.lstrip().startswith("<data")
                else render_inherit_replace_arch(vt, arch)
            )
            if (
                stock_model
                and vt == "form"
                and inherit_arch_looks_like_full_form_replace(inherit_arch)
                and body.spec is not None
            ):
                inherit_arch = build_additive_form_inherit_arch(
                    body.spec,
                    existing_field_names=_existing_names_for_designer_additive(
                        client, body.model, primary.arch
                    ),
                    major=major,
                )
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
        msg = str(exc)
        if "Model not found" in msg and body.model.startswith("x_"):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Odoo could not find custom model {body.model!r}. "
                    "Create it under Models & Fields first, or retry Save to Odoo "
                    "(the app will auto-create x_* models when missing)."
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

