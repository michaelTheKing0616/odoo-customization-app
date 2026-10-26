"""TAX-TIERS unit tests (offline: versioncaps data files, no RPC)."""

from __future__ import annotations

import pytest

from app.bots import tiers as tt


@pytest.mark.parametrize(
    ("tid", "tier"),
    [
        ("m:res.partner:create", 1),
        ("s:group_uom", 1),
        ("mod:sale:install", 1),
        ("b:sale.order:action_confirm", 1),
        ("c:res.partner:customize-field", 2),
        ("v:res.partner:form", 2),
        ("code:040:migrate", 3),
        ("mod:sale:frobnicate", None),
        ("zz:x", None),
        ("m:", None),
        ("nocolon", None),
        (None, None),
    ],
)
def test_tier_of(tid, tier):
    assert tt.tier_of(tid) == tier


def test_unknown_kind_refused():
    a = tt.assess("zz:thing", version=17, installed_modules=["base"])
    assert a.grade == tt.UNKNOWN and not a.allowed and "will not run" in a.message()


def test_t3_not_built_yet_with_alternatives():
    a = tt.assess("code:040:migrate", version=17, installed_modules=["base"])
    assert a.grade == tt.NOT_BUILT_YET and a.tier == 3 and len(a.instead) == 3
    assert "What you can do instead" in a.message() and not tt.tier_ready(3)


def test_registering_t3_capabilities_flips_to_allowed(monkeypatch):
    from types import MappingProxyType

    caps_on = dict(tt._CAPABILITIES, **{"module-authoring": True, "module-test-gate": True})
    monkeypatch.setattr(tt, "_CAPABILITIES", MappingProxyType(caps_on))
    assert tt.assess("code:040:migrate", version=17, installed_modules=["base"]).allowed
    half = dict(caps_on, **{"module-test-gate": False})
    monkeypatch.setattr(tt, "_CAPABILITIES", MappingProxyType(half))
    assert not tt.assess("code:040:migrate", version=17, installed_modules=["base"]).allowed


def test_capabilities_not_mutable_or_caller_settable():
    import inspect

    with pytest.raises(TypeError):
        tt._CAPABILITIES["module-authoring"] = True  # type: ignore[index]
    assert "supported" not in inspect.signature(tt.assess).parameters


@pytest.mark.parametrize("ver", [17, 20])
def test_t1_installed_model_ok(ver):
    a = tt.assess("m:res.partner:create", version=ver, installed_modules=["base"])
    assert a.allowed and a.tier == 1


@pytest.mark.parametrize("ver", [17, 20])
def test_needs_install_named_step(ver):
    a = tt.assess("m:sale.order:create", version=ver, installed_modules=["base"])
    assert a.grade == tt.NEEDS_STEP and "mod:sale:install" in a.prior_steps


def test_unknown_installed_fails_closed():
    a = tt.assess("m:res.partner:create", version=17, installed_modules=None)
    assert a.grade == tt.UNKNOWN


def test_unknown_model_fails_closed():
    a = tt.assess("m:x.no.such.model:create", version=17, installed_modules=["base"])
    assert not a.allowed and a.grade in (tt.UNKNOWN, tt.NOT_IN_VERSION)


def test_bad_version_fails_closed():
    a = tt.assess("m:res.partner:create", version="banana", installed_modules=["base"])
    assert a.grade == tt.UNKNOWN


