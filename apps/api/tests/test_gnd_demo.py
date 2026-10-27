"""GND-DEMO: one scripted model call, then a version/edition check."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from app.llm_provider import LLMProvider
from app.live_demo_copilot.stage2_answer import (
    CUSTOMIZATION,
    LIVE_UNCERTAIN_BANNER,
    NOT_SURE,
    STOCK_COMMUNITY,
    STOCK_ENTERPRISE_ONLY,
    STOCK_ONCE_INSTALLED,
    DemoProposal,
    all_version_claim_tokens,
    check_demo_proposal,
    claimed_technical_names,
    generate_live_answer,
    present_version_claim_tokens,
)

pytestmark = pytest.mark.no_app_db

_STOCK = {STOCK_COMMUNITY, STOCK_ENTERPRISE_ONLY, STOCK_ONCE_INSTALLED}
_CONNECT_ASK = re.compile(
    r"connect (a |an |your |the )?(database|db|odoo instance|instance)",
    re.I,
)


class ScriptedDemoModel(LLMProvider):
    """Canned JSON. No network, no live key. A wrong verdict is allowed."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.json_calls = 0
        self.text_calls = 0
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "scripted-demo"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "scripted"

    def generate_json(self, prompt: str, **kwargs: Any) -> str:
        self.json_calls += 1
        self.prompts.append(prompt)
        return json.dumps(self.payload)

    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        self.text_calls += 1
        raise AssertionError("a second model call must not rewrite bullets")


def _surface(answer) -> str:
    return " ".join(
        [
            answer.verdict,
            answer.answer_markdown or "",
            " ".join(answer.bullets),
            answer.confidence_flag or "",
            answer.app_name or "",
        ]
    )


def _answer(
    question: str,
    payload: dict[str, Any],
    *,
    major: int = 20,
    edition: str = "community",
) -> tuple[Any, ScriptedDemoModel]:
    model = ScriptedDemoModel(payload)
    answer = generate_live_answer(
        None,
        question=question,
        connection_id=None,
        major=major,
        edition=edition,
        provider=model,
    )
    return answer, model


def test_quotations_community_20_is_sales_stock_and_does_not_ask_for_a_database() -> None:
    answer, model = _answer(
        "Can Odoo do quotations?",
        {
            "verdict": "stock_community",
            "app": "Sales",
            "text": (
                "Stock Community — Sales. "
                "Quotations are a standard Sales feature on Odoo Community 20."
            ),
            "claimed_names": [],
            "hosting_depends": False,
        },
        major=20,
        edition="community",
    )
    assert answer.verdict == STOCK_COMMUNITY
    assert answer.app_name == "Sales"
    assert "Community" in _surface(answer)
    assert "Sales" in _surface(answer)
    assert "database" not in _surface(answer).lower()
    assert not _CONNECT_ASK.search(_surface(answer))
    assert model.json_calls == 1
    assert model.text_calls == 0
    assert re.search(r"QUESTION: <<UNTRUSTED source=client_chat id=\w+>>\n" + re.escape('Can Odoo do quotations?'), model.prompts[0])
    assert 2 <= len(answer.bullets) <= 3
    for bullet in answer.bullets:
        assert bullet in answer.answer_markdown


def test_helpdesk_community_is_enterprise_only_when_the_model_says_so() -> None:
    answer, model = _answer(
        "Can Odoo do a helpdesk?",
        {
            "verdict": "stock_enterprise_only",
            "app": "Helpdesk",
            "text": (
                "Stock Enterprise only — Helpdesk. "
                "Helpdesk is not in Community. "
                "This is not a customization."
            ),
            "claimed_names": [],
        },
        edition="community",
    )
    assert answer.verdict == STOCK_ENTERPRISE_ONLY
    assert answer.app_name == "Helpdesk"
    assert answer.verdict != STOCK_COMMUNITY
    assert answer.verdict != CUSTOMIZATION
    blob = _surface(answer)
    assert "Enterprise" in blob
    assert "not in Community" in blob
    assert model.json_calls == 1
    assert model.text_calls == 0
    assert re.search(r"QUESTION: <<UNTRUSTED source=client_chat id=\w+>>\n" + re.escape('Can Odoo do a helpdesk?'), model.prompts[0])


