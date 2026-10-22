"""Wireframe photo upload. Preview and clarify only. No apply."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import get_connection_or_404
from app.wireframe_live import clarify_uploaded_sketch, read_uploaded_photo, vision_status

router = APIRouter(
    prefix="/connections/{connection_id}/wireframe",
    tags=["wireframe"],
)

_ALLOWED_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
    "application/pdf",
}
_MAX_BYTES = 10 * 1024 * 1024
_MAX_PDF_PAGES = 10


class WireframeClarifyBody(BaseModel):
    sketch: dict[str, Any]
    merge_key: str = "wireframe_region"
    answer_id: str
    answer_text: str = Field(default="")


def _require_connection(connection_id: str, db: Session) -> None:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _normalize_mime(content_type: str | None, filename: str | None) -> str:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime in _ALLOWED_MIME:
        return "image/jpeg" if mime == "image/jpg" else mime
    name = (filename or "").lower()
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".gif"):
        return "image/gif"
    if name.endswith((".heic", ".heif")):
        return "image/heic"
    if name.endswith(".pdf"):
        return "application/pdf"
    raise HTTPException(status_code=400, detail="Upload a photo (JPEG, PNG, WebP, HEIC) or a PDF of up to 10 pages.")


def _pdf_pages(data: bytes) -> int:
    import io

    from pypdf import PdfReader

    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a bad upload
        raise HTTPException(status_code=400, detail="That PDF could not be opened.") from exc


@router.get("/status")
def wireframe_vision_status(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_connection(connection_id, db)
    return vision_status()


@router.post("/read")
async def wireframe_read_photo(
    connection_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_connection(connection_id, db)
    mime = _normalize_mime(file.content_type, file.filename)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="The file is larger than 10 MB.")
    if mime == "application/pdf" and _pdf_pages(data) > _MAX_PDF_PAGES:
        raise HTTPException(status_code=400, detail="That PDF has more than 10 pages. Send the pages with the screens only.")
    return read_uploaded_photo(data, mime)


@router.post("/clarify")
def wireframe_clarify(
    connection_id: str,
    body: WireframeClarifyBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_connection(connection_id, db)
    return clarify_uploaded_sketch(
        body.sketch,
        merge_key=body.merge_key,
        answer_id=body.answer_id,
        answer_text=body.answer_text,
    )


class WireframeMapBody(BaseModel):
    sketch: dict[str, Any]


@router.post("/map")
def wireframe_map(connection_id: str, body: WireframeMapBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Q6: stock-first mapping of the read sketch onto this database (metadata reads only)."""
    from app.hosting import connection_hosting
    from app.odoo_service import OdooClientError, client_from_connection
    from app.wireframe.reader import read_sketch
    from app.wireframe.stock_map import guard_sketch, map_regions

    try:
        conn = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    sketch = read_sketch(body.sketch)
    guards = guard_sketch(sketch)
    try:
        client = client_from_connection(conn)
        result = map_regions(sketch, lambda m, meth, a, k: client.execute_kw(m, meth, a, k))
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=f"Odoo did not answer: {exc}") from exc
    hosting = connection_hosting(conn)
    result["install"] = (
        {"mode": "data", "why": "Odoo Online installs data modules only, so new fields ship as a data module."}
        if hosting == "online"
        else {"mode": "module", "why": "This database can install a custom module."}
    )
    result["hosting"] = hosting
    result["guards"] = guards
    return result
