"""Serialize odoo-client capability matrix for API responses (M1)."""

from __future__ import annotations

from typing import Any

from odoo_client.compat import (
    CapabilityId,
    UnsupportedOdooMajorError,
    VersionCapabilities,
    for_major,
    parse_major,
)

from app.hosting import (
    hosting_hint_from_url,
    hosting_operator_message,
    python_modules_allowed,
)
from app.schemas import CapabilityMatrixOut, UnsupportedCapabilityOut

# Operator-facing labels (kept in API layer so UI stays thin).
CAPABILITY_LABELS: dict[str, str] = {
    CapabilityId.RELATED_WRITE_DOTTED_PATH.value: (
        "Related write (dotted update_path)"
    ),
    CapabilityId.OBJECT_WRITE_UPDATE_PATH.value: "Update field (object_write)",
    CapabilityId.OBJECT_CREATE_CRUD_MODEL.value: "Create record (object_create)",
    CapabilityId.BASE_AUTOMATION_SAFE_TRIGGERS.value: "Safe automation triggers",
    CapabilityId.VIEW_INJECT_INHERIT.value: "View inject via inherit",
    CapabilityId.VIEW_INJECT_MUTATE.value: "View inject via mutate (advanced)",
    CapabilityId.SMART_BUTTON_INHERIT_BOX.value: "Smart buttons (button_box inherit)",
    CapabilityId.LIST_AS_LIST_TYPE.value: "List views as type=list",
    CapabilityId.LIST_TREE_FALLBACK.value: "List↔tree view type fallback",
}


def _edition_hint(server_version: str) -> str:
    # Odoo Enterprise often appends +e; Community is plain.
    if "+e" in server_version.lower() or "enterprise" in server_version.lower():
        return "enterprise"
    return "community"


def capabilities_from_version(
    server_version: str | None,
    *,
    url: str | None = None,
    installed_modules: list[str] | None = None,
) -> CapabilityMatrixOut | None:
    """Build matrix from stored/probed server_version. None if version unknown."""
    if not server_version:
        return None
    hosting = hosting_hint_from_url(url)
    py_ok = python_modules_allowed(hosting)
    mods = list(installed_modules or [])
    warnings: list[str] = []
    if not py_ok:
        warnings.append(
            "Custom Python module install is not available on Odoo Online — "
            "use data/XML export or move to Odoo.sh / self-host for Option A."
        )
    if any(m in {"web_studio", "studio_customization"} for m in mods):
        warnings.append(
            "Studio-related modules detected on the database — we still only use "
            "public ORM/RPC; Studio UI/source is never used."
        )
    try:
        major = parse_major(server_version)
        caps = for_major(major, edition=_edition_hint(server_version))
    except UnsupportedOdooMajorError:
        edition = _edition_hint(server_version)
        host_msg = hosting_operator_message(hosting, edition=edition)
        return CapabilityMatrixOut(
            major=None,
            edition=edition,
            server_version=server_version,
            supported=[],
            unsupported=[
                UnsupportedCapabilityOut(
                    id=cid.value,
                    label=CAPABILITY_LABELS.get(cid.value, cid.value),
                    reason=(
                        f"Odoo major from {server_version!r} is not in the support "
                        "registry (GA: 19+18+17; experimental: 16)."
                    ),
                )
                for cid in CapabilityId
            ],
            ga=False,
            message=(
                f"Unsupported Odoo version {server_version!r}. "
                "Supported: Community 19+18+17 (GA), 16 (experimental)."
                + (f" {host_msg}" if host_msg else "")
            ),
            hosting_hint=hosting,
            python_module_install=py_ok,
            installed_modules_sample=mods[:40],
            warnings=warnings,
        )
    return _matrix_from_caps(
        caps,
        server_version,
        hosting_hint=hosting,
        python_module_install=py_ok,
        installed_modules=mods,
        warnings=warnings,
    )


def sample_installed_modules(client: Any, *, limit: int = 40) -> list[str]:
    """Return sorted technical names of installed modules (best-effort)."""
    try:
        rows = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("state", "=", "installed")]],
            {"fields": ["name"], "limit": limit, "order": "name"},
        )
        return sorted({str(r["name"]) for r in rows if r.get("name")})
    except Exception:  # noqa: BLE001 — probe must not fail connections
        return []


def _matrix_from_caps(
    caps: VersionCapabilities,
    server_version: str,
    *,
    hosting_hint: str = "unknown",
    python_module_install: bool = True,
    installed_modules: list[str] | None = None,
    warnings: list[str] | None = None,
) -> CapabilityMatrixOut:
    supported = sorted(c.value for c in caps.enabled)
    unsupported: list[UnsupportedCapabilityOut] = []
    for cid in CapabilityId:
        if cid not in caps.enabled:
            unsupported.append(
                UnsupportedCapabilityOut(
                    id=cid.value,
                    label=CAPABILITY_LABELS.get(cid.value, cid.value),
                    reason=f"Not available on Odoo {caps.major} ({caps.edition})",
                )
            )
    ga = bool(getattr(caps, "ga", caps.major == 19))
    message = (
        f"Odoo {caps.major} {caps.edition.title()} — "
        f"{len(supported)} capabilities enabled"
        + (" (GA)" if ga else " (experimental / limited)")
    )
    host_msg = hosting_operator_message(hosting_hint, edition=caps.edition)
    if host_msg:
        message += f". {host_msg}"
    return CapabilityMatrixOut(
        major=caps.major,
        edition=caps.edition,
        server_version=server_version,
        supported=supported,
        unsupported=unsupported,
        ga=ga,
        message=message,
        hosting_hint=hosting_hint,
        python_module_install=python_module_install,
        installed_modules_sample=list(installed_modules or [])[:40],
        warnings=list(warnings or []),
    )
