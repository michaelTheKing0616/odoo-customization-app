"""Website page block editor API (UIX-7)."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.snapshots import snapshot_view
from app.website_blocks import blocks_from_dicts, parse_website_arch, render_website_arch

router = APIRouter(prefix="/connections/{connection_id}/website", tags=["website"])


class WebsiteBlocksOut(BaseModel):
    page_id: int
    view_id: int
    name: str
    url: str | None
    is_published: bool
    blocks: list[dict[str, Any]]


class WebsiteBlocksSaveBody(BaseModel):
    blocks: list[dict[str, Any]]
    page_id: int
    view_id: int


class PublishBody(BaseModel):
    page_id: int
    publish: bool = True


class UploadImageOut(BaseModel):
    attachment_id: int
    src: str
    name: str


_MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _client_or_404(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
        return row, client_from_connection(row)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _website_installed(client) -> bool:
    try:
        mods = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", "website"), ("state", "=", "installed")]],
            {"fields": ["name"], "limit": 1},
        )
        return bool(mods)
    except Exception:  # noqa: BLE001
        return False


@router.get("/pages/{page_id}/blocks", response_model=WebsiteBlocksOut)
def get_page_blocks(
    connection_id: str,
    page_id: int,
    db: Session = Depends(get_db),
) -> WebsiteBlocksOut:
    _row, client = _client_or_404(connection_id, db)
    if not _website_installed(client):
        raise HTTPException(status_code=409, detail="website module not installed")

    pages = client.execute_kw(
        "website.page",
        "read",
        [[page_id]],
        {"fields": ["name", "url", "view_id", "is_published"]},
    )
    if not pages:
        raise HTTPException(status_code=404, detail="website.page not found")
    page = pages[0]
    view_id = page["view_id"][0] if isinstance(page.get("view_id"), list) else page["view_id"]
    views = client.execute_kw(
        "ir.ui.view",
        "read",
        [[view_id]],
        {"fields": ["arch_db"]},
    )
    arch = views[0].get("arch_db") or ""
    blocks = [b.to_dict() for b in parse_website_arch(arch)]
    return WebsiteBlocksOut(
        page_id=page_id,
        view_id=int(view_id),
        name=str(page.get("name") or ""),
        url=page.get("url"),
        is_published=bool(page.get("is_published")),
        blocks=blocks,
    )


@router.put("/pages/{page_id}/blocks")
def save_page_blocks(
    connection_id: str,
    page_id: int,
    body: WebsiteBlocksSaveBody,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row, client = _client_or_404(connection_id, db)
    if not _website_installed(client):
        raise HTTPException(status_code=409, detail="website module not installed")

    blocks = blocks_from_dicts(body.blocks)
    new_arch = render_website_arch(blocks)
    snapshot_view(db, connection_id, client, body.view_id)
    client.execute_kw(
        "ir.ui.view",
        "write",
        [[body.view_id], {"arch_db": new_arch}],
    )
    return {"ok": True, "view_id": body.view_id, "arch_len": len(new_arch)}


@router.post("/pages/{page_id}/publish")
def publish_page(
    connection_id: str,
    page_id: int,
    body: PublishBody,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _row, client = _client_or_404(connection_id, db)
    if not _website_installed(client):
        raise HTTPException(status_code=409, detail="website module not installed")
    client.execute_kw(
        "website.page",
        "write",
        [[page_id], {"is_published": body.publish}],
    )
    return {"ok": True, "page_id": page_id, "is_published": body.publish}


@router.post("/upload-image", response_model=UploadImageOut)
async def upload_website_image(
    connection_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadImageOut:
    """Upload image → ir.attachment (public) → /web/image/{id} src."""
    _row, client = _client_or_404(connection_id, db)
    if not _website_installed(client):
        raise HTTPException(status_code=409, detail="website module not installed")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds 5MB limit")

    filename = file.filename or "upload.png"
    mimetype = file.content_type or "application/octet-stream"
    b64 = base64.b64encode(raw).decode("ascii")
    att_id = client.execute_kw(
        "ir.attachment",
        "create",
        [
            {
                "name": filename,
                "type": "binary",
                "datas": b64,
                "mimetype": mimetype,
                "public": True,
            }
        ],
    )
    if isinstance(att_id, list):
        att_id = att_id[0]
    src = f"/web/image/{int(att_id)}"
    return UploadImageOut(attachment_id=int(att_id), src=src, name=filename)
