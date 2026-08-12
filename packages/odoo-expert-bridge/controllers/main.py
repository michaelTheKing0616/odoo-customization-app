# Copyright 2026 Odoo Customization Platform
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import html
import json
import urllib.parse
import urllib.request

import werkzeug
from werkzeug.wrappers import Response

from odoo import http
from odoo.http import request


def _html_error(title: str, message: str, *, status: int = 503) -> Response:
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{html.escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem;color:#1a1a1a}}
code{{background:#f4f4f4;padding:.1rem .35rem;border-radius:4px}}</style></head>
<body><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p></body></html>"""
    return Response(body, status=status, mimetype="text/html; charset=utf-8")


def _api_bases(web_base: str, api_base: str | None) -> list[str]:
    bases: list[str] = []
    if api_base:
        bases.append(api_base.rstrip("/"))
    if web_base:
        bases.append(web_base.rstrip("/"))
    for base in list(bases):
        if "localhost" in base or "127.0.0.1" in base:
            bases.append(
                base.replace("localhost", "host.docker.internal").replace(
                    "127.0.0.1", "host.docker.internal"
                )
            )
            bases.append("http://host.docker.internal:8001")
    seen: set[str] = set()
    out: list[str] = []
    for base in bases:
        if base and base not in seen:
            seen.add(base)
            out.append(base)
    return out


def _resolve_connection_id(*, web_base: str, api_base: str | None, odoo_url: str, db_name: str) -> str | None:
    query = urllib.parse.urlencode({"url": odoo_url.rstrip("/"), "db_name": db_name})
    for base in _api_bases(web_base, api_base):
        url = f"{base}/api/connections/resolve/by-instance?{query}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                payload = json.loads(resp.read().decode())
            connection_id = str(payload.get("id") or "").strip()
            if connection_id:
                return connection_id
        except Exception:  # noqa: BLE001 — try next base
            continue
    return None


class ExpertBridgeController(http.Controller):
    @http.route("/odoo-expert-bridge/open", type="http", auth="user")
    def open_expert(self, model=None, res_id=None, **kwargs):
        """Redirect to the customization app Expert panel with optional record context."""
        icp = request.env["ir.config_parameter"].sudo()
        web_base = (icp.get_param("expert_bridge.base_url") or "").rstrip("/")
        api_base = (icp.get_param("expert_bridge.api_base_url") or "").strip() or None
        connection_id = (icp.get_param("expert_bridge.connection_id") or "").strip()

        if not web_base:
            return _html_error(
                "Expert Bridge not configured",
                "Set expert_bridge.base_url (e.g. http://localhost:3000) under Settings → Technical → System Parameters.",
            )

        odoo_url = request.httprequest.url_root.rstrip("/")
        db_name = request.env.cr.dbname

        if not connection_id:
            connection_id = _resolve_connection_id(
                web_base=web_base,
                api_base=api_base,
                odoo_url=odoo_url,
                db_name=db_name,
            ) or ""

        if not connection_id:
            return _html_error(
                "No Customization app connection found",
                f"No saved connection matches {odoo_url} database {db_name}. "
                f"Open {web_base}, add a connection for this Odoo instance, then retry. "
                "Optional: set expert_bridge.connection_id to the UUID from /connections/{id}.",
            )

        path = f"/connections/{werkzeug.urls.url_quote(connection_id)}/builder"
        params = ["expert=1"]
        if model:
            params.append(f"model={werkzeug.urls.url_quote(str(model))}")
        if res_id:
            try:
                params.append(f"res_id={int(res_id)}")
            except (TypeError, ValueError):
                pass
        url = f"{web_base}{path}?{'&'.join(params)}"
        return werkzeug.utils.redirect(url, 302)
