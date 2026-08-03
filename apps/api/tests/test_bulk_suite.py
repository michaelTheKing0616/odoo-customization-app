"""Unit tests for Bulk Suite BLK-1 (discovery + run engine)."""

from __future__ import annotations

from typing import Any

import pytest
from odoo_client.client import OdooClientError

from app.bulk_suite.discovery import classify_buttons, discover_buttons_from_arch, parse_object_buttons
from app.bulk_suite.domain_util import DomainParseError, parse_domain
from app.bulk_suite.transitions import (
    BulkSuiteError,
    discover_transitions,
    invalidate_discovery_cache,
    resolve_record_ids,
    run_bulk_transition,
)

SAMPLE_WORKFLOW_ARCH = """
<form>
  <header>
    <field name="x_status" widget="statusbar"/>
    <button name="action_confirm" type="object" string="Confirm"/>
    <button name="action_cancel" type="object" string="Cancel"/>
  </header>
  <sheet>
    <field name="x_name"/>
    <button name="open_wizard_lines" type="object" string="Add lines"/>
    <button name="preview_report" type="object" string="Preview"/>
  </sheet>
</form>
"""

WIZARD_ARCH = """
<form>
  <header>
    <button name="action_apply" type="object" string="Apply"/>
    <button name="action_open_wizard" type="object" string="Open wizard"
            context="{'active_id': active_id, 'active_model': active_model}"/>
    <button name="discard" type="object" string="Discard" special="cancel"/>
  </header>
  <field name="state" widget="statusbar"/>
</form>
"""


def test_parse_object_buttons_workflow_arch() -> None:
    raw = parse_object_buttons(SAMPLE_WORKFLOW_ARCH)
    names = {b["name"] for b in raw}
    assert "action_confirm" in names
    assert "open_wizard_lines" in names
    assert raw[0]["in_header"] is True


def test_classify_bulk_safe_vs_wizard() -> None:
    raw = parse_object_buttons(SAMPLE_WORKFLOW_ARCH)
    buttons = classify_buttons(raw, has_state_field=True)
    by_name = {b.name: b for b in buttons}
    assert by_name["action_confirm"].bulk_safe is True
    assert by_name["open_wizard_lines"].bulk_safe is False
    assert by_name["preview_report"].bulk_safe is False


def test_wizard_button_patterns_not_bulk_safe() -> None:
    raw = parse_object_buttons(WIZARD_ARCH)
    buttons = classify_buttons(raw, has_state_field=True)
    by_name = {b.name: b for b in buttons}
    assert by_name["action_apply"].bulk_safe is True
    assert by_name["action_open_wizard"].bulk_safe is False
    assert by_name["discard"].bulk_safe is False


def test_discover_buttons_from_arch_no_state_field() -> None:
    raw = parse_object_buttons(SAMPLE_WORKFLOW_ARCH)
    buttons = classify_buttons(raw, has_state_field=False)
    assert all(not b.bulk_safe for b in buttons)


def test_parse_domain_json_and_literal() -> None:
    assert parse_domain("[]") == []
    assert parse_domain("[('state','=','draft')]") == [("state", "=", "draft")]
    assert parse_domain([("id", "in", [1, 2])]) == [("id", "in", [1, 2])]


def test_parse_domain_invalid() -> None:
    with pytest.raises(DomainParseError):
        parse_domain("not-a-domain")


class _FakeClient:
    def __init__(self, *, batch_fail: bool = False, fail_ids: set[int] | None = None) -> None:
        self.batch_fail = batch_fail
        self.fail_ids = fail_ids or set()
        self.calls: list[tuple] = []
        self._ids = [1, 2, 3]

    def model_exists(self, model: str) -> bool:
        return model == "x_test.order"

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        self.calls.append((model, method, args, kwargs or {}))
        if method == "search":
            return list(self._ids)
        if method == "search_read" and model == "ir.model.fields":
            return [{"name": "x_status"}]
        if method == "search_read" and model == "ir.ui.view":
            return [{"arch": SAMPLE_WORKFLOW_ARCH}]
        if method == "read":
            ids = args[0]
            return [{"id": i, "display_name": f"Rec {i}"} for i in ids]
        if method == "get_views":
            raise OdooClientError("unsupported")
        if method == "action_confirm":
            ids = args[0]
            if self.batch_fail and len(ids) > 1:
                raise RuntimeError("batch failed")
            for rid in ids:
                if int(rid) in self.fail_ids:
                    raise RuntimeError(f"fail id {rid}")
            return True
        raise AssertionError(f"unexpected {model}.{method} {args}")


from odoo_client.client import OdooClientError  # noqa: E402


def test_resolve_record_ids_cap() -> None:
    client = _FakeClient()
    with pytest.raises(BulkSuiteError, match="cap"):
        resolve_record_ids(
            client,  # type: ignore[arg-type]
            model="x_test.order",
            ids=list(range(1, 1002)),
            domain=None,
            cap=1000,
        )


def test_resolve_record_ids_domain_cap() -> None:
    client = _FakeClient()
    client._ids = list(range(1, 1002))  # noqa: SLF001
    with pytest.raises(BulkSuiteError, match="Domain matches"):
        resolve_record_ids(
            client,  # type: ignore[arg-type]
            model="x_test.order",
            ids=None,
            domain=[("id", ">", 0)],
            cap=1000,
        )


def test_dry_run_transition() -> None:
    client = _FakeClient()
    result = run_bulk_transition(
        client,  # type: ignore[arg-type]
        model="x_test.order",
        method="action_confirm",
        record_ids=[1, 2],
        dry_run=True,
    )
    assert result.dry_run
    assert result.total == 2
    assert result.succeeded == 2
    assert not any(c[1] == "action_confirm" for c in client.calls)


