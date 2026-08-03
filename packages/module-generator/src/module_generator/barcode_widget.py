"""CMP-9 exported OWL barcode scan field widget (original add-on, not native Odoo)."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

BARCODE_README = """# Barcode scan field widget (Odoo Custom add-on)

This module ships **our original** OWL field widget `x_barcode_scan` — it is **not** a native
Odoo Enterprise/Community widget.

## Usage

On any char field in form views:

```xml
<field name="x_barcode" widget="x_barcode_scan"/>
```

## Scanning

1. **Fast path:** when the browser exposes `BarcodeDetector` (Chrome/Android), the widget uses
   it directly on the camera stream.
2. **Fallback:** otherwise the bundled **ZXing** library in `static/lib/zxing-browser.min.js`
   decodes 1D/2D codes from the same stream (Safari, Firefox, desktop).

Operators can always type or paste values manually if camera access is denied.

## Licenses

| Component | License |
|-----------|---------|
| Widget code in this module (`static/src/js`, `static/src/xml`) | LGPL-3 (same as module) |
| `static/lib/zxing-browser.min.js` | Apache-2.0 — see `static/lib/ZXING-NOTICE.txt` |

The in-app scanner in Odoo Custom (web app) also uses **@zxing/browser** (Apache-2.0).
Upstream: https://github.com/zxing-js/browser
"""

ZXING_NOTICE = """ZXing for JS (@zxing/browser bundled build)
Copyright contributors to https://github.com/zxing-js/browser and https://github.com/zxing-js/library

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

X_BARCODE_SCAN_JS = """/** @odoo-module **/
/** LGPL-3 — Odoo Custom generated barcode scan char field (not native Odoo). */
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { useState } from "@odoo/owl";

const SCAN_TIMEOUT_MS = 15000;
const DETECTOR_FORMATS = ["qr_code", "code_128", "ean_13", "ean_8", "upc_a", "upc_e"];

async function openCameraVideo() {
    const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
    });
    const video = document.createElement("video");
    video.playsInline = true;
    video.muted = true;
    video.srcObject = stream;
    await video.play();
    return { stream, video };
}

async function scanWithBarcodeDetector(video) {
    const detector = new BarcodeDetector({ formats: DETECTOR_FORMATS });
    const deadline = Date.now() + SCAN_TIMEOUT_MS;
    while (Date.now() < deadline) {
        const codes = await detector.detect(video);
        if (codes.length) {
            return codes[0].rawValue;
        }
        await new Promise((resolve) => setTimeout(resolve, 200));
    }
    return null;
}

async function scanWithZxing(video) {
    const Reader = window.ZXingBrowser?.BrowserMultiFormatReader;
    if (!Reader) {
        throw new Error("ZXing scanner library failed to load.");
    }
    const reader = new Reader();
    try {
        const result = await reader.decodeOnceFromVideoElement(video);
        return result?.getText?.() || null;
    } finally {
        reader.reset?.();
    }
}

export class XBarcodeScanCharField extends CharField {
    setup() {
        super.setup();
        this.scanState = useState({ busy: false, error: null });
    }

    async onScanClick() {
        this.scanState.error = null;
        if (!navigator.mediaDevices?.getUserMedia) {
            this.scanState.error =
                "Camera unavailable — type or paste the value, or use Odoo Custom in-app scanner.";
            return;
        }
        let stream = null;
        try {
            this.scanState.busy = true;
            const opened = await openCameraVideo();
            stream = opened.stream;
            const { video } = opened;
            let value = null;
            if ("BarcodeDetector" in window) {
                try {
                    value = await scanWithBarcodeDetector(video);
                } catch {
                    value = null;
                }
            }
            if (!value) {
                value = await scanWithZxing(video);
            }
            if (value) {
                await this.props.record.update({ [this.props.name]: value });
            } else {
                this.scanState.error = "No barcode detected — try again or enter manually.";
            }
        } catch (err) {
            this.scanState.error = err?.message || String(err);
        } finally {
            stream?.getTracks().forEach((track) => track.stop());
            this.scanState.busy = false;
        }
    }
}

XBarcodeScanCharField.template = "x_barcode_scan.CharField";

registry.category("fields").add("x_barcode_scan", {
    ...charField,
    component: XBarcodeScanCharField,
});
"""

X_BARCODE_SCAN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="x_barcode_scan.CharField" t-inherit="web.CharField" t-inherit-mode="extension" owl="1">
        <xpath expr="//input" position="after">
            <button type="button" class="btn btn-secondary ms-1 o_x_barcode_scan_btn"
                    t-on-click="onScanClick" t-att-disabled="scanState.busy">
                <i class="fa fa-barcode"/> Scan
            </button>
            <span t-if="scanState.error" class="text-danger small ms-1" t-esc="scanState.error"/>
        </xpath>
    </t>
</templates>
"""


def _vendor_zxing_bundle() -> str:
    path = files("module_generator.vendor").joinpath("zxing-browser.min.js")
    return path.read_text(encoding="utf-8")


def emit_barcode_scan_widget_files(
    spec: Any,
    files: dict[str, str],
) -> None:
    """Add static assets + README when include_barcode_scan_widget is set."""
    if not getattr(spec, "include_barcode_scan_widget", False):
        return
    root = spec.technical_name
    files[f"{root}/static/lib/zxing-browser.min.js"] = _vendor_zxing_bundle()
    files[f"{root}/static/lib/ZXING-NOTICE.txt"] = ZXING_NOTICE
    files[f"{root}/static/src/js/x_barcode_scan_field.js"] = X_BARCODE_SCAN_JS
    files[f"{root}/static/src/xml/x_barcode_scan_field.xml"] = X_BARCODE_SCAN_XML
    files[f"{root}/README_BARCODE.md"] = BARCODE_README
