"""Unit tests that do not require a live Odoo instance."""

import pytest
from pydantic import ValidationError

from odoo_client.models import CreateFieldRequest, CreateModelRequest, FieldType


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
