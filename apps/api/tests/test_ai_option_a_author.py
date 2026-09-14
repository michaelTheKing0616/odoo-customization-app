"""LLM-authored Option A — classify, policy gate, zip lock. Gold CBN/POS unchanged."""

from __future__ import annotations

import json

import pytest

from app.ai_generation_engine import (
    classify_generation,
    is_gold_option_a_draft,
    is_option_a_authored_draft,
    maybe_seed_from_capability,
)
from app.ai_option_a_author import author_option_a_module, coerce_author_payload, seed_option_a_authored
from app.ai_option_a_gate import (
    authoring_gate_passed,
    evaluate_authoring_gate,
    requires_authoring_gate,
)
from app.ai_option_a_policy import policy_findings

MARKUP = (
    "The Client wants a Mark-up line added to every Sale. The Markup is calculated "
    "as a percentage of every sale made. A Withholding Tax, on the markup is to be "
    "calculated as well (if possible). The WT is made on the Markup only, and only "
    "for Sales, NOT Purchases."
)

DELIVERY = (
    "Odoo, by default, appends the name of the Customer to the Delivery address "
    "under the Shipping Address section of the Delivery Note. The client wants "
    "that name - the Customer Name - removed from the Shipping Address."
)

UNSEEN = (
    "Email me when stock hits minimum via a cron that calls a public HTTP status "
    "URL https://status.example.com/health"
)

CBN = (
    "Company currency NGN. Activate USD, GBP, and EUR. "
    "Add Central Bank of Nigeria as the Service on Automatic Currency Rates "
    "so the cron pulls live CBN rates."
)

CLIENT_MARKUP = (
    'The Client wants a "Mark-up" line added to every Sale they make. They purchase '
    "products on requests from their customers and the selling price is the additive "
    "value of the purchase/cost price and their own mark-up. The Markup is calculated "
    "as a percentage of every sale made in a single session/instance. The mark-up "
    "should be a range between 10% - 25% and they want to be able to choose at the "
    "time of entry into the Odoo DB which exact markup percentage (between 10% - 25%) "
    "is to be the markup for that particular sale. A Witholding Tax, on the markup is "
    "to be calculated as well. The Witholding Tax is made on the Markup portion of "
    "the total selling price only, and only for Sales, NOT Purchases."
)


def _clean_inherit_blocks(_prompt: str, _draft: dict) -> list[dict]:
    return [
        {
            "source_file": "models/sale_markup.py",
            "kind": "python",
            "content": (
                "from odoo import fields, models\n\n"
                "class SaleOrder(models.Model):\n"
                "    _inherit = 'sale.order'\n"
                "    x_markup_percent = fields.Float(string='Markup %')\n"
            ),
        },
        {
            "source_file": "models/__init__.py",
            "kind": "python",
            "content": "from . import sale_markup\n",
        },
    ]


def test_client_markup_prompt_seeds_sale_order_inherit() -> None:
    from app.ai_conversation.clarify import apply_clarification_answer
    from app.ai_grain import preferred_inherit_host

    assert preferred_inherit_host(CLIENT_MARKUP) == "sale.order"
    plan = classify_generation(CLIENT_MARKUP)
    assert plan.capability == "option_a_authored"
    seed = maybe_seed_from_capability(CLIENT_MARKUP)
    assert seed is not None
    assert seed.get("display_name") == "Sales markup"
    models = seed.get("models") or []
    assert models and models[0].get("model") == "sale.order"
    assert models[0].get("mode") == "inherit"
    names = {str(f.get("name")) for f in (models[0].get("fields") or [])}
    assert "x_markup_percent" in names

    merged, _answers = apply_clarification_answer(
        CLIENT_MARKUP,
        merge_key="pack_choice",
        answer_id="on_existing_form",
        answer_text="Add it to a form you already use",
    )
    assert "Add fields" not in merged
    assert "Host: sale.order" in merged
    merged_plan = classify_generation(merged)
    assert merged_plan.capability == "option_a_authored"
    merged_seed = maybe_seed_from_capability(merged)
    assert merged_seed is not None
    assert (merged_seed.get("models") or [])[0].get("model") == "sale.order"