def test_batch_success() -> None:
    client = _FakeClient()
    result = run_bulk_transition(
        client,  # type: ignore[arg-type]
        model="x_test.order",
        method="action_confirm",
        record_ids=[1, 2, 3],
        dry_run=False,
    )
    assert result.succeeded == 3
    assert result.failed == 0
    confirm_calls = [c for c in client.calls if c[1] == "action_confirm"]
    assert confirm_calls
    assert confirm_calls[0][2][0] == [1, 2, 3]


def test_batch_fail_per_record_partial() -> None:
    client = _FakeClient(batch_fail=True, fail_ids={2})
    result = run_bulk_transition(
        client,  # type: ignore[arg-type]
        model="x_test.order",
        method="action_confirm",
        record_ids=[1, 2, 3],
        dry_run=False,
    )
    assert result.succeeded == 2
    assert result.failed == 1
    by_id = {r.id: r for r in result.per_record}
    assert by_id[2].ok is False
    assert by_id[1].ok is True
    assert by_id[3].ok is True


def test_discovery_cache_invalidation() -> None:
    invalidate_discovery_cache()
    client = _FakeClient()
    buttons = discover_transitions(
        client,  # type: ignore[arg-type]
        connection_id="conn-1",
        model="x_test.order",
        odoo_version="19.0",
    )
    assert any(b.name == "action_confirm" for b in buttons)
    cached = discover_transitions(
        client,  # type: ignore[arg-type]
        connection_id="conn-1",
        model="x_test.order",
        odoo_version="19.0",
    )
    assert len(cached) == len(buttons)
    invalidate_discovery_cache(connection_id="conn-1")
    discover_transitions(
        client,  # type: ignore[arg-type]
        connection_id="conn-1",
        model="x_test.order",
        odoo_version="19.0",
    )
    view_calls = [c for c in client.calls if c[0] == "ir.ui.view"]
    assert len(view_calls) >= 2


class _MassEditClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        self.calls.append((model, method, args, kwargs or {}))
        if method == "fields_get":
            return {
                "x_label": {"type": "char", "readonly": False},
                "x_status": {
                    "type": "selection",
                    "readonly": False,
                    "selection": [("draft", "Draft"), ("done", "Done")],
                },
                "x_readonly": {"type": "char", "readonly": True},
            }
        if method == "read":
            ids = args[0]
            fields = (kwargs or {}).get("fields") or args[1] if len(args) > 1 else []
            return [
                {"id": i, "display_name": f"R{i}", **{f: f"old-{f}" for f in fields}}
                for i in ids
            ]
        if method == "write":
            return True
        if method == "search":
            return [1, 2]
        raise AssertionError(f"unexpected {model}.{method}")


def test_mass_edit_validation_bad_field() -> None:
    from app.bulk_suite.mass_edit import MassEditValidationError, validate_mass_edit_values

    client = _MassEditClient()
    with pytest.raises(MassEditValidationError, match="Unknown field"):
        validate_mass_edit_values(
            client,  # type: ignore[arg-type]
            model="x_test.item",
            values={"missing": "x"},
        )


def test_mass_edit_validation_bad_selection() -> None:
    from app.bulk_suite.mass_edit import MassEditValidationError, validate_mass_edit_values

    client = _MassEditClient()
    with pytest.raises(MassEditValidationError, match="Invalid selection"):
        validate_mass_edit_values(
            client,  # type: ignore[arg-type]
            model="x_test.item",
            values={"x_status": "nope"},
        )


def test_mass_edit_validation_readonly() -> None:
    from app.bulk_suite.mass_edit import MassEditValidationError, validate_mass_edit_values

    client = _MassEditClient()
    with pytest.raises(MassEditValidationError, match="readonly"):
        validate_mass_edit_values(
            client,  # type: ignore[arg-type]
            model="x_test.item",
            values={"x_readonly": "nope"},
        )


def test_mass_edit_dry_run_preview() -> None:
    from app.bulk_suite.mass_edit import run_mass_edit

    client = _MassEditClient()
    result = run_mass_edit(
        client,  # type: ignore[arg-type]
        model="x_test.item",
        record_ids=[1, 2],
        values={"x_label": "new"},
        dry_run=True,
    )
    assert result.preview
    assert result.preview[0].after["x_label"] == "new"
    assert not any(c[1] == "write" for c in client.calls)


def test_discover_inbound_references() -> None:
    from app.bulk_suite.dedupe import discover_inbound_references

    class _RefClient:
        def model_exists(self, model: str) -> bool:
            return model in {"x_child", "x_parent", "mail.message"}

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.model.fields" and method == "search_read":
                return [
                    {
                        "name": "x_parent_id",
                        "model": "x_child",
                        "ttype": "many2one",
                        "relation": "x_parent",
                    },
                    {
                        "name": "x_tag_ids",
                        "model": "x_child",
                        "ttype": "many2many",
                        "relation": "x_parent",
                    },
                ]
            raise AssertionError(f"unexpected {model}.{method}")

    refs = discover_inbound_references(_RefClient(), "x_parent")  # type: ignore[arg-type]
    assert len(refs) == 2
    assert {r.field for r in refs} == {"x_parent_id", "x_tag_ids"}


