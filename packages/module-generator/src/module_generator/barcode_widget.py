"""CMP-9 exported OWL barcode scan field widget (original add-on, not native Odoo)."""

from __future__ import annotations

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

The widget uses the browser **BarcodeDetector** API when available (Chrome/Android). On
unsupported browsers, operators can type or paste values manually.

## Third-party licenses

The in-app scanner in Odoo Custom (web app) uses **@zxing/browser** (Apache-2.0). If you
bundle a local copy of ZXing in `static/lib/` for offline parity, retain the Apache-2.0
NOTICE per https://github.com/zxing-js/browser .

Our widget code in this module is LGPL-3 (same as the module license).
"""

X_BARCODE_SCAN_JS = """/** @odoo-module **/
/** LGPL-3 — Odoo Custom generated barcode scan char field (not native Odoo). */
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { useState } from "@odoo/owl";

export class XBarcodeScanCharField extends CharField {
    setup() {
        super.setup();
        this.scanState = useState({ busy: false, error: null });
    }

    async onScanClick() {
        this.scanState.error = null;
        if (!("BarcodeDetector" in window)) {
            this.scanState.error =
                "Camera barcode API unavailable — type or paste the value, or use Odoo Custom in-app scanner.";
            return;
        }
        try {
            this.scanState.busy = true;
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" },
            });
            const video = document.createElement("video");
            video.srcObject = stream;
            await video.play();
            const detector = new BarcodeDetector({
                formats: ["qr_code", "code_128", "ean_13", "ean_8", "upc_a", "upc_e"],
            });
            const deadline = Date.now() + 15000;
            let value = null;
            while (Date.now() < deadline && !value) {
                const codes = await detector.detect(video);
                if (codes.length) {
                    value = codes[0].rawValue;
                } else {
                    await new Promise((r) => setTimeout(r, 200));
                }
            }
            stream.getTracks().forEach((t) => t.stop());
            if (value) {
                await this.props.record.update({ [this.props.name]: value });
            } else {
                this.scanState.error = "No barcode detected — try again or enter manually.";
            }
        } catch (err) {
            this.scanState.error = err?.message || String(err);
        } finally {
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


def emit_barcode_scan_widget_files(
    spec: Any,
    files: dict[str, str],
) -> None:
    """Add static assets + README when include_barcode_scan_widget is set."""
    if not getattr(spec, "include_barcode_scan_widget", False):
        return
    root = spec.technical_name
    files[f"{root}/static/src/js/x_barcode_scan_field.js"] = X_BARCODE_SCAN_JS
    files[f"{root}/static/src/xml/x_barcode_scan_field.xml"] = X_BARCODE_SCAN_XML
    files[f"{root}/README_BARCODE.md"] = BARCODE_README
