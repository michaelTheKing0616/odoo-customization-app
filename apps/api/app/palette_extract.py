"""Extract Odoo instance brand colors from compiled web CSS (CMP-3 §20)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

_CSS_VAR_PATTERNS = (
    re.compile(r"--o-brand-primary\s*:\s*([^;\s}]+)", re.I),
    re.compile(r"--o-color-primary\s*:\s*([^;\s}]+)", re.I),
    re.compile(r"--primary\s*:\s*([^;\s}]+)", re.I),
    re.compile(r"--o-brand-odoo\s*:\s*([^;\s}]+)", re.I),
)
_ACCENT_PATTERNS = (
    re.compile(r"--o-brand-secondary\s*:\s*([^;\s}]+)", re.I),
    re.compile(r"--o-color-success\s*:\s*([^;\s}]+)", re.I),
)


def parse_theme_from_css(css: str) -> dict[str, str]:
    """Parse primary/accent CSS variables from compiled Odoo web CSS."""
    primary: str | None = None
    accent: str | None = None
    for pat in _CSS_VAR_PATTERNS:
        m = pat.search(css)
        if m:
            primary = m.group(1).strip().strip("'\"")
            break
    for pat in _ACCENT_PATTERNS:
        m = pat.search(css)
        if m:
            accent = m.group(1).strip().strip("'\"")
            break
    out: dict[str, str] = {}
    if primary:
        out["primary"] = primary
    if accent:
        out["accent"] = accent
    return out


def theme_to_preview_vars(theme: dict[str, str]) -> dict[str, str]:
    """Map extracted theme to designer preview CSS variables (scoped only)."""
    primary = theme.get("primary")
    if not primary:
        return {}
    return {
        "--odoo-primary": primary,
        "--odoo-primary-hover": primary,
        "--odoo-statusbar": primary,
    }


def extract_theme_from_opener(opener: Any, base_url: str, *, timeout: int = 30) -> dict[str, Any]:
    """Fetch web login HTML, follow first web.assets stylesheet, parse CSS."""
    from urllib.request import Request

    base = base_url.rstrip("/")
    html = ""
    try:
        req = Request(f"{base}/web/login", headers={"User-Agent": "OdooCustomizer/1.0"})
        with opener.open(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "theme": {}, "preview_vars": {}}

    css_urls: list[str] = []
    for m in re.finditer(r"""href=["']([^"']+\.css[^"']*)["']""", html, re.I):
        href = m.group(1)
        if "web.assets" in href or "/assets/" in href:
            css_urls.append(urljoin(base + "/", href))
    if not css_urls:
        return {"ok": False, "error": "no web.assets css link in login HTML", "theme": {}, "preview_vars": {}}

    css_blob = ""
    for url in css_urls[:3]:
        try:
            req = Request(url, headers={"User-Agent": "OdooCustomizer/1.0"})
            with opener.open(req, timeout=timeout) as resp:
                css_blob += resp.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue

    if not css_blob:
        return {"ok": False, "error": "css fetch failed", "theme": {}, "preview_vars": {}}

    theme = parse_theme_from_css(css_blob)
    preview_vars = theme_to_preview_vars(theme)
    return {
        "ok": bool(preview_vars),
        "theme": theme,
        "preview_vars": preview_vars,
        "css_bytes": len(css_blob),
    }


def serialize_theme(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)