def test_scan_duplicates_exact_groups() -> None:
    from app.bulk_suite.dedupe import scan_duplicates

    class _ScanClient:
        def model_exists(self, model: str) -> bool:
            return model == "x_item"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if method == "search_read":
                return [
                    {"id": 1, "display_name": "A1", "x_code": "DUP"},
                    {"id": 2, "display_name": "A2", "x_code": "DUP"},
                    {"id": 3, "display_name": "B1", "x_code": "UNIQ"},
                ]
            raise AssertionError(method)

    result = scan_duplicates(
        _ScanClient(),  # type: ignore[arg-type]
        model="x_item",
        match_fields=["x_code"],
        mode="exact",
    )
    assert len(result.groups) == 1
    assert {r.id for r in result.groups[0].records} == {1, 2}


def test_merge_duplicates_dry_run_counts_relinks() -> None:
    from app.bulk_suite.dedupe import merge_duplicates

    class _MergeClient:
        def model_exists(self, model: str) -> bool:
            return model in {"x_parent", "x_child"}

        def field_exists(self, model: str, name: str) -> bool:
            return False

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.model.fields" and method == "search_read":
                return [
                    {
                        "name": "x_parent_id",
                        "model": "x_child",
                        "ttype": "many2one",
                        "relation": "x_parent",
                    }
                ]
            if method == "search":
                if args and args[0] == [("x_parent_id", "in", [2])]:
                    return [10]
                return []
            raise AssertionError(f"{model}.{method} {args}")

    result = merge_duplicates(
        _MergeClient(),  # type: ignore[arg-type]
        model="x_parent",
        winner_id=1,
        loser_ids=[2],
        dry_run=True,
    )
    assert result.relinks
    assert result.relinks[0].count == 1
    assert not any(
        c[1] == "write"
        for c in getattr(_MergeClient(), "calls", [])
    )


def test_render_cron_description_known_hint() -> None:
    from app.bulk_suite.cron_manager import render_cron_description

    text = render_cron_description(
        {
            "name": "Mail: Email Queue Manager",
            "model_name": "mail.mail",
            "interval_number": 1,
            "interval_type": "hours",
            "active": True,
        }
    )
    assert "Every hour" in text
    assert "process outgoing mail queue" in text


def test_render_cron_description_parses_model_method() -> None:
    from app.bulk_suite.cron_manager import render_cron_description

    text = render_cron_description(
        {
            "name": "Custom job",
            "model_name": "x_blk_wf_item",
            "interval_number": 2,
            "interval_type": "days",
            "code": "model.action_confirm()",
            "active": False,
        }
    )
    assert "Every 2 days" in text
    assert "x_blk_wf_item.action_confirm()" in text
    assert "inactive" in text


def test_run_crons_now_dry_run() -> None:
    from app.bulk_suite.cron_manager import run_crons_now

    class _CronClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.cron" and method == "read":
                return [{"name": "Autovacuum"}]
            raise AssertionError(f"{model}.{method}")

    result = run_crons_now(_CronClient(), cron_ids=[7, 7], dry_run=True)  # type: ignore[arg-type]
    assert result.succeeded == 1
    assert result.run_via == "dry_run"
    assert result.per_record[0].display_name == "Autovacuum"


def test_run_single_cron_fallback_model_method() -> None:
    from app.bulk_suite.cron_manager import run_single_cron

    calls: list[tuple[str, str, list[Any]]] = []

    class _CronClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            calls.append((model, method, args))
            if model == "ir.cron" and method == "method_direct_trigger":
                raise OdooClientError("RPC blocked")
            if model == "ir.cron" and method == "read":
                return [
                    {
                        "name": "Custom",
                        "model_name": "x_blk_wf_item",
                        "code": "model.action_confirm()",
                    }
                ]
            if model == "x_blk_wf_item" and method == "action_confirm":
                return True
            raise AssertionError(f"{model}.{method}")

    via, detail = run_single_cron(_CronClient(), 9, dry_run=False)  # type: ignore[arg-type]
    assert via == "model_method"
    assert detail == "x_blk_wf_item.action_confirm()"
    assert ("x_blk_wf_item", "action_confirm", [[]]) in calls


def test_create_cron_for_existing_method() -> None:
    from app.bulk_suite.cron_manager import create_cron_for_existing_method

    created: dict[str, Any] = {}

    class _CronClient:
        def model_exists(self, model: str) -> bool:
            return model == "x_blk_wf_item"

        def _model_id(self, model: str) -> int:
            return 42

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.cron" and method == "create":
                created.update(args[0])
                return 99
            raise AssertionError(f"{model}.{method}")

    cron_id = create_cron_for_existing_method(
        _CronClient(),  # type: ignore[arg-type]
        name="Confirm drafts nightly",
        model="x_blk_wf_item",
        method="action_confirm",
    )
    assert cron_id == 99
    assert created["code"] == "model.action_confirm()"
    assert created["model_id"] == 42


def test_security_preview_add_and_implied_warning() -> None:
    from app.bulk_suite.security import preview_security_changes

    class _SecClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "res.users" and method == "read":
                return [{"id": 1, "name": "Alice", "login": "alice", "groups_id": [10]}]
            if model == "res.groups" and method == "read":
                if args[0] == [20]:
                    return [
                        {
                            "id": 20,
                            "name": "Sales",
                            "full_name": "Sales / User",
                            "implied_ids": [30],
                        }
                    ]
                return [
                    {"id": 10, "name": "Internal", "full_name": "Internal User"},
                    {"id": 30, "name": "Contact Creation", "full_name": "Contact Creation"},
                ]
            if model == "ir.model.data" and method == "search_read":
                return [{"res_id": 10}]
            raise AssertionError(f"{model}.{method}")

    preview = preview_security_changes(
        _SecClient(),  # type: ignore[arg-type]
        user_ids=[1],
        group_ids=[20],
        mode="add",
    )
    assert preview.users[0].add_groups[0].id == 20
    assert preview.users[0].implied_warnings


