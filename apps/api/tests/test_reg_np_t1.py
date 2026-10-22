"""REG-NP-T1 — pin schema-grounding behaviour that is already in code.

Product code is read-only. Each test fails if the named behaviour regresses.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_draft_jobs import studio_generate_offline_finish  # noqa: E402
from app.ai_generate_ir import (  # noqa: E402
    STRUCTURAL_ALLOWLIST,
    Proposal,
    admit_and_apply,
)
from app.ai_repair_loop import DEFAULT_MAX_REPAIR  # noqa: E402
from app.ai_schema_client import (  # noqa: E402
    SCHEMA_CATALOG_TTL_S,
    CatalogSchemaClient,
    DenySchemaClient,
    FakeSchemaClient,
    LiveSchemaClient,
    schema_client_for_draft,
)

_REPO = Path(__file__).resolve().parents[3]
_API = _REPO / "apps" / "api"
_APP = _API / "app"
_GENERATE_IR_SOURCES = (
    _APP / "ai_generate_ir.py",
    _APP / "ai_generate_ir_enforce.py",
    _APP / "ai_generate_ir_lint.py",
)
_MAINTENANCE_BRIEF = (
    "Build Maintenance tickets: checklist lines with done flags, parts used (product + qty), "
    "state Draft→Done; Online-honest on stock moves."
)
_TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "addons/ext_markup_test/models/sale_order.py", line 42, in write\n'
    '    raise ValidationError("bad field x_markup")\n'
    "ValidationError: bad field x_markup"
)


def _partner_fake() -> FakeSchemaClient:
    return FakeSchemaClient(
        models={"res.partner", "res.users", "x_ticket"},
        fields={
            "x_ticket": {
                "x_partner_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "readonly": False,
                },
                "x_display": {
                    "type": "char",
                    "ttype": "char",
                    "readonly": True,
                    "related": "x_partner_id.name",
                },
            },
            "res.partner": {
                "name": {"type": "char", "ttype": "char", "readonly": False},
            },
        },
    )


def _draft_invent_counts(draft: dict[str, Any]) -> tuple[int, int, int]:
    field_total = o2m_total = 0
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            field_total += 1
            if field.get("ttype") == "one2many":
                o2m_total += 1
    menus = draft.get("menus")
    menu_total = len(menus) if isinstance(menus, list) else 0
    return field_total, o2m_total, menu_total


def _generate_ir_invent_counts(draft: dict[str, Any]) -> tuple[int, int, int]:
    ir = draft.get("_generate_ir")
    if not isinstance(ir, dict):
        return (-1, -1, -1)
    fields_by_model = ir.get("fields_by_model")
    field_total = (
        sum(len(rows) for rows in fields_by_model.values())
        if isinstance(fields_by_model, dict)
        else 0
    )
    return field_total, len(ir.get("o2ms") or []), len(ir.get("menus") or [])


def _assert_finish_seed_counts_match_generate_ir(draft: dict[str, Any]) -> None:
    ir_counts = _generate_ir_invent_counts(draft)
    assert ir_counts[0] >= 0, "expected _generate_ir on draft after _finish_seed_draft"
    assert _draft_invent_counts(draft) == ir_counts


def _maintenance_finish_seed_draft() -> dict[str, Any]:
    from app.ai_depth import apply_deterministic_depth
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_pipeline import seed_studio_draft

    draft = seed_studio_draft(_MAINTENANCE_BRIEF)
    draft["_schema_client"] = FakeSchemaClient(
        models={
            "res.partner",
            "res.users",
            "res.company",
            "product.product",
            "hr.employee",
            "purchase.order",
        },
        fields={
            "res.partner": {"name": {"ttype": "char", "readonly": False}},
            "product.product": {"name": {"ttype": "char", "readonly": False}},
        },
    )
    apply_deterministic_depth(draft, user_prompt=_MAINTENANCE_BRIEF)
    return _finish_seed_draft(_MAINTENANCE_BRIEF, draft, warnings=[])


def _brief_branch_hits(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        text = ast.unparse(node.test).lower()
        if (
            "maintenance" in text
            or "service.card" in text
            or "service card" in text
            or "service_card" in text
        ):
            hits.append(f"{path.name}:{node.lineno}")
    return hits


def _display_name_denylist_hits(path: Path) -> list[str]:
    """``if display_name == "…"`` (or ``in`` a string list) inside a condition."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        for compare in ast.walk(node.test):
            if not isinstance(compare, ast.Compare):
                continue
            mentions = False
            for sub in ast.walk(compare.left):
                if isinstance(sub, ast.Name) and sub.id == "display_name":
                    mentions = True
                if isinstance(sub, ast.Attribute) and sub.attr == "display_name":
                    mentions = True
                if isinstance(sub, ast.Constant) and sub.value == "display_name":
                    mentions = True
            if not mentions:
                continue
            for comparator, op in zip(compare.comparators, compare.ops, strict=True):
                if not isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                    continue
                values: list[Any] = []
                if isinstance(comparator, ast.Constant):
                    values = [comparator.value]
                elif isinstance(comparator, (ast.List, ast.Tuple, ast.Set)):
                    values = [
                        elt.value
                        for elt in comparator.elts
                        if isinstance(elt, ast.Constant)
                    ]
                named = [
                    value
                    for value in values
                    if isinstance(value, str) and value.strip() and value != "display_name"
                ]
                if named:
                    hits.append(f"{path.name}:{compare.lineno}")
    return hits


