"""Bulk image import — CSV manifest + ZIP of images → base64 RPC writes (CMP-6 §14)."""

from __future__ import annotations

import base64
import csv
import io
import zipfile
from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError
from odoo_client.image_pipeline import MAX_IMAGE_EDGE, MAX_UPLOAD_BYTES, is_image_field

MatchMode = Literal["name", "code"]


@dataclass
class ImageImportRow:
    row_index: int
    match_value: str
    filename: str
    ok: bool = False
    record_id: int | None = None
    action: str | None = None
    error: str | None = None
    bytes_in: int = 0
    bytes_out: int = 0


@dataclass
class ImageImportPreview:
    row_count: int
    sample_rows: list[dict[str, str]]
    image_field: str
    match_field: str
    match_mode: MatchMode
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImageImportResult:
    ok: bool
    updated: int = 0
    failed: int = 0
    skipped: int = 0
    message: str = ""
    results: list[ImageImportRow] = field(default_factory=list)


def _normalize_manifest_rows(raw_csv: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = raw_csv.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("manifest CSV has no header row")
    headers = [str(h).strip() for h in reader.fieldnames if h]
    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {
            str(k).strip().lower(): ("" if v is None else str(v).strip())
            for k, v in row.items()
            if k is not None and str(k).strip()
        }
        if any(cleaned.values()):
            rows.append(cleaned)
    return headers, rows


def _pick_column(headers: set[str], *candidates: str) -> str | None:
    for c in candidates:
        if c in headers:
            return c
    return None


def parse_manifest_csv(raw_csv: bytes) -> tuple[list[dict[str, str]], str, str, MatchMode]:
    headers, rows = _normalize_manifest_rows(raw_csv)
    hset = {h.lower() for h in headers}
    # Normalize row keys to lowercase (already done in _normalize_manifest_rows)
    match_col = _pick_column(
        {k for r in rows[:1] for k in r} if rows else hset,
        "match",
        "name",
        "code",
        "default_code",
        "x_name",
    )
    file_col = _pick_column(
        {k for r in rows[:1] for k in r} if rows else hset,
        "filename",
        "file",
        "image",
        "image_file",
    )
    field_col = _pick_column(
        {k for r in rows[:1] for k in r} if rows else hset,
        "image_field",
        "field",
    )
    if not match_col or not file_col:
        raise ValueError("manifest CSV needs match/name and filename/image columns")
    image_field = "image_1920"
    if field_col and rows:
        image_field = rows[0].get(field_col) or image_field
    match_mode: MatchMode = "code" if match_col in {"code", "default_code"} else "name"
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append(
            {
                "match": row.get(match_col, ""),
                "filename": row.get(file_col, ""),
                "image_field": row.get(field_col, "") if field_col else image_field,
            }
        )
    return normalized, image_field, match_col, match_mode


def build_image_import_preview(
    *,
    manifest_rows: list[dict[str, str]],
    image_field: str,
    match_field: str,
    match_mode: MatchMode,
    zip_names: set[str],
) -> ImageImportPreview:
    warnings: list[str] = []
    missing = [r["filename"] for r in manifest_rows if r["filename"] and r["filename"] not in zip_names]
    if missing:
        warnings.append(f"{len(missing)} manifest filename(s) not found in ZIP")
    return ImageImportPreview(
        row_count=len(manifest_rows),
        sample_rows=manifest_rows[:5],
        image_field=image_field,
        match_field=match_field,
        match_mode=match_mode,
        warnings=warnings,
    )


def _load_zip_images(raw_zip: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.split("/")[-1]
            if not name or name.startswith("."):
                continue
            data = zf.read(info)
            if data:
                out[name] = data
                out[info.filename] = data
    return out


def _prepare_image_bytes(raw: bytes) -> tuple[bytes, str]:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError(f"image exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit")
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow is required for image import — install API dep pillow") from exc

    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        w, h = img.size
        max_edge = max(w, h)
        if max_edge > MAX_IMAGE_EDGE:
            scale = MAX_IMAGE_EDGE / max_edge
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        out = buf.getvalue()
    return out, "image/jpeg"


def _resolve_image_field(meta: dict[str, dict[str, Any]], preferred: str) -> str:
    if preferred in meta and str(meta[preferred].get("ttype")) in {"binary", "image"}:
        return preferred
    for name, info in meta.items():
        if is_image_field({"name": name, "ttype": info.get("ttype")}):
            return name
    raise ValueError(f"Image field {preferred!r} not found on model")


def _find_record_id(
    client: OdooClient,
    model: str,
    match_value: str,
    match_field: str,
) -> int | None:
    if not match_value:
        return None
    domain = [(match_field, "=", match_value)]
    ids = client.execute_kw(model, "search", [domain], {"limit": 2})
    if not ids:
        return None
    if len(ids) > 1:
        raise ValueError(f"Ambiguous match for {match_value!r} on {match_field}")
    return int(ids[0])


def run_image_import(
    client: OdooClient,
    *,
    model: str,
    manifest_rows: list[dict[str, str]],
    zip_images: dict[str, bytes],
    image_field: str,
    match_field: str = "x_name",
    dry_run: bool = True,
) -> ImageImportResult:
    if not client.model_exists(model):
        raise OdooClientError(f"Model {model} not found")
    meta_rows = client.execute_kw(
        "ir.model.fields",
        "search_read",
        [[("model", "=", model)]],
        {"fields": ["name", "ttype"], "limit": 5000},
    )
    meta = {str(r["name"]): r for r in meta_rows}
    target_field = _resolve_image_field(meta, image_field)

    results: list[ImageImportRow] = []
    updated = failed = skipped = 0

    for idx, row in enumerate(manifest_rows, start=1):
        match_value = row.get("match", "")
        filename = row.get("filename", "")
        row_field = row.get("image_field") or target_field
        try:
            if not match_value or not filename:
                skipped += 1
                results.append(
                    ImageImportRow(
                        row_index=idx,
                        match_value=match_value,
                        filename=filename,
                        ok=True,
                        action="skip",
                        error="empty match or filename",
                    )
                )
                continue
            blob = zip_images.get(filename)
            if blob is None:
                blob = zip_images.get(f"images/{filename}")
            if blob is None:
                raise ValueError(f"image {filename!r} not found in ZIP")
            field_name = _resolve_image_field(meta, row_field)
            record_id = _find_record_id(client, model, match_value, match_field)
            if record_id is None:
                raise ValueError(f"No record matching {match_field}={match_value!r}")
            prepared, _mime = _prepare_image_bytes(blob)
            b64 = base64.b64encode(prepared).decode("ascii")
            if dry_run:
                updated += 1
                results.append(
                    ImageImportRow(
                        row_index=idx,
                        match_value=match_value,
                        filename=filename,
                        ok=True,
                        record_id=record_id,
                        action="write",
                        bytes_in=len(blob),
                        bytes_out=len(prepared),
                    )
                )
            else:
                client.execute_kw(model, "write", [[record_id], {field_name: b64}])
                updated += 1
                results.append(
                    ImageImportRow(
                        row_index=idx,
                        match_value=match_value,
                        filename=filename,
                        ok=True,
                        record_id=record_id,
                        action="write",
                        bytes_in=len(blob),
                        bytes_out=len(prepared),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            results.append(
                ImageImportRow(
                    row_index=idx,
                    match_value=match_value,
                    filename=filename,
                    ok=False,
                    error=str(exc),
                )
            )

    message = (
        f"{'Dry-run' if dry_run else 'Commit'}: {updated} updated, {failed} failed, {skipped} skipped"
    )
    return ImageImportResult(
        ok=failed == 0,
        updated=updated,
        failed=failed,
        skipped=skipped,
        message=message,
        results=results,
    )


def parse_image_upload(manifest_csv: bytes, zip_bytes: bytes) -> tuple[list[dict[str, str]], str, str, MatchMode, dict[str, bytes]]:
    rows, image_field, match_field, match_mode = parse_manifest_csv(manifest_csv)
    images = _load_zip_images(zip_bytes)
    return rows, image_field, match_field, match_mode, images
