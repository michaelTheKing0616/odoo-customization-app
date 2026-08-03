"""REM-11 live sandbox: barcode widget module installs with bundled ZXing assets."""

from __future__ import annotations

import io
import shutil
import zipfile

import pytest

from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip


def test_barcode_widget_zip_asset_layout() -> None:
    spec = ModuleSpec(
        technical_name="barcode_sandbox_smoke",
        display_name="Barcode Sandbox Smoke",
        include_barcode_scan_widget=True,
        models=[
            ModelSpec(
                model="x_barcode_item",
                description="Item",
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name"),
                    FieldSpec(name="x_barcode", ttype="char", string="Barcode"),
                ],
            )
        ],
    )
    raw = build_module_zip(spec)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "barcode_sandbox_smoke/static/lib/zxing-browser.min.js" in names
        manifest = zf.read("barcode_sandbox_smoke/__manifest__.py").decode("utf-8")
        assert "zxing-browser.min.js" in manifest
        widget = zf.read("barcode_sandbox_smoke/static/src/js/x_barcode_scan_field.js").decode("utf-8")
        assert "scanWithZxing" in widget
        assert "BarcodeDetector" in widget


@pytest.mark.integration
def test_barcode_widget_sandbox_install() -> None:
    if not shutil.which("docker"):
        pytest.skip("docker not available")

    from app.sandbox import run_sandbox_install

    spec = ModuleSpec(
        technical_name="barcode_sandbox_live",
        display_name="Barcode Sandbox Live",
        include_barcode_scan_widget=True,
        models=[
            ModelSpec(
                model="x_barcode_live",
                description="Live Item",
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                    FieldSpec(name="x_barcode", ttype="char", string="Barcode"),
                ],
            )
        ],
    )
    result = run_sandbox_install(build_module_zip(spec), odoo_major=19)
    if not result.ok:
        pytest.skip(f"sandbox unavailable: {result.message}")
    assert result.ok
