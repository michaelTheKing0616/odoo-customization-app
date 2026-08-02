"""Hosting / edition honesty helpers for capability probes (mastery M1)."""

from __future__ import annotations

from urllib.parse import urlparse

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "0.0.0.0", "host.docker.internal", "::1"})


def hosting_hint_from_url(url: str | None) -> str:
    """Heuristic hosting tier for operator honesty (not a hard security boundary).

    Returns: online | odoo_sh | self_hosted | unknown
    """
    if not url or not str(url).strip():
        return "unknown"
    raw = str(url).strip()
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    host = (parsed.hostname or "").lower()
    if not host:
        return "unknown"
    if host in LOCAL_HOSTS or host.endswith(".local"):
        return "self_hosted"
    # Odoo.sh build/platform hostnames
    if host == "odoo.sh" or host.endswith(".odoo.sh") or "odoo.sh" in host:
        return "odoo_sh"
    # Odoo Online SaaS databases are typically <db>.odoo.com
    if host == "odoo.com" or host.endswith(".odoo.com"):
        return "online"
    return "self_hosted"


def python_modules_allowed(hosting_hint: str) -> bool:
    """Whether custom Python module install is expected to work on this tier."""
    if hosting_hint == "online":
        return False
    if hosting_hint in {"odoo_sh", "self_hosted"}:
        return True
    return True  # unknown: allow attempt; promote path still validates


def hosting_operator_message(hosting_hint: str, *, edition: str) -> str:
    parts: list[str] = []
    if hosting_hint == "online":
        parts.append(
            "Hosting looks like Odoo Online: metadata customization and data/XML "
            "module import are OK; custom Python modules cannot be installed on Online — "
            "export install_mode=data or use Odoo.sh / self-host for Option A Python."
        )
    elif hosting_hint == "odoo_sh":
        parts.append(
            "Hosting looks like Odoo.sh: Git/filesystem module install and staging "
            "branches are first-class; use matching-major sandbox before promote."
        )
    elif hosting_hint == "self_hosted":
        parts.append(
            "Hosting looks self-hosted / VPS: sandbox → filesystem or data promote is available."
        )
    if edition == "enterprise":
        parts.append(
            "Enterprise edition detected — metadata customization via public ORM only; "
            "Studio/`web_studio` source is never used."
        )
    return " ".join(parts)