def test_markup_classifies_as_authored_not_gold() -> None:
    plan = classify_generation(MARKUP)
    assert plan.capability == "option_a_authored"
    assert plan.gold_artifact_id is None
    assert plan.module_delivery is True
    seed = maybe_seed_from_capability(MARKUP)
    assert seed is not None
    assert is_option_a_authored_draft(seed)
    assert not is_gold_option_a_draft(seed)


def test_delivery_note_classifies_as_authored_not_invoice_qweb() -> None:
    plan = classify_generation(DELIVERY)
    assert plan.capability == "option_a_authored"
    assert plan.gold_artifact_id is None
    seed = maybe_seed_from_capability(DELIVERY)
    assert seed is not None
    assert is_option_a_authored_draft(seed)


def test_unseen_http_cron_classifies_as_authored() -> None:
    plan = classify_generation(UNSEEN)
    assert plan.capability == "option_a_authored"
    assert "option_a_authored" in (plan.notes or [])


def test_cbn_still_gold() -> None:
    plan = classify_generation(CBN)
    assert plan.gold_artifact_id == "currency_rate_cbn"
    draft = maybe_seed_from_capability(CBN)
    assert draft is not None
    assert is_gold_option_a_draft(draft)
    assert not requires_authoring_gate(draft)
    assert authoring_gate_passed(draft)


def test_policy_blocks_os_ssrf_and_tax_create() -> None:
    draft = seed_option_a_authored("bad", classify_generation(MARKUP))
    draft["custom_code_blocks"] = [
        {
            "source_file": "models/bad.py",
            "kind": "python",
            "content": (
                "import os\n"
                "self.env['account.tax'].create({'name': 'WHT'})\n"
                "url = 'http://127.0.0.1/secret'\n"
            ),
        }
    ]
    codes = {f["code"] for f in policy_findings(draft)}
    assert "tax_create_forbidden" in codes
    assert "ssrf_host" in codes
    payload = evaluate_authoring_gate(draft)
    assert payload["status"] == "fail"
    lint_codes = {str(f.get("code")) for f in payload.get("findings") or []}
    assert "import_forbidden" in lint_codes or "tax_create_forbidden" in lint_codes


def test_stub_author_can_pass_gate() -> None:
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(
        draft, prompt=MARKUP, generate_blocks=_clean_inherit_blocks
    )
    assert payload["status"] == "pass"
    assert authoring_gate_passed(draft)
    assert any(
        str(b.get("source_file")).endswith("sale_markup.py")
        for b in draft.get("custom_code_blocks") or []
    )


def test_empty_authored_draft_blocks_zip() -> None:
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    assert requires_authoring_gate(draft)
    assert not authoring_gate_passed(draft)
    evaluate_authoring_gate(draft)
    assert not authoring_gate_passed(draft)


def test_author_gemini_503_is_retryable_without_empty_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.llm_provider import LLMError

    class Dummy:
        name = "gemini"

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy()
    )

    def boom(*_a, **_k):
        raise LLMError(
            'Gemini HTTP 503: { "error": { "code": 503, "message": "high demand", '
            '"status": "UNAVAILABLE" } }',
            status_code=503,
        )

    monkeypatch.setattr("app.llm_provider.generate_json_with_timeout_retry", boom)
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(draft, prompt=MARKUP)
    assert payload["status"] == "fail"
    assert payload["retryable"] is True
    codes = [row.get("code") for row in payload["findings"]]
    assert "author_failed" in codes
    assert "empty_module" not in codes
    assert "Retry authoring" in str(payload["findings"][0].get("message") or "")


def test_author_uses_timeout_retry_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dummy:
        name = "gemini"

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy()
    )
    monkeypatch.setattr(
        "app.llm_provider.generate_json_with_timeout_retry",
        lambda *_a, **_k: json.dumps({"blocks": _clean_inherit_blocks(MARKUP, {})}),
    )
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(draft, prompt=MARKUP)
    assert payload["status"] == "pass"
    assert authoring_gate_passed(draft)


