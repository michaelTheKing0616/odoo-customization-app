"""Unit tests for safe form-bound action models."""

from odoo_client.actions import (
    CreateMailPostServerAction,
    CreateNextActivityServerAction,
    CreateRelatedCountField,
    CreateRelatedWindowAction,
    CreateSmartButtonBundle,
    CreateUpdateFieldServerAction,
    assert_safe_server_state,
)
from odoo_client.automation import MailPostAction
import pytest


def test_assert_safe_blocks_code() -> None:
    with pytest.raises(ValueError, match="blocked"):
        assert_safe_server_state("code")
    assert_safe_server_state("object_write")
    assert_safe_server_state("next_activity")
    assert_safe_server_state("mail_post")


def test_create_update_field_request() -> None:
    req = CreateUpdateFieldServerAction(
        name="Mark Available",
        model="x_lib_book",
        field_name="x_status",
        value="available",
    )
    assert req.field_name == "x_status"


def test_related_window_request() -> None:
    req = CreateRelatedWindowAction(
        name="Loans",
        source_model="x_lib_book",
        target_model="x_lib_loan",
        relation_field="x_book_id",
    )
    assert req.relation_field == "x_book_id"


def test_activity_mail_and_smart_models() -> None:
    act = CreateNextActivityServerAction(
        name="Follow up",
        model="x_lib_book",
        activity_type_id=1,
    )
    assert act.summary == "Follow up"
    mail = CreateMailPostServerAction(
        name="Notify",
        model="x_lib_book",
        mail_post_method="note",
    )
    assert mail.mail_post_method == "note"
    count = CreateRelatedCountField(
        model="x_lib_book",
        name="x_loan_count",
        one2many_field="x_loan_ids",
    )
    assert count.name == "x_loan_count"
    bundle = CreateSmartButtonBundle(
        name="Loans",
        source_model="x_lib_book",
        target_model="x_lib_loan",
        relation_field="x_book_id",
        one2many_field="x_loan_ids",
        create_count_field=True,
    )
    assert bundle.create_count_field is True
    auto_mail = MailPostAction(mail_post_method="email", subject="Hi")
    assert auto_mail.kind == "mail_post"
