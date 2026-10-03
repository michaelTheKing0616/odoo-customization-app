"""RT-10 through RT-16 stay blocked. A tenant overlay cannot shrink the core registry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.changeset.executor import _protocol, apply, get_journal, reset_journal
from app.changeset.handlers import apply_memory
from app.changeset.ops import op_base_risk
from app.changeset.policy import policy_for_op, risk_of
from app.changeset.protected_registry import (
    _FLOOR_MODELS,
    deny_models,
    detections,
    elevate_models,
    protected_case,
    protected_denial,
    requires_domain_owner,
    reset_detections,
)
from app.changeset.validate import validate


def _assert_policy_denied(
    op: dict,
    case: str,
    *,
    document: list[dict] | None = None,
    tenant: dict | None = None,
) -> None:
    """The named RT case blocks, records policy_denied, and is R4."""
    reset_detections()
    assert protected_denial(op, document=document, tenant=tenant) == "protected_deny"
    record = detections()[-1]
    assert record["case"] == case
    assert record["alert"] == "policy_denied"
    assert risk_of(op, document=document, tenant=tenant) == "R4"


def _batch(model: str, **extra: object) -> dict:
    params: dict = {"model": model, "domain": [["id", "=", 1]], "values": {"x": 1}}
    params.update(extra)
    return {"type": "data.update_batch", "params": params}


def test_core_yaml_matches_the_floor() -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "changeset" / "protected_core.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert set(loaded["deny_models"]) == set(_FLOOR_MODELS)
    assert "stock.quant" in deny_models()
    from app.changeset.protected_registry import _code_tricks

    for trick in loaded["code_tricks"]:
        assert trick in _code_tricks()


def test_tenant_cannot_remove_a_core_model() -> None:
    tenant = {"remove_models": ["stock.quant"], "add_models": ["x_secret"]}
    assert protected_case(_batch("stock.quant"), tenant=tenant) == "RT-12"
    assert protected_case(_batch("x_secret"), tenant=tenant) == "RT-12"
    assert "stock.quant" in deny_models(tenant)
    removed = {"remove_models": ["stock.quant", "account.move", "hr.payslip"]}
    assert deny_models(removed) == deny_models()
    assert deny_models(tenant) == deny_models() | {"x_secret"}
    assert "x_secret" in deny_models({"add_models": ["x_secret"], "remove_models": ["x_secret"]})
    _assert_policy_denied(_batch("stock.quant"), "RT-12", tenant=removed)


def test_rt10_scaffold_expansion_into_a_protected_model() -> None:
    blocked = {
        "type": "model.scaffold",
        "params": {
            "model": "x_ticket",
            "models": ["account.payment"],
            "ops": [{"type": "data.update_batch", "params": {"model": "stock.quant", "domain": [["id", "=", 1]], "values": {}}}],
        },
    }
    allowed = {"type": "model.scaffold", "params": {"model": "x_ticket", "fields": [{"name": "x_note"}]}}
    relation = {
        "type": "model.scaffold",
        "params": {"model": "x_ticket", "fields": [{"name": "x_move", "relation": "account.move"}]},
    }
    assert protected_case(blocked) == "RT-10"
    assert protected_case(relation) == "RT-10"
    assert protected_case(allowed) is None
    _assert_policy_denied(blocked, "RT-10")


def test_rt11_ref_to_a_protected_model() -> None:
    document = [
        {"type": "field.update", "params": {"model": "account.move", "name": "ref"}},
        {
            "type": "field.update",
            "params": {"model": "sale.order", "$ref": "#/ops/0/params/model", "name": "x_note"},
        },
    ]
    assert protected_case(document[1], document=document) == "RT-11"
    _assert_policy_denied(document[1], "RT-11", document=document)
    bare = [
        {"type": "field.update", "params": {"model": "account.move", "name": "ref"}},
        {"type": "field.update", "params": {"model": {"$ref": "#/0/params/model"}, "name": "x_note"}},
    ]
    assert protected_case(bare[1], document=bare) == "RT-11"
    assert protected_case({"type": "field.update", "params": {"model": "sale.order", "name": "x_note"}}) is None


def test_rt12_widened_domain_and_extra_models() -> None:
    widened = _batch("res.partner", domain=["|", ["id", ">", 0], ["move_id", "=", "account.move"]])
    extra = _batch("res.partner", also_models=["stock.quant"])
    assert protected_case(widened) == "RT-12"
    assert protected_case(extra) == "RT-12"
    assert protected_case(_batch("res.partner")) is None
    _assert_policy_denied(widened, "RT-12")


def test_rt13_setting_side_effects() -> None:
    lock = {"type": "setting.set", "params": {"key": "module_sale", "value": True}}
    assert protected_case(lock) == "RT-13"
    assert (
        protected_case(
            {
                "type": "setting.set",
                "params": {"key": "sale.auto", "side_effects": [{"op": "module.install", "module": "sale"}]},
            }
        )
        == "RT-13"
    )
    assert (
        protected_case({"type": "company.update", "params": {"values": {"fiscalyear_lock_date": "2026-01-01"}}})
        == "RT-13"
    )
    assert protected_case({"type": "setting.set", "params": {"key": "sale.auto", "value": True}}) is None
    _assert_policy_denied(lock, "RT-13")


def test_rt14_stored_compute_and_private_field() -> None:
    compute = {
        "type": "field.create",
        "params": {"model": "account.move", "name": "x_total", "compute": "1", "store": True},
    }
    private = {"type": "field.update", "params": {"model": "hr.employee", "name": "ssnid"}}
    label = {"type": "field.update", "params": {"model": "account.move", "name": "ref"}}
    assert protected_case(compute) == "RT-14"
    assert protected_case(private) == "RT-14"
    assert protected_case(label) is None
    assert risk_of(compute) == "R4"
    assert risk_of({"type": "field.create", "params": {"model": "product.category", "name": "x_note"}}) == "R3"
    _assert_policy_denied(compute, "RT-14")


def test_rt15_server_action_tricks() -> None:
    trick = {"type": "server_action.create", "params": {"code": "getattr(env, 'ref')('account.move')"}}
    named = {"type": "server_action.create", "params": {"code": "env['stock.quant'].write({})"}}
    fetched = {"type": "server_action.create", "params": {"code": "env.get('account.move').write({})"}}
    plain = {"type": "server_action.create", "params": {"code": "record.write({'x_flag': True})"}}
    assert protected_case(trick) == "RT-15"
    assert protected_case(named) == "RT-15"
    assert protected_case(fetched) == "RT-15"
    assert protected_case(plain) is None
    _assert_policy_denied(trick, "RT-15")
    with pytest.raises(PermissionError):
        apply_memory({}, trick)


def test_rt16_journal_sequence_alias_and_confusable() -> None:
    alias = {"type": "sequence.update", "params": {"code": "sale.order", "alias": "account.journal"}}
    homoglyph = {"type": "sequence.create", "params": {"code": "sale.order", "name": "аccount.journal"}}
    plain = {"type": "sequence.create", "params": {"code": "sale.order", "name": "Sales"}}
    assert protected_case(alias) == "RT-16"
    assert protected_case(homoglyph) == "RT-16"
    assert protected_case(plain) is None
    _assert_policy_denied(alias, "RT-16")


def test_blocked_cases_do_not_journal_and_are_alerted() -> None:
    reset_journal()
    error = _protocol().BridgeError
    cases = [
        {"type": "model.scaffold", "params": {"model": "account.move"}},
        {"type": "field.create", "params": {"model": "stock.move", "name": "x_cost", "compute": "1", "store": True}},
        {"type": "server_action.create", "params": {"code": "sudo().write({})"}},
        {"type": "sequence.update", "params": {"code": "account.move"}},
        {"type": "company.update", "params": {"lock_date": "2026-01-01"}},
    ]
    for op in cases:
        reset_journal()
        with pytest.raises(error) as denied:
            apply([op], mode="T", port=None)
        assert denied.value.code == "protected_deny"
        assert get_journal() == []
        assert detections()[-1]["alert"] == "policy_denied"
        assert protected_denial(op) == "protected_deny"


def test_validate_rejects_a_protected_scaffold() -> None:
    report = validate(
        [{"type": "model.scaffold", "params": {"model": "x_ticket", "models": ["hr.payslip"]}}],
        known_models={"x_ticket", "hr.payslip"},
    )
    static = next(stage for stage in report["stages"] if stage["name"] == "static")
    assert static["passed"] is False
    assert any("protected_deny" in error for error in static["errors"])
    assert report["valid"] is False


def test_review_bypasses_stay_blocked() -> None:
    assert protected_case({"type": "company.update", "params": {"tax_lock_date": "2026-01-01"}}) == "RT-13"
    assert protected_case({"type": "company.update", "params": {"period_lock_date": "2026-01-01"}}) == "RT-13"
    assert protected_case({"type": "setting.set", "params": {"key": " Module_sale ", "value": True}}) == "RT-13"
    assert protected_case({"type": "setting.set", "params": {"side_effects": ["module.install"]}}) == "RT-13"
    assert protected_case({"type": "setting.set", "params": {"side_effects": {"module.install": "sale"}}}) == "RT-13"
    assert protected_case({"type": "company.update", "params": {"name": "Acme"}}) is None

    assert protected_case({"type": "server_action.create", "params": {"code": "record.sudo\t().write({})"}}) == "RT-15"
    assert (
        protected_case({"type": "server_action.create", "params": {"code": "env.__getitem__('account.move')"}})
        == "RT-15"
    )
    assert (
        protected_case(
            {"type": "automation.create", "params": {"actions": [{"python_code": "sudo()"}]}}
        )
        == "RT-15"
    )
    assert protected_case({"type": "server_action.create", "params": {"code": "record.write({'x_flag': True})"}}) is None

    missing = [{"type": "field.update", "params": {"model": {"$ref": "#/9/params/model"}, "name": "x_note"}}]
    assert protected_case(missing[0], document=missing) == "RT-11"
    whole = [
        {"type": "field.update", "params": {"model": "account.move", "name": "ref"}},
        {"type": "field.update", "params": {"model": {"$ref": "#/0"}, "name": "x_note"}},
    ]
    assert protected_case(whole[1], document=whole) == "RT-11"
    listed = [
        {"type": "field.update", "params": {"targets": ["account.move"], "model": "sale.order", "name": "x_note"}},
        {"type": "field.update", "params": {"model": {"$ref": "#/0/params/targets/0"}, "name": "x_note"}},
    ]
    assert protected_case(listed[1], document=listed) == "RT-11"

    nested: dict = {"type": "server_action.create", "params": {"code": "sudo()"}}
    for _ in range(12):
        nested = {"type": "model.scaffold", "params": {"model": "x_ticket", "ops": [nested]}}
    assert protected_case(nested) == "RT-10"
    inherit = {"type": "model.scaffold", "params": {"model": "x_ticket", "_inherit": "account.move"}}
    assert protected_case(inherit) == "RT-10"

    rows = {"type": "data.create_batch", "params": {"model": "res.users", "rows": [{"password": "secret"}]}}
    assert protected_case(rows) == "RT-14"
    assert "secret" not in str(detections())
    assert protected_case(_batch("res.partner", related_models=["stock.quant"])) == "RT-12"
    unstored = {
        "type": "field.create",
        "params": {"model": "account.move", "name": "x_note", "compute": "1", "store": False},
    }
    assert protected_case(unstored) is None
    assert protected_case({"type": "model.create", "params": {"model": " account.move"}}) == "RT-10"
    assert (
        protected_case(
            {"type": "field.create", "params": {"model": "account.move\n", "name": "x_cost", "compute": "1", "store": True}}
        )
        == "RT-14"
    )
    assert protected_case({"type": "company.update", "params": {"hard_lock_date": "2026-01-01"}}) == "RT-13"
    assert protected_case({"type": "data.update_batch", "params": {"model": "hr.employee", "domain": [["id", "=", 1]], "field_name": "ssnid", "values": {}}}) == "RT-14"
    assert protected_case({"type": "data.import_upsert", "params": {"model": "hr.employee", "columns": ["ssnid", 1]}}) == "RT-14"
    source = [
        {
            "type": "view.create_base",
            "params": {
                "payload": {"ssnid": "1"},
                "x": {"code": "sudo()"},
                "v": {"tax_lock_date": "2026-01-01"},
            },
        }
    ]
    assert (
        protected_case(
            {
                "type": "data.update_batch",
                "params": {"model": "hr.employee", "domain": [["id", "=", 1]], "values": {"$ref": "#/0/params/payload"}},
            },
            document=source
            + [
                {
                    "type": "data.update_batch",
                    "params": {"model": "hr.employee", "domain": [["id", "=", 1]], "values": {"$ref": "#/0/params/payload"}},
                }
            ],
        )
        == "RT-14"
    )
    code_ref = source + [{"type": "automation.create", "params": {"model": "sale.order", "actions": {"$ref": "#/0/params/x"}}}]
    assert protected_case(code_ref[1], document=code_ref) == "RT-15"
    lock_ref = source + [{"type": "company.update", "params": {"values": {"$ref": "#/0/params/v"}}}]
    assert protected_case(lock_ref[1], document=lock_ref) == "RT-13"
    assert (
        protected_case({"type": "server_action.create", "params": {"code": "record.env.cr.execute('delete from account_move')"}})
        == "RT-15"
    )
    assert (
        protected_case({"type": "server_action.create", "params": {"code": "record.company_id.write({'tax_lock_date': '2026'})"}})
        == "RT-15"
    )
    linked = [
        {"type": "field.update", "params": {"model": "sale.order", "name": "client_order_ref"}},
        {"type": "field.create", "params": {"model": {"$ref": "#/0/params/model"}, "name": "x_a"}},
    ]
    assert protected_case(linked[1], document=linked) is None
    assert risk_of(linked[1], document=linked) == "R2"


def test_protected_elevate_is_risk_plus_one_and_needs_a_domain_owner() -> None:
    order = ("R0", "R1", "R2", "R3", "R4")
    denied = {"type": "model.scaffold", "params": {"model": "account.move"}}
    denied_policy = policy_for_op(denied, "production")
    assert risk_of(denied) == "R4"
    assert denied_policy["deny"] is True
    assert denied_policy["domain_owner"] is False
    assert requires_domain_owner(denied) is False

    for model in sorted(elevate_models()):
        op = {"type": "field.create", "params": {"model": model, "name": "x_note"}}
        base = op_base_risk("field.create", op["params"])
        bumped = risk_of(op)
        assert order.index(bumped) == order.index(base) + 1
        assert requires_domain_owner(op) is True
        assert requires_domain_owner(op, tenant={"remove_models": [model]}) is True
        for environment, approvers in (("production", 2), ("staging", 1)):
            decision = policy_for_op(op, environment)
            assert decision["domain_owner"] is True
            assert decision["deny"] is False
            assert decision["approvers"] == approvers

    plain = {"type": "field.create", "params": {"model": "sale.order", "name": "x_note"}}
    assert risk_of(plain) == "R2"
    assert policy_for_op(plain, "production")["domain_owner"] is False


def test_apply_uses_tenant_additions_and_elevated_risk() -> None:
    reset_journal()
    error = _protocol().BridgeError
    with pytest.raises(error) as added:
        apply([_batch("x_secret")], mode="T", tenant={"add_models": ["x_secret"]})
    assert added.value.code == "protected_deny"
    assert get_journal() == []
    reset_journal()
    with pytest.raises(error) as elevated:
        apply(
            [{"type": "field.create", "params": {"model": "product.category", "name": "x_note"}}],
            mode="T",
            max_risk="R2",
        )
    assert elevated.value.code == "max_risk"
    assert get_journal() == []


def test_plan_card_and_dispatch_resolve_a_cross_op_ref() -> None:
    from app.changeset.dispatch import dispatch_op
    from app.changeset.plan_card import render_plan_card

    changeset = [
        {"type": "field.update", "params": {"model": "sale.order", "name": "client_order_ref"}},
        {"type": "field.create", "params": {"model": {"$ref": "#/0/params/model"}, "name": "x_a"}},
    ]
    card = render_plan_card(changeset, goal="Add a note", assumptions=["The host exists"], environment="staging")
    assert card["risk"]["per_op"][1] == "R2"

    class _Port:
        def __init__(self) -> None:
            self.created: list[tuple[str, dict]] = []

        def create(self, model: str, values: dict) -> int:
            self.created.append((model, values))
            return 1

        def write(self, model: str, ids: list[int], values: dict) -> None:
            return None

    port = _Port()
    dispatch_op(port, changeset[1], document=changeset)
    assert port.created[0][1]["model"] == "sale.order"
