"""Version capability matrix — M3: 16–19 supported; 17+18+19 GA."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CapabilityId(str, Enum):
    """Feature switches probed by client/UI."""

    RELATED_WRITE_DOTTED_PATH = "related_write_dotted_path"
    OBJECT_WRITE_UPDATE_PATH = "object_write_update_path"
    OBJECT_CREATE_CRUD_MODEL = "object_create_crud_model"
    BASE_AUTOMATION_SAFE_TRIGGERS = "base_automation_safe_triggers"
    VIEW_INJECT_INHERIT = "view_inject_inherit"
    VIEW_INJECT_MUTATE = "view_inject_mutate"
    SMART_BUTTON_INHERIT_BOX = "smart_button_inherit_box"
    LIST_AS_LIST_TYPE = "list_as_list_type"
    LIST_TREE_FALLBACK = "list_tree_fallback"


# Full current product set (18 / 19).
_FULL_SAFE: frozenset[CapabilityId] = frozenset(
    {
        CapabilityId.RELATED_WRITE_DOTTED_PATH,
        CapabilityId.OBJECT_WRITE_UPDATE_PATH,
        CapabilityId.OBJECT_CREATE_CRUD_MODEL,
        CapabilityId.BASE_AUTOMATION_SAFE_TRIGGERS,
        CapabilityId.VIEW_INJECT_INHERIT,
        CapabilityId.VIEW_INJECT_MUTATE,
        CapabilityId.SMART_BUTTON_INHERIT_BOX,
        CapabilityId.LIST_AS_LIST_TYPE,
        CapabilityId.LIST_TREE_FALLBACK,
    }
)

ODOO_19_CAPABILITIES = _FULL_SAFE
ODOO_18_CAPABILITIES = _FULL_SAFE

# Odoo 17: update_path-era object_write; ir.ui.view.type still expects ``tree`` (not ``list``).
ODOO_17_CAPABILITIES: frozenset[CapabilityId] = frozenset(
    {
        CapabilityId.RELATED_WRITE_DOTTED_PATH,
        CapabilityId.OBJECT_WRITE_UPDATE_PATH,
        CapabilityId.OBJECT_CREATE_CRUD_MODEL,
        CapabilityId.BASE_AUTOMATION_SAFE_TRIGGERS,
        CapabilityId.VIEW_INJECT_INHERIT,
        CapabilityId.VIEW_INJECT_MUTATE,
        CapabilityId.SMART_BUTTON_INHERIT_BOX,
        CapabilityId.LIST_TREE_FALLBACK,
    }
)

# Odoo 16: no dotted update_path claim; tree-primary views; inherit inject + simple autos.
ODOO_16_CAPABILITIES: frozenset[CapabilityId] = frozenset(
    {
        CapabilityId.OBJECT_CREATE_CRUD_MODEL,
        CapabilityId.BASE_AUTOMATION_SAFE_TRIGGERS,
        CapabilityId.VIEW_INJECT_INHERIT,
        CapabilityId.VIEW_INJECT_MUTATE,
        CapabilityId.SMART_BUTTON_INHERIT_BOX,
        CapabilityId.LIST_TREE_FALLBACK,
        # OBJECT_WRITE_UPDATE_PATH / RELATED_WRITE omitted — encode uses 17+ update_path
    }
)


@dataclass(frozen=True)
class VersionCapabilities:
    """Immutable capability set for one major."""

    major: int
    edition: str = "community"
    enabled: frozenset[CapabilityId] = field(default_factory=frozenset)
    ga: bool = False

    def supports(self, capability: CapabilityId) -> bool:
        return capability in self.enabled

    def require(self, capability: CapabilityId) -> None:
        if not self.supports(capability):
            raise UnsupportedCapabilityError(
                f"Capability {capability.value!r} is not available on "
                f"Odoo {self.major} ({self.edition})"
            )


class UnsupportedCapabilityError(Exception):
    """Raised when a feature is not in the version capability set."""


class UnsupportedOdooMajorError(Exception):
    """Raised when the major is not registered in the compat registry."""
