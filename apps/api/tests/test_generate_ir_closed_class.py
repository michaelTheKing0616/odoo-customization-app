"""Closed GenerateIR fidelity — flips handoff §3/§4 Nos that are code-provable.

Harness = seed → depth → ``studio_generate_offline_finish`` (PR-F.0 Studio
Generate AI-off path). Injects ``FakeSchemaClient`` so Tier-1/2 gates consult
live-schema facade (PR-F). Mac UI Install walkthrough remains operator §9.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_depth import apply_deterministic_depth  # noqa: E402
from app.ai_draft_jobs import studio_generate_offline_finish  # noqa: E402
from app.ai_generate_ir import (  # noqa: E402
    Proposal,
    build_ir,
    ir_closure_violations,
    proposal_allowed,
)
from app.ai_generate_ir_lint import invent_outside_admit_violations  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from app.ai_schema_client import FakeSchemaClient, schema_client_for_draft  # noqa: E402

MAINTENANCE = (
    "Build Maintenance tickets: checklist lines with done flags, parts used (product + qty), "
    "state Draft→Done; Online-honest on stock moves."
)
VISITOR = (
    "Build a Visitor Log: Name, Company (link to Contact), Visit date, "
    "Purpose selection (Meeting / Delivery / Other), Host (link to Employee). "
    "Menu under Contacts or Reception."
)
SERVICE_CARDS = (
    "Build Service cards: checklist lines with done flags, parts used (product + qty), "
    "state Draft→Done; Online-honest on stock moves."
)

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
_GENERATE_IR_BRIEF_BRANCH_SOURCES = (
    _APP_DIR / "ai_generate_ir.py",
    _APP_DIR / "ai_generate_ir_enforce.py",
)


def _brief_lexeme_forbidden_in_string(value: str) -> bool:
    low = value.lower()
    return (
        "maintenance" in low
        or "service card" in low
        or "service.card" in low
        or "service_card" in low
    )


def _forbidden_lexeme_in_identifier(name: str) -> bool:
    low = name.lower().replace(".", "_")
    if "maintenance" in low:
        return True
    return "service_card" in low or "servicecard" in low


def _if_test_mentions_forbidden_lexeme(test: ast.AST) -> bool:
    """True when an ``if`` / ``elif`` condition (not a comment) names golden siblings."""
    for node in ast.walk(test):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _brief_lexeme_forbidden_in_string(node.value):
                return True
        if isinstance(node, ast.Name) and _forbidden_lexeme_in_identifier(node.id):
            return True
        if isinstance(node, ast.Attribute) and _forbidden_lexeme_in_identifier(node.attr):
            return True
    return False


def _brief_lexical_branch_violations(source_path: Path) -> list[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _if_test_mentions_forbidden_lexeme(node.test):
            hits.append(f"{source_path.name}:{node.lineno}")
    return hits


def test_generate_ir_sources_forbid_brief_maintenance_or_service_card_branch() -> None:
    """T1-GATE: GenerateIR must not ``if`` / ``elif`` on Maintenance or Service cards."""
    violations: list[str] = []
    for path in _GENERATE_IR_BRIEF_BRANCH_SOURCES:
        violations.extend(_brief_lexical_branch_violations(path))
    assert not violations, (
        "GenerateIR modules must not branch on brief text maintenance or service card; "
        f"found: {', '.join(violations)}"
    )


def _stock_fake() -> FakeSchemaClient:
    """Minimal CE stock graph for schema_verified_reuse on the finish harness."""
    return FakeSchemaClient(
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
            "res.users": {"name": {"ttype": "char", "readonly": False}},
            "res.company": {"name": {"ttype": "char", "readonly": False}},
            "product.product": {"name": {"ttype": "char", "readonly": False}},
            "hr.employee": {"name": {"ttype": "char", "readonly": False}},
            "purchase.order": {"name": {"ttype": "char", "readonly": False}},
        },
    )


def _finish(brief: str) -> dict:
    """PR-F.0 + PR-F: Studio Generate AI-off path with Fake schema grounding."""
    draft = seed_studio_draft(brief)
    draft["_schema_client"] = _stock_fake()
    apply_deterministic_depth(draft, user_prompt=brief)
    return studio_generate_offline_finish(brief, draft, warnings=[])


def _fields(draft: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        for f in m.get("fields") or []:
            if isinstance(f, dict) and f.get("name"):
                out[f"{mid}.{f['name']}"] = f
    return out


def test_finish_entrypoint_keeps_fake_schema_client() -> None:
    """PR-F Tier1: confirmed entrypoint retains injected FakeSchemaClient."""
    draft = seed_studio_draft(MAINTENANCE)
    fake = _stock_fake()
    draft["_schema_client"] = fake
    apply_deterministic_depth(draft, user_prompt=MAINTENANCE)
    out = studio_generate_offline_finish(MAINTENANCE, draft, warnings=[])
    assert schema_client_for_draft(out) is fake
    assert invent_outside_admit_violations(out) == []


def test_visitor_keeps_cued_company_contact_and_purpose_selection() -> None:
    draft = _finish(VISITOR)
    by = _fields(draft)
    company = by.get("x_visitor_log.x_company_id")
    assert company is not None
    assert company.get("relation") == "res.partner"
    purpose = by.get("x_visitor_log.x_purpose") or by.get("x_visitor_log.x_purpose_selection")
    assert purpose is not None
    assert purpose.get("ttype") == "selection"
    assert "meeting" in str(purpose.get("selection") or "").lower()
    assert ir_closure_violations(draft) == []
    assert invent_outside_admit_violations(draft) == []


def test_maintenance_closed_ir_no_uncued_spray() -> None:
    draft = _finish(MAINTENANCE)
    blob = " ".join(
        f"{f.get('name')}:{f.get('relation')}"
        for f in _fields(draft).values()
    )
    assert "purchase.order" not in blob
    assert "res.company" not in blob or "multi" in str(draft.get("_user_prompt") or "").lower()
    # Contact only if cued — Maintenance does not cue Contact Identity spray.
    partners = [
        k
        for k, f in _fields(draft).items()
        if f.get("relation") == "res.partner"
        and str(f.get("name") or "") in {
            "x_partner_id",
            "x_contact_id",
            "x_customer_id",
            "x_client_id",
        }
    ]
    assert partners == []
    assert invent_outside_admit_violations(draft) == []
    closure = draft.get("_generate_ir_closure") or {}
    assert closure.get("ok") is True or not ir_closure_violations(draft)


def test_service_cards_sibling_closed() -> None:
    draft = _finish(SERVICE_CARDS)
    assert invent_outside_admit_violations(draft) == []
    models = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    assert models, "expected residual header"
    assert not any(m.endswith("_party") for m in models)


def test_maintenance_o2ms_subseteq_generate_ir() -> None:
    """Wave 3: Install-facing O2Ms must be stamped on GenerateIR.o2ms."""
    from app.ai_generate_ir import draft_o2ms_outside_ir, o2ms_for_install

    draft = _finish(MAINTENANCE)
    install = o2ms_for_install(draft)
    assert install, "expected checklist/parts O2Ms on IR"
    names = {str(r.get("name")) for r in install}
    assert any("checklist" in n for n in names)
    assert any("parts" in n for n in names)
    assert draft_o2ms_outside_ir(draft) == []
    # Menus present after admit path (root + document or pruned set)
    menus = draft.get("menus") or []
    assert isinstance(menus, list)


def test_invent_outside_admit_flags_density_source() -> None:
    """CI: thin finish must fail when invent-source fields lack admit."""
    draft = {
        "_user_prompt": "thin residual tickets Draft→Done",
        "_ambition": "thin",
        "_document_shape": "register",
        "grain": "full_app",
        "models": [
            {
                "model": "x_tickets",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_pad_field",
                        "ttype": "char",
                        "string": "Pad",
                        "source": "density",
                    },
                ],
            }
        ],
        "_generate_ir": {"admitted": [{"name": "x_name"}]},
    }
    hits = invent_outside_admit_violations(draft)
    assert any("x_pad_field" in h for h in hits)


def test_uncued_not_allowlisted_not_schema_verified_rejected() -> None:
    """PR-B: uncued + not allowlisted + not schema-verified must reject.

    Today this would have been admitted by source_cue=structural_default or by
    the quality_scaffold / density_role proposer shortcuts.
    """
    draft = {
        "_user_prompt": "Thin tickets Draft→Done only",
        "_understanding": {"must_do": ["State Draft→Done"]},
        "models": [{"model": "x_ticket", "mode": "new", "fields": []}],
    }
    ir = build_ir(draft)
    tagged = Proposal(
        kind="m2o",
        name="x_partner_id",
        payload={
            "model": "x_ticket",
            "ttype": "many2one",
            "relation": "res.partner",
            "string": "Contact",
        },
        source_cue="structural_default",
        proposer="test.structural_default_tag",
    )
    ok, reason = proposal_allowed(tagged, ir=ir, draft=draft)
    assert ok is False
    assert reason == "no_cue_or_craft"

    scaffold = Proposal(
        kind="field",
        name="x_pad_field",
        payload={"model": "x_ticket", "ttype": "char", "string": "Pad"},
        source_cue=None,
        proposer="ai_model_quality.ensure_min_workflows",
    )
    ok, reason = proposal_allowed(scaffold, ir=ir, draft=draft)
    assert ok is False
    assert reason == "no_cue_or_craft"


def test_purge_owns_uncued_spray_removal() -> None:
    """Wave 4 — scrub deleted; purge_unadmitted_spray owns spray removal."""
    from app.ai_generate_ir_enforce import purge_unadmitted_spray
    from app.ai_odoo_app_bar import _scrub_mutate_enabled

    assert _scrub_mutate_enabled() is False
    draft = {
        "_user_prompt": "thin residual without partner cue",
        "_ambition": "thin",
        "_document_shape": "register",
        "grain": "full_app",
        "models": [
            {
                "model": "x_thing",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            }
        ],
        "_generate_ir": {"admitted": [{"name": "x_name"}]},
    }
    notes = purge_unadmitted_spray(draft)
    assert notes
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_partner_id" not in names


def test_scrub_uncued_must_do_asserts_on_uncued_date() -> None:
    """T1-RET negative — uncued Date Must-do must not reach assert-only scrub."""
    from app.ai_brief_cues import scrub_uncued_invent_must_do_rows

    with pytest.raises(AssertionError):
        scrub_uncued_invent_must_do_rows(
            ["Date"],
            prompt="Build tickets with name only",
        )
