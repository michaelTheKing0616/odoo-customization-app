"""Purchase request pack — retrieval, structure, and satellite scrub."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_domain_pack_purchase_request import purchase_request_pack
from app.ai_domain_packs import retrieve_domain_pack_lexical


class TestPurchaseRequestPackRetrieval:
    @pytest.mark.parametrize(
        "prompt",
        [
            "Purchase requests with amount, requester, and a manager approval flow",
            "Staff submit a purchase request; a manager must approve or refuse it",
            "I need an approval workflow for purchase requisitions",
            "Budget request with manager approval",
            "Spending approval flow",
        ],
    )
    def test_retrieves_purchase_request(self, prompt: str) -> None:
        result = retrieve_domain_pack_lexical(prompt)
        assert result is not None, f"No pack retrieved for: {prompt!r}"
        pack_id, _pack, _score = result
        assert pack_id == "purchase_request"


class TestPurchaseRequestPackStructure:
    def test_has_monetary_amount_and_currency(self) -> None:
        pack = purchase_request_pack()
        models = pack["models"]
        pr = next(m for m in models if m["model"] == "x_purchase_request")
        field_names = {f["name"] for f in pr["fields"]}
        assert "x_amount" in field_names
        assert "x_currency_id" in field_names
        amount = next(f for f in pr["fields"] if f["name"] == "x_amount")
        assert amount["ttype"] == "monetary"
        assert amount["required"] is True

    def test_requester_is_hr_employee(self) -> None:
        pack = purchase_request_pack()
        pr = next(m for m in pack["models"] if m["model"] == "x_purchase_request")
        req = next(f for f in pr["fields"] if f["name"] == "x_requester_id")
        assert req["relation"] == "hr.employee"

    def test_manager_is_res_users(self) -> None:
        pack = purchase_request_pack()
        pr = next(m for m in pack["models"] if m["model"] == "x_purchase_request")
        mgr = next(f for f in pr["fields"] if f["name"] == "x_manager_id")
        assert mgr["relation"] == "res.users"

    def test_no_subsidiary_models(self) -> None:
        pack = purchase_request_pack()
        models = [m["model"] for m in pack["models"]]
        assert len(models) == 1
        assert models[0] == "x_purchase_request"

    def test_document_shape_is_transactional_header(self) -> None:
        pack = purchase_request_pack()
        assert pack.get("document_shape") == "transactional_header"

    def test_currency_precedes_amount(self) -> None:
        pack = purchase_request_pack()
        pr = next(m for m in pack["models"] if m["model"] == "x_purchase_request")
        names = [f["name"] for f in pr["fields"]]
        assert names.index("x_currency_id") < names.index("x_amount")

    def test_approval_flow_marker(self) -> None:
        pack = purchase_request_pack()
        assert "_approval_flow" in pack

    def test_automation_targets_manager(self) -> None:
        pack = purchase_request_pack()
        auto = pack["automations"][0]
        action = auto["safe_actions"][0]
        assert action["user_field_name"] == "x_manager_id"
        assert action["user_type"] == "specific"
