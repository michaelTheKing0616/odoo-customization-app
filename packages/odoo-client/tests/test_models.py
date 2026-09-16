"""Unit tests that do not require a live Odoo instance."""

import pytest
from pydantic import ValidationError

from odoo_client.models import CreateFieldRequest, CreateModelRequest, FieldType


def test_normalize_odoo_base_url_strips_web_ui_path() -> None:
    from odoo_client.models import ConnectionConfig, normalize_odoo_base_url

    assert (
        normalize_odoo_base_url("https://experiment-company.odoo.com/odoo")
        == "https://experiment-company.odoo.com"
    )
    assert (
        normalize_odoo_base_url("https://experiment-company.odoo.com/odoo/")
        == "https://experiment-company.odoo.com"
    )
    assert normalize_odoo_base_url("http://127.0.0.1:8069/web") == "http://127.0.0.1:8069"
    assert normalize_odoo_base_url("http://127.0.0.1:8069") == "http://127.0.0.1:8069"
    cfg = ConnectionConfig(
        url="https://experiment-company.odoo.com/odoo",
        db="experiment-company",
        username="admin",
        password="x",
    )
    assert cfg.url == "https://experiment-company.odoo.com"


def test_create_model_requires_x_prefix() -> None:
    with pytest.raises(ValidationError):
        CreateModelRequest(name="Thing", model="thing")


def test_create_model_accepts_x_prefix() -> None:
    req = CreateModelRequest(name="Thing", model="x_thing")
    assert req.model == "x_thing"


def test_reserved_field_name_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateFieldRequest(
            model="x_thing",
            name="id",
            field_description="ID",
            ttype=FieldType.CHAR,
        )


def test_field_requires_x_prefix() -> None:
    with pytest.raises(ValidationError):
        CreateFieldRequest(
            model="res.partner",
            name="nickname",
            field_description="Nickname",
            ttype=FieldType.CHAR,
        )


def test_field_type_enum() -> None:
    req = CreateFieldRequest(
        model="res.partner",
        name="x_nickname",
        field_description="Nickname",
        ttype=FieldType.CHAR,
    )
    assert req.ttype == FieldType.CHAR


def test_many2one_requires_relation() -> None:
    req = CreateFieldRequest(
        model="x_thing",
        name="x_partner_id",
        field_description="Partner",
        ttype=FieldType.MANY2ONE,
    )
    with pytest.raises(ValueError, match="relation"):
        req.validate_type_requirements()


def test_update_access_request_booleans() -> None:
    from odoo_client.security import UpdateAccessRightRequest

    req = UpdateAccessRightRequest(perm_read=True, perm_write=False, active=True)
    assert req.perm_read is True
    assert req.perm_write is False
    assert req.active is True


def test_related_requires_path() -> None:
    req = CreateFieldRequest(
        model="x_thing",
        name="x_partner_name",
        field_description="Partner Name",
        ttype=FieldType.RELATED,
    )
    with pytest.raises(ValueError, match="related"):
        req.validate_type_requirements()


def test_related_and_monetary_attrs() -> None:
    related = CreateFieldRequest(
        model="x_thing",
        name="x_partner_name",
        field_description="Partner Name",
        ttype=FieldType.CHAR,
        related="partner_id.name",
    )
    related.validate_type_requirements()
    assert related.related == "partner_id.name"

    deprecated = CreateFieldRequest(
        model="x_thing",
        name="x_partner_name2",
        field_description="Partner Name",
        ttype=FieldType.RELATED,
        related="partner_id.name",
    )
    deprecated.validate_type_requirements()

    monetary = CreateFieldRequest(
        model="x_thing",
        name="x_amount",
        field_description="Amount",
        ttype=FieldType.MONETARY,
        currency_field="x_currency_id",
    )
    monetary.validate_type_requirements()
    assert monetary.currency_field == "x_currency_id"


def test_normalize_odoo_online_deep_links_and_fragments() -> None:
    from odoo_client.models import (
        detect_hosting_kind,
        normalize_odoo_base_url,
        suggest_db_name_from_url,
    )

    assert (
        normalize_odoo_base_url("https://acme.odoo.com/odoo/discuss?debug=1#action=mail")
        == "https://acme.odoo.com"
    )
    assert normalize_odoo_base_url("https://acme.odoo.com/web/login") == "https://acme.odoo.com"
    assert detect_hosting_kind("https://acme.odoo.com/odoo") == "online"
    assert detect_hosting_kind("https://proj.odoo.sh") == "odoo_sh"
    assert detect_hosting_kind("http://127.0.0.1:8069") == "self_hosted"
    assert suggest_db_name_from_url("https://acme.odoo.com/odoo") == "acme"


def test_parse_major_accepts_minor_and_enterprise_suffix() -> None:
    from odoo_client.compat.registry import parse_major

    assert parse_major("19.4") == 19
    assert parse_major("19.4+e") == 19
    assert parse_major("18.0-20241201") == 18
    assert parse_major("saas~19.4+e") == 19
