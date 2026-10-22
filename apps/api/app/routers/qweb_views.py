"""DOC-QWEB — list / open / save general ir.ui.view type=qweb arches.

Dedicated operate surface (not Designer form/list/kanban). Reuses
``qweb_view_blocks`` gate family → ``qweb_unsafe_gate`` + RT-22 root-replace.
Prefer extension (inherit) writes; overwrite requires advanced confirm.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.qweb_view_blocks import (
    blocks_from_dicts,
    compile_inherit_fragment,
    compile_qweb_view_blocks,
    default_qweb_view_blocks,
    extract_t_call_targets,
    gate_qweb_view_save,
    try_parse_qweb_view_blocks,
)
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
    snapshot_view,
)

router = APIRouter(
    prefix="/connections/{connection_id}/qweb-views", tags=["qweb-views"]
)


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


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _m2o_id(val: Any) -> int | None:
    if isinstance(val, (list, tuple)) and val:
        try:
            return int(val[0])
        except (TypeError, ValueError):
            return None
    if isinstance(val, int):
        return val
    return None


def _m2o_name(val: Any) -> str | None:
    if isinstance(val, (list, tuple)) and len(val) > 1:
        return str(val[1]) if val[1] else None
    return None


class QwebViewListOut(BaseModel):
    id: int
    name: str
    key: str | None = None
    model: str | None = None
    inherit_id: int | None = None
    inherit_name: str | None = None
    mode: str | None = None
    priority: int | None = None
    report_bound: bool = False
    report_name: str | None = None


class QwebViewDetailOut(QwebViewListOut):
    arch: str | None = None
    blocks: list[dict[str, Any]] | None = None
    blocks_parseable: bool = False
    existing_t_call_targets: list[str] = Field(default_factory=list)


class QwebViewCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    key: str = Field(..., min_length=3, max_length=200)
    model: str | None = Field(
        None, description="Optional model for grounded t-field blocks"
    )
    wrap_external_layout: bool = True
    blocks: list[dict[str, Any]] | None = None
    arch: str | None = None


class QwebViewSaveBody(BaseModel):
    arch: str | None = None
    blocks: list[dict[str, Any]] | None = None
    strategy: Literal["inherit", "overwrite"] = "inherit"
    inherit_xpath: str | None = Field(
        None, description="Required when strategy=inherit (extension view) and compiling blocks"
    )
    inherit_position: str = "inside"
    # Grandfathered t-call targets from the loaded arch (client echoes them).
    existing_t_call_targets: list[str] = Field(default_factory=list)
    confirm_advanced: bool = False
    confirm_phrase: str | None = None
    child_name: str | None = Field(
        None,
        description="Inherit child name; default {key}.ingenium.qweb",
    )


class QwebViewSaveOut(BaseModel):
    id: int
    name: str
    key: str | None = None
    snapshot_id: str | None = None
    strategy: str
    arch_len: int


def _report_keys(client: Any) -> dict[str, str]:
    """Map report_name (QWeb key) → report display name."""
    try:
        rows = client.execute_kw(
            "ir.actions.report",
            "search_read",
            [[]],
            {"fields": ["name", "report_name"], "limit": 500},
        )
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, str] = {}
    for r in rows or []:
        key = r.get("report_name")
        if key:
            out[str(key)] = str(r.get("name") or key)
    return out


def _list_row(row: dict[str, Any], report_map: dict[str, str]) -> QwebViewListOut:
    key = row.get("key") or None
    if key is not None:
        key = str(key) or None
    inherit = row.get("inherit_id")
    report_name = report_map.get(key) if key else None
    return QwebViewListOut(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        key=key,
        model=(str(row["model"]) if row.get("model") else None),
        inherit_id=_m2o_id(inherit),
        inherit_name=_m2o_name(inherit),
        mode=(str(row["mode"]) if row.get("mode") else None),
        priority=int(row["priority"]) if row.get("priority") is not None else None,
        report_bound=bool(report_name),
        report_name=report_name,
    )


@router.get("", response_model=list[QwebViewListOut])
def list_qweb_views(
    connection_id: str,
    model: str | None = Query(None),
    key_prefix: str | None = Query(None),
    exclude_report_bound: bool = Query(
        False,
        description="When true, omit views whose key is bound to ir.actions.report",
    ),
    limit: int = Query(150, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[QwebViewListOut]:
    client = _client(connection_id, db)
    domain: list[Any] = [("type", "=", "qweb")]
    if model:
        domain.append(("model", "=", model))
    if key_prefix:
        domain.append(("key", "=ilike", f"{key_prefix}%"))
    try:
        rows = client.execute_kw(
            "ir.ui.view",
            "search_read",
            [domain],
            {
                "fields": [
                    "id",
                    "name",
                    "key",
                    "model",
                    "inherit_id",
                    "mode",
                    "priority",
                ],
                "limit": limit,
                "order": "name, id",
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report_map = _report_keys(client)
    out = [_list_row(r, report_map) for r in rows or []]
    if exclude_report_bound:
        out = [r for r in out if not r.report_bound]
    return out


@router.get("/{view_id}", response_model=QwebViewDetailOut)
def get_qweb_view(
    connection_id: str, view_id: int, db: Session = Depends(get_db)
) -> QwebViewDetailOut:
    client = _client(connection_id, db)
    try:
        rows = client.execute_kw(
            "ir.ui.view",
            "read",
            [[view_id]],
            {
                "fields": [
                    "id",
                    "name",
                    "key",
                    "model",
                    "type",
                    "arch",
                    "inherit_id",
                    "mode",
                    "priority",
                ]
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="QWeb view not found")
    row = rows[0]
    if str(row.get("type") or "") != "qweb":
        raise HTTPException(
            status_code=422,
            detail=f"View #{view_id} is type={row.get('type')!r}, not qweb",
        )
    arch = row.get("arch") or ""
    if arch is False:
        arch = ""
    arch_s = str(arch)
    parsed = try_parse_qweb_view_blocks(arch_s)
    report_map = _report_keys(client)
    base = _list_row(row, report_map)
    targets = sorted(extract_t_call_targets(arch_s))
    return QwebViewDetailOut(
        **base.model_dump(),
        arch=arch_s,
        blocks=[b.to_dict() for b in parsed] if parsed is not None else None,
        blocks_parseable=parsed is not None,
        existing_t_call_targets=targets,
    )


@router.post("", response_model=QwebViewDetailOut, status_code=201)
def create_qweb_view(
    connection_id: str, body: QwebViewCreateBody, db: Session = Depends(get_db)
) -> QwebViewDetailOut:
    client = _client(connection_id, db)
    key = body.key.strip()
    if "." not in key:
        raise HTTPException(
            status_code=422,
            detail="key must be a dotted xmlid-style key (module.name)",
        )

    blocks = (
        blocks_from_dicts(body.blocks)
        if body.blocks is not None
        else default_qweb_view_blocks(body.name)
    )
    if body.arch:
        arch = body.arch
    else:
        arch = compile_qweb_view_blocks(
            blocks, wrap_external_layout=body.wrap_external_layout
        )
    try:
        gate_qweb_view_save(blocks, arch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Refuse collide with existing key.
    existing = client.execute_kw(
        "ir.ui.view",
        "search",
        [[("key", "=", key), ("type", "=", "qweb")]],
        {"limit": 1},
    )
    if existing:
        raise HTTPException(
            status_code=409, detail=f"QWeb view key {key!r} already exists"
        )

    vals: dict[str, Any] = {
        "name": body.name,
        "type": "qweb",
        "key": key,
        "arch": arch,
        "priority": 16,
    }
    if body.model:
        vals["model"] = body.model
    try:
        view_id = int(client.execute_kw("ir.ui.view", "create", [vals]))
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_qweb_view(connection_id, view_id, db)


@router.put("/{view_id}", response_model=QwebViewSaveOut)
def save_qweb_view(
    connection_id: str,
    view_id: int,
    body: QwebViewSaveBody,
    db: Session = Depends(get_db),
) -> QwebViewSaveOut:
    client = _client(connection_id, db)
    try:
        rows = client.execute_kw(
            "ir.ui.view",
            "read",
            [[view_id]],
            {"fields": ["id", "name", "key", "model", "type", "arch", "mode"]},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="QWeb view not found")
    row = rows[0]
    if str(row.get("type") or "") != "qweb":
        raise HTTPException(
            status_code=422,
            detail=f"View #{view_id} is type={row.get('type')!r}, not qweb",
        )

    loaded_arch = row.get("arch") or ""
    if loaded_arch is False:
        loaded_arch = ""
    loaded_targets = extract_t_call_targets(str(loaded_arch))
    allow = set(loaded_targets) | set(body.existing_t_call_targets or [])

    blocks = blocks_from_dicts(body.blocks) if body.blocks is not None else None

    if body.arch is not None:
        arch = body.arch
    elif blocks is not None and body.strategy == "inherit":
        xpath = (body.inherit_xpath or "").strip()
        if not xpath:
            raise HTTPException(
                status_code=422,
                detail="An extension path (inherit_xpath) is required when saving blocks with strategy=inherit",
            )
        try:
            arch = compile_inherit_fragment(
                blocks,
                xpath=xpath,
                position=body.inherit_position or "inside",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif blocks is not None:
        arch = compile_qweb_view_blocks(blocks, wrap_external_layout=False)
    else:
        raise HTTPException(status_code=422, detail="Provide arch or blocks")

    try:
        gate_qweb_view_save(
            blocks,
            arch,
            allow_existing_t_calls=allow,
            inherit_xpath=body.inherit_xpath if body.strategy == "inherit" else None,
            inherit_position=(
                body.inherit_position if body.strategy == "inherit" else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    key = row.get("key")
    key_s = str(key) if key else None

    if body.strategy == "overwrite":
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Overwrite will mutate QWeb view #{view_id} "
                    f"({row.get('name')}) directly — prefer inherit."
                ),
                risks=[
                    "Can break stock module xpath inherits",
                    "Upgrade / module update may conflict with mutated arches",
                    "Snapshot is taken — use Undo when reversible",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

        snap = snapshot_view(db, connection_id, client, view_id)
        try:
            client.execute_kw("ir.ui.view", "write", [[view_id], {"arch": arch}])
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return QwebViewSaveOut(
            id=view_id,
            name=str(row.get("name") or ""),
            key=key_s,
            snapshot_id=snap.id if snap else None,
            strategy="overwrite",
            arch_len=len(arch),
        )

    # inherit strategy
    child_name = (
        body.child_name
        or (f"{key_s}.ingenium.qweb" if key_s else f"view{view_id}.ingenium.qweb")
    )
    xpath = (body.inherit_xpath or "").strip()
    # If caller passed a full <data><xpath> arch, write that as the child.
    # If they passed a fragment without xpath wrapper and no inherit_xpath, refuse.
    looks_inherit = arch.lstrip().startswith("<data")
    if not looks_inherit:
        if not xpath:
            raise HTTPException(
                status_code=422,
                detail=(
                    "strategy=inherit needs a <data><xpath> arch or "
                    "inherit_xpath + blocks"
                ),
            )
        try:
            from app.report_design import refuse_root_replace

            refuse_root_replace(xpath, body.inherit_position or "inside")
            pos = body.inherit_position or "inside"
            arch = (
                f'<data>\n'
                f'  <xpath expr="{xpath}" position="{pos}">\n'
                f"    {arch}\n"
                f"  </xpath>\n"
                f"</data>"
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing_child = client.execute_kw(
        "ir.ui.view",
        "search",
        [[("name", "=", child_name), ("inherit_id", "=", view_id)]],
        {"limit": 1},
    )
    snap = snapshot_view(db, connection_id, client, view_id)
    try:
        if existing_child:
            child_id = int(existing_child[0])
            client.execute_kw("ir.ui.view", "write", [[child_id], {"arch": arch}])
            out_id = child_id
        else:
            vals = {
                "name": child_name,
                "type": "qweb",
                "inherit_id": view_id,
                "mode": "extension",
                "arch": arch,
                "priority": 99,
            }
            if row.get("model"):
                vals["model"] = row["model"]
            if key_s:
                vals["key"] = f"{key_s}_ingenium"
            out_id = int(client.execute_kw("ir.ui.view", "create", [vals]))
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return QwebViewSaveOut(
        id=out_id,
        name=child_name,
        key=key_s,
        snapshot_id=snap.id if snap else None,
        strategy="inherit",
        arch_len=len(arch),
    )