def test_security_apply_requires_preview_ack() -> None:
    from app.bulk_suite.security import SecurityValidationError, apply_security_changes

    with pytest.raises(SecurityValidationError, match="preview_acknowledged"):
        apply_security_changes(
            _FakeSecClient(),  # type: ignore[arg-type]
            user_ids=[1],
            group_ids=[20],
            mode="add",
            dry_run=False,
            preview_acknowledged=False,
        )


class _FakeSecClient:
    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        if model == "res.users" and method == "read":
            return [{"id": 1, "name": "Alice", "groups_id": []}]
        if model == "res.groups" and method == "read":
            return [{"id": 20, "name": "Sales", "full_name": "Sales", "implied_ids": []}]
        if model == "ir.model.data" and method == "search_read":
            return []
        raise AssertionError(f"{model}.{method}")


def test_bulk_activities_dry_run() -> None:
    from app.bulk_suite.activities import run_bulk_activities

    class _ActClient:
        def _model_id(self, model: str) -> int:
            return 7

        def model_exists(self, model: str) -> bool:
            return model in {"mail.activity", "x_test", "x_no_activity"}

        def ensure_mail_mixins(self, model: str) -> dict[str, bool]:
            return {"is_mail_thread": False, "is_mail_activity": False}

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if method == "fields_get":
                if model == "x_test":
                    return {"activity_ids": {}, "display_name": {}}
                if model == "x_no_activity":
                    return {"display_name": {}}
            if model == "x_test" and method == "read":
                return [{"id": 1, "display_name": "Row 1"}]
            if model == "mail.activity.type" and method == "read":
                return [{"id": 3, "name": "To Do"}]
            raise AssertionError(f"{model}.{method}")

    from app.bulk_suite.activities import ActivityValidationError, run_bulk_activities

    probe_model = "x_no_activity"
    with pytest.raises(ActivityValidationError):
        run_bulk_activities(
            _ActClient(),  # type: ignore[arg-type]
            model=probe_model,
            record_ids=[1],
            activity_type_id=3,
            summary="Follow up",
            date_deadline="2026-08-10",
            dry_run=True,
        )

    result = run_bulk_activities(
        _ActClient(),  # type: ignore[arg-type]
        model="x_test",
        record_ids=[1],
        activity_type_id=3,
        summary="Follow up",
        date_deadline="2026-08-10",
        dry_run=True,
    )
    assert result.succeeded == 1


def test_portal_grant_requires_email() -> None:
    from app.bulk_suite.portal_access import run_bulk_portal

    class _PortalClient:
        def model_exists(self, model: str) -> bool:
            return model == "portal.wizard"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "res.partner" and method == "read":
                return [
                    {"id": 1, "name": "No Email", "email": False, "user_ids": []},
                    {"id": 2, "name": "Has Email", "email": "a@example.com", "user_ids": []},
                ]
            raise AssertionError(f"{model}.{method}")

    result = run_bulk_portal(
        _PortalClient(),  # type: ignore[arg-type]
        partner_ids=[1, 2],
        action="grant",
        dry_run=True,
    )
    assert result.failed == 1
    assert result.succeeded == 1


def test_recompute_probe_fail_returns_honesty_message() -> None:
    from app.bulk_suite.recompute import run_recompute

    class _RecClient:
        config = type("C", (), {"url": "https://example.odoo.com"})()

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if method == "fields_get":
                return {"x_plain": {"type": "char"}}
            raise AssertionError(f"{model}.{method}")

    result = run_recompute(
        _RecClient(),  # type: ignore[arg-type]
        model="x_test",
        field_name="x_plain",
        record_ids=[1],
        dry_run=False,
    )
    assert result.failed == 1
    assert result.probe is not None
    assert result.probe.honesty_message
    assert "shell access" in result.message


def test_send_message_dry_run_per_record() -> None:
    from app.bulk_suite.send_message import run_bulk_send_message

    posts: list[int] = []

    class _MailClient:
        def model_exists(self, model: str) -> bool:
            return model == "mail.message"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "x_test" and method == "fields_get":
                return {"message_ids": {}, "display_name": {}}
            if model == "x_test" and method == "read":
                return [{"id": i, "display_name": f"R{i}"} for i in args[0]]
            if method == "message_post":
                posts.append(int(args[0][0]))
            raise AssertionError(f"{model}.{method}")

    result = run_bulk_send_message(
        _MailClient(),  # type: ignore[arg-type]
        model="x_test",
        record_ids=[1, 2],
        body="<p>Hi</p>",
        dry_run=True,
    )
    assert result.succeeded == 2
    assert posts == []


def test_orphan_scan_detects_missing_parent() -> None:
    from app.bulk_suite.attachments import scan_orphan_attachments

    class _AttClient:
        def model_exists(self, model: str) -> bool:
            return model == "x_parent"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {f: {} for f in ["name", "res_model", "res_id", "checksum", "file_size"]}
            if model == "ir.attachment" and method == "search_read":
                domain = args[0]
                if domain == ["|", ("res_model", "=", False), ("res_id", "=", 0)]:
                    return []
                return [
                    {
                        "id": 1,
                        "name": "orphan.pdf",
                        "res_model": "x_parent",
                        "res_id": 99,
                        "file_size": 100,
                    },
                    {
                        "id": 2,
                        "name": "live.pdf",
                        "res_model": "x_parent",
                        "res_id": 1,
                        "file_size": 50,
                    },
                ]
            if model == "x_parent" and method == "search":
                return [1]
            raise AssertionError(f"{model}.{method}")

    result = scan_orphan_attachments(_AttClient(), limit=100)  # type: ignore[arg-type]
    assert len(result.orphans) == 1
    assert result.orphans[0].id == 1
    assert result.total_reclaimable_bytes == 100


