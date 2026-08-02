"""Compat package — version capabilities + 19 adapters (M0)."""

from odoo_client.compat.capabilities import (
    CapabilityId,
    UnsupportedCapabilityError,
    UnsupportedOdooMajorError,
    VersionCapabilities,
)
from odoo_client.compat.registry import (
    for_major,
    ga_majors,
    parse_major,
    supported_majors,
)

__all__ = [
    "CapabilityId",
    "UnsupportedCapabilityError",
    "UnsupportedOdooMajorError",
    "VersionCapabilities",
    "for_major",
    "ga_majors",
    "parse_major",
    "supported_majors",
]
