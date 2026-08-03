"""CMP-9 barcode widget module emission."""

from __future__ import annotations

from module_generator import ModuleSpec, render_module_files


def test_barcode_widget_assets_in_manifest_and_static() -> None:
    spec = ModuleSpec(
        technical_name="scan_demo",
        display_name="Scan Demo",
        include_barcode_scan_widget=True,
    )
    files = render_module_files(spec)
    manifest = files["scan_demo/__manifest__.py"]
    assert "x_barcode_scan_field.js" in manifest
    assert "web.assets_backend" in manifest
    assert "scan_demo/static/src/js/x_barcode_scan_field.js" in files
    assert "x_barcode_scan" in files["scan_demo/static/src/js/x_barcode_scan_field.js"]
    assert "scan_demo/README_BARCODE.md" in files
    assert "Apache-2" in files["scan_demo/README_BARCODE.md"]
