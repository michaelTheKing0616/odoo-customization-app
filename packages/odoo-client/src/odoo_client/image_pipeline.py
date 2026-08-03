"""Compendium §14 image field conventions — variants, arch picks, avatar heuristic."""

from __future__ import annotations

import re
from typing import Any, Literal

ImageRole = Literal["avatar", "content"]
ViewSurface = Literal["form", "list", "kanban", "tree"]

IMAGE_VARIANT_SIZES: tuple[int, ...] = (128, 256)
MAX_IMAGE_EDGE = 1920
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

_IMAGE_NAME_RE = re.compile(
    r"(^x_(image|photo|picture|avatar|logo|thumbnail)|_(image|photo|avatar|128|256)$|image_|photo_)",
    re.I,
)


def name_suggests_image(field_name: str, *, widget: str | None = None) -> bool:
    if widget == "image":
        return True
    return bool(_IMAGE_NAME_RE.search(field_name or ""))


def is_image_field(
    field: dict[str, Any] | None,
    *,
    widget: str | None = None,
) -> bool:
    if not field:
        return False
    ttype = str(field.get("ttype") or "")
    if ttype not in {"binary", "image"}:
        return False
    if field.get("is_image") is True:
        return True
    name = str(field.get("name") or "")
    w = widget or field.get("widget")
    return name_suggests_image(name, widget=str(w) if w else None)


def variant_field_name(base: str, size: int) -> str:
    if base.endswith(f"_{size}"):
        return base
    return f"{base}_{size}"


def guess_image_role(model_name: str, field_name: str) -> ImageRole:
    low_model = (model_name or "").lower()
    low_field = (field_name or "").lower()
    if any(k in low_model for k in ("staff", "employee", "user", "partner", "contact")):
        return "avatar"
    if any(k in low_field for k in ("avatar", "profile", "photo", "picture", "logo")):
        return "avatar"
    return "content"


def models_using_compact_views(
    *,
    views: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
) -> set[str]:
    out: set[str] = set()
    for v in views or []:
        if not isinstance(v, dict):
            continue
        vtype = str(v.get("type") or "")
        model = str(v.get("model") or "")
        if model and vtype in {"list", "tree", "kanban"}:
            out.add(model)
    for a in actions or []:
        if not isinstance(a, dict):
            continue
        model = str(a.get("model") or "")
        mode = str(a.get("view_mode") or "")
        if model and any(x in mode for x in ("list", "tree", "kanban")):
            out.add(model)
    return out


def arch_field_name_for_image(
    base_name: str,
    *,
    view_type: ViewSurface,
    field_names: set[str] | frozenset[str],
) -> str:
    """Pick base (form) or small variant (list/kanban) when variants exist."""
    if view_type in {"list", "tree", "kanban"}:
        for size in IMAGE_VARIANT_SIZES:
            cand = variant_field_name(base_name, size)
            if cand in field_names:
                return cand
    return base_name


def image_field_xml(
    base_name: str,
    *,
    view_type: ViewSurface,
    field_names: set[str] | frozenset[str],
    role: ImageRole | None = None,
    string: str | None = None,
) -> str:
    name = arch_field_name_for_image(base_name, view_type=view_type, field_names=field_names)
    attrs: list[str] = [f'name="{name}"', 'widget="image"']
    if role == "avatar":
        attrs.append('class="oe_avatar"')
    if string:
        attrs.append(f'string="{string}"')
    return f"<field {' '.join(attrs)}/>"
