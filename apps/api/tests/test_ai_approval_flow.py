"""Community approval / execution flow stamps on residual drafts."""

from __future__ import annotations

from app.ai_approval_flow import apply_approval_flow, brief_wants_approval
from app.ai_conversation.refine import apply_refinement
from app.ai_odoo_app_bar import rebuild_form_transition_headers
from app.ai_workflow import build_transition_header_buttons, transition_button_label


def test_brief_wants_approval_phrases() -> None:
    assert brief_wants_approval(
        "Purchase requests with a manager approval flow: submit then approve or refuse"
    )
    assert not brief_wants_approval("Helpdesk tickets with requester and status workflow")
    assert not brief_wants_approval("approved host is sale.order")


def test_apply_approval_flow_stamps_submit_approve_refuse() -> None:
    draft = {
        "technical_name": "purchase_requests",
        "display_name": "Purchase Requests",
        "_user_prompt": (
            "Purchase requests with amount, requester, and a manager approval flow. "
            "Staff submit; manager approves or refuses."
        ),
        "models": [
            {
                "model": "x_purchase_request",
                "description": "Purchase Request",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference"},
                    {"name": "x_amount", "ttype": "float", "string": "Amount"},
                    {
                        "name": "x_manager_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                        "string": "Manager",
                    },
                ],
            }
        ],
        "views": [
            {
                "model": "x_purchase_request",
                "type": "form",
                "arch": '<form><sheet><group><field name="x_name"/></group></sheet></form>',
            }
        ],
    }
    notes = apply_approval_flow(draft)
    assert notes
    model = draft["models"][0]
    assert model["is_workflow"] is True
    sf = model["state_field"]
    assert sf["states"] == ["draft", "submitted", "approved", "refused"]
    assert ["draft", "submitted"] in sf["transitions"]
    assert ["submitted", "approved"] in sf["transitions"]
    assert ["submitted", "refused"] in sf["transitions"]
    status = next(f for f in model["fields"] if f["name"] == "x_status")
    assert status.get("readonly") is True
    flow = draft["_approval_flow"]
    assert flow["kind"] == "community_button_gate"
    autos = draft.get("automations") or []
    submitted_autos = [a for a in autos if "submitted" in str(a.get("filter_domain") or "")]
    assert submitted_autos
    safe0 = (submitted_autos[0].get("safe_actions") or [{}])[0]
    assert safe0.get("user_field_name") == "x_manager_id"
    assert safe0.get("user_type") == "specific"
    arch = draft["views"][0]["arch"]
    assert 'string="Submit"' in arch
    assert 'string="Approve"' in arch
    assert 'string="Refuse"' in arch
    assert 'data-approval-role="manager"' in arch
    assert "data-transition-to=\"approved\"" in arch


def test_refine_can_add_approval_flow() -> None:
    draft = {
        "technical_name": "leave",
        "display_name": "Leave",
        "models": [
            {
                "model": "x_leave_request",
                "fields": [{"name": "x_name", "ttype": "char", "string": "Subject"}],
            }
        ],
        "views": [
            {
                "model": "x_leave_request",
                "type": "form",
                "arch": '<form><sheet><field name="x_name"/></sheet></form>',
            }
        ],
    }
    result = apply_refinement(draft, "add a manager approval flow")
    assert result["ok"] is True
    assert result["draft"].get("_approval_flow")
    assert "Approve" in (result["draft"]["views"][0].get("arch") or "")


def test_transition_labels_for_approval() -> None:
    assert transition_button_label("draft", "submitted") == "Submit"
    assert transition_button_label("submitted", "approved") == "Approve"
    assert transition_button_label("submitted", "refused") == "Refuse"
    xml = build_transition_header_buttons(
        [["draft", "submitted"], ["submitted", "approved"], ["submitted", "refused"]],
        manager_dests={"approved", "refused"},
    )
    assert "Submit" in xml and "Approve" in xml and "Refuse" in xml
    assert xml.count('data-approval-role="manager"') == 2


def test_rebuild_headers_uses_state_field_name() -> None:
    draft = {
        "models": [
            {
                "model": "x_request",
                "is_workflow": True,
                "state_field": {
                    "field": "x_status",
                    "transitions": [["draft", "submitted"]],
                    "statusbar_visible": ["draft", "submitted"],
                    "approval": True,
                },
            }
        ],
        "views": [
            {
                "model": "x_request",
                "type": "form",
                "arch": '<form><header></header><sheet/></form>',
            }
        ],
        "_approval_flow": {"manager_dests": ["approved", "refused"]},
    }
    rebuild_form_transition_headers(draft)
    arch = draft["views"][0]["arch"]
    assert 'name="x_status"' in arch
    assert "Submit" in arch