def test_orphan_scan_excludes_standalone_and_view() -> None:
    from app.bulk_suite.attachments import scan_orphan_attachments

    class _AttClient:
        def model_exists(self, model: str) -> bool:
            return True

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {
                    f: {}
                    for f in [
                        "name",
                        "res_model",
                        "res_id",
                        "res_field",
                        "checksum",
                        "file_size",
                    ]
                }
            if model == "ir.attachment" and method == "search_read":
                domain = args[0]
                if domain == ["|", ("res_model", "=", False), ("res_id", "=", 0)]:
                    return [
                        {
                            "id": 10,
                            "name": "standalone.bin",
                            "res_model": False,
                            "res_id": 0,
                            "file_size": 20,
                        }
                    ]
                return [
                    {
                        "id": 11,
                        "name": "view asset",
                        "res_model": "ir.ui.view",
                        "res_id": 5,
                        "file_size": 30,
                    },
                    {
                        "id": 12,
                        "name": "binary field",
                        "res_model": "x_parent",
                        "res_id": 1,
                        "res_field": "x_doc",
                        "file_size": 40,
                    },
                ]
            if method == "search":
                return [1]
            raise AssertionError(f"{model}.{method}")

    result = scan_orphan_attachments(_AttClient(), limit=100)  # type: ignore[arg-type]
    assert not result.orphans
    assert any(r.id == 10 for r in result.standalone)
    assert any(r.id == 11 for r in result.excluded)
    assert any(r.id == 12 for r in result.excluded)


def test_duplicate_scan_groups_checksum_keep_newest() -> None:
    from app.bulk_suite.attachments import scan_duplicate_attachments

    class _AttClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {
                    f: {}
                    for f in ["name", "res_model", "res_id", "checksum", "file_size", "create_date"]
                }
            if model == "ir.attachment" and method == "search_read":
                return [
                    {
                        "id": 1,
                        "name": "a",
                        "res_model": "x_parent",
                        "res_id": 1,
                        "checksum": "abc",
                        "file_size": 100,
                        "create_date": "2026-01-02",
                    },
                    {
                        "id": 2,
                        "name": "b",
                        "res_model": "x_parent",
                        "res_id": 2,
                        "checksum": "abc",
                        "file_size": 100,
                        "create_date": "2026-01-01",
                    },
                ]
            raise AssertionError(f"{model}.{method}")

    result = scan_duplicate_attachments(_AttClient(), limit=100)  # type: ignore[arg-type]
    assert len(result.groups) == 1
    assert result.groups[0].keep_id == 1
    assert result.groups[0].duplicate_ids == [2]
    assert result.total_reclaimable_bytes == 100


def test_clean_attachments_blocks_standalone() -> None:
    from app.bulk_suite.attachments import AttachmentValidationError, clean_attachments

    class _AttClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {f: {} for f in ["name", "res_model", "res_id", "file_size"]}
            if model == "ir.attachment" and method == "read":
                return [
                    {
                        "id": 5,
                        "name": "solo",
                        "res_model": False,
                        "res_id": 0,
                        "file_size": 10,
                    }
                ]
            raise AssertionError(f"{model}.{method}")

    with pytest.raises(AttachmentValidationError, match="Standalone"):
        clean_attachments(_AttClient(), attachment_ids=[5], dry_run=True)  # type: ignore[arg-type]


class _MassEditClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        self.calls.append((model, method, args, kwargs or {}))
        if method == "fields_get":
            return {
                "x_label": {"type": "char", "readonly": False},
                "x_status": {
                    "type": "selection",
                    "readonly": False,
                    "selection": [("draft", "Draft"), ("done", "Done")],
                },
                "x_readonly": {"type": "char", "readonly": True},
            }
        if method == "read":
            ids = args[0]
            fields = (kwargs or {}).get("fields") or args[1] if len(args) > 1 else []
            return [
                {"id": i, "display_name": f"R{i}", **{f: f"old-{f}" for f in fields}}
                for i in ids
            ]
        if method == "write":
            return True
        if method == "search":
            return [1, 2]
        raise AssertionError(f"unexpected {model}.{method}")


def test_mass_edit_validation_bad_field() -> None:
    from app.bulk_suite.mass_edit import MassEditValidationError, validate_mass_edit_values

    client = _MassEditClient()
    with pytest.raises(MassEditValidationError, match="Unknown field"):
        validate_mass_edit_values(
            client,  # type: ignore[arg-type]
            model="x_test.item",
            values={"missing": "x"},
        )


def test_mass_edit_validation_bad_selection() -> None:
    from app.bulk_suite.mass_edit import MassEditValidationError, validate_mass_edit_values

    client = _MassEditClient()
    with pytest.raises(MassEditValidationError, match="Invalid selection"):
        validate_mass_edit_values(
            client,  # type: ignore[arg-type]
            model="x_test.item",
            values={"x_status": "nope"},
        )


def test_mass_edit_validation_readonly() -> None:
    from app.bulk_suite.mass_edit import MassEditValidationError, validate_mass_edit_values

    client = _MassEditClient()
    with pytest.raises(MassEditValidationError, match="readonly"):
        validate_mass_edit_values(
            client,  # type: ignore[arg-type]
            model="x_test.item",
            values={"x_readonly": "nope"},
        )


