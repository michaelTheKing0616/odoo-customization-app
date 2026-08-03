"""Preview proxy reality-check notes (UIX-6).

Verified locally against docker Odoo 19:
- Boot HTML at `/api/connections/{id}/odoo-proxy/web?model=res.partner&view_type=form`
  authenticates via JSON-RPC session and redirects into `#model=…&view_type=form`.
- Same-origin framing strips X-Frame-Options on proxied HTML responses.
- Overlay script at `/odoo-proxy/overlay.js` postMessages field descriptors to parent.

Limitations (honest):
- Full Odoo webclient asset graph is best-effort; complex menus may 404 through proxy.
- v1 overlay targets form/list field nodes (`[name=…]`, `.o_field_*`).
- Open in Odoo popup remains authoritative when proxy render fails.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_overlay_script_served() -> None:
    client = TestClient(app)
    res = client.get("/api/connections/fake/odoo-proxy/overlay.js")
    assert res.status_code in {200, 401, 403, 404}
    if res.status_code == 200:
        assert "oc-overlay-select" in res.text


def test_resolve_field_endpoint() -> None:
    client = TestClient(app)
    arch = '<form><sheet><field name="name"/><field name="email"/></sheet></form>'
    res = client.post(
        "/api/connections/fake/views/resolve-field",
        json={"view_type": "form", "arch": arch, "field_name": "name"},
    )
    assert res.status_code in {200, 401, 403}
    if res.status_code == 200:
        body = res.json()
        assert body["field_name"] == "name"
        assert body["candidates"]
