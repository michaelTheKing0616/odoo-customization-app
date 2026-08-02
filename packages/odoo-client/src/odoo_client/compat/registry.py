"""Major → capability registry. M3: 16–19; GA = 17 + 18 + 19."""

from __future__ import annotations

from odoo_client.compat.capabilities import (
    ODOO_16_CAPABILITIES,
    ODOO_17_CAPABILITIES,
    ODOO_18_CAPABILITIES,
    ODOO_19_CAPABILITIES,
    UnsupportedOdooMajorError,
    VersionCapabilities,
)

_REGISTRY: dict[int, VersionCapabilities] = {
    19: VersionCapabilities(
        major=19,
        edition="community",
        enabled=ODOO_19_CAPABILITIES,
        ga=True,
    ),
    18: VersionCapabilities(
        major=18,
        edition="community",
        enabled=ODOO_18_CAPABILITIES,
        ga=True,
    ),
    17: VersionCapabilities(
        major=17,
        edition="community",
        enabled=ODOO_17_CAPABILITIES,
        ga=True,
    ),
    16: VersionCapabilities(
        major=16,
        edition="community",
        enabled=ODOO_16_CAPABILITIES,
        ga=False,
    ),
}


def supported_majors() -> frozenset[int]:
    return frozenset(_REGISTRY.keys())


def ga_majors() -> frozenset[int]:
    return frozenset(m for m, caps in _REGISTRY.items() if caps.ga)


def for_major(major: int, *, edition: str = "community") -> VersionCapabilities:
    """Return capabilities for a major, or fail closed."""
    caps = _REGISTRY.get(major)
    if caps is None:
        raise UnsupportedOdooMajorError(
            f"Odoo major {major} is not supported. "
            f"Supported majors: {sorted(_REGISTRY)} "
            f"(GA: {sorted(ga_majors())}). "
            "See MULTI_VERSION_ODOO_PLAN.md / MEMORY.md."
        )
    if edition != caps.edition and edition != "unknown":
        return VersionCapabilities(
            major=caps.major,
            edition=edition,
            enabled=caps.enabled,
            ga=caps.ga,
        )
    return caps


def parse_major(server_version: str) -> int:
    """Normalize ``server_version`` like ``19.0+e`` / ``19.0`` → major int."""
    text = (server_version or "").strip()
    if not text:
        raise UnsupportedOdooMajorError("Empty server_version")
    core = text.split("+", 1)[0].split("-", 1)[0]
    major_s = core.split(".", 1)[0]
    if not major_s.isdigit():
        raise UnsupportedOdooMajorError(f"Cannot parse major from {server_version!r}")
    return int(major_s)