def test_mass_edit_dry_run_preview() -> None:
    from app.bulk_suite.mass_edit import run_mass_edit

    client = _MassEditClient()
    result = run_mass_edit(
        client,  # type: ignore[arg-type]
        model="x_test.item",
        record_ids=[1, 2],
        values={"x_label": "new"},
        dry_run=True,
    )
    assert result.preview
    assert result.preview[0].after["x_label"] == "new"
    assert not any(c[1] == "write" for c in client.calls)


def test_discover_inbound_references() -> None:
    from app.bulk_suite.dedupe import discover_inbound_references

    class _RefClient:
        def model_exists(self, model: str) -> bool:
            return model in {"x_child", "x_parent", "mail.message"}

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.model.fields" and method == "search_read":
                return [
                    {
                        "name": "x_parent_id",
                        "model": "x_child",
                        "ttype": "many2one",
                        "relation": "x_parent",
                    },
                    {
                        "name": "x_tag_ids",
                        "model": "x_child",
                        "ttype": "many2many",
                        "relation": "x_parent",
                    },
                ]
            raise AssertionError(f"unexpected {model}.{method}")

    refs = discover_inbound_references(_RefClient(), "x_parent")  # type: ignore[arg-type]
    assert len(refs) == 2
    assert {r.field for r in refs} == {"x_parent_id", "x_tag_ids"}


def test_scan_duplicates_exact_groups() -> None:
    from app.bulk_suite.dedupe import scan_duplicates

    class _ScanClient:
        def model_exists(self, model: str) -> bool:
            return model == "x_item"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if method == "search_read":
                return [
                    {"id": 1, "display_name": "A1", "x_code": "DUP"},
                    {"id": 2, "display_name": "A2", "x_code": "DUP"},
                    {"id": 3, "display_name": "B1", "x_code": "UNIQ"},
                ]
            raise AssertionError(method)

    result = scan_duplicates(
        _ScanClient(),  # type: ignore[arg-type]
        model="x_item",
        match_fields=["x_code"],
        mode="exact",
    )
    assert len(result.groups) == 1
    assert {r.id for r in result.groups[0].records} == {1, 2}


def test_merge_duplicates_dry_run_counts_relinks() -> None:
    from app.bulk_suite.dedupe import merge_duplicates

    class _MergeClient:
        def model_exists(self, model: str) -> bool:
            return model in {"x_parent", "x_child"}

        def field_exists(self, model: str, name: str) -> bool:
            return False

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.model.fields" and method == "search_read":
                return [
                    {
                        "name": "x_parent_id",
                        "model": "x_child",
                        "ttype": "many2one",
                        "relation": "x_parent",
                    }
                ]
            if method == "search":
                if args and args[0] == [("x_parent_id", "in", [2])]:
                    return [10]
                return []
            raise AssertionError(f"{model}.{method} {args}")

    result = merge_duplicates(
        _MergeClient(),  # type: ignore[arg-type]
        model="x_parent",
        winner_id=1,
        loser_ids=[2],
        dry_run=True,
    )
    assert result.relinks
    assert result.relinks[0].count == 1
    assert not any(
        c[1] == "write"
        for c in getattr(_MergeClient(), "calls", [])
    )


def test_render_cron_description_known_hint() -> None:
    from app.bulk_suite.cron_manager import render_cron_description

    text = render_cron_description(
        {
            "name": "Mail: Email Queue Manager",
            "model_name": "mail.mail",
            "interval_number": 1,
            "interval_type": "hours",
            "active": True,
        }
    )
    assert "Every hour" in text
    assert "process outgoing mail queue" in text


def test_render_cron_description_parses_model_method() -> None:
    from app.bulk_suite.cron_manager import render_cron_description

    text = render_cron_description(
        {
            "name": "Custom job",
            "model_name": "x_blk_wf_item",
            "interval_number": 2,
            "interval_type": "days",
            "code": "model.action_confirm()",
            "active": False,
        }
    )
    assert "Every 2 days" in text
    assert "x_blk_wf_item.action_confirm()" in text
    assert "inactive" in text


def test_run_crons_now_dry_run() -> None:
    from app.bulk_suite.cron_manager import run_crons_now

    class _CronClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.cron" and method == "read":
                return [{"name": "Autovacuum"}]
            raise AssertionError(f"{model}.{method}")

    result = run_crons_now(_CronClient(), cron_ids=[7, 7], dry_run=True)  # type: ignore[arg-type]
    assert result.succeeded == 1
    assert result.run_via == "dry_run"
    assert result.per_record[0].display_name == "Autovacuum"


def test_run_single_cron_fallback_model_method() -> None:
    from app.bulk_suite.cron_manager import run_single_cron

    calls: list[tuple[str, str, list[Any]]] = []

    class _CronClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            calls.append((model, method, args))
            if model == "ir.cron" and method == "method_direct_trigger":
                raise OdooClientError("RPC blocked")
            if model == "ir.cron" and method == "read":
                return [
                    {
                        "name": "Custom",
                        "model_name": "x_blk_wf_item",
                        "code": "model.action_confirm()",
                    }
                ]
            if model == "x_blk_wf_item" and method == "action_confirm":
                return True
            raise AssertionError(f"{model}.{method}")

    via, detail = run_single_cron(_CronClient(), 9, dry_run=False)  # type: ignore[arg-type]
    assert via == "model_method"
    assert detail == "x_blk_wf_item.action_confirm()"
    assert ("x_blk_wf_item", "action_confirm", [[]]) in calls


