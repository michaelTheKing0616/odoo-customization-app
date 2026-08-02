"""Same-origin Odoo preview proxy — strips X-Frame-Options for Designer iframe.

Authenticates with the connection credentials, then proxies HTML/assets under
``/api/connections/{id}/odoo-proxy/...`` so the browser can embed Odoo without
third-party framing blocks. Not a full SPA rewrite; best-effort for form/list
deep links.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.crypto import decrypt_secret
from app.db import get_db
from app.odoo_service import get_connection_or_404

router = APIRouter(prefix="/connections/{connection_id}", tags=["preview-proxy"])

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}


def _opener_for_connection(row: Any) -> tuple[Any, str]:
    """Return (urllib opener with session cookie, base_url)."""
    base = row.url.rstrip("/")
    password = decrypt_secret(row.secret_encrypted)
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {
                "db": row.db_name,
                "login": row.username,
                "password": password,
            },
        }
    ).encode()
    req = Request(
        f"{base}/web/session/authenticate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Odoo auth failed: {exc}") from exc
    if not body.get("result", {}).get("uid"):
        raise HTTPException(status_code=502, detail="Odoo authentication rejected")
    return opener, base


def _rewrite_html(html: str, proxy_prefix: str, odoo_base: str) -> str:
    """Rewrite absolute Odoo URLs to the proxy prefix (best-effort)."""
    # Remove frame blockers in meta / keep link/script under proxy when absolute
    html = re.sub(
        r'<meta[^>]+http-equiv=["\']X-Frame-Options["\'][^>]*>',
        "",
        html,
        flags=re.I,
    )
    # Absolute same-host paths → proxy
    parsed = urlparse(odoo_base)
    host_root = f"{parsed.scheme}://{parsed.netloc}"
    html = html.replace(f'href="{host_root}/', f'href="{proxy_prefix}/')
    html = html.replace(f"href='{host_root}/", f"href='{proxy_prefix}/")
    html = html.replace(f'src="{host_root}/', f'src="{proxy_prefix}/')
    html = html.replace(f"src='{host_root}/", f"src='{proxy_prefix}/")
    html = html.replace('href="/', f'href="{proxy_prefix}/')
    html = html.replace("href='/", f"href='{proxy_prefix}/")
    html = html.replace('src="/', f'src="{proxy_prefix}/')
    html = html.replace("src='/", f"src='{proxy_prefix}/")
    return html


@router.get("/preview/frame")
def preview_frame(
    connection_id: str,
    model: str,
    view_type: str = "form",
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redirect into the proxy at an Odoo deep link for the model."""
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    path = f"/web#model={model}&view_type={view_type}"
    # Fragment isn't sent to server — use query that Odoo webclient understands via hash
    # Serve a tiny HTML bootstrapping page that sets location.hash after proxy load
    return RedirectResponse(
        url=f"/api/connections/{connection_id}/odoo-proxy/web?model={model}&view_type={view_type}",
        status_code=302,
    )


@router.api_route("/odoo-proxy/{path:path}", methods=["GET", "POST"])
async def odoo_proxy(
    connection_id: str,
    path: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        opener, base = _opener_for_connection(row)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Special boot for /web?model=&view_type=
    if path.rstrip("/") == "web" and request.method == "GET":
        model = request.query_params.get("model")
        view_type = request.query_params.get("view_type", "form")
        if model:
            proxy_prefix = f"/api/connections/{connection_id}/odoo-proxy"
            boot = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Odoo preview</title></head>
<body>
<p style="font-family:system-ui;padding:1rem">Loading Odoo preview…</p>
<script>
  location.replace({json.dumps(proxy_prefix + "/web")} + "#model=" +
    encodeURIComponent({json.dumps(model)}) + "&view_type=" +
    encodeURIComponent({json.dumps(view_type)});
</script>
</body></html>"""
            return HTMLResponse(
                boot,
                headers={
                    "Content-Security-Policy": "frame-ancestors *",
                    "X-Frame-Options": "ALLOWALL",
                },
            )

    target = urljoin(base + "/", path)
    # SSRF guard: only proxy to the connection's own Odoo host.
    base_host = urlparse(base).netloc
    target_host = urlparse(target).netloc
    if target_host != base_host or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Proxy path rejected")
    if request.url.query and "model=" not in (request.url.query or ""):
        target = f"{target}?{request.url.query}"
    elif request.url.query and path.rstrip("/") != "web":
        target = f"{target}?{request.url.query}"

    body = await request.body() if request.method == "POST" else None
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "connection"}
    }
    headers.pop("cookie", None)
    req = Request(target, data=body if body else None, headers=headers, method=request.method)
    try:
        with opener.open(req, timeout=60) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            out_headers = {
                k: v
                for k, v in resp.headers.items()
                if k.lower() not in _HOP_BY_HOP
                and k.lower() not in {"x-frame-options", "content-security-policy"}
            }
            out_headers["Content-Security-Policy"] = "frame-ancestors *"
            out_headers["Cache-Control"] = "no-store"
            # Intentionally omit X-Frame-Options so Designer iframe can embed
            if "text/html" in content_type:
                html = raw.decode("utf-8", errors="replace")
                proxy_prefix = f"/api/connections/{connection_id}/odoo-proxy"
                html = _rewrite_html(html, proxy_prefix, base)
                # Soft banner: proxy is best-effort; Open-in-Odoo is authoritative
                banner = (
                    '<div id="oc-preview-banner" style="position:sticky;top:0;z-index:9999;'
                    "background:#0f1a16;color:#9fd6c0;font:12px system-ui;padding:6px 10px;"
                    'border-bottom:1px solid #2a433b">'
                    "Preview proxy (best-effort). Prefer Open in Odoo for authoritative UI."
                    "</div>"
                )
                if "<body" in html.lower():
                    html = re.sub(
                        r"(<body[^>]*>)",
                        r"\1" + banner,
                        html,
                        count=1,
                        flags=re.I,
                    )
                else:
                    html = banner + html
                return HTMLResponse(html, headers=out_headers, status_code=resp.status)
            return Response(content=raw, media_type=content_type, headers=out_headers, status_code=resp.status)
    except HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail=str(exc.reason)) from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=str(exc.reason)) from exc