def _load_closed_class():
    path = _API / "tests" / "test_generate_ir_closed_class.py"
    spec = importlib.util.spec_from_file_location("_reg_np_t1_closed_class", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authored_draft() -> dict[str, Any]:
    return {
        "technical_name": "ext_markup_test",
        "display_name": "Markup test",
        "depends": ["sale"],
        "grain": "full_app",
        "models": [{"model": "sale.order", "mode": "inherit", "fields": []}],
        "custom_code_blocks": [
            {
                "option_a": True,
                "source_file": "models/sale_order.py",
                "content": (
                    "from odoo import models\n\n"
                    "class SaleOrder(models.Model):\n"
                    "    _inherit = 'sale.order'\n"
                ),
            }
        ],
        "_generation_engine": {
            "capability": "option_a_authored",
            "artifact_kind": "option_a_module",
            "delivery_lane": "module_sh_or_self",
            "prove_status": "pending",
        },
        "_user_prompt": (
            "On Sales Orders add markup percent with Python compute. "
            "Option A module zip → sandbox → Promote."
        ),
    }


def _ok_install(*, tests_ran: bool) -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        module="ext_markup_test",
        message="installed",
        log_tail="ok",
        job_id=None,
        tests_ran=tests_ran,
        test_failures=[],
    )


def _fail_install(msg: str) -> SimpleNamespace:
    return SimpleNamespace(
        ok=False,
        module="ext_markup_test",
        message=msg,
        log_tail=f"FAIL: {msg}",
        job_id=None,
        tests_ran=False,
        test_failures=[f"FAIL: {msg}"],
    )


def _patch_prove_install(
    monkeypatch: pytest.MonkeyPatch, install: Any, repair: Any | None = None
) -> None:
    monkeypatch.setattr(
        "app.module_spec_codec.export_draft_module_zip",
        lambda *_args, **_kwargs: b"PK\x03\x04fake",
    )
    monkeypatch.setattr("app.sandbox.run_sandbox_install", install)
    if repair is not None:
        monkeypatch.setattr("app.ai_option_a_feedback.repair_option_a_from_feedback", repair)


def test_ac2_offline_finish_calls_seed_and_locked_craft() -> None:
    source = inspect.getsource(studio_generate_offline_finish)
    assert "_finish_seed_draft" in source
    assert "_apply_locked_craft_and_surface" in source


def test_ac2_offline_finish_docstring_names_golden_entrypoint() -> None:
    doc = studio_generate_offline_finish.__doc__ or ""
    assert "Goldens must call" in doc
    assert "_finish_seed_draft" in doc


def test_ac2_finish_seed_counts_match_generate_ir() -> None:
    draft = _maintenance_finish_seed_draft()
    _assert_finish_seed_counts_match_generate_ir(draft)


