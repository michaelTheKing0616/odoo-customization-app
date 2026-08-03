"""CMP-9 barcode widget module emission."""

from __future__ import annotations

import io
import zipfile

from module_generator import ModuleSpec, build_module_zip, render_module_files


def test_barcode_widget_assets_in_manifest_and_static() -> None:
    spec = ModuleSpec(
        technical_name="scan_demo",
        display_name="Scan Demo",
        include_barcode_scan_widget=True,
    )
    files = render_module_files(spec)
    manifest = files["scan_demo/__manifest__.py"]
    assert "x_barcode_scan_field.js" in manifest
    assert "zxing-browser.min.js" in manifest
    assert manifest.index("zxing-browser.min.js") < manifest.index("x_barcode_scan_field.js")
    assert "web.assets_backend" in manifest
    assert "scan_demo/static/src/js/x_barcode_scan_field.js" in files
    assert "scan_demo/static/lib/zxing-browser.min.js" in files
    assert "scan_demo/static/lib/ZXING-NOTICE.txt" in files
    js = files["scan_demo/static/src/js/x_barcode_scan_field.js"]
    assert "x_barcode_scan" in js
    assert "BarcodeDetector" in js
    assert "ZXingBrowser" in js
    assert "decodeOnceFromVideoElement" in js
    zxing = files["scan_demo/static/lib/zxing-browser.min.js"]
    assert "BrowserMultiFormatReader" in zxing
    assert len(zxing) > 100_000
    assert "scan_demo/README_BARCODE.md" in files
    readme = files["scan_demo/README_BARCODE.md"]
    assert "Apache-2.0" in readme
    assert "static/lib/zxing-browser.min.js" in readme
    assert "if you bundle" not in readme.lower()


def test_barcode_widget_zip_contains_lib_and_widget() -> None:
    spec = ModuleSpec(
        technical_name="scan_zip",
        display_name="Scan Zip",
        include_barcode_scan_widget=True,
    )
    raw = build_module_zip(spec)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "scan_zip/static/lib/zxing-browser.min.js" in names
        assert "scan_zip/static/lib/ZXING-NOTICE.txt" in names
        assert "scan_zip/static/src/js/x_barcode_scan_field.js" in names
        manifest = zf.read("scan_zip/__manifest__.py").decode("utf-8")
        assert "zxing-browser.min.js" in manifest
        widget_js = zf.read("scan_zip/static/src/js/x_barcode_scan_field.js").decode("utf-8")
        assert "scanWithZxing" in widget_js
