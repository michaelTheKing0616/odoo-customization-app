"""Live grounding for the App Studio understand step.

Edition, hosting, installed / missing apps and Odoo Online limits for the
connection the brief targets. Set per request (contextvar) by the router, read
by classify_generation, understand and the LLM prompts. No connection means
"unknown": copy stays edition-neutral (never assumes Community).
"""

from __future__ import annotations

import contextvars
import re
from dataclasses import dataclass
from typing import Any

ONLINE_LIMITS = (
    "Odoo Online cannot install custom Python modules. Fields, views, menus, "
    "automations and data files are fine; Python pieces go to the custom-code path "
    "(module, sandbox, you publish on Odoo.sh or self-hosted)."
)


@dataclass(frozen=True)
class StudioGrounding:
    edition: str = "unknown"  # enterprise | community | unknown
    hosting: str = "unknown"  # online | odoo_sh | self_hosted | local | unknown
    server_version: str = ""
    apps_installed: tuple[str, ...] = ()
    apps_missing: tuple[str, ...] = ()

    @property
    def online(self) -> bool:
        return self.hosting == "online"

    def as_dict(self) -> dict[str, Any]:
        return {
            "edition": self.edition,
            "hosting": self.hosting,
            "server_version": self.server_version,
            "apps_installed": list(self.apps_installed),
            "apps_missing": list(self.apps_missing),
            "online_limits": ONLINE_LIMITS if self.online else "",
        }

    @classmethod
    def from_dict(cls, raw: Any) -> StudioGrounding | None:
        if not isinstance(raw, dict):
            return None
        return cls(
            edition=str(raw.get("edition") or "unknown"),
            hosting=str(raw.get("hosting") or "unknown"),
            server_version=str(raw.get("server_version") or ""),
            apps_installed=tuple(str(x) for x in raw.get("apps_installed") or []),
            apps_missing=tuple(str(x) for x in raw.get("apps_missing") or []),
        )


_GROUNDING: contextvars.ContextVar[StudioGrounding | None] = contextvars.ContextVar(
    "studio_grounding", default=None
)


def set_grounding(value: StudioGrounding | None) -> contextvars.Token:
    return _GROUNDING.set(value)


def reset_grounding(token: contextvars.Token) -> None:
    _GROUNDING.reset(token)


def current_grounding() -> StudioGrounding | None:
    return _GROUNDING.get()


def grounding_from_connection(conn: Any, plan: dict[str, Any] | None = None) -> StudioGrounding | None:
    """Edition via detect_edition (version + URL + installed modules), hosting via URL."""
    if conn is None:
        return None
    from app.hosting import hosting_hint_from_url
    from app.tier_matrix import detect_edition

    # Installed modules are not cached on the connection row; the brief's
    # integration plan carries installed / missing apps instead.
    installed_modules = None
    url = str(getattr(conn, "url", "") or "")
    version = str(getattr(conn, "server_version", "") or "")
    try:
        edition = detect_edition(version, installed_modules, url=url)
    except Exception:  # noqa: BLE001
        edition = "unknown"
    installed: list[str] = []
    missing: list[str] = []
    for item in (plan or {}).get("integrations") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("app_label") or item.get("module") or "").strip()
        if not label:
            continue
        (installed if item.get("status") == "available" else missing).append(label)
    return StudioGrounding(
        edition=str(edition or "unknown"),
        hosting=str(hosting_hint_from_url(url, version, getattr(conn, "hosting", None)) or "unknown"),
        server_version=version,
        apps_installed=tuple(dict.fromkeys(installed)),
        apps_missing=tuple(dict.fromkeys(missing)),
    )


def edition_label(g: StudioGrounding | None = None) -> str:
    g = g if g is not None else current_grounding()
    edition = (g.edition if g else "unknown").lower()
    return {"enterprise": "Enterprise", "community": "Community"}.get(edition, "")


def odoo_phrase(g: StudioGrounding | None = None) -> str:
    label = edition_label(g)
    return f"Odoo {label}" if label else "Odoo"


def stock_apps_phrase(g: StudioGrounding | None = None) -> str:
    label = edition_label(g)
    return f"Stock {label} apps" if label else "Stock apps"


def grounding_prompt_block(g: StudioGrounding | None = None) -> str:
    g = g if g is not None else current_grounding()
    if g is None:
        return ""
    where = {
        "online": "Odoo Online",
        "odoo_sh": "Odoo.sh",
        "self_hosted": "a self-hosted server",
        "local": "a local server",
    }.get(g.hosting, "an unknown host")
    lines = [
        f"Live database: {odoo_phrase(g)} {g.server_version}".rstrip() + f", hosted on {where}."
    ]
    if g.apps_installed:
        lines.append("Installed apps this brief touches: " + ", ".join(g.apps_installed) + ".")
    if g.apps_missing:
        lines.append("Not installed (links wait until installed): " + ", ".join(g.apps_missing) + ".")
    if g.online:
        lines.append(ONLINE_LIMITS)
    return "\n".join(lines)


_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+\S")
_NUMBERED_RE = re.compile(r"(?m)^\s*\d+[.)]\s+\S")
LONG_BRIEF_WORDS = 60


def brief_wants_llm(prompt: str) -> bool:
    """Long or structured briefs get the AI step by default (class-wide)."""
    text = prompt or ""
    if len(re.findall(r"\w+", text)) >= LONG_BRIEF_WORDS:
        return True
    if _HEADING_RE.search(text):
        return True
    return len(_NUMBERED_RE.findall(text)) >= 3


def llm_timeout_for(prompt: str) -> float:
    """20s up to 2k chars, then about +2s per 1k chars, capped at 60s."""
    extra = max(0, len(prompt or "") - 2000) / 450.0
    return round(min(60.0, 20.0 + extra), 1)


def plain_lane_copy(lane: str | None, g: StudioGrounding | None = None) -> str:
    g = g if g is not None else current_grounding()
    lane = str(lane or "")
    if lane == "online_metadata" or (g is not None and g.online and lane != "option_a"):
        return (
            "Delivered as fields, views and menus. Custom Python cannot install on Odoo Online, "
            "so any Python pieces go to the custom-code path."
        )
    if lane in {"option_a", "option_a_module"}:
        return "Delivered as an installable module: built, proved in a sandbox, then published by a person."
    return "Delivered as fields, views and menus on your database."


__all__ = [
    "LONG_BRIEF_WORDS",
    "ONLINE_LIMITS",
    "StudioGrounding",
    "brief_wants_llm",
    "current_grounding",
    "edition_label",
    "grounding_from_connection",
    "grounding_prompt_block",
    "llm_timeout_for",
    "odoo_phrase",
    "plain_lane_copy",
    "reset_grounding",
    "set_grounding",
    "stock_apps_phrase",
]
