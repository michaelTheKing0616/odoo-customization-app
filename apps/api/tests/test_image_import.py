"""CMP-6 bulk image import."""

from __future__ import annotations

import base64
import csv
import io
import zipfile
from typing import Any

import pytest

from app.image_import import (
    _prepare_image_bytes,
    parse_manifest_csv,
    run_image_import,
)


def _tiny_png() -> bytes:
    # 1x1 PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_parse_manifest_csv() -> None:
    csv_text = "match,filename,image_field\nAcme,photo.jpg,x_photo\n"
    rows, field, match_col, mode = parse_manifest_csv(csv_text.encode())
    assert len(rows) == 1
    assert rows[0]["match"] == "Acme"
    assert rows[0]["filename"] == "photo.jpg"
    assert field == "x_photo"
    assert match_col == "match"
    assert mode == "name"


def test_prepare_image_bytes_downscales_and_jpeg() -> None:
    out, mime = _prepare_image_bytes(_tiny_png())
    assert mime == "image/jpeg"
    assert out.startswith(b"\xff\xd8")


class _FakeClient:
    def __init__(self) -> None:
        self.records = {1: {"x_name": "Acme", "x_photo": False}}
        self.writes: list[tuple[int, dict[str, Any]]] = []

    def model_exists(self, model: str) -> bool:
        return model == "x_item"

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        kwargs = kwargs or {}
        if model == "ir.model.fields" and method == "search_read":
            return [
                {"name": "x_name", "ttype": "char"},
                {"name": "x_photo", "ttype": "binary"},
            ]
        if model == "x_item" and method == "search":
            domain = args[0]
            if domain == [("x_name", "=", "Acme")]:
                return [1]
            return []
        if model == "x_item" and method == "write":
            rid, vals = args[0][0], args[1]
            self.writes.append((rid, vals))
            return True
        raise AssertionError(f"unexpected {model}.{method}")


def test_run_image_import_dry_run() -> None:
    client = _FakeClient()
    png = _tiny_png()
    result = run_image_import(
        client,
        model="x_item",
        manifest_rows=[{"match": "Acme", "filename": "photo.jpg", "image_field": "x_photo"}],
        zip_images={"photo.jpg": png},
        image_field="x_photo",
        match_field="x_name",
        dry_run=True,
    )
    assert result.updated == 1
    assert result.failed == 0
    assert not client.writes


def test_run_image_import_commit() -> None:
    client = _FakeClient()
    png = _tiny_png()
    result = run_image_import(
        client,
        model="x_item",
        manifest_rows=[{"match": "Acme", "filename": "photo.jpg", "image_field": "x_photo"}],
        zip_images={"photo.jpg": png},
        image_field="x_photo",
        match_field="x_name",
        dry_run=False,
    )
    assert result.updated == 1
    assert len(client.writes) == 1
    assert "x_photo" in client.writes[0][1]


def test_manifest_missing_columns_raises() -> None:
    with pytest.raises(ValueError, match="manifest CSV needs"):
        parse_manifest_csv(b"only_one_col\nval\n")
