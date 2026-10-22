"""Hosting / edition honesty helpers for capability probes (mastery M1)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "0.0.0.0", "host.docker.internal", "::1"})


HOSTING_CHOICES = ("online", "odoo_sh", "self_hosted")


def hosting_hint_from_url(
    url: str | None, server_version: str | None = None, saved: str | None = None
) -> str:
    """Saved choice wins; else server version (saas~ = Online); else the URL.

    Heuristic hosting tier for operator honesty (not a hard security boundary).

    Returns: online | odoo_sh | self_hosted | unknown
    """
    if saved in HOSTING_CHOICES:
        return str(saved)
    if server_version and "saas" in str(server_version).lower():
        return "online"
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
    if host == "odoo.sh" or host.endswith(".odoo.sh") or "odoo.sh" in host or host.endswith(".dev.odoo.com"):
        return "odoo_sh"
    # Odoo Online SaaS databases are typically <db>.odoo.com
    if host == "odoo.com" or host.endswith(".odoo.com"):
        return "online"
    return "self_hosted"


def hosting_operator_message(hosting_hint: str, *, edition: str) -> str:
    parts: list[str] = []
    if hosting_hint == "online":
        parts.append(
            "Hosting looks like Odoo Online: metadata customization and data/XML "
            "module import are OK; custom Python modules cannot be installed on Online — "
            "export install_mode=data or use Odoo.sh / self-host for custom-code Python."
        )
    elif hosting_hint == "odoo_sh":
        parts.append(
            "Hosting looks like Odoo.sh: Git/filesystem module install and staging "
            "branches are first-class; use matching-major sandbox before publish."
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


def python_modules_allowed(hosting_hint: str) -> bool:
    """Backward-compatible shim — delegates to tier_matrix (lazy import)."""
    from app.tier_matrix import python_modules_allowed as matrix_python_modules_allowed

    return matrix_python_modules_allowed(hosting_hint)


def online_option_a_python_blocked(hosting_hint: str) -> bool:
    """True when this host cannot install custom-code Python modules."""
    return hosting_hint == "online" or not python_modules_allowed(hosting_hint)


def online_python_promote_block(*, hosting_hint: str | None = None) -> dict[str, Any]:
    """Honest block payload for Online + Python custom code promote.

    Reuses tier_gating / class-stamp alternatives — do not fork copy.
    """
    from app.ai_class_stamp import LANE_COPY, online_python_block_alternatives
    from app.tier_gating import online_python_promote_gating

    callout = online_python_promote_gating()
    alts = online_python_block_alternatives()
    return {
        "blocked": True,
        "hosting_hint": hosting_hint or "online",
        "delivery_lane": "online_metadata",
        "delivery_lane_copy": LANE_COPY["online_metadata"],
        "module_lane_copy": LANE_COPY["module_sh_or_self"],
        "connector_lane_copy": LANE_COPY["external_connector"],
        "title": callout.title,
        "why": callout.why,
        "alternatives": list(alts),
        "gating": callout.to_dict(),
        "promote_human": True,
        "message": (
            f"{callout.why} Alternatives: (1) {alts[0]} (2) {alts[1]} (3) {alts[2]}"
        ),
    }


def connection_hosting(conn: Any) -> str:
    """Effective hosting for a saved connection (saved choice, version, then URL)."""
    return hosting_hint_from_url(
        getattr(conn, "url", None),
        getattr(conn, "server_version", None),
        getattr(conn, "hosting", None),
    )