def test_check_refuses_helpdesk_as_community_stock() -> None:
    answer, model = _answer(
        "Can Odoo do a helpdesk?",
        {
            "verdict": "stock_community",
            "app": "Helpdesk",
            "text": "Stock Community — Helpdesk. Tickets are a Community stock app.",
            "claimed_names": [],
        },
        edition="community",
    )
    assert model.json_calls == 1
    assert answer.check_passed is False
    assert answer.verdict == NOT_SURE
    assert answer.verdict != STOCK_COMMUNITY
    assert answer.app_name is None
    assert "Community stock" not in answer.answer_markdown
    assert answer.confidence == "low"
    assert answer.confidence_flag == LIVE_UNCERTAIN_BANNER
    fail = check_demo_proposal(
        DemoProposal(
            verdict=STOCK_COMMUNITY,
            app="Helpdesk",
            text="Stock Community — Helpdesk.",
            claimed_names=(),
            hosting_depends=False,
        ),
        major=20,
        edition="community",
    )
    assert fail == "enterprise_app_as_community_stock"


def test_bank_api_is_never_stock() -> None:
    answer, model = _answer(
        "Can Odoo post to our bank's API?",
        {
            "verdict": "customization",
            "app": "",
            "text": (
                "Customization. "
                "Posting to a bank's API is not a stock Odoo feature on Community 20."
            ),
            "claimed_names": [],
        },
    )
    assert answer.verdict in {CUSTOMIZATION, NOT_SURE}
    assert answer.verdict not in _STOCK
    assert answer.app_name is None
    assert model.json_calls == 1
    assert model.text_calls == 0
    assert re.search(r"QUESTION: <<UNTRUSTED source=client_chat id=\w+>>\n" + re.escape("Can Odoo post to our bank's API?"), model.prompts[0])


def test_feature_only_on_20_is_not_stock_on_19() -> None:
    payload = {
        "verdict": "stock_community",
        "app": "Settings",
        "text": "Stock Community — Settings. ir.access is the access model.",
        "claimed_names": ["ir.access"],
    }
    on_20, model_20 = _answer(
        "Can Odoo use ir.access?", payload, major=20, edition="community"
    )
    on_19, model_19 = _answer(
        "Can Odoo use ir.access?", payload, major=19, edition="community"
    )
    assert model_20.json_calls == 1
    assert model_19.json_calls == 1
    assert on_20.verdict in _STOCK
    assert on_19.verdict not in _STOCK
    assert on_19.verdict == NOT_SURE
    assert on_19.check_passed is False
    assert not on_19.answer_markdown.lower().startswith("stock")
    assert "ir.access" not in claimed_technical_names(on_19.answer_markdown)


def test_not_sure_keeps_low_confidence_on_screen() -> None:
    answer, _model = _answer(
        "Can Odoo teleport invoices to Mars?",
        {
            "verdict": "not_sure",
            "app": "",
            "text": "Not sure. The version table does not list this as stock on Odoo Community 20.",
        },
    )
    assert answer.verdict == NOT_SURE
    assert answer.confidence == "low"
    assert answer.confidence_flag == LIVE_UNCERTAIN_BANNER


def test_never_asks_to_connect_a_database() -> None:
    payloads = (
        (
            "Can Odoo do quotations?",
            {
                "verdict": "stock_community",
                "app": "Sales",
                "text": "Stock Community — Sales. Connect a database to confirm.",
            },
        ),
        (
            "Can Odoo do a helpdesk?",
            {
                "verdict": "stock_enterprise_only",
                "app": "Helpdesk",
                "text": "Stock Enterprise only — Helpdesk. Helpdesk is not in Community.",
            },
        ),
        (
            "Can Odoo post to our bank's API?",
            {"verdict": "customization", "app": "", "text": "Customization."},
        ),
    )
    for question, payload in payloads:
        answer, _model = _answer(question, payload)
        blob = _surface(answer).lower()
        assert "connect a database" not in blob
        assert "connect an odoo" not in blob


