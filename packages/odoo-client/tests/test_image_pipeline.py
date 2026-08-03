"""CMP-6 image pipeline unit tests."""

from __future__ import annotations

from odoo_client.image_pipeline import (
    arch_field_name_for_image,
    guess_image_role,
    image_field_xml,
    is_image_field,
    name_suggests_image,
)


def test_name_suggests_image() -> None:
    assert name_suggests_image("x_photo")
    assert name_suggests_image("x_avatar")
    assert not name_suggests_image("x_notes")


def test_arch_picks_small_variant_for_list() -> None:
    names = {"x_photo", "x_photo_128", "x_photo_256"}
    assert arch_field_name_for_image("x_photo", view_type="list", field_names=names) == "x_photo_128"


def test_avatar_xml_includes_oe_avatar() -> None:
    xml = image_field_xml(
        "x_photo",
        view_type="form",
        field_names={"x_photo", "x_photo_128"},
        role="avatar",
    )
    assert 'class="oe_avatar"' in xml
    assert 'widget="image"' in xml


def test_guess_image_role_partner() -> None:
    assert guess_image_role("x_staff", "x_photo") == "avatar"


def test_is_image_field_with_widget() -> None:
    assert is_image_field({"name": "x_doc", "ttype": "binary", "widget": "image"})