def test_ac2_node_after_stamp_generate_ir_fails_count_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A field invented inside attach, which runs after stamp_generate_ir, breaks counts."""
    import app.ai_generation_engine as gen_engine

    real_attach = gen_engine.attach_generation_engine

    def _attach_with_post_invent(
        draft: dict[str, Any], prompt: str, *, user_phase: str = "review"
    ) -> dict[str, Any]:
        models = draft.get("models") or []
        if models and isinstance(models[0], dict):
            fields = list(models[0].get("fields") or [])
            fields.append({"name": "x_post_entrypoint_spray", "ttype": "char"})
            models[0]["fields"] = fields
        return real_attach(draft, prompt, user_phase=user_phase)

    monkeypatch.setattr(gen_engine, "attach_generation_engine", _attach_with_post_invent)
    draft = _maintenance_finish_seed_draft()
    with pytest.raises(AssertionError):
        _assert_finish_seed_counts_match_generate_ir(draft)


def test_ac4_fake_schema_client_positive_and_negative() -> None:
    client = _partner_fake()
    assert client.model_exists("res.partner") is True
    assert client.model_exists("x_invent_nowhere") is False
    assert "x_partner_id" in client.fields_get("x_ticket")
    assert client.fields_get("x_invent_nowhere") == {}
    assert client.relation_ok("x_ticket", "x_partner_id", "res.partner") is True
    assert client.relation_ok("x_ticket", "x_partner_id", "res.users") is False


def test_ac5_stale_catalog_denies_and_does_not_admit_field() -> None:
    now = time.time()
    draft: dict[str, Any] = {
        "_user_prompt": "Tickets with optional res.partner contact link",
        "_ambition": "thin",
        "_connection_catalog": {
            "available_models": ["res.partner", "sale.order"],
            "stock": [{"model": "res.partner"}],
            "loaded_at": now - SCHEMA_CATALOG_TTL_S - 10,
        },
        "_schema_fields": {
            "x_ticket": {
                "x_partner_id": {
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "readonly": False,
                }
            }
        },
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "_generate_ir": {"admitted": []},
    }
    client = schema_client_for_draft(draft, now=now)
    assert isinstance(client, DenySchemaClient)
    assert client.reason == "stale_or_missing_catalog_ts"
    assert client.model_exists("res.partner") is False
    ir, _notes = admit_and_apply(
        draft,
        [
            Proposal(
                kind="m2o",
                name="x_partner_id",
                payload={
                    "model": "x_ticket",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "string": "Contact",
                },
                source_cue="res.partner",
                proposer="test",
            )
        ],
    )
    names = {f.get("name") for f in draft["models"][0]["fields"] if isinstance(f, dict)}
    assert "x_partner_id" not in names
    rejected = {
        str(row.get("name")): str(row.get("reject_reason") or "")
        for row in ir.rejected_proposals
        if isinstance(row, dict) and row.get("name")
    }
    assert rejected.get("x_partner_id") == "stale_or_missing_catalog_ts"


def test_ac6_field_is_writable() -> None:
    client = _partner_fake()
    assert client.field_is_writable("x_ticket", "x_partner_id") is True
    assert client.field_is_writable("x_ticket", "x_display") is False
    assert client.field_is_writable("x_ticket", "nope") is False


def test_ac7_view_has_field_stays_as_built() -> None:
    assert DenySchemaClient().view_has_field("x_ticket", "x_partner_id") is False
    catalog = CatalogSchemaClient(models={"res.partner"}, loaded_at=time.time())
    assert catalog.view_has_field("res.partner", "name") is False
    listed = FakeSchemaClient(view_fields={"x_ticket": {"x_partner_id"}})
    assert listed.view_has_field("x_ticket", "x_partner_id") is True
    assert listed.view_has_field("x_ticket", "x_other") is False
    assert listed.view_has_field("res.partner", "name") is False

    class _Client:
        def execute_kw(
            self, model: str, method: str, args: list, kwargs: dict | None = None
        ) -> dict:
            del model, args, kwargs
            if method == "get_views":
                return {"views": {"form": {"arch": '<form><field name="partner_id"/></form>'}}}
            raise AssertionError(method)

    live = LiveSchemaClient(_Client())
    assert live.view_has_field("sale.order", "partner_id") is True
    assert live.view_has_field("sale.order", "amount_total") is False


def test_ac8_allowlist_constant_rejects_uncued_unlisted_node() -> None:
    """Negative only. Extra admit reasons are reported open on AC8."""
    assert isinstance(STRUCTURAL_ALLOWLIST, dict)
    assert STRUCTURAL_ALLOWLIST
    assert len(STRUCTURAL_ALLOWLIST) < 40
    assert all(isinstance(reason, str) and reason for reason in STRUCTURAL_ALLOWLIST.values())
    assert "x_name" in STRUCTURAL_ALLOWLIST
    draft: dict[str, Any] = {
        "_user_prompt": "Thin tickets Draft→Done only",
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
    }
    ir, _notes = admit_and_apply(
        draft,
        [
            Proposal(
                kind="field",
                name="x_name",
                payload={"model": "x_ticket", "ttype": "char"},
                source_cue=None,
                proposer="test",
            ),
            Proposal(
                kind="field",
                name="x_qqqz_marker",
                payload={"model": "x_ticket", "ttype": "char", "string": "Spray"},
                source_cue="structural_default",
                proposer="test",
            ),
        ],
    )
    assert any(
        row.get("name") == "x_name" and row.get("admit_reason") == "structural_default"
        for row in ir.admitted
    )
    assert any(
        row.get("name") == "x_qqqz_marker" and row.get("reject_reason") == "no_cue_or_craft"
        for row in ir.rejected_proposals
    )
    names = {f.get("name") for f in draft["models"][0]["fields"] if isinstance(f, dict)}
    assert "x_qqqz_marker" not in names


def test_ac9_rate_line_without_o2m_cue_rejects_one2many() -> None:
    draft: dict[str, Any] = {
        "_user_prompt": (
            "Build Maintenance tickets for a service desk: "
            "State Draft→Done; Online-honest on stock moves."
        ),
        "models": [
            {
                "model": "x_maintenance_tickets",
                "mode": "new",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "_understanding": {
            "constraint_ast": {"fields": [], "o2ms": [], "states": ["draft", "done"]}
        },
    }
    ir, _notes = admit_and_apply(
        draft,
        [
            Proposal(
                kind="o2m",
                name="x_rate_line_ids",
                payload={
                    "model": "x_maintenance_tickets",
                    "ttype": "one2many",
                    "relation": "x_maintenance_tickets_line",
                    "relation_field": "x_maintenance_tickets_id",
                    "string": "Rate Line",
                    "line_model": {
                        "model": "x_maintenance_tickets_line",
                        "description": "Rate Line",
                        "mode": "new",
                        "fields": [
                            {"name": "x_name", "ttype": "char"},
                            {
                                "name": "x_maintenance_tickets_id",
                                "ttype": "many2one",
                                "relation": "x_maintenance_tickets",
                            },
                        ],
                    },
                },
                source_cue="service",
                proposer="test.rate_line_regress",
            )
        ],
    )
    assert any(
        row.get("name") == "x_rate_line_ids" and row.get("reject_reason") == "uncued_line_invent"
        for row in ir.rejected_proposals
    ), ir.rejected_proposals
    assert not any(model.get("model") == "x_maintenance_tickets_line" for model in draft["models"])


def test_ac9_generic_many2one_res_partner_without_cue_rejected() -> None:
    fake = FakeSchemaClient(
        models={"res.partner", "x_ticket"},
        fields={"x_ticket": {}, "res.partner": {}},
    )
    draft: dict[str, Any] = {
        "_user_prompt": "Thin tickets Draft→Done only",
        "_schema_client": fake,
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
    }
    ir, _notes = admit_and_apply(
        draft,
        [
            Proposal(
                kind="m2o",
                name="x_partner_id",
                payload={
                    "model": "x_ticket",
                    "ttype": "many2one",
                    "relation": "res.partner",
                },
                source_cue=None,
                proposer="test",
            )
        ],
        schema_client=fake,
    )
    assert all(row.get("name") != "x_partner_id" for row in ir.admitted)
    assert any(
        row.get("name") == "x_partner_id" and row.get("reject_reason") == "no_cue_or_craft"
        for row in ir.rejected_proposals
    )


def test_ac10_sibling_golden_shares_module_and_has_no_brief_branch() -> None:
    closed = (_API / "tests" / "test_generate_ir_closed_class.py").read_text(encoding="utf-8")
    maintenance_at = closed.index("def test_maintenance_closed_ir_no_uncued_spray")
    sibling_at = closed.index("def test_service_cards_sibling_closed")
    assert maintenance_at > 0
    assert sibling_at > maintenance_at
    hits: list[str] = []
    for path in _GENERATE_IR_SOURCES:
        hits.extend(_brief_branch_hits(path))
    assert hits == []


def test_ac11_approved_craft_defaults_off_and_toggle_changes_xml() -> None:
    from module_generator import render_module_files

    from app.ai_conversation.understand import (
        APPROVED_CRAFT_KEYS,
        Understanding,
        coerce_approved_craft,
        default_approved_craft,
    )
    from app.ai_depth import _ensure_currency_on_amounts
    from app.ai_enrich import _build_form_arch, _field_list
    from app.ai_generate_ir import build_ir, stamp_generate_ir
    from app.module_spec_codec import draft_dict_to_module_spec

    expected = {key: False for key in APPROVED_CRAFT_KEYS}
    assert default_approved_craft() == expected
    assert coerce_approved_craft(None) == expected
    assert coerce_approved_craft({}) == expected
    assert not any(Understanding(title="Demo", grain="full_app").approved_craft.values())

    bare = {
        "display_name": "Maintenance Tickets",
        "models": [
            {"model": "x_ticket", "mode": "new", "fields": [{"name": "x_name", "ttype": "char"}]}
        ],
    }
    assert build_ir(bare).approved_craft == {}
    assert stamp_generate_ir(bare).approved_craft == {}

    def _views_xml(*, money_slots: bool) -> str:
        draft: dict[str, Any] = {
            "technical_name": "maint_craft_demo",
            "display_name": "Maintenance Tickets",
            "_user_prompt": "Build Maintenance tickets: checklist and parts, Draft→Done",
            "models": [
                {
                    "model": "x_ticket",
                    "mode": "new",
                    "description": "Ticket",
                    "fields": [
                        {"name": "x_name", "ttype": "char", "string": "Name"},
                        {"name": "x_amount", "ttype": "float", "string": "Amount"},
                    ],
                }
            ],
        }
        if money_slots:
            draft["_approved_craft"] = {"money_slots": True}
        _ensure_currency_on_amounts(draft)
        model = draft["models"][0]
        mid = str(model["model"])
        draft["views"] = [
            {
                "name": f"{mid}.form",
                "model": mid,
                "type": "form",
                "arch": _build_form_arch(
                    str(model.get("description") or mid),
                    _field_list(model),
                    odoo_major=19,
                    model_id=mid,
                ),
                "mode": "primary",
            }
        ]
        spec = draft_dict_to_module_spec(draft)
        files = render_module_files(spec)
        return files[f"{draft['technical_name']}/views/views.xml"]

    off_xml = _views_xml(money_slots=False)
    on_xml = _views_xml(money_slots=True)
    assert "x_currency_id" not in off_xml
    assert "x_currency_id" in on_xml
    assert on_xml != off_xml

    web = (_REPO / "apps/web/src/components/studio/ClarifyInterstitial.tsx").read_text(
        encoding="utf-8"
    )
    empty = web.split("function emptyApprovedCraft", 1)[1].split("function ", 1)[0]
    assert "true" not in empty.lower()
    assert "off by default" in web
    assert '{on ? "On" : "Off"}' in web


def test_ac13_default_max_repair_is_three() -> None:
    assert DEFAULT_MAX_REPAIR == 3


@pytest.mark.parametrize("asked", [3, 4])
def test_ac13_failing_installs_stop_at_three_and_are_not_install_ready(
    monkeypatch: pytest.MonkeyPatch, asked: int
) -> None:
    from app.ai_option_a_quality import prove_option_a_in_sandbox

    draft = _authored_draft()
    calls = {"n": 0}

    def install(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        calls["n"] += 1
        return _fail_install(f"boom attempt {calls['n']}")

    def repair(draft_in: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        count = int(draft_in.get("_sandbox_repair_count") or 0) + 1
        draft_in["_sandbox_repair_count"] = count
        return {
            "applied": True,
            "gate_status": "pass",
            "repair": {"ok": True, "bucket": "sandbox", "repair_count": count},
        }

    _patch_prove_install(monkeypatch, install, repair)
    out = prove_option_a_in_sandbox(
        draft, odoo_major=19, run_tests=True, auto_repair=True, max_attempts=asked
    )
    assert calls["n"] == 3
    assert out["prove_status"] == "failed"
    assert out["promote_eligible"] is False
    assert out["prove_status"] != "install_ready"
    assert draft.get("prove_status") != "install_ready"
    assert out.get("install_ready") is not True


def test_ac14_ac17_smoke_only_stays_pending_and_run_tests_proves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai_option_a_quality import prove_option_a_in_sandbox

    for path in (
        _APP / "ai_option_a_quality.py",
        _APP / "ai_class_stamp.py",
        _APP / "ai_repair_loop.py",
        _APP / "sandbox.py",
    ):
        assert "proved_smoke_only" not in path.read_text(encoding="utf-8")

    pending = _authored_draft()
    _patch_prove_install(monkeypatch, lambda *_a, **_k: _ok_install(tests_ran=False))
    out_pending = prove_option_a_in_sandbox(pending, odoo_major=19, run_tests=False)
    assert out_pending["prove_status"] == "pending"
    assert out_pending["promote_eligible"] is False

    proved = _authored_draft()

    def install_with_tests(*_args: Any, **kwargs: Any) -> SimpleNamespace:
        assert kwargs.get("run_tests") is True
        return _ok_install(tests_ran=True)

    monkeypatch.setattr("app.sandbox.run_sandbox_install", install_with_tests)
    out_proved = prove_option_a_in_sandbox(proved, odoo_major=19, run_tests=True)
    assert out_proved["prove_status"] == "proved"
    assert out_proved["promote_eligible"] is True


def test_ac15_verbatim_sandbox_log_keeps_traceback_and_redacts() -> None:
    from app.job_runner import _set_status
    from app.sandbox import sandbox_job_error_from_result, verbatim_sandbox_error_text

    secret = "password=reg-np-t1-secret"
    raw = f"{_TRACEBACK}\n{secret}\napi_key=sk-reg-np-t1-example"
    stored = verbatim_sandbox_error_text(message="Module install failed", log_tail=raw)
    assert _TRACEBACK in stored
    assert "ValidationError: bad field x_markup" in stored
    assert "reg-np-t1-secret" not in stored
    assert "sk-reg-np-t1-example" not in stored
    assert "[redacted]" in stored
    job_text = sandbox_job_error_from_result(
        {"ok": False, "message": "Module install failed", "log_tail": raw}
    )
    assert job_text is not None
    assert _TRACEBACK in job_text
    setter = inspect.getsource(_set_status)
    assert "row.error = error" in setter
    assert "error[" not in setter
    runner = (_APP / "job_runner.py").read_text(encoding="utf-8")
    assert "sandbox_job_error_from_result(result)" in runner
    assert "job_error[:" not in runner


def test_ac16_fast_ci_rejects_schema_invalid_and_slow_sandbox_is_separate() -> None:
    from app.ai_ollama import validate_draft_module_spec

    with pytest.raises(ValueError, match="x_"):
        validate_draft_module_spec(
            {
                "technical_name": "ok_mod",
                "display_name": "Ok",
                "models": [{"model": "book", "fields": [{"name": "x_name"}]}],
            }
        )
    ci = (_REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    api_unit = ci.split("api-unit:", 1)[1].split("\n  api-sandbox-prove-slow:", 1)[0]
    slow = ci.split("\n  api-sandbox-prove-slow:", 1)[1]
    assert "needs:" not in api_unit
    assert "tests/test_schema_invalid_module_output.py" in api_unit
    assert "tests/test_generate_ir_closed_class.py" in api_unit
    assert "tests/test_ai_schema_client.py" in api_unit
    assert "tests/test_sandbox_prove_slow.py" not in api_unit
    assert '-m "sandbox and slow"' not in api_unit
    assert '-m "sandbox and slow"' in slow
    ini = (_API / "pytest.ini").read_text(encoding="utf-8")
    assert "sandbox:" in ini
    assert "slow:" in ini
    slow_test = (_API / "tests" / "test_sandbox_prove_slow.py").read_text(encoding="utf-8")
    assert "pytest.mark.sandbox" in slow_test
    assert "pytest.mark.slow" in slow_test


def test_ac18_ac19_maintenance_and_service_cards_goldens_stay_green() -> None:
    closed = _load_closed_class()
    closed.test_maintenance_closed_ir_no_uncued_spray()
    closed.test_service_cards_sibling_closed()
    hits: list[str] = []
    for path in _GENERATE_IR_SOURCES:
        hits.extend(_brief_branch_hits(path))
    assert hits == []


def test_ac22_gates_hold_without_display_name_denylist() -> None:
    hits: list[str] = []
    for path in (*_GENERATE_IR_SOURCES, _APP / "ai_surface_invariants.py"):
        hits.extend(_display_name_denylist_hits(path))
        if path.name.startswith("ai_generate_ir"):
            hits.extend(_brief_branch_hits(path))
    assert hits == []
    now = time.time()
    client = schema_client_for_draft(
        {
            "_connection_catalog": {
                "available_models": ["res.partner"],
                "loaded_at": now - SCHEMA_CATALOG_TTL_S - 10,
            }
        },
        now=now,
    )
    assert isinstance(client, DenySchemaClient)
    assert client.reason == "stale_or_missing_catalog_ts"
    assert client.model_exists("res.partner") is False