def test_answer_never_claims_a_field_absent_from_the_version_table() -> None:
    version_tokens = all_version_claim_tokens()
    cases = (
        (
            20,
            {
                "verdict": "stock_community",
                "app": "Settings",
                "text": "Stock Community — Settings. ir.access is listed on 20.",
                "claimed_names": ["ir.access"],
            },
        ),
        (
            19,
            {
                "verdict": "stock_community",
                "app": "Settings",
                "text": "Stock Community — Settings. ir.access is listed on 20.",
                "claimed_names": ["ir.access"],
            },
        ),
        (
            19,
            {
                "verdict": "stock_community",
                "app": "Sales",
                "text": "Stock Community — Sales. Quotations are stock.",
                "claimed_names": [],
            },
        ),
    )
    for major, payload in cases:
        answer, _model = _answer("Can Odoo do this?", payload, major=major)
        allowed = present_version_claim_tokens(major)
        for name in claimed_technical_names(_surface(answer)):
            if name in version_tokens:
                assert name in allowed


def test_major_16_is_not_a_demo_target() -> None:
    model = ScriptedDemoModel(
        {
            "verdict": "stock_community",
            "app": "Sales",
            "text": "Stock Community — Sales.",
        }
    )
    answer = generate_live_answer(
        None,
        question="Can Odoo do quotations?",
        connection_id=None,
        major=16,
        edition="community",
        provider=model,
    )
    assert model.json_calls == 0
    assert answer.verdict == NOT_SURE
    assert answer.verdict not in _STOCK


def test_second_model_call_is_not_used() -> None:
    answer, model = _answer(
        "Can Odoo do quotations?",
        {
            "verdict": "stock_community",
            "app": "Sales",
            "text": (
                "Stock Community — Sales. "
                "Quotations are a standard Sales feature on Odoo Community 20."
            ),
        },
    )
    assert model.json_calls == 1
    assert model.text_calls == 0
    assert answer.bullets == [
        p.strip()
        for p in re.split(r"(?<=[.!?])\s+", answer.answer_markdown.strip())
        if p.strip()
    ][:3]


def test_each_answer_names_the_edition() -> None:
    for edition, label in (
        ("community", "Community"),
        ("enterprise", "Enterprise"),
        ("both", "Community and Enterprise"),
    ):
        answer, _model = _answer(
            "Can Odoo do quotations?",
            {
                "verdict": "stock_community",
                "app": "Sales",
                "text": "Stock Community — Sales.",
            },
            edition=edition,
        )
        assert label in _surface(answer)
        assert answer.demo_edition == edition


def test_model_not_sure_on_quotations_is_not_upgraded_to_sales_stock() -> None:
    answer, model = _answer(
        "Can Odoo do quotations?",
        {"verdict": "not_sure", "app": "", "text": "Not sure."},
        major=20,
        edition="community",
    )
    assert model.json_calls == 1
    assert re.search(r"QUESTION: <<UNTRUSTED source=client_chat id=\w+>>\n" + re.escape('Can Odoo do quotations?'), model.prompts[0])
    assert answer.verdict == NOT_SURE
    assert answer.verdict != STOCK_COMMUNITY
    assert answer.app_name is None
    assert answer.confidence == "low"
    assert answer.confidence_flag == LIVE_UNCERTAIN_BANNER


def test_bank_api_stock_claim_is_rejected_to_not_sure() -> None:
    answer, model = _answer(
        "Can Odoo post to our bank's API?",
        {
            "verdict": "stock_community",
            "app": "Accounting",
            "text": "Stock Community — Accounting. Posting to the bank API is built in.",
        },
    )
    assert model.json_calls == 1
    assert model.text_calls == 0
    assert answer.check_passed is False
    assert answer.verdict == NOT_SURE
    assert answer.verdict not in _STOCK
    assert answer.confidence == "low"
    assert answer.confidence_flag == LIVE_UNCERTAIN_BANNER
    fail = check_demo_proposal(
        DemoProposal(
            verdict=STOCK_COMMUNITY,
            app="Accounting",
            text="Stock Community — Accounting.",
            claimed_names=(),
            hosting_depends=False,
        ),
        major=20,
        edition="community",
        question="Can Odoo post to our bank's API?",
    )
    assert fail == "partner_api_not_stock"


def test_helpdesk_customization_is_rejected_to_not_sure() -> None:
    answer, model = _answer(
        "Can Odoo do a helpdesk?",
        {
            "verdict": "customization",
            "app": "",
            "text": "Customization. Build a ticket model.",
        },
        edition="community",
    )
    assert model.json_calls == 1
    assert answer.check_passed is False
    assert answer.verdict == NOT_SURE
    assert answer.verdict != CUSTOMIZATION
    assert answer.verdict != STOCK_COMMUNITY
    assert answer.confidence == "low"
