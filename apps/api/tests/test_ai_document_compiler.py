"""Document grammar compiler — thin shapes, isomorphic siblings, naming."""

from __future__ import annotations

from app.ai_document_compiler import compile_document_grammar, premium_surface_findings
from app.ai_document_shape import classify_document_shape, naming_from_residual
from app.ai_live_apply_contract import live_apply_contract_findings
from app.ai_operator_brief import stated_residual_kind

PURCHASE_PROMPT = (
    "Purchase requests with amount, requester, and a manager approval flow.\n"
    "Staff submit a request; a manager must approve or refuse it.\n"
    "When something is waiting, notify the manager with a to-do."
)


def _sibling(mid: str, desc: str) -> dict:
    return {
        "model": mid,
        "description": desc,
        "mode": "new",
        "fields": [
            {"name": "x_name", "ttype": "char", "string": "Name"},
            {
                "name": "x_partner_id",
                "ttype": "many2one",
                "relation": "res.partner",
                "string": "Contact",
            },
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": "[('draft','Draft'),('open','Open')]",
            },
        ],
    }


def test_purchase_prompt_is_transactional_header() -> None:
    assert classify_document_shape(PURCHASE_PROMPT) == "transactional_header"


def test_hotel_prompt_stays_workspace() -> None:
    assert (
        classify_document_shape("Hotel PMS with guest folio, check-in and housekeeping")
        == "workspace"
    )


def test_named_in_brief_is_not_the_title() -> None:
    kind, residual = stated_residual_kind(
        PURCHASE_PROMPT + "\nCustom residual: named in brief.\nCapability path: residual_app"
    )
    assert kind == "named"
    assert residual == ""
    display, slug = naming_from_residual(
        PURCHASE_PROMPT + "\nCustom residual: named in brief."
    )
    assert "named" not in display.lower()
    assert "brief" not in display.lower()
    assert "purchase" in display.lower()
    assert slug.startswith("purchase")


def test_compiler_collapses_agreements_expenses_named_in_brief() -> None:
    draft = {
        "technical_name": "named_in_brief",
        "display_name": "Named In Brief",
        "depends": ["base", "mail"],
        "_user_prompt": PURCHASE_PROMPT,
        "models": [
            {
                "model": "x_named_brief",
                "description": "Named Brief",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Contact",
                    },
                    {
                        "name": "x_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                        "string": "Employee",
                    },
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.company",
                        "string": "Company",
                    },
                    {
                        "name": "x_agreement_ids",
                        "ttype": "one2many",
                        "relation": "x_agreement",
                        "relation_field": "x_parent_id",
                        "string": "Agreements",
                    },
                    {
                        "name": "x_expense_ids",
                        "ttype": "one2many",
                        "relation": "x_expense",
                        "relation_field": "x_parent_id",
                        "string": "Expenses",
                    },
                ],
            },
            _sibling("x_agreement", "Agreement"),
            _sibling("x_expense", "Expense"),
        ],
        "actions": [
            {"name": "Named Briefs", "model": "x_named_brief", "technical_name": "action_x_named_brief"},
            {"name": "Agreements", "model": "x_agreement", "technical_name": "action_x_agreement"},
            {"name": "Expenses", "model": "x_expense", "technical_name": "action_x_expense"},
        ],
        "menus": [
            {"name": "Named In Brief", "technical_name": "root_named_in_brief", "xml_id": "menu_root_named_in_brief"},
            {
                "name": "Agreements",
                "action_xml_id": "action_x_agreement",
                "parent_xml_id": "menu_root_named_in_brief",
            },
            {
                "name": "Expenses",
                "action_xml_id": "action_x_expense",
                "parent_xml_id": "menu_root_named_in_brief",
            },
        ],
    }
    notes = compile_document_grammar(draft, prompt=PURCHASE_PROMPT)
    assert notes
    models = [m.get("model") for m in draft.get("models") or [] if isinstance(m, dict)]
    assert "x_agreement" not in models
    assert "x_expense" not in models
    assert any(str(m).startswith("x_") and "agreement" not in str(m) for m in models)
    header = next(m for m in draft["models"] if isinstance(m, dict) and not str(m.get("model")).endswith("_line"))
    names = {f["name"] for f in header["fields"] if isinstance(f, dict)}
    assert "x_amount" in names
    assert "x_currency_id" in names
    assert "x_requester_id" in names
    assert "x_manager_id" in names
    assert "x_agreement_ids" not in names
    assert "x_expense_ids" not in names
    assert "Named" not in str(draft.get("display_name"))
    assert "purchase" in str(draft.get("display_name") or "").lower()
    grammar = draft.get("_document_grammar") or {}
    assert grammar.get("extra_apps") == 0
    assert "Amount" in " ".join(grammar.get("slots") or [])
    menus = draft.get("menus") or []
    assert len([m for m in menus if isinstance(m, dict) and m.get("action_xml_id")]) == 1


def test_surface_gate_fails_duplicate_notebooks() -> None:
    draft = {
        "display_name": "Named In Brief",
        "technical_name": "named_in_brief",
        "_user_prompt": PURCHASE_PROMPT,
        "_document_shape": "workspace",
        "models": [
            {
                "model": "x_named_brief",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_agreement_ids",
                        "ttype": "one2many",
                        "relation": "x_agreement",
                        "string": "Agreements",
                    },
                    {
                        "name": "x_expense_ids",
                        "ttype": "one2many",
                        "relation": "x_expense",
                        "string": "Expenses",
                    },
                ],
            },
            _sibling("x_agreement", "Agreement"),
            _sibling("x_expense", "Expense"),
        ],
    }
    findings = premium_surface_findings(draft)
    details = " ".join(str(f.get("detail") or "") for f in findings).lower()
    assert "grounded" in details or "isomorphic" in details or "duplicate notebook" in details
    live = live_apply_contract_findings(draft)
    assert any(str(f.get("detail") or "").startswith("surface:") for f in live)


def test_workspace_collapses_isomorphic_siblings() -> None:
    draft = {
        "display_name": "Hotel",
        "technical_name": "hotel",
        "domain_pack": "hotel",
        "_document_shape": "workspace",
        "_user_prompt": "Hotel PMS with guest folio, check-in and housekeeping",
        "models": [
            {
                "model": "x_hotel_booking",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Booking"}],
            },
            _sibling("x_agreement", "Agreement"),
            _sibling("x_expense", "Expense"),
        ],
    }
    compile_document_grammar(draft, prompt=str(draft["_user_prompt"]))
    models = {m.get("model") for m in draft["models"] if isinstance(m, dict)}
    assert "x_hotel_booking" in models
    # One of the isomorphic pair may remain; both must not.
    assert not ({"x_agreement", "x_expense"} <= models)