def test_author_repairs_unterminated_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dummy:
        name = "gemini"

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy()
    )
    complete = json.dumps({"blocks": _clean_inherit_blocks(MARKUP, {})})
    truncated = complete.rsplit('"', 2)[0]
    monkeypatch.setattr(
        "app.llm_provider.generate_json_with_timeout_retry",
        lambda *_a, **_k: truncated,
    )
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(draft, prompt=MARKUP)
    assert draft.get("custom_code_blocks")
    assert payload.get("status") in {"pass", "fail"}


def test_author_retries_compact_json_then_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dummy:
        name = "gemini"

    calls = {"n": 0}

    def fake(_prov: object, prompt: str, **_k: object) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "{not json at all"
        return json.dumps({"blocks": _clean_inherit_blocks(MARKUP, {})})

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy()
    )
    monkeypatch.setattr("app.llm_provider.generate_json_with_timeout_retry", fake)
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(draft, prompt=MARKUP)
    assert calls["n"] == 2
    assert payload["status"] == "pass"


def test_author_empty_blocks_triggers_compact_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dummy:
        name = "gemini"

    calls = {"n": 0}

    def fake(_prov: object, prompt: str, **_k: object) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"blocks": []})
        return json.dumps({"blocks": _clean_inherit_blocks(MARKUP, {})})

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy()
    )
    monkeypatch.setattr("app.llm_provider.generate_json_with_timeout_retry", fake)
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(draft, prompt=MARKUP)
    assert calls["n"] == 2
    assert payload["status"] == "pass"


def test_coerce_author_payload_wraps_bare_array() -> None:
    rows = _clean_inherit_blocks(MARKUP, {})
    wrapped = coerce_author_payload(rows)
    assert wrapped["blocks"] == rows
    single = coerce_author_payload(rows[0])
    assert single["blocks"][0]["source_file"] == rows[0]["source_file"]


def test_author_accepts_bare_blocks_array(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dummy:
        name = "gemini"

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy()
    )
    monkeypatch.setattr(
        "app.llm_provider.generate_json_with_timeout_retry",
        lambda *_a, **_k: json.dumps(_clean_inherit_blocks(MARKUP, {})),
    )
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(draft, prompt=MARKUP)
    assert payload["status"] == "pass"
    assert authoring_gate_passed(draft)


def test_author_unrepairable_json_is_retryable_not_busy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Dummy:
        name = "gemini"

    monkeypatch.setattr(
        "app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy()
    )
    monkeypatch.setattr(
        "app.llm_provider.generate_json_with_timeout_retry",
        lambda *_a, **_k: "{not json at all",
    )
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    payload = author_option_a_module(draft, prompt=MARKUP)
    assert payload["status"] == "fail"
    assert payload["retryable"] is True
    msg = str(payload["findings"][0].get("message") or "")
    assert "incomplete JSON" in msg
    assert "busy" not in msg.lower()


def test_rewrite_sale_order_amount_tax_xpath() -> None:
    from app.ai_static_odoo import rewrite_draft_stock_xpaths, rewrite_stock_inherit_xpaths

    xml = (
        '<record id="view_order_form_with_markup" model="ir.ui.view">\n'
        '  <field name="model">sale.order</field>\n'
        '  <field name="inherit_id" ref="sale.view_order_form"/>\n'
        '  <field name="arch" type="xml">\n'
        '    <xpath expr="//field[@name=\'amount_tax\']" position="after">\n'
        '      <field name="x_markup_percent"/>\n'
        "    </xpath>\n"
        "  </field>\n"
        "</record>\n"
    )
    out = rewrite_stock_inherit_xpaths(xml)
    assert "amount_tax" not in out
    assert "tax_totals" in out
    draft = {
        "custom_code_blocks": [
            {"source_file": "views/sale_order_views.xml", "kind": "xml", "content": xml}
        ]
    }
    assert rewrite_draft_stock_xpaths(draft) == 1
    assert "tax_totals" in draft["custom_code_blocks"][0]["content"]
