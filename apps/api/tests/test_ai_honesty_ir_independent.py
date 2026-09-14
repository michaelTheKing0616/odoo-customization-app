"""Independent CHECKER suite: honesty IR / Draft Studio (AI-off).

Authoritative spec is the rubric in the checker mission — not maker tests.
Calls production entry points the way Draft Studio does.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.ai_architecture_plan import (
    architecture_plan_drift,
    build_architecture_plan,
    stamp_architecture_plan,
)
from app.ai_certification import build_certification, stamp_certification
from app.ai_depth import depth_gaps
from app.ai_document_shape import (
    allowed_bridge_modules,
    classify_document_shape,
    clip_llm_models_to_plan,
    clip_missing_models_to_budget,
    forbidden_stock_hosts,
    honor_operator_brief,
    llm_models_outside_plan,
    may_add_line_satellite,
    may_add_party_satellite,
    naming_from_residual,
    stamp_document_shape,
)
from app.ai_domain_nouns import domain_noun_coverage, extract_prompt_nouns
from app.ai_domain_packs import match_domain_pack
from app.ai_draft_jobs import _finish_seed_draft, complete_matched_pack_draft
from app.ai_draft_scorecard import attach_scorecard, draft_scorecard
from app.ai_enrich_jobs import finalize_enriched_draft
from app.ai_generation_engine import is_stock_reuse_draft
from app.ai_grain import classify_grain
from app.ai_llm_status import banner_for_mode
from app.ai_domain_density import ensure_domain_density
from app.ai_odoo_app_bar import (
    close_odoo_architecture,
    ensure_residual_satellites,
    ensure_stock_inherit_bridges,
    prune_generic_loop_models,
)
from app.ai_ollama import _build_prompt_with_context
from app.ai_operator_brief import (
    build_operator_brief,
    prompt_for_generators,
    stated_residual_kind,
)
from app.ai_pipeline import seed_studio_draft
from app.ai_prompt_constants import few_shot_exemplar_block
from app.expert.draft_review import (
    _worse_after_closer,
    apply_deterministic_scorecard_fixes,
)
from app.llm_provider import LLMError, generate_json_with_timeout_retry

# --- Prompts constructed from the rubric (not copied from maker suites) ---

VISITOR_LOG = (
    "I want a simple visitor log in Odoo: visitor name, who they came to see "
    "(an hr.employee host), purpose, time in, time out, and optional ID number. "
    "Optional res.partner only unless they are already a contact. This is not CRM "
    "and not a second Contacts app. Don't invent invoicing. Do not use Python. "
    "If they stay more than two hours, a no-code alert would be nice. Reception "
    "sits at a desk in Accra. Completeness 10.0 is not Certification Production."
)

SLA_INVOICES = (
    "Add an SLA due date field on invoices. Inherit the stock account.move form. "
    "Do not open a restaurant pack and do not invent a new Invoices app menu."
)

POS_STOCK_FIRST = (
    "Configure Community Point of Sale together with Invoicing.\n"
    "## Custom residual\n"
    "None\n"
    "## Capability path\n"
    "stock_first\n"
    "Receipts stay stock until a separate Option A."
)

HOTEL_LODGING = (
    "We operate a hotel with lodging, guest rooms, housekeeping, and "
    "front-desk check-in plus check-out for overnight guests."
)

CASHIERS_NO_MENU = (
    "Cashiers shouldn't see a new menu — they keep the existing POS screen; "
    "do not install a restaurant dining app."
)

LAW_FIRM_MATTERS = (
    "Law-firm practice management: matter files plus stock invoices on "
    "account.move. This is not a visitor register and not a guestbook."
)

DONT_INVENT_INVOICING = (
    "I want a simple visitor log in Odoo for the lobby book. Don't invent invoicing."
)

DONT_INVENT_PARALLEL_INVOICE = (
    "Law firm matter management that invoices clients on stock account.move. "
    "Do not invent a parallel invoice."
)

POLICY_PLUS_STOCK = (
    "Custom residual is the policy file. Reuse Sales quotations and Invoicing "
    "(account.move). Keep both stock apps; do not collapse this to a one-row register."
)

CHAINED_NEGATION = (
    "I want a simple visitor log in Odoo. This is not CRM and not a second Contacts app."
)

SLA_NAMED_FROM_GOAL = (
    "Goal: add SLA due date on customer invoices so finance can chase late bills.\n"
    "## Custom residual\n"
    "\n"
)

LONG_VISITOR_BOOK = (
    "Please build a simple visitor book for the lobby so the receptionist can "
    "write down each guest who arrives during office hours and who they came to "
    "see, without turning this request into a comprehensive workspace, ERP, or "
    "practice-management system with extra satellites."
)


def _model_ids(draft: dict[str, Any]) -> list[str]:
    return [
        str(m.get("model") or "")
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    ]


def _new_x_ids(draft: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        if mid.startswith("x_") and str(m.get("mode") or "new") != "inherit":
            out.append(mid)
    return out


def _inherit_ids(draft: dict[str, Any]) -> list[str]:
    return [
        str(m.get("model") or "")
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("mode") or "") == "inherit"
        and m.get("model")
    ]


def _field_names(draft: dict[str, Any], mid: str) -> set[str]:
    for m in draft.get("models") or []:
        if isinstance(m, dict) and m.get("model") == mid:
            return {
                str(f.get("name") or "")
                for f in (m.get("fields") or [])
                if isinstance(f, dict)
            }
    return set()


def _field_relations(draft: dict[str, Any]) -> set[str]:
    rels: set[str] = set()
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        for f in m.get("fields") or []:
            if isinstance(f, dict) and f.get("relation"):
                rels.add(str(f["relation"]))
    return rels


def _close_ai_off(prompt: str) -> dict[str, Any]:
    """Production AI-off path: seed then finish (no LLM, no HTTP)."""
    warnings: list[str] = []
    seed = seed_studio_draft(prompt)
    return _finish_seed_draft(prompt, seed, warnings)


def _satellite_ids(draft: dict[str, Any]) -> list[str]:
    return [
        mid
        for mid in _model_ids(draft)
        if mid.endswith("_party") or mid.endswith("_line")
    ]


# ---------------------------------------------------------------------------
# Wave 0 — Golden prompt-fit (AI off: seed + finish)
# ---------------------------------------------------------------------------


class TestWave0GoldenPromptFit:
    def test_visitor_log_is_one_header_not_crm_or_invoice(self) -> None:
        draft = _close_ai_off(VISITOR_LOG)
        ids = _model_ids(draft)
        x_ids = _new_x_ids(draft)
        assert len(x_ids) == 1, x_ids
        assert x_ids[0] == "x_visitor_log"
        assert "crm.lead" not in ids
        assert "account.move" not in ids
        assert not any(mid.endswith("_party") or mid.endswith("_line") for mid in ids)
        depends = {str(d) for d in (draft.get("depends") or [])}
        assert "hr" in depends
        assert "mail" in depends
        assert "crm" not in depends
        fields = _field_names(draft, "x_visitor_log")
        assert "x_name" in fields
        assert "x_employee_id" in fields
        assert "x_purpose" in fields
        assert "x_time_in" in fields
        assert "x_time_out" in fields
        rels = _field_relations(draft)
        assert "hr.employee" in rels
        assert "res.partner" in rels
        cert = draft.get("_certification") or {}
        score = (draft.get("_scorecard") or {}).get("score_0_10")
        if score is not None and float(score) >= 9.9:
            assert cert.get("tier") != "Production"
            assert cert.get("tier") != "Gold"
        display = str(draft.get("display_name") or "")
        assert display.lower() == "visitor log"
        assert "completeness" not in display.lower()
        assert "i want" not in display.lower()
        status = draft.get("_llm_status") or {}
        assert status.get("mode") == "pack_fallback"
        assert status.get("reason") == "honesty_seed"
        live = draft.get("_live_apply") or {}
        assert live.get("certification_tier") == "ReviewRequired"
        assert (draft.get("_certification") or {}).get("tier") == "ReviewRequired"
        card = draft.get("_scorecard") or {}
        assert float(card.get("score_0_10") or 0) >= 10.0
        dims = card.get("dimensions") or {}
        assert float(dims.get("domain_fit") or 0) >= 10.0
        assert not any(
            str(f.get("element") or "") == "attorney" for f in (card.get("findings") or [])
        )
        brief = draft.get("_operator_brief") or {}
        assert str(brief.get("country") or "") == "Ghana"

    def test_visitor_seed_without_finish_is_already_a_header(self) -> None:
        seed = seed_studio_draft(VISITOR_LOG)
        assert classify_document_shape(VISITOR_LOG, seed) == "register"
        x_ids = _new_x_ids(seed)
        assert x_ids == ["x_visitor_log"]
        assert seed.get("domain_pack") not in {"restaurant", "law_firm", "hotel"}

    def test_sla_on_invoices_is_field_pack_not_restaurant(self) -> None:
        assert classify_grain(SLA_INVOICES) == "field_pack"
        draft = _close_ai_off(SLA_INVOICES)
        assert draft.get("grain") == "field_pack" or draft.get("_component")
        assert draft.get("domain_pack") != "restaurant"
        ids = _model_ids(draft)
        assert "account.move" in ids
        assert not any(str(m).startswith("x_") and str(m) not in ids for m in ids)
        assert "x_visitor_log" not in ids
        assert not _satellite_ids(draft)
        inherit = _inherit_ids(draft)
        assert "account.move" in inherit or "account.move" in ids

    def test_stock_first_residual_none_pos_is_empty_stock_reuse(self) -> None:
        draft = _close_ai_off(POS_STOCK_FIRST)
        assert is_stock_reuse_draft(draft)
        engine = draft.get("_generation_engine") or {}
        assert engine.get("capability") == "stock_reuse"
        assert _new_x_ids(draft) == []
        assert classify_document_shape(POS_STOCK_FIRST, draft) == "stock_reuse"

    def test_hotel_with_lodging_collocates_still_matches_hotel_pack(self) -> None:
        matched = match_domain_pack(HOTEL_LODGING)
        assert matched is not None
        assert matched[0] == "hotel"
        draft = _close_ai_off(HOTEL_LODGING)
        assert draft.get("domain_pack") == "hotel"
        shape = classify_document_shape(HOTEL_LODGING, draft)
        assert shape == "workspace"
        assert "x_visitor_log" not in _model_ids(draft)
        assert len(_new_x_ids(draft)) > 1

    def test_cashiers_shouldnt_see_new_menu_is_not_restaurant(self) -> None:
        matched = match_domain_pack(CASHIERS_NO_MENU)
        if matched is not None:
            assert matched[0] != "restaurant"
        draft = _close_ai_off(CASHIERS_NO_MENU)
        assert draft.get("domain_pack") != "restaurant"

    def test_law_firm_pack_is_matters_plus_invoices_not_visitor_register(self) -> None:
        matched = match_domain_pack(LAW_FIRM_MATTERS)
        assert matched is not None
        assert matched[0] == "law_firm"
        draft = _close_ai_off(LAW_FIRM_MATTERS)
        assert draft.get("domain_pack") == "law_firm"
        assert classify_document_shape(LAW_FIRM_MATTERS, draft) == "workspace"
        ids = _model_ids(draft)
        assert "x_visitor_log" not in ids
        assert any("matter" in mid for mid in ids)
        assert "account.move" in ids or "account" in {
            str(d) for d in (draft.get("depends") or [])
        }


# ---------------------------------------------------------------------------
# Wave 1 — Operator brief honesty IR
# ---------------------------------------------------------------------------


class TestWave1OperatorBrief:
    def test_chained_negation_splits_crm_and_contacts_not_glued_fragment(self) -> None:
        brief = build_operator_brief(CHAINED_NEGATION)
        scope = [str(x).lower() for x in brief.out_of_scope]
        glued = [x for x in scope if "crm and not" in x or "crm and" in x]
        assert not glued, scope
        assert "crm" in scope
        assert any("contact" in x for x in scope), scope
        assert "contacts_app" in scope or any(x == "contacts_app" for x in scope)

    def test_dont_invent_invoicing_forbids_account_bridge_not_stock_reuse_wording(self) -> None:
        brief = build_operator_brief(DONT_INVENT_INVOICING)
        assert "account" in brief.forbidden_bridges
        blob = " ".join(brief.out_of_scope).lower() + " " + " ".join(brief.forbidden_bridges)
        assert "stock_reuse includes account" not in blob
        formatted = prompt_for_generators(DONT_INVENT_INVOICING)
        assert "account" in formatted.lower() or "account" in brief.forbidden_bridges
        assert "crm" in brief.forbidden_bridges or "crm" not in DONT_INVENT_INVOICING.lower()
        # Visitor log must not treat "don't invent invoicing" as "reuse Accounting"
        assert "account" not in [a.lower() for a in brief.stock_reuse]

    def test_named_residual_from_goal_when_custom_residual_section_empty(self) -> None:
        kind, noun = stated_residual_kind(VISITOR_LOG)
        assert kind == "named"
        assert "visitor" in noun.lower()
        brief = build_operator_brief(VISITOR_LOG)
        assert "visitor" in (brief.custom_residual or "").lower()
        sla_kind, sla_noun = stated_residual_kind(SLA_NAMED_FROM_GOAL)
        sla_brief = build_operator_brief(SLA_NAMED_FROM_GOAL)
        assert sla_kind == "named"
        assert "sla" in sla_noun.lower()
        assert "sla" in (sla_brief.custom_residual or "").lower()

    def test_accra_does_not_invent_industry_or_company(self) -> None:
        brief = build_operator_brief(VISITOR_LOG)
        unknown = [u.lower() for u in brief.unknowns]
        assert not any(u == "country" or u.startswith("country") for u in unknown)
        assert not brief.industry
        assert "oil" not in (brief.industry or "").lower()
        assert any("company" in u for u in unknown)

    def test_accra_gazetteer_records_ghana_in_operator_ir(self) -> None:
        brief = build_operator_brief(VISITOR_LOG)
        blob = json.dumps(brief.to_dict()).lower()
        assert "ghana" in blob or "ghana" in brief.formatted.lower()

    def test_capability_path_stock_first_only_when_residual_none(self) -> None:
        named = build_operator_brief(VISITOR_LOG)
        assert named.capability_path == "residual_app"
        none = build_operator_brief(POS_STOCK_FIRST)
        assert none.capability_path == "stock_first"
        assert stated_residual_kind(POS_STOCK_FIRST)[0] == "none"

    def test_prompt_for_generators_includes_forbidden_bridges(self) -> None:
        text = prompt_for_generators(CHAINED_NEGATION)
        low = text.lower()
        assert "crm" in low
        assert "forbidden" in low
        invoicing = prompt_for_generators(DONT_INVENT_INVOICING)
        assert "account" in invoicing.lower()


# ---------------------------------------------------------------------------
# Wave 2 — Additive closer gated on shape
# ---------------------------------------------------------------------------


class TestWave2AdditiveCloser:
    def test_register_skips_satellites_density_loops_and_unnamed_bridges(self) -> None:
        draft = _close_ai_off(VISITOR_LOG)
        assert classify_document_shape(VISITOR_LOG, draft) == "register"
        assert not _satellite_ids(draft)
        assert "crm.lead" not in _inherit_ids(draft)
        assert "account.move" not in _inherit_ids(draft)
        assert "sale.order" not in _inherit_ids(draft)
        # Host named in the brief (employee) is a field, not a cloned HR app
        assert "hr.employee" in _field_relations(draft)
        assert "x_employee" not in _new_x_ids(draft)
        # Density / operational-loop seeds
        loopish = {
            mid
            for mid in _new_x_ids(draft)
            if any(
                tok in mid
                for tok in ("deposit", "task", "bill", "event", "milestone", "fee")
            )
        }
        assert not loopish, loopish

    def test_field_pack_skips_satellites_and_density(self) -> None:
        draft = _close_ai_off(SLA_INVOICES)
        assert not _satellite_ids(draft)
        assert len(_new_x_ids(draft)) == 0
        assert "restaurant" != draft.get("domain_pack")

    def test_transactional_header_line_only_if_prompt_names_lines(self) -> None:
        bare = {
            "_user_prompt": "I want a booking in Odoo for studio sessions.",
            "models": [
                {
                    "model": "x_booking",
                    "mode": "new",
                    "fields": [{"name": "x_name", "ttype": "char"}],
                }
            ],
        }
        stamp_document_shape(bare, prompt=bare["_user_prompt"])
        assert classify_document_shape(bare["_user_prompt"], bare) in {
            "transactional_header",
            "workspace",
        }
        if classify_document_shape(bare["_user_prompt"], bare) == "transactional_header":
            assert may_add_line_satellite(bare, prompt=bare["_user_prompt"]) is False
            assert may_add_party_satellite(bare, prompt=bare["_user_prompt"]) is False
        lined = dict(bare)
        lined["_user_prompt"] = "I want a booking in Odoo with lines and items."
        lined["_document_shape"] = "transactional_header"
        assert may_add_line_satellite(lined, prompt=lined["_user_prompt"]) is True
        roles = dict(bare)
        roles["_user_prompt"] = "I want a booking in Odoo with parties and attendees."
        roles["_document_shape"] = "transactional_header"
        assert may_add_party_satellite(roles, prompt=roles["_user_prompt"]) is True

    def test_stock_bridges_need_positive_reuse_and_not_out_of_scope(self) -> None:
        draft: dict[str, Any] = {
            "_user_prompt": DONT_INVENT_INVOICING,
            "_document_shape": "workspace",
            "depends": ["mail", "account", "hr"],
            "models": [
                {
                    "model": "x_visitor_log",
                    "mode": "new",
                    "fields": [{"name": "x_name", "ttype": "char"}],
                }
            ],
        }
        from app.ai_operator_brief import attach_operator_brief

        attach_operator_brief(draft, user_prompt=DONT_INVENT_INVOICING)
        allowed = allowed_bridge_modules(draft, prompt=DONT_INVENT_INVOICING)
        assert "account" not in allowed
        hosts = forbidden_stock_hosts(draft)
        assert "account.move" in hosts
        ensure_stock_inherit_bridges(draft)
        assert "account.move" not in _inherit_ids(draft)

    def test_prune_generic_loop_does_not_keep_three_model_floor_on_register(self) -> None:
        prompt = "I want a simple visitor log in Odoo."
        draft: dict[str, Any] = {
            "_user_prompt": prompt,
            "_document_shape": "register",
            "_architecture_plan": {
                "document_shape": "register",
                "surface_budget": {"new_models": 1},
                "new_x_models": ["x_visitor_log"],
            },
            "models": [
                {"model": "x_visitor_log", "mode": "new", "fields": [{"name": "x_name"}]},
                {"model": "x_deposit", "mode": "new", "fields": [{"name": "x_name"}]},
                {"model": "x_task", "mode": "new", "fields": [{"name": "x_name"}]},
                {"model": "x_bill", "mode": "new", "fields": [{"name": "x_name"}]},
            ],
        }
        prune_generic_loop_models(draft, user_prompt=prompt)
        x_ids = _new_x_ids(draft)
        assert "x_visitor_log" in x_ids
        assert "x_deposit" not in x_ids
        assert "x_task" not in x_ids
        assert "x_bill" not in x_ids
        assert len(x_ids) == 1, x_ids

    def test_duration_alert_is_no_code_on_time_not_python_or_new_model(self) -> None:
        draft = _close_ai_off(VISITOR_LOG)
        assert _new_x_ids(draft) == ["x_visitor_log"]
        autos = [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
        timed = [a for a in autos if str(a.get("trigger") or "") == "on_time"]
        assert timed, autos
        assert len(timed) == 1, [a.get("name") for a in timed]
        blob = json.dumps(timed).lower()
        assert "next_activity" in blob
        assert "python" not in blob
        assert str(timed[0].get("state") or "") != "code"
        assert not (draft.get("custom_code_blocks") or [])

    def test_unpacked_register_seed_is_not_five_model_workspace(self) -> None:
        from app.ai_domain_briefing import build_domain_briefing
        from app.ai_pipeline import seed_unpacked_draft

        seed = seed_unpacked_draft(
            VISITOR_LOG,
            briefing=build_domain_briefing(VISITOR_LOG),
            ambition="comprehensive",
        )
        assert len(_new_x_ids(seed)) == 1
        assert seed.get("_document_shape") == "register"
        ensure_domain_density(seed, user_prompt=VISITOR_LOG, ambition="comprehensive")
        ensure_residual_satellites(seed)
        assert len(_new_x_ids(seed)) == 1
        assert not _satellite_ids(seed)


# ---------------------------------------------------------------------------
# Wave 3 — Flash as field-filler
# ---------------------------------------------------------------------------


class TestWave3FlashFieldFiller:
    def test_flash_prompt_includes_locked_plan_and_operator_brief(self) -> None:
        brief = build_operator_brief(VISITOR_LOG)
        plan = {
            "document_shape": "register",
            "new_x_models": ["x_visitor_log"],
            "forbidden_clones": ["x_bill", "x_invoice"],
            "forbidden_hosts": ["crm.lead", "account.move"],
            "surface_budget": {"new_models": 1, "new_js": 0, "new_controllers": 0},
        }
        blob = _build_prompt_with_context(
            VISITOR_LOG,
            architecture_plan=plan,
            document_shape="register",
            operator_brief=brief.formatted,
        )
        assert "LOCKED architecture_plan" in blob
        assert "OPERATOR BRIEF CONTRACT" in blob
        assert "Document shape: register" in blob
        assert "Original operator message (verbatim — authoritative)" in blob
        assert "Upstream operator brief IR (may be wrong" in blob
        assert "Source of truth" in blob
        assert "x_visitor_log" in blob
        assert '"document_shape": "register"' in blob or "register" in blob
        assert "surface_budget" in blob
        assert "# Operator brief" in blob or "Custom residual" in blob
        assert "forbidden" in blob.lower()

    def test_extra_models_versus_plan_are_invalid_and_clipped(self) -> None:
        plan = {
            "document_shape": "register",
            "new_x_models": ["x_visitor_log"],
            "surface_budget": {"new_models": 1},
        }
        draft: dict[str, Any] = {
            "_architecture_plan": plan,
            "_document_shape": "register",
            "models": [
                {"model": "x_visitor_log", "mode": "new", "fields": []},
                {"model": "x_visitor_log_party", "mode": "new", "fields": []},
                {"model": "x_deposit", "mode": "new", "fields": []},
            ],
        }
        extra = llm_models_outside_plan(draft, plan)
        assert "x_deposit" in extra
        assert "x_visitor_log_party" in extra
        clip_llm_models_to_plan(draft, plan)
        assert _new_x_ids(draft) == ["x_visitor_log"]

    def test_critique_missing_models_past_budget_are_dropped(self) -> None:
        draft: dict[str, Any] = {
            "_document_shape": "register",
            "_architecture_plan": {
                "document_shape": "register",
                "new_x_models": ["x_visitor_log"],
                "surface_budget": {"new_models": 1},
            },
            "models": [{"model": "x_visitor_log", "mode": "new"}],
        }
        missing = [
            {"model": "x_deposit", "description": "pad"},
            {"model": "x_visitor_log_line", "description": "line"},
        ]
        kept = clip_missing_models_to_budget(draft, missing)
        assert kept == []

    def test_generate_json_retries_http_503_unavailable_not_timeouts_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.llm_provider.time.sleep", lambda *_a, **_k: None)

        class Flaky503:
            def __init__(self) -> None:
                self.calls = 0

            def generate_json(self, **_kwargs: Any) -> str:
                self.calls += 1
                if self.calls < 3:
                    raise LLMError("Gemini HTTP 503: high demand", status_code=503)
                return '{"ok": true}'

        flaky = Flaky503()
        out = generate_json_with_timeout_retry(flaky, "prompt")  # type: ignore[arg-type]
        assert out == '{"ok": true}'
        assert flaky.calls == 3

        class UnavailableStatus:
            def __init__(self) -> None:
                self.calls = 0

            def generate_json(self, **_kwargs: Any) -> str:
                self.calls += 1
                if self.calls < 3:
                    raise LLMError("Gemini error: UNAVAILABLE", status_code=503)
                return "{}"

        u = UnavailableStatus()
        generate_json_with_timeout_retry(u, "prompt")  # type: ignore[arg-type]
        assert u.calls == 3

        class TimeoutThenFail:
            def __init__(self) -> None:
                self.calls = 0

            def generate_json(self, **_kwargs: Any) -> str:
                self.calls += 1
                raise LLMError("Gemini request timed out")

        timed = TimeoutThenFail()
        with pytest.raises(LLMError):
            generate_json_with_timeout_retry(timed, "prompt")  # type: ignore[arg-type]
        # Timeout retries once (not the 503 double-backoff loop of 1+2).
        assert timed.calls == 2

        class ClientError:
            def __init__(self) -> None:
                self.calls = 0

            def generate_json(self, **_kwargs: Any) -> str:
                self.calls += 1
                raise LLMError("bad request", status_code=400)

        bad = ClientError()
        with pytest.raises(LLMError):
            generate_json_with_timeout_retry(bad, "prompt")  # type: ignore[arg-type]
        assert bad.calls == 1

    def test_llm_fail_honesty_seed_pack_fallback_and_locked_residual_copy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.ai_draft_jobs._cache_draft", lambda *_a, **_k: None)
        seed = seed_studio_draft(VISITOR_LOG)
        result = complete_matched_pack_draft(
            prompt=VISITOR_LOG,
            seed=seed,
            db_factory=lambda: None,  # type: ignore[arg-type, return-value]
            connection_id=None,
        )
        draft = result["draft"]
        status = draft.get("_llm_status") or {}
        assert status.get("mode") == "pack_fallback"
        assert status.get("reason") == "honesty_seed"
        copy = banner_for_mode("pack_fallback", reason="honesty_seed") or ""
        assert "Flash unavailable" in copy or "locked residual" in copy.lower()
        assert "padded workspace" in copy.lower()
        assert not _satellite_ids(draft)
        # Direct seed (AI off) must not density-pad either
        seeded = seed_studio_draft(VISITOR_LOG)
        assert not _satellite_ids(seeded)
        assert len(_new_x_ids(seeded)) == 1
        seed_status = seeded.get("_llm_status") or {}
        assert seed_status.get("mode") == "pack_fallback"
        assert seed_status.get("reason") == "honesty_seed"
        copy2 = banner_for_mode(
            str(seed_status.get("mode")), reason=str(seed_status.get("reason"))
        ) or ""
        assert "Flash unavailable" in copy2 or "locked residual" in copy2.lower()

    def test_display_and_technical_name_from_residual_noun(self) -> None:
        display, slug = naming_from_residual(VISITOR_LOG)
        assert display.lower() == "visitor log"
        assert slug == "visitor_log"
        draft = seed_studio_draft(VISITOR_LOG)
        assert str(draft.get("display_name") or "").lower() == "visitor log"
        assert str(draft.get("technical_name") or "") == "visitor_log"
        assert "i want a simple" not in str(draft.get("display_name") or "").lower()

    def test_register_few_shot_exists_and_car_rental_workspace_shot_skipped(self) -> None:
        register = few_shot_exemplar_block("car_rental", document_shape="register") or ""
        assert "x_paper_register" in register
        assert "x_visitor_log" not in register
        assert "One paper-book row" not in register
        assert "one row in the named paper book" not in register.lower()
        assert "x_rent_vehicle" not in register
        assert "x_rent_contract" not in register
        skipped = few_shot_exemplar_block("car_rental")
        assert skipped is None
        workspace = few_shot_exemplar_block("law_firm")
        assert workspace is not None
        assert "x_visitor_log" not in workspace
        assert "x_paper_register" not in workspace


# ---------------------------------------------------------------------------
# Wave 4 — Scorecard / Cert truth
# ---------------------------------------------------------------------------


class TestWave4ScorecardCert:
    def test_expanded_stopwords_are_not_uncovered_nouns(self) -> None:
        nouns = extract_prompt_nouns(VISITOR_LOG)
        banned = {
            "they",
            "came",
            "just",
            "unless",
            "already",
            "would",
            "nice",
            "only",
            "safe",
            "optional",
        }
        assert not (banned & set(nouns)), nouns
        brief = build_operator_brief(VISITOR_LOG)
        assert "python" in " ".join(brief.out_of_scope).lower() or "python" in VISITOR_LOG.lower()
        draft = {"_operator_brief": brief.to_dict(), "models": [{"model": "x_visitor_log"}]}
        _items, uncovered, _w = domain_noun_coverage(draft, VISITOR_LOG)
        assert "python" not in uncovered
        assert "they" not in uncovered
        assert "nice" not in uncovered
        accra_nouns = extract_prompt_nouns(ACCRA_UAT_PROMPT)
        assert "they're" not in accra_nouns
        assert "we're" not in accra_nouns
        assert "that'" not in accra_nouns

    def test_register_completeness_one_model_can_be_ten_and_depth_not_1_of_10(
        self,
    ) -> None:
        draft = _close_ai_off(VISITOR_LOG)
        assert len(_new_x_ids(draft)) == 1
        gaps = depth_gaps(draft)
        assert "depth_models" not in gaps, gaps
        card = draft.get("_scorecard") or draft_scorecard(draft, user_prompt=VISITOR_LOG)
        # 1 model + fields + views + ACL is allowed to reach 10.0; do not require it
        # if UI stubs are incomplete — but never fail because depth wants 10 models.
        assert card.get("score_0_10") is not None
        dims = card.get("dimensions") or card.get("dimension_scores") or {}
        # If the closer stamped views/ACL, completeness may be 10.0
        views = draft.get("views") or []
        acls = draft.get("access_rules") or draft.get("groups") or []
        if views and (acls or draft.get("access_rules")):
            score = float(card.get("score_0_10") or 0)
            assert score >= 10.0, (score, card.get("findings"), dims)
            assert float((dims.get("domain_fit") or 0)) >= 10.0
            assert "depth_models" not in str(card.get("findings") or "")

    def test_cert_hard_failures_oos_host_drift_satellites_and_x_bill(self) -> None:
        visitor = _close_ai_off(VISITOR_LOG)
        poisoned = dict(visitor)
        poisoned["models"] = list(visitor.get("models") or []) + [
            {
                "model": "crm.lead",
                "mode": "inherit",
                "inherit": "crm.lead",
                "fields": [],
            },
            {
                "model": "x_visitor_log_party",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_bill",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ]
        poisoned["_document_shape"] = "register"
        poisoned["_architecture_plan"] = {
            **(visitor.get("_architecture_plan") or {}),
            "document_shape": "register",
            "new_x_models": ["x_visitor_log"],
            "forbidden_clones": ["x_bill", "x_invoice"],
            "surface_budget": {"new_models": 1, "new_js": 0, "new_controllers": 0},
        }
        poisoned["_architecture_drift"] = architecture_plan_drift(poisoned)
        stamp_certification(poisoned)
        cert = poisoned["_certification"]
        fails = set(cert.get("hard_failures") or [])
        assert "out_of_scope_stock_host" in fails, fails
        assert "architecture_plan_drift" in fails, fails
        assert "register_satellites" in fails, fails
        assert "stock_clone_models" in fails or any(
            "bill" in str(x) for x in fails
        ), fails
        assert cert.get("tier") == "Reject"

    def test_unknown_or_skip_sandbox_is_not_production_for_full_app_residual(self) -> None:
        draft = _close_ai_off(VISITOR_LOG)
        draft["_sandbox_install"] = {}
        draft.pop("_sandbox_install", None)
        cert = build_certification(draft)
        assert cert.get("tier") not in {"Production", "Gold"}
        # Explicit UNKNOWN install evidence
        draft["_sandbox_install"] = {"ok": False, "message": "skipped"}
        # ok False is FAIL → Reject; UNKNOWN is the empty path above.
        skipped = dict(draft)
        skipped.pop("_sandbox_install", None)
        skipped["grain"] = "full_app"
        skipped["_scorecard"] = {
            "score_0_10": 10.0,
            "validators": {"all_green": True},
        }
        skipped["_live_apply"] = {"rpc_ok": False}
        skipped.pop("_option_a_smoke", None)
        cert2 = build_certification(skipped)
        assert cert2.get("tier") not in {"Production", "Gold"}

    def test_live_apply_review_required_must_not_display_as_production(self) -> None:
        draft = _close_ai_off(VISITOR_LOG)
        live = draft.get("_live_apply") or {}
        live_tier = live.get("certification_tier")
        cert_tier = (draft.get("_certification") or {}).get("tier")
        assert live_tier == "ReviewRequired"
        assert cert_tier == "ReviewRequired"
        # Contract: even if scorecard cert were Production, live stamp wins in UI.
        fake = {
            "_certification": {"tier": "Production"},
            "_live_apply": {"certification_tier": "ReviewRequired"},
        }
        # Source of truth for the wizard helper is web; API must still not claim
        # Production on the live_apply blob when ReviewRequired is stamped.
        assert fake["_live_apply"]["certification_tier"] != "Production"


# ---------------------------------------------------------------------------
# Wave 5 — Enrichment / Expert subtractive
# ---------------------------------------------------------------------------


class TestWave5EnrichmentExpert:
    def test_finalize_enriched_draft_honors_brief_and_does_not_pack_merge_register(
        self,
    ) -> None:
        draft = seed_studio_draft(VISITOR_LOG)
        before = list(_new_x_ids(draft))
        # Tempt the pack merger with a foreign pack id — additive growth is blocked.
        draft["domain_pack"] = "law_firm"
        warnings: list[str] = []
        finalize_enriched_draft(draft, prompt=VISITOR_LOG, warnings=warnings)
        after = _new_x_ids(draft)
        assert "x_visitor_log" in after
        assert not any("matter" in mid for mid in after)
        assert not _satellite_ids(draft)
        assert len(after) == 1, (before, after)
        assert "crm.lead" not in _model_ids(draft)
        assert "account.move" not in _inherit_ids(draft)

    def test_expert_merge_does_not_readd_satellites_or_density_on_register(self) -> None:
        draft = _close_ai_off(VISITOR_LOG)
        draft.setdefault("models", []).extend(
            [
                {
                    "model": "x_visitor_log_party",
                    "mode": "new",
                    "fields": [{"name": "x_name", "ttype": "char"}],
                },
                {
                    "model": "x_visitor_log_line",
                    "mode": "new",
                    "fields": [{"name": "x_name", "ttype": "char"}],
                },
                {
                    "model": "x_deposit",
                    "mode": "new",
                    "fields": [{"name": "x_name", "ttype": "char"}],
                },
            ]
        )
        out, _notes = apply_deterministic_scorecard_fixes(
            draft, user_prompt=VISITOR_LOG
        )
        assert not _satellite_ids(out), _model_ids(out)
        assert "x_deposit" not in _new_x_ids(out)
        assert _new_x_ids(out) == ["x_visitor_log"]

    def test_worse_after_closer_treats_leftover_forbidden_crm_invoice_as_worse(
        self,
    ) -> None:
        from app.ai_operator_brief import attach_operator_brief

        original: dict[str, Any] = {
            "_user_prompt": VISITOR_LOG,
            "models": [
                {"model": "x_visitor_log", "mode": "new", "fields": [{"name": "x_name"}]}
            ],
            "technical_name": "visitor_log",
        }
        attach_operator_brief(original, user_prompt=VISITOR_LOG)
        stamp_document_shape(original, prompt=VISITOR_LOG)
        candidate = {
            **original,
            "models": [
                *original["models"],
                {"model": "crm.lead", "mode": "inherit", "inherit": "crm.lead", "fields": []},
                {
                    "model": "account.move",
                    "mode": "inherit",
                    "inherit": "account.move",
                    "fields": [],
                },
            ],
        }
        attach_operator_brief(candidate, user_prompt=VISITOR_LOG)
        reason = _worse_after_closer(
            original, candidate, score_before=7.0, score_after=10.0
        )
        assert reason is not None, "leftover CRM/invoice must be worse even if score rose"
        low = reason.lower()
        assert "crm" in low or "invoice" in low or "account.move" in low or "forbidden" in low


# ---------------------------------------------------------------------------
# Adversarial extras
# ---------------------------------------------------------------------------


class TestAdversarialExtras:
    def test_long_simple_visitor_book_does_not_become_comprehensive_workspace(self) -> None:
        assert len(LONG_VISITOR_BOOK.split()) >= 20
        draft = _close_ai_off(LONG_VISITOR_BOOK)
        shape = classify_document_shape(LONG_VISITOR_BOOK, draft)
        assert shape == "register", shape
        assert len(_new_x_ids(draft)) == 1
        assert draft.get("domain_pack") not in {"law_firm", "hotel", "restaurant"}
        assert "comprehensive" not in str(draft.get("_ambition") or "")

    def test_inherit_sla_does_not_get_party_line_or_crm(self) -> None:
        draft = _close_ai_off(SLA_INVOICES)
        assert not _satellite_ids(draft)
        assert "crm.lead" not in _model_ids(draft)
        assert "crm" not in {str(d) for d in (draft.get("depends") or [])}

    def test_dont_invent_invoicing_versus_dont_invent_parallel_invoice(self) -> None:
        forbid = build_operator_brief(DONT_INVENT_INVOICING)
        assert "account" in forbid.forbidden_bridges
        parallel = build_operator_brief(DONT_INVENT_PARALLEL_INVOICE)
        assert "account" not in parallel.forbidden_bridges
        closed = _close_ai_off(DONT_INVENT_PARALLEL_INVOICE)
        ids = _model_ids(closed)
        # Legitimate stock invoice inherit may remain when invoices are named.
        assert "account.move" in ids or "account" in {
            str(d) for d in (closed.get("depends") or [])
        }
        visitor = _close_ai_off(DONT_INVENT_INVOICING)
        assert "account.move" not in _inherit_ids(visitor)
        assert "x_bill" not in _new_x_ids(visitor)

    def test_hotel_and_law_firm_packs_stay_workspace_not_register(self) -> None:
        hotel = _close_ai_off(HOTEL_LODGING)
        law = _close_ai_off(LAW_FIRM_MATTERS)
        assert classify_document_shape(HOTEL_LODGING, hotel) == "workspace"
        assert classify_document_shape(LAW_FIRM_MATTERS, law) == "workspace"
        assert hotel.get("domain_pack") == "hotel"
        assert law.get("domain_pack") == "law_firm"
        assert len(_new_x_ids(hotel)) > 1
        assert len(_new_x_ids(law)) > 1

    def test_named_residual_plus_two_stock_apps_does_not_collapse_to_one_model_register(
        self,
    ) -> None:
        shape = classify_document_shape(POLICY_PLUS_STOCK)
        assert shape != "register", shape
        draft = _close_ai_off(POLICY_PLUS_STOCK)
        assert classify_document_shape(POLICY_PLUS_STOCK, draft) != "register"
        assert len(_new_x_ids(draft)) != 1 or draft.get("domain_pack")
        # Must not be the visitor-log one-header shape
        assert _new_x_ids(draft) != ["x_visitor_log"]
        assert len(_new_x_ids(draft)) >= 1
        if not draft.get("domain_pack"):
            assert len(_new_x_ids(draft)) > 1, _new_x_ids(draft)


def test_honor_operator_brief_strips_forbidden_hosts_on_register() -> None:
    draft: dict[str, Any] = {
        "_user_prompt": VISITOR_LOG,
        "_document_shape": "register",
        "depends": ["mail", "hr", "crm", "account"],
        "models": [
            {"model": "x_visitor_log", "mode": "new", "fields": []},
            {"model": "crm.lead", "mode": "inherit", "fields": []},
            {"model": "account.move", "mode": "inherit", "fields": []},
            {"model": "x_visitor_log_party", "mode": "new", "fields": []},
        ],
    }
    honor_operator_brief(draft, user_prompt=VISITOR_LOG)
    ids = _model_ids(draft)
    assert "crm.lead" not in ids
    assert "account.move" not in ids
    assert "x_visitor_log_party" not in ids
    depends = {str(d) for d in (draft.get("depends") or [])}
    assert "crm" not in depends
    assert "account" not in depends


def test_architecture_plan_register_budget_is_one() -> None:
    seed = seed_studio_draft(VISITOR_LOG)
    plan = build_architecture_plan(seed, prompt=VISITOR_LOG)
    assert plan.get("document_shape") == "register"
    assert (plan.get("surface_budget") or {}).get("new_models") == 1
    stamp_architecture_plan(seed, prompt=VISITOR_LOG, rebuild=True)
    assert seed.get("_document_shape") == "register"


def test_close_odoo_architecture_does_not_pad_register() -> None:
    seed = seed_studio_draft(VISITOR_LOG)
    close_odoo_architecture(seed, user_prompt=VISITOR_LOG)
    assert _new_x_ids(seed) == ["x_visitor_log"]
    assert not _satellite_ids(seed)


# ---------------------------------------------------------------------------
# Accra UAT — paper-book visitor log (09:53 chrome leaks)
# ---------------------------------------------------------------------------

ACCRA_UAT_PROMPT = (
    "Front desk still uses a paper book. I want a simple visitor log in Odoo: "
    "visitor name, who they came to see (an employee), purpose, time in, time out, "
    "optional ID number. This is not CRM and not a second Contacts app — the host "
    "is an Employee, the visitor can just be a name unless they're already a contact. "
    "We're a 40-person office in Accra. Don't invent invoicing. Mail notifications "
    "if someone sits in reception more than two hours would be nice but only if "
    "that's safe no-code, not Python."
)


def _accra_poisoned_flash_draft() -> dict[str, Any]:
    """Hotel-shaped visitor log the 09:53 Flash pass actually emitted."""
    from app.ai_operator_brief import attach_operator_brief

    draft: dict[str, Any] = {
        "_user_prompt": ACCRA_UAT_PROMPT,
        "technical_name": "front_desk_still_uses_a",
        "display_name": "Front Desk Still Uses A Paper Book",
        "depends": ["mail", "hr", "crm", "account"],
        "_document_shape": "register",
        "models": [
            {
                "model": "x_visitor_log",
                "mode": "new",
                "is_workflow": True,
                "state_field": {"name": "x_status"},
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Log Entry Reference", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": (
                            "[('draft','Draft'),('signed_in','Signed in'),"
                            "('checked_in','Checked in'),('signed_out','Signed out'),"
                            "('checked_out','Checked out')]"
                        ),
                    },
                    {"name": "x_code", "ttype": "char", "required": True},
                    {
                        "name": "x_host_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                    },
                    {
                        "name": "x_purpose",
                        "ttype": "selection",
                        "string": "Purpose of Visit",
                        "selection": (
                            "[('meeting','Meeting'),('interview','Interview'),"
                            "('delivery','Delivery'),('service','Service'),('other','Other')]"
                        ),
                    },
                    {"name": "x_time_in", "ttype": "datetime", "string": "Check-in Time"},
                    {"name": "x_time_out", "ttype": "datetime", "string": "Check-out Time"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "required": True,
                        "relation": "res.company",
                    },
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "required": False,
                    },
                ],
            }
        ],
        "views": [
            {
                "model": "x_visitor_log",
                "type": "list",
                "arch": (
                    '<list string="Visitor Logs" sample="1" '
                    'decoration-danger="x_status == \'cancelled\'" '
                    'decoration-muted="x_status == \'draft\'">'
                    '<field name="x_name"/></list>'
                ),
            },
            {
                "model": "x_visitor_log",
                "type": "kanban",
                "arch": '<kanban default_group_by="x_status"></kanban>',
            },
            {
                "model": "x_visitor_log",
                "type": "form",
                "arch": (
                    '<form><header><field name="x_status" widget="statusbar"/>'
                    "</header><sheet><field name=\"x_name\"/></sheet></form>"
                ),
            },
        ],
        "actions": [
            {
                "model": "x_visitor_log",
                "view_mode": "list,kanban,form",
                "technical_name": "action_x_visitor_log",
            }
        ],
        "menus": [
            {
                "name": "Front Desk Still Uses A",
                "xml_id": "menu_root_front_desk_still_uses_a",
                "technical_name": "root_front_desk_still_uses_a",
            }
        ],
        "smart_buttons": [
            {
                "on_model": "res.partner",
                "related_model": "x_visitor_log",
                "relation_field": "x_partner_id",
                "label": "Visits",
            }
        ],
        "sequences": [{"model": "x_visitor_log", "code": "VL/%(year)s/"}],
        "multi_company": True,
        "record_rules": [
            {
                "name": "Multi-company (x_visitor_log)",
                "model": "x_visitor_log",
                "domain_force": "['|', ('x_company_id', '=', False), ('x_company_id', 'in', company_ids)]",
                "technical_name": "rule_x_visitor_log_multi_company",
            }
        ],
        "automations": [
            {
                "name": "Notify Host on Long Visitor Stay",
                "model": "x_visitor_log",
                "trigger": "on_time",
                "description": "Notify Host on Long Visitor Stay",
                "filter_domain": None,
                "safe_actions": [
                    {
                        "kind": "next_activity",
                        "summary": "Visitor has been in reception for over 2 hours.",
                        "activity_type_id": "mail.activity_data_todo",
                        "user_id": "x_host_id",
                    }
                ],
                "source": "critique",
                "trg_date_field_name": "create_date",
            }
        ],
        "reuse": {
            "models": [
                "hr.employee",
                "res.partner",
                "res.users",
                "res.company",
                "res.currency",
                "account.move",
                "crm.lead",
            ],
            "catalog_suggestions": [
                {"model": "crm.tag", "modules": ["crm"]},
                {"model": "mail.bot", "modules": ["mail"]},
                {"model": "account.move", "modules": ["account"]},
            ],
        },
        "reuse_hints": [
            {"model": "account.move", "reason": "Invoicing"},
            {"model": "crm.lead", "reason": "CRM"},
        ],
        "_architecture_plan": {
            "document_shape": "register",
            "stock_hosts": ["hr.employee", "res.partner", "account.move", "crm.lead"],
            "surface_budget": {"new_models": 1},
        },
        "custom_code_blocks": [
            {
                "source_file": "tests/test_visitor_log_smoke.py",
                "kind": "test",
                "reason": "elite: generated smoke tests",
            },
            {
                "source_file": "i18n/visitor_log.pot",
                "kind": "i18n",
                "reason": "elite: translation template",
            },
        ],
    }
    attach_operator_brief(draft, user_prompt=ACCRA_UAT_PROMPT)
    return draft


class TestAccraUatRegisterPolish:
    def test_ai_off_finish_is_paper_book_not_hotel_checkin(self) -> None:
        draft = _close_ai_off(ACCRA_UAT_PROMPT)
        assert _new_x_ids(draft) == ["x_visitor_log"]
        header = next(m for m in draft["models"] if m.get("model") == "x_visitor_log")
        assert header.get("is_workflow") is not True
        fields = _field_names(draft, "x_visitor_log")
        assert "x_status" not in fields
        assert "x_code" not in fields
        assert "x_notes" not in fields
        assert "x_company_id" not in fields
        assert draft.get("multi_company") is not True
        blob = json.dumps(header).lower()
        assert "checked_in" not in blob
        assert "signed_in" not in blob
        assert "check-in" not in blob
        assert "res.company" not in {
            str(f.get("relation") or "")
            for f in (header.get("fields") or [])
            if isinstance(f, dict)
        }
        assert not any(
            isinstance(v, dict) and str(v.get("type") or "") == "kanban"
            for v in (draft.get("views") or [])
        )
        assert not any(
            "x_status" in str(v.get("arch") or "")
            for v in (draft.get("views") or [])
            if isinstance(v, dict)
        )
        purpose = next(
            (
                f
                for f in (header.get("fields") or [])
                if isinstance(f, dict) and f.get("name") == "x_purpose"
            ),
            {},
        )
        assert purpose.get("ttype") != "selection"
        assert not any(
            isinstance(b, dict) and str(b.get("on_model") or "") == "res.partner"
            for b in (draft.get("smart_buttons") or [])
        )
        assert not (draft.get("sequences") or [])
        xml_ids = [
            str(m.get("xml_id") or "")
            for m in (draft.get("menus") or [])
            if isinstance(m, dict) and not m.get("parent_xml_id")
        ]
        assert any(x == "menu_root_visitor_log" for x in xml_ids), xml_ids
        autos = [a for a in (draft.get("automations") or []) if isinstance(a, dict)]
        timed = [a for a in autos if str(a.get("trigger") or "") == "on_time"]
        assert timed, autos
        assert len(timed) == 1, [a.get("name") for a in timed]
        assert "next_activity" in json.dumps(timed).lower()
        assert "python" not in json.dumps(timed).lower()
        assert str(timed[0].get("state") or "") != "code"
        header_fields = {
            str(f.get("name")): f
            for f in (header.get("fields") or [])
            if isinstance(f, dict)
        }
        name_string = str(header_fields.get("x_name", {}).get("string") or "")
        assert name_string[:1].isupper(), name_string
        assert "visitor" in name_string.lower()
        search_arch = next(
            (
                str(v.get("arch") or "")
                for v in (draft.get("views") or [])
                if isinstance(v, dict) and str(v.get("type") or "") == "search"
            ),
            "",
        )
        assert "my_x_employee_id" not in search_arch
        assert "x_employee_id','=', uid" not in search_arch.replace(" ", "")
        plan = draft.get("_architecture_plan") or {}
        hosts = {str(h) for h in (plan.get("stock_hosts") or [])}
        assert "account.move" not in hosts
        assert "crm.lead" not in hosts
        reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
        assert "account.move" not in (reuse.get("models") or [])
        assert "res.currency" not in (reuse.get("models") or [])
        assert "res.users" not in (reuse.get("models") or [])
        assert "res.company" not in (reuse.get("models") or [])
        sugg = " ".join(
            json.dumps(row)
            for row in (reuse.get("catalog_suggestions") or [])
            if isinstance(row, dict)
        ).lower()
        assert "account.move" not in sugg
        assert "crm.tag" not in sugg
        card = draft.get("_scorecard") or {}
        assert float(card.get("score_0_10") or 0) >= 10.0
        dims = card.get("dimensions") or {}
        assert float(dims.get("domain_fit") or 0) >= 10.0
        findings = json.dumps(card.get("findings") or []).lower()
        assert "noun:front" not in findings
        assert "noun:still" not in findings
        assert "noun:mail" not in findings
        assert "noun:invoicing" not in findings
        assert "noun:python" not in findings
        comp_ids = {
            str(c.get("id") or "")
            for c in (draft.get("_completeness") or [])
            if isinstance(c, dict)
        }
        assert "noun_uncovered:invoicing" not in comp_ids
        assert "noun_uncovered:python" not in comp_ids
        assert "noun_uncovered:front" not in comp_ids
        assert "noun_uncovered:still" not in comp_ids
        cert = draft.get("_certification") or {}
        assert cert.get("tier") == "ReviewRequired"
        live = draft.get("_live_apply") or {}
        assert live.get("certification_tier") == "ReviewRequired"
        assert not (live.get("option_a") or [])
        brief = draft.get("_operator_brief") or {}
        assert str(brief.get("country") or "") == "Ghana"

    def test_honor_strips_flash_hotel_chrome_and_restamps_duration(self) -> None:
        from app.ai_live_apply_contract import attach_live_apply_contract
        from app.ai_odoo_app_bar import looks_like_register

        assert looks_like_register("x_visitor_log")
        draft = _accra_poisoned_flash_draft()
        honor_operator_brief(draft, user_prompt=ACCRA_UAT_PROMPT)
        header = next(m for m in draft["models"] if m.get("model") == "x_visitor_log")
        assert header.get("is_workflow") is not True
        names = {
            str(f.get("name"))
            for f in (header.get("fields") or [])
            if isinstance(f, dict)
        }
        assert "x_status" not in names
        assert "x_code" not in names
        assert "x_notes" not in names
        assert "x_company_id" not in names
        assert "company_id" not in names
        assert draft.get("multi_company") is not True
        fields_by_name = {
            str(f.get("name")): f
            for f in (header.get("fields") or [])
            if isinstance(f, dict)
        }
        time_in = str(fields_by_name.get("x_time_in", {}).get("string") or "")
        assert "check" not in time_in.lower()
        assert fields_by_name["x_purpose"].get("ttype") == "char"
        assert "selection" not in fields_by_name["x_purpose"]
        assert "reference" not in str(fields_by_name["x_name"].get("string") or "").lower()
        assert "visitor" in str(fields_by_name["x_name"].get("string") or "").lower()
        list_arch = next(
            str(v.get("arch") or "")
            for v in (draft.get("views") or [])
            if isinstance(v, dict) and v.get("type") == "list"
        )
        assert "x_status" not in list_arch
        assert "decoration-" not in list_arch
        reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
        assert "res.currency" not in (reuse.get("models") or [])
        assert "res.users" not in (reuse.get("models") or [])
        assert "res.company" not in (reuse.get("models") or [])
        assert not (draft.get("record_rules") or [])
        sugg = json.dumps(reuse.get("catalog_suggestions") or []).lower()
        assert "mail.bot" not in sugg
        comp_ids = {
            str(c.get("id") or ""): c
            for c in (draft.get("_completeness") or [])
            if isinstance(c, dict)
        }
        assert "noun_uncovered:invoicing" not in comp_ids
        assert "noun_uncovered:python" not in comp_ids
        assert not any(
            isinstance(v, dict) and v.get("type") == "kanban"
            for v in (draft.get("views") or [])
        )
        form = next(
            v
            for v in (draft.get("views") or [])
            if isinstance(v, dict) and v.get("type") == "form"
        )
        assert "<header>" not in str(form.get("arch") or "").lower()
        assert not any(
            isinstance(b, dict) and b.get("on_model") == "res.partner"
            for b in (draft.get("smart_buttons") or [])
        )
        assert not (draft.get("sequences") or [])
        root = next(
            m
            for m in (draft.get("menus") or [])
            if isinstance(m, dict) and not m.get("parent_xml_id")
        )
        assert root.get("xml_id") == "menu_root_visitor_log"
        timed = [
            a
            for a in (draft.get("automations") or [])
            if isinstance(a, dict) and a.get("trigger") == "on_time"
        ]
        assert timed
        assert len(timed) == 1, [a.get("name") for a in timed]
        assert str(timed[0].get("trg_date_field_name") or "") == "x_time_in"
        assert str(timed[0].get("source") or "") == "honesty_ir"
        assert "x_host_id" not in json.dumps(timed)
        hosts = {
            str(h)
            for h in ((draft.get("_architecture_plan") or {}).get("stock_hosts") or [])
        }
        assert "account.move" not in hosts
        attach_live_apply_contract(draft)
        live = draft.get("_live_apply") or {}
        assert not (live.get("option_a") or [])

    def test_honor_rewrites_few_shot_acl_names_and_brief_required(self) -> None:
        draft: dict[str, Any] = {
            "_user_prompt": ACCRA_UAT_PROMPT,
            "technical_name": "visitor_log",
            "display_name": "Visitor Log",
            "_document_shape": "register",
            "models": [
                {
                    "model": "x_visitor_log",
                    "description": "One Row In The Named Paper Book",
                    "mode": "new",
                    "fields": [
                        {"name": "x_name", "ttype": "char", "string": "Visitor Name", "required": True},
                        {
                            "name": "x_employee_id",
                            "ttype": "many2one",
                            "relation": "hr.employee",
                            "string": "Employee",
                        },
                        {"name": "x_purpose", "ttype": "char", "string": "Purpose"},
                        {"name": "x_time_in", "ttype": "datetime", "string": "Time In"},
                        {"name": "x_time_out", "ttype": "datetime", "string": "Time Out"},
                        {"name": "x_id_number", "ttype": "char", "string": "ID Number"},
                    ],
                }
            ],
            "access_rules": [
                {
                    "id": "access_x_visitor_log_user",
                    "name": "One Row In The Named Paper Book user",
                    "model": "model_x_visitor_log",
                    "group": "group_visitor_log_user",
                    "perm_read": 1,
                    "perm_write": 1,
                    "perm_create": 1,
                    "perm_unlink": 0,
                },
                {
                    "id": "access_x_visitor_log_manager",
                    "name": "One Row In The Named Paper Book manager",
                    "model": "model_x_visitor_log",
                    "group": "group_visitor_log_manager",
                    "perm_read": 1,
                    "perm_write": 1,
                    "perm_create": 1,
                    "perm_unlink": 1,
                },
            ],
        }
        honor_operator_brief(draft, user_prompt=ACCRA_UAT_PROMPT)
        header = next(m for m in draft["models"] if m.get("model") == "x_visitor_log")
        assert header.get("description") == "Visitor Log"
        by_name = {
            str(f.get("name")): f
            for f in (header.get("fields") or [])
            if isinstance(f, dict)
        }
        assert by_name["x_employee_id"].get("required") is True
        assert by_name["x_purpose"].get("required") is True
        assert by_name["x_time_in"].get("required") is True
        assert not by_name["x_id_number"].get("required")
        names = [str(r.get("name") or "") for r in (draft.get("access_rules") or [])]
        assert names == ["Visitor Log user", "Visitor Log manager"]
        assert "paper book" not in json.dumps(draft.get("access_rules")).lower()

    def test_close_after_flash_does_not_drop_duration_or_readd_kanban(self) -> None:
        draft = _accra_poisoned_flash_draft()
        close_odoo_architecture(draft, user_prompt=ACCRA_UAT_PROMPT)
        header = next(m for m in draft["models"] if m.get("model") == "x_visitor_log")
        assert header.get("is_workflow") is not True
        names = _field_names(draft, "x_visitor_log")
        assert "x_status" not in names
        assert "x_notes" not in names
        assert "x_company_id" not in names
        assert not any(
            isinstance(v, dict) and v.get("type") == "kanban"
            for v in (draft.get("views") or [])
        )
        timed = [
            a
            for a in (draft.get("automations") or [])
            if isinstance(a, dict) and str(a.get("trigger") or "") == "on_time"
        ]
        assert timed
        assert len(timed) == 1, [a.get("name") for a in timed]
        assert str(timed[0].get("trg_date_field_name") or "") == "x_time_in"
        assert "next_activity" in json.dumps(timed).lower()

    def test_humanized_duration_name_does_not_restamp_a_second_alert(self) -> None:
        from app.ai_post_critique import rewrite_critique_automations

        draft = _close_ai_off(ACCRA_UAT_PROMPT)
        rewrite_critique_automations(draft)
        honor_operator_brief(draft, user_prompt=ACCRA_UAT_PROMPT)
        honor_operator_brief(draft, user_prompt=ACCRA_UAT_PROMPT)
        close_odoo_architecture(draft, user_prompt=ACCRA_UAT_PROMPT)
        timed = [
            a
            for a in (draft.get("automations") or [])
            if isinstance(a, dict) and str(a.get("trigger") or "") == "on_time"
        ]
        assert len(timed) == 1, [a.get("name") for a in timed]
        attach_scorecard(draft, user_prompt=ACCRA_UAT_PROMPT)
        findings = json.dumps((draft.get("_scorecard") or {}).get("findings") or []).lower()
        assert "duplicate automation" not in findings


KEY_LOG = (
    "Warehouse still uses a paper book. I want a simple key log in Odoo: "
    "key name, who signed it out (an employee), purpose, time in, time out, "
    "optional ID number. This is not CRM and not a second Contacts app. "
    "Don't invent invoicing. Mail notifications if a key sits out more than "
    "two hours would be nice but only if that's safe no-code, not Python."
)


def test_key_log_uses_same_register_closer_as_any_noun_log() -> None:
    """Register polish is document-shape, not a visitor vertical."""
    from app.ai_document_shape import classify_document_shape
    from app.ai_odoo_app_bar import looks_like_register

    assert classify_document_shape(KEY_LOG) == "register"
    assert looks_like_register("x_key_log")
    draft = _close_ai_off(KEY_LOG)
    assert _new_x_ids(draft) == ["x_key_log"]
    header = next(m for m in draft["models"] if m.get("model") == "x_key_log")
    assert header.get("is_workflow") is not True
    names = _field_names(draft, "x_key_log")
    assert "x_status" not in names
    assert "x_employee_id" in names
    assert not any(
        isinstance(v, dict) and str(v.get("type") or "") == "kanban"
        for v in (draft.get("views") or [])
    )
    timed = [
        a
        for a in (draft.get("automations") or [])
        if isinstance(a, dict) and str(a.get("trigger") or "") == "on_time"
    ]
    assert timed
    assert len(timed) == 1, [a.get("name") for a in timed]
    assert "next_activity" in json.dumps(timed).lower()
    assert (draft.get("_certification") or {}).get("tier") == "ReviewRequired"
    xml_ids = [
        str(m.get("xml_id") or "")
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and not m.get("parent_xml_id")
    ]
    assert "menu_root_key_log" in xml_ids