def test_create_cron_for_existing_method() -> None:
    from app.bulk_suite.cron_manager import create_cron_for_existing_method

    created: dict[str, Any] = {}

    class _CronClient:
        def model_exists(self, model: str) -> bool:
            return model == "x_blk_wf_item"

        def _model_id(self, model: str) -> int:
            return 42

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.cron" and method == "create":
                created.update(args[0])
                return 99
            raise AssertionError(f"{model}.{method}")

    cron_id = create_cron_for_existing_method(
        _CronClient(),  # type: ignore[arg-type]
        name="Confirm drafts nightly",
        model="x_blk_wf_item",
        method="action_confirm",
    )
    assert cron_id == 99
    assert created["code"] == "model.action_confirm()"
    assert created["model_id"] == 42


def test_security_preview_add_and_implied_warning() -> None:
    from app.bulk_suite.security import preview_security_changes

    class _SecClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "res.users" and method == "read":
                return [{"id": 1, "name": "Alice", "login": "alice", "groups_id": [10]}]
            if model == "res.groups" and method == "read":
                if args[0] == [20]:
                    return [
                        {
                            "id": 20,
                            "name": "Sales",
                            "full_name": "Sales / User",
                            "implied_ids": [30],
                        }
                    ]
                return [
                    {"id": 10, "name": "Internal", "full_name": "Internal User"},
                    {"id": 30, "name": "Contact Creation", "full_name": "Contact Creation"},
                ]
            if model == "ir.model.data" and method == "search_read":
                return [{"res_id": 10}]
            raise AssertionError(f"{model}.{method}")

    preview = preview_security_changes(
        _SecClient(),  # type: ignore[arg-type]
        user_ids=[1],
        group_ids=[20],
        mode="add",
    )
    assert preview.users[0].add_groups[0].id == 20
    assert preview.users[0].implied_warnings


def test_security_apply_requires_preview_ack() -> None:
    from app.bulk_suite.security import SecurityValidationError, apply_security_changes

    with pytest.raises(SecurityValidationError, match="preview_acknowledged"):
        apply_security_changes(
            _FakeSecClient(),  # type: ignore[arg-type]
            user_ids=[1],
            group_ids=[20],
            mode="add",
            dry_run=False,
            preview_acknowledged=False,
        )


class _FakeSecClient:
    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        if model == "res.users" and method == "read":
            return [{"id": 1, "name": "Alice", "groups_id": []}]
        if model == "res.groups" and method == "read":
            return [{"id": 20, "name": "Sales", "full_name": "Sales", "implied_ids": []}]
        if model == "ir.model.data" and method == "search_read":
            return []
        raise AssertionError(f"{model}.{method}")


def test_bulk_activities_dry_run() -> None:
    from app.bulk_suite.activities import run_bulk_activities

    class _ActClient:
        def _model_id(self, model: str) -> int:
            return 7

        def model_exists(self, model: str) -> bool:
            return model in {"mail.activity", "x_test", "x_no_activity"}

        def ensure_mail_mixins(self, model: str) -> dict[str, bool]:
            return {"is_mail_thread": False, "is_mail_activity": False}

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if method == "fields_get":
                if model == "x_test":
                    return {"activity_ids": {}, "display_name": {}}
                if model == "x_no_activity":
                    return {"display_name": {}}
            if model == "x_test" and method == "read":
                return [{"id": 1, "display_name": "Row 1"}]
            if model == "mail.activity.type" and method == "read":
                return [{"id": 3, "name": "To Do"}]
            raise AssertionError(f"{model}.{method}")

    from app.bulk_suite.activities import ActivityValidationError, run_bulk_activities

    probe_model = "x_no_activity"
    with pytest.raises(ActivityValidationError):
        run_bulk_activities(
            _ActClient(),  # type: ignore[arg-type]
            model=probe_model,
            record_ids=[1],
            activity_type_id=3,
            summary="Follow up",
            date_deadline="2026-08-10",
            dry_run=True,
        )

    result = run_bulk_activities(
        _ActClient(),  # type: ignore[arg-type]
        model="x_test",
        record_ids=[1],
        activity_type_id=3,
        summary="Follow up",
        date_deadline="2026-08-10",
        dry_run=True,
    )
    assert result.succeeded == 1


def test_portal_grant_requires_email() -> None:
    from app.bulk_suite.portal_access import run_bulk_portal

    class _PortalClient:
        def model_exists(self, model: str) -> bool:
            return model == "portal.wizard"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "res.partner" and method == "read":
                return [
                    {"id": 1, "name": "No Email", "email": False, "user_ids": []},
                    {"id": 2, "name": "Has Email", "email": "a@example.com", "user_ids": []},
                ]
            raise AssertionError(f"{model}.{method}")

    result = run_bulk_portal(
        _PortalClient(),  # type: ignore[arg-type]
        partner_ids=[1, 2],
        action="grant",
        dry_run=True,
    )
    assert result.failed == 1
    assert result.succeeded == 1


def test_recompute_probe_fail_returns_honesty_message() -> None:
    from app.bulk_suite.recompute import run_recompute

    class _RecClient:
        config = type("C", (), {"url": "https://example.odoo.com"})()

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if method == "fields_get":
                return {"x_plain": {"type": "char"}}
            raise AssertionError(f"{model}.{method}")

    result = run_recompute(
        _RecClient(),  # type: ignore[arg-type]
        model="x_test",
        field_name="x_plain",
        record_ids=[1],
        dry_run=False,
    )
    assert result.failed == 1
    assert result.probe is not None
    assert result.probe.honesty_message
    assert "shell access" in result.message


