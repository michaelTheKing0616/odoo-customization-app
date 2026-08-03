"""CMP-6 ai_enrich image arch emission."""

from __future__ import annotations

from app.ai_enrich import _build_form_arch, _build_kanban_arch, _build_list_arch


def _fields():
    return [
        {"name": "x_name", "ttype": "char", "string": "Name"},
        {"name": "x_photo", "ttype": "binary", "string": "Photo", "is_image": True, "image_role": "avatar"},
        {"name": "x_photo_128", "ttype": "binary", "string": "Photo 128", "is_image": True},
        {"name": "x_status", "ttype": "selection", "string": "Status", "selection": "[('draft','Draft'),('done','Done')]"},
    ]


def test_list_arch_uses_small_image_variant() -> None:
    arch = _build_list_arch("Staff", _fields())
    assert 'name="x_photo_128"' in arch
    assert 'widget="image"' in arch


def test_form_arch_uses_base_image_with_avatar_class() -> None:
    arch = _build_form_arch("Staff", _fields())
    assert 'name="x_photo"' in arch
    assert 'class="oe_avatar"' in arch


def test_kanban_arch_includes_image_variant() -> None:
    arch = _build_kanban_arch(_fields(), model_name="x_staff")
    assert arch is not None
    assert "x_photo_128" in arch or 'name="x_photo"' in arch
