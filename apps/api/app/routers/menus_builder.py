"""Visual menu & window-action builder via public ORM/RPC."""

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
    prefix="/connections/{connection_id}/menus-builder",
    tags=["menus-builder"],
)


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


class MenuNodeOut(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    parent_name: str | None = None
    action: str | None = None
    action_id: int | None = None
    action_type: str | None = None
    sequence: int = 10
    web_icon: str | None = None
    child_count: int = 0


class WindowActionOut(BaseModel):
    id: int
    name: str
    res_model: str | None = None
    view_mode: str | None = None
    domain: str | None = None
    context: str | None = None
    target: str | None = None
    requires_active_id: bool = False


def _expr_as_str(value: Any) -> str | None:
    if value is None or value is False:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _requires_active_id(domain: str | None, context: str | None) -> bool:
    blob = f"{domain or ''} {context or ''}"
    return "active_id" in blob or "active_ids" in blob


def _window_action_out(action_id: int, row: dict[str, Any]) -> WindowActionOut:
    dom = _expr_as_str(row.get("domain"))
    ctx = _expr_as_str(row.get("context"))
    return WindowActionOut(
        id=action_id,
        name=str(row.get("name") or ""),
        res_model=row.get("res_model") or None,
        view_mode=row.get("view_mode") or None,
        domain=dom,
        context=ctx,
        target=row.get("target") or None,
        requires_active_id=_requires_active_id(dom, ctx),
    )


class CreateMenuBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parent_id: int | None = None
    action_id: int | None = None
    sequence: int = 10
    web_icon: str | None = None


class UpdateMenuBody(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    clear_parent: bool = False
    action_id: int | None = None
    clear_action: bool = False
    sequence: int | None = None
    web_icon: str | None = None


class CreateWindowActionBody(BaseModel):
    name: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    view_mode: str = "list,form"
    domain: str | None = None
    context: str | None = None
    target: str = "current"


class UpdateWindowActionBody(BaseModel):
    name: str | None = None
    view_mode: str | None = None
    domain: str | None = None
    context: str | None = None
    target: str | None = None


class BindMenuActionBody(BaseModel):
    action_id: int


def _parse_action_ref(action: Any) -> tuple[str | None, int | None]:
    if not isinstance(action, str) or "," not in action:
        return None, None
    typ, _, sid = action.partition(",")
    try:
        return typ.strip(), int(sid.strip())
    except ValueError:
        return typ.strip(), None


def _menu_out(row: dict[str, Any], child_counts: dict[int, int]) -> MenuNodeOut:
    parent = row.get("parent_id")
    parent_id = int(parent[0]) if isinstance(parent, (list, tuple)) and parent else None
    parent_name = (
        str(parent[1]) if isinstance(parent, (list, tuple)) and len(parent) > 1 else None
    )
    action = row.get("action") if isinstance(row.get("action"), str) else None
    action_type, action_id = _parse_action_ref(action)
    mid = int(row["id"])
    return MenuNodeOut(
        id=mid,
        name=str(row.get("name") or ""),
        parent_id=parent_id,
        parent_name=parent_name,
        action=action,
        action_id=action_id,
        action_type=action_type,
        sequence=int(row.get("sequence") or 10),
        web_icon=row.get("web_icon") or None,
        child_count=child_counts.get(mid, 0),
    )


@router.get("/tree", response_model=list[MenuNodeOut])
def list_menu_tree(
    connection_id: str,
    parent_id: int | None = Query(None),
    roots_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[MenuNodeOut]:
    client = _client(connection_id, db)
    domain: list[Any] = []
    if roots_only:
        domain = [("parent_id", "=", False)]
    elif parent_id is not None:
        domain = [("parent_id", "=", parent_id)]
    try:
        rows = client.execute_kw(
            "ir.ui.menu",
            "search_read",
            [domain],
            {
                "fields": ["name", "parent_id", "action", "sequence", "web_icon", "child_id"],
                "limit": 500,
                "order": "sequence, id",
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    child_counts: dict[int, int] = {}
    for r in rows:
        children = r.get("child_id") or []
        if isinstance(children, list):
            child_counts[int(r["id"])] = len(children)
    return [_menu_out(r, child_counts) for r in rows]


@router.post("/menus", response_model=MenuNodeOut, status_code=201)
def create_menu(
    connection_id: str, body: CreateMenuBody, db: Session = Depends(get_db)
) -> MenuNodeOut:
    client = _client(connection_id, db)
    try:
        mid = client.create_menu(
            name=body.name,
            parent_id=body.parent_id,
            action_id=body.action_id,
            sequence=body.sequence,
            web_icon=body.web_icon,
        )
        try:
            from app.snapshots import snapshot_created_menu

            snapshot_created_menu(db, connection_id, client, mid)
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
        rows = client.execute_kw(
            "ir.ui.menu",
            "read",
            [[mid]],
            {
                "fields": [
                    "name",
                    "parent_id",
                    "action",
                    "sequence",
                    "web_icon",
                    "child_id",
                ]
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _menu_out(rows[0], {mid: 0})


@router.patch("/menus/{menu_id}", response_model=MenuNodeOut)
def update_menu(
    connection_id: str,
    menu_id: int,
    body: UpdateMenuBody,
    db: Session = Depends(get_db),
) -> MenuNodeOut:
    client = _client(connection_id, db)
    from app.snapshots import snapshot_menu

    try:
        snapshot_menu(db, connection_id, client, menu_id)
    except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
        pass
    vals: dict[str, Any] = {}
    if body.name is not None:
        vals["name"] = body.name
    if body.clear_parent:
        vals["parent_id"] = False
    elif body.parent_id is not None:
        vals["parent_id"] = body.parent_id
    if body.clear_action:
        vals["action"] = False
    elif body.action_id is not None:
        vals["action"] = f"ir.actions.act_window,{body.action_id}"
    if body.sequence is not None:
        vals["sequence"] = body.sequence
    if body.web_icon is not None:
        vals["web_icon"] = body.web_icon
    if not vals:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        client.execute_kw("ir.ui.menu", "write", [[menu_id], vals])
        rows = client.execute_kw(
            "ir.ui.menu",
            "read",
            [[menu_id]],
            {
                "fields": [
                    "name",
                    "parent_id",
                    "action",
                    "sequence",
                    "web_icon",
                    "child_id",
                ]
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    children = rows[0].get("child_id") or []
    return _menu_out(
        rows[0], {menu_id: len(children) if isinstance(children, list) else 0}
    )


@router.post("/menus/{menu_id}/bind-action", response_model=MenuNodeOut)
def bind_menu_action(
    connection_id: str,
    menu_id: int,
    body: BindMenuActionBody,
    db: Session = Depends(get_db),
) -> MenuNodeOut:
    return update_menu(
        connection_id,
        menu_id,
        UpdateMenuBody(action_id=body.action_id),
        db,
    )


@router.delete("/menus/{menu_id}")
def delete_menu(
    connection_id: str,
    menu_id: int,
    body: ConfirmAdvancedBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Deleting a menu removes it from the Odoo app switcher / navbar.",
            risks=[
                "Child menus may become orphans or also delete depending on Odoo cascade",
                "Actions bound only via this menu remain but are harder to discover",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    client = _client(connection_id, db)
    from app.snapshots import snapshot_menu
    import json

    try:
        snap = snapshot_menu(db, connection_id, client, menu_id)
        payload = json.loads(snap.payload_json)
        payload["deleted"] = True
        snap.payload_json = json.dumps(payload)
        db.add(snap)
        db.commit()
    except Exception:  # noqa: BLE001 — snapshot best-effort before delete
        pass
    try:
        client.execute_kw("ir.ui.menu", "unlink", [[menu_id]])
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "menu_id": menu_id}


@router.get("/actions", response_model=list[WindowActionOut])
def list_window_actions(
    connection_id: str,
    model: str | None = Query(None),
    q: str | None = Query(None),
    standalone_only: bool = Query(
        False,
        description="Exclude related/smart-button actions that need active_id",
    ),
    db: Session = Depends(get_db),
) -> list[WindowActionOut]:
    client = _client(connection_id, db)
    domain: list[Any] = []
    if model:
        domain.append(("res_model", "=", model))
    if q:
        domain.append(("name", "ilike", q))
    try:
        rows = client.execute_kw(
            "ir.actions.act_window",
            "search_read",
            [domain],
            {
                "fields": ["name", "res_model", "view_mode", "domain", "context", "target"],
                "limit": 200,
                "order": "name",
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out: list[WindowActionOut] = []
    for r in rows:
        item = _window_action_out(int(r["id"]), r)
        if standalone_only and item.requires_active_id:
            continue
        out.append(item)
    # Standalone first so naive clients (first match) stay safe for Open-in-Odoo
    out.sort(key=lambda a: (a.requires_active_id, a.name.lower(), a.id))
    return out


@router.post("/actions", response_model=WindowActionOut, status_code=201)
def create_window_action(
    connection_id: str, body: CreateWindowActionBody, db: Session = Depends(get_db)
) -> WindowActionOut:
    client = _client(connection_id, db)
    try:
        aid = client.create_window_action(
            name=body.name,
            model=body.model,
            view_mode=body.view_mode,
            domain=body.domain,
            context=body.context,
        )
        if body.target and body.target != "current":
            client.execute_kw(
                "ir.actions.act_window", "write", [[aid], {"target": body.target}]
            )
        try:
            from app.snapshots import snapshot_action

            snapshot_action(
                db,
                connection_id,
                client,
                model="ir.actions.act_window",
                action_id=aid,
                created=True,
            )
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
        rows = client.execute_kw(
            "ir.actions.act_window",
            "read",
            [[aid]],
            {"fields": ["name", "res_model", "view_mode", "domain", "context", "target"]},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    r = rows[0]
    return _window_action_out(aid, r)


@router.patch("/actions/{action_id}", response_model=WindowActionOut)
def update_window_action(
    connection_id: str,
    action_id: int,
    body: UpdateWindowActionBody,
    db: Session = Depends(get_db),
) -> WindowActionOut:
    client = _client(connection_id, db)
    vals = {k: v for k, v in body.model_dump().items() if v is not None}
    if not vals:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        client.execute_kw("ir.actions.act_window", "write", [[action_id], vals])
        rows = client.execute_kw(
            "ir.actions.act_window",
            "read",
            [[action_id]],
            {"fields": ["name", "res_model", "view_mode", "domain", "context", "target"]},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    r = rows[0]
    return _window_action_out(action_id, r)
