"""Fake T8-OD-DRIFT answers for majors 17, 18, 19, and 20.

This module does not call Odoo. Live Odoo 20 payloads for the six cells that
stay unknown here are in test_odoo20_drift_cells.py.
"""

from __future__ import annotations

import inspect

import pytest

from odoo_client.automation import (
    CreateActivityAction,
    FollowersAction,
    RelatedWriteAction,
    RemoveFollowersAction,
    SmsAction,
    UpdateFieldAction,
    WebhookAction,
)
from odoo_client.client import OdooClient
from odoo_client.compat.adapters import (
    automation_v17,
    automation_v18,
    automation_v19,
    automation_v20,
    views_v17,
    views_v18,
    views_v19,
    views_v20,
)
from odoo_client.compat.capabilities import (
    ODOO_17_CAPABILITIES,
    ODOO_18_CAPABILITIES,
    ODOO_19_CAPABILITIES,
    ODOO_20_CAPABILITIES,
    CapabilityId,
)
from odoo_client.compat.drift import (
    DRIFT_MAJORS,
    DRIFT_ROWS,
    UNKNOWN,
    UnknownDriftRow,
    drift_answer,
    fake_drift_reply,
)
from odoo_client.field_attrs import emit_field_modifiers

# Literals the repo already states. A wrong known cell fails this table.
# tree_vs_list on 20 is compared to views_v20 instead of restating that test.
_EXPECTED: dict[tuple[str, int], str] = {
    ("view_modifiers", 17): "direct attributes",
    ("view_modifiers", 18): "direct attributes",
    ("view_modifiers", 19): "direct attributes",
    ("view_modifiers", 20): "direct attributes",
    ("tree_vs_list", 17): "tree",
    ("tree_vs_list", 18): "list",
    ("tree_vs_list", 19): "list",
    ("chatter", 17): "<chatter/> sibling",
    ("chatter", 18): "<chatter/> sibling",
    ("chatter", 19): "<chatter/> sibling",
    ("chatter", 20): "<chatter/> sibling",
    ("get_view", 17): "get_views",
    ("get_view", 18): "get_views",
    ("get_view", 19): "get_views",
    ("get_view", 20): "get_views",
    ("translations", 17): "context lang reads",
    ("translations", 18): "context lang reads",
    ("translations", 19): "context lang reads; without ir.translation",
    ("translations", 20): UNKNOWN,
    ("server_action_states", 17): "same safe-subset encode as v19",
    ("server_action_states", 18): "encoding shared for the safe subset",
    ("server_action_states", 19): (
        "object_write, next_activity, object_create, mail_post, "
        "webhook, sms, followers, remove_followers"
    ),
    ("server_action_states", 20): "re-exports v19 encode",
}

_UNKNOWN_ROWS = (
    "kanban",
    "name_get",
    "company_dependent_fields",
    "selection_storage",
    "mail_template_syntax",
)

_COVERED_ELSEWHERE = (
    "read_group",
    "name_search",
    "groups_id",
    "automation_split",
    "cron_numbercall",
    "accounting_stock_renames",
    "external_api",
    "ir_access",
)


@pytest.mark.parametrize("major", DRIFT_MAJORS)
@pytest.mark.parametrize("row", DRIFT_ROWS)
def test_fake_drift_reply(row: str, major: int) -> None:
    reply = fake_drift_reply(row, major)
    assert reply["probed"] is False
    assert reply["row"] == row
    assert reply["major"] == major
    assert reply["answer"] == drift_answer(row, major)
    assert isinstance(reply["answer"], str)
    assert reply["answer"] != ""


@pytest.mark.parametrize(
    ("row", "major"),
    sorted(_EXPECTED),
    ids=[f"{row}-m{major}" for row, major in sorted(_EXPECTED)],
)
def test_known_or_explicit_unknown_cell(row: str, major: int) -> None:
    assert drift_answer(row, major) == _EXPECTED[(row, major)]


@pytest.mark.parametrize("major", DRIFT_MAJORS)
@pytest.mark.parametrize("row", _UNKNOWN_ROWS)
def test_unstated_cell_stays_unknown(row: str, major: int) -> None:
    assert drift_answer(row, major) == UNKNOWN


def test_covered_rows_are_not_restated() -> None:
    assert set(_COVERED_ELSEWHERE).isdisjoint(DRIFT_ROWS)
    for row in _COVERED_ELSEWHERE:
        with pytest.raises(UnknownDriftRow):
            drift_answer(row, 19)


def test_view_modifiers_emit_direct_attributes() -> None:
    for major in DRIFT_MAJORS:
        assert drift_answer("view_modifiers", major) == "direct attributes"
        emitted = emit_field_modifiers(
            major=major, required=True, readonly=True, invisible=True
        )
        assert "attrs" not in emitted
        assert emitted == {"required": "1", "readonly": "1", "invisible": "1"}