def test_send_message_dry_run_per_record() -> None:
    from app.bulk_suite.send_message import run_bulk_send_message

    posts: list[int] = []

    class _MailClient:
        def model_exists(self, model: str) -> bool:
            return model == "mail.message"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "x_test" and method == "fields_get":
                return {"message_ids": {}, "display_name": {}}
            if model == "x_test" and method == "read":
                return [{"id": i, "display_name": f"R{i}"} for i in args[0]]
            if method == "message_post":
                posts.append(int(args[0][0]))
            raise AssertionError(f"{model}.{method}")

    result = run_bulk_send_message(
        _MailClient(),  # type: ignore[arg-type]
        model="x_test",
        record_ids=[1, 2],
        body="<p>Hi</p>",
        dry_run=True,
    )
    assert result.succeeded == 2
    assert posts == []


def test_orphan_scan_detects_missing_parent() -> None:
    from app.bulk_suite.attachments import scan_orphan_attachments

    class _AttClient:
        def model_exists(self, model: str) -> bool:
            return model == "x_parent"

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {f: {} for f in ["name", "res_model", "res_id", "checksum", "file_size"]}
            if model == "ir.attachment" and method == "search_read":
                domain = args[0]
                if domain == ["|", ("res_model", "=", False), ("res_id", "=", 0)]:
                    return []
                return [
                    {
                        "id": 1,
                        "name": "orphan.pdf",
                        "res_model": "x_parent",
                        "res_id": 99,
                        "file_size": 100,
                    },
                    {
                        "id": 2,
                        "name": "live.pdf",
                        "res_model": "x_parent",
                        "res_id": 1,
                        "file_size": 50,
                    },
                ]
            if model == "x_parent" and method == "search":
                return [1]
            raise AssertionError(f"{model}.{method}")

    result = scan_orphan_attachments(_AttClient(), limit=100)  # type: ignore[arg-type]
    assert len(result.orphans) == 1
    assert result.orphans[0].id == 1
    assert result.total_reclaimable_bytes == 100


def test_orphan_scan_excludes_standalone_and_view() -> None:
    from app.bulk_suite.attachments import scan_orphan_attachments

    class _AttClient:
        def model_exists(self, model: str) -> bool:
            return True

        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {
                    f: {}
                    for f in [
                        "name",
                        "res_model",
                        "res_id",
                        "res_field",
                        "checksum",
                        "file_size",
                    ]
                }
            if model == "ir.attachment" and method == "search_read":
                domain = args[0]
                if domain == ["|", ("res_model", "=", False), ("res_id", "=", 0)]:
                    return [
                        {
                            "id": 10,
                            "name": "standalone.bin",
                            "res_model": False,
                            "res_id": 0,
                            "file_size": 20,
                        }
                    ]
                return [
                    {
                        "id": 11,
                        "name": "view asset",
                        "res_model": "ir.ui.view",
                        "res_id": 5,
                        "file_size": 30,
                    },
                    {
                        "id": 12,
                        "name": "binary field",
                        "res_model": "x_parent",
                        "res_id": 1,
                        "res_field": "x_doc",
                        "file_size": 40,
                    },
                ]
            if method == "search":
                return [1]
            raise AssertionError(f"{model}.{method}")

    result = scan_orphan_attachments(_AttClient(), limit=100)  # type: ignore[arg-type]
    assert not result.orphans
    assert any(r.id == 10 for r in result.standalone)
    assert any(r.id == 11 for r in result.excluded)
    assert any(r.id == 12 for r in result.excluded)


def test_duplicate_scan_groups_checksum_keep_newest() -> None:
    from app.bulk_suite.attachments import scan_duplicate_attachments

    class _AttClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {
                    f: {}
                    for f in ["name", "res_model", "res_id", "checksum", "file_size", "create_date"]
                }
            if model == "ir.attachment" and method == "search_read":
                return [
                    {
                        "id": 1,
                        "name": "a",
                        "res_model": "x_parent",
                        "res_id": 1,
                        "checksum": "abc",
                        "file_size": 100,
                        "create_date": "2026-01-02",
                    },
                    {
                        "id": 2,
                        "name": "b",
                        "res_model": "x_parent",
                        "res_id": 2,
                        "checksum": "abc",
                        "file_size": 100,
                        "create_date": "2026-01-01",
                    },
                ]
            raise AssertionError(f"{model}.{method}")

    result = scan_duplicate_attachments(_AttClient(), limit=100)  # type: ignore[arg-type]
    assert len(result.groups) == 1
    assert result.groups[0].keep_id == 1
    assert result.groups[0].duplicate_ids == [2]
    assert result.total_reclaimable_bytes == 100


def test_clean_attachments_blocks_standalone() -> None:
    from app.bulk_suite.attachments import AttachmentValidationError, clean_attachments

    class _AttClient:
        def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
            if model == "ir.attachment" and method == "fields_get":
                return {f: {} for f in ["name", "res_model", "res_id", "file_size"]}
            if model == "ir.attachment" and method == "read":
                return [
                    {
                        "id": 5,
                        "name": "solo",
                        "res_model": False,
                        "res_id": 0,
                        "file_size": 10,
                    }
                ]
            raise AssertionError(f"{model}.{method}")

    with pytest.raises(AttachmentValidationError, match="Standalone"):
        clean_attachments(_AttClient(), attachment_ids=[5], dry_run=True)  # type: ignore[arg-type]