def test_classifier_failure_fails_closed(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("x")

    monkeypatch.setattr(tt.classifier, "task_floor", boom)
    assert tt.assess("s:group_uom", version=17, installed_modules=[]).grade == tt.UNKNOWN


@pytest.mark.parametrize("bad", ["res.partner", b"base", 42, {"base": 1}.keys(), iter(["base"])])
def test_installed_modules_non_collection_unknown(bad):
    assert tt.assess("m:res.partner:create", version=17, installed_modules=bad).grade == tt.UNKNOWN


def test_uninstall_needs_approval():
    a = tt.assess("mod:sale:uninstall", version=17, installed_modules=["base", "sale"])
    assert a.grade == tt.APPROVAL_REQUIRED and "backup" in a.message()
    ok = tt.assess("s:group_uom", version=17, installed_modules=["base"])
    p = tt.compose([ok, a])
    assert p.grade == tt.APPROVAL_REQUIRED and not p.allowed


@pytest.mark.parametrize(
    ("tid", "model"),
    [
        ("m:res.partner:create", "res.partner"),
        ("b:sale.order:action_confirm", "sale.order"),
        ("wiz:sale.advance.payment.inv:create_invoices", "sale.advance.payment.inv"),
        ("sa:Do thing:hr.employee", "hr.employee"),
        ("v:sale.order:form", "sale.order"),
        ("c:res.partner:automation", "res.partner"),
        ("t:Portal: User Invite:portal.wizard.user:send", "portal.wizard.user"),
        ("r:hr_expense.report_expense_sheet", None),
        ("cron:Mail queue", None),
    ],
)
def test_model_of_contract(tid, model):
    assert tt.model_of(tid) == model


@pytest.mark.parametrize("ver", [17, 20])
def test_view_on_uninstalled_model_not_ok(ver):
    a = tt.assess("v:sale.order:form", version=ver, installed_modules=["base"])
    assert a.grade == tt.NEEDS_STEP and "mod:sale:install" in a.prior_steps


@pytest.mark.parametrize("tid", ["r:hr_expense.report_expense_sheet", "cron:Mail queue"])
def test_no_model_ids_unknown(tid):
    assert tt.assess(tid, version=17, installed_modules=["base"]).grade == tt.UNKNOWN


def test_model_of_fault_unknown(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("x")

    monkeypatch.setattr(tt.classifier, "_model_of", boom)
    assert (
        tt.assess("m:res.partner:create", version=17, installed_modules=["base"]).grade == "unknown"
    )


def test_availability_fault_unknown(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("x")

    monkeypatch.setattr(tt.caps, "availability", boom)
    assert (
        tt.assess("m:res.partner:create", version=17, installed_modules=["base"]).grade == "unknown"
    )


def test_compose_odd_grade_unknown():
    odd = tt.Assessment("m:x:create", 1, "weird", "")
    assert tt.compose([odd]).grade == tt.UNKNOWN


def test_compose_order_and_all_or_nothing():
    ok1 = tt.assess("m:res.partner:create", version=17, installed_modules=["base"])
    ok2 = tt.assess("c:res.partner:customize-field", version=17, installed_modules=["base"])
    p = tt.compose([ok1, ok2])
    assert p.allowed and p.tier == 2 and p.order == (ok2.task_id, ok1.task_id)
    bad = tt.assess("code:040:migrate", version=17, installed_modules=["base"])
    p2 = tt.compose([ok1, bad, ok2])
    assert not p2.allowed and p2.grade == tt.NOT_BUILT_YET and p2.tier == 3
    assert p2.order[0] == bad.task_id and "Nothing runs: 1 of 3" in p2.message()
    assert ok1.task_id in p2.message()


def test_compose_unknown_dominates_and_empty():
    unk = tt.assess("zz:x", version=17, installed_modules=[])
    t3 = tt.assess("code:040:migrate", version=17, installed_modules=[])
    p = tt.compose([t3, unk])
    assert p.grade == tt.UNKNOWN and p.tier is None
    assert tt.compose([]).grade == tt.UNKNOWN


def test_claim_is_tier_scoped():
    assert (
        "T1" in tt.CLAIM
        and "T2" in tt.CLAIM
        and "T3" in tt.CLAIM
        and "any Odoo task" not in tt.CLAIM
        and "not yet available" in tt.CLAIM
    )


def test_module_is_read_only():
    import inspect

    src = inspect.getsource(tt)
    for w in ("execute_kw", ".write(", ".create(", ".unlink(", "call_kw"):
        assert w not in src