def test_tree_vs_list_follows_view_adapters() -> None:
    assert drift_answer("tree_vs_list", 17) == "tree"
    assert views_v17.list_arch_root("list") == "tree"
    assert views_v17.list_arch_root("tree") == "tree"
    assert CapabilityId.LIST_AS_LIST_TYPE not in ODOO_17_CAPABILITIES

    assert drift_answer("tree_vs_list", 18) == "list"
    assert views_v18.list_arch_root("list") == "list"
    assert CapabilityId.LIST_AS_LIST_TYPE in ODOO_18_CAPABILITIES

    assert drift_answer("tree_vs_list", 19) == "list"
    assert views_v19.list_arch_root("list") == "list"
    assert CapabilityId.LIST_AS_LIST_TYPE in ODOO_19_CAPABILITIES

    # Major 20 list-vs-tree literal stays in test_odoo20_version_table.
    assert drift_answer("tree_vs_list", 20) == views_v20.list_arch_root("list")
    assert drift_answer("tree_vs_list", 20) == views_v20.list_arch_root("tree")
    assert CapabilityId.LIST_AS_LIST_TYPE in ODOO_20_CAPABILITIES


def test_get_view_cell_matches_client_get_views() -> None:
    source = inspect.getsource(OdooClient.get_combined_view_arch)
    assert "get_views" in source
    for major in DRIFT_MAJORS:
        assert drift_answer("get_view", major) == "get_views"


def test_server_action_state_cells_match_adapters() -> None:
    assert drift_answer("server_action_states", 17) == "same safe-subset encode as v19"
    assert drift_answer("server_action_states", 18) == "encoding shared for the safe subset"
    assert drift_answer("server_action_states", 20) == "re-exports v19 encode"
    assert (
        automation_v17.encode_update_field_server_vals
        is automation_v19.encode_update_field_server_vals
    )
    assert (
        automation_v18.encode_update_field_server_vals
        is automation_v19.encode_update_field_server_vals
    )
    assert (
        automation_v20.encode_update_field_server_vals
        is automation_v19.encode_update_field_server_vals
    )

    action = UpdateFieldAction(field_name="x_note", value="hi")
    states = {
        automation_v19.encode_update_field_server_vals(
            name="n", model_id=1, action=action
        )["state"],
        automation_v19.encode_related_write_server_vals(
            name="n",
            model_id=1,
            action=RelatedWriteAction(
                relation_field="x_partner_id", field_name="name", value="a"
            ),
        )["state"],
        automation_v19.encode_create_activity_server_vals(
            name="n",
            model_id=1,
            action=CreateActivityAction(activity_type_id=1, summary="s"),
            activity_user_field_name="create_uid",
        )["state"],
        automation_v19.encode_create_record_server_vals(
            name="n",
            model_id=1,
            target_model="res.partner",
            target_model_id=2,
            field_values={"name": "A"},
        )["state"],
        automation_v19.encode_mail_post_server_vals(
            name="n", model_id=1, template_id=1, mail_post_method="comment"
        )["state"],
        automation_v19.encode_webhook_server_vals(
            name="n",
            model_id=1,
            action=WebhookAction(webhook_url="https://example.com/h"),
        )["state"],
        automation_v19.encode_sms_server_vals(
            name="n", model_id=1, action=SmsAction(body="hi"), sms_template_id=1
        )["state"],
        automation_v19.encode_followers_server_vals(
            name="n",
            model_id=1,
            action=FollowersAction(partner_ids=[1], followers_type="specific"),
        )["state"],
        automation_v19.encode_remove_followers_server_vals(
            name="n", model_id=1, action=RemoveFollowersAction(partner_ids=[1])
        )["state"],
    }
    cell = drift_answer("server_action_states", 19)
    assert set(cell.split(", ")) == states


_LIVE_TIP_20 = frozenset(
    {
        "kanban",
        "name_get",
        "company_dependent_fields",
        "selection_storage",
        "mail_template_syntax",
        "translations",
    }
)


@pytest.mark.parametrize("major", DRIFT_MAJORS)
@pytest.mark.parametrize("row", DRIFT_ROWS)
def test_live_drift_unrun(row: str, major: int) -> None:
    if major == 20 and row in _LIVE_TIP_20:
        pytest.skip("live Odoo 20 payload is test_odoo20_drift_cells")
    pytest.skip("live nightly unrun; no Odoo major was probed")


def test_major_outside_checklist_is_refused() -> None:
    with pytest.raises(ValueError, match="17"):
        drift_answer("kanban", 16)
