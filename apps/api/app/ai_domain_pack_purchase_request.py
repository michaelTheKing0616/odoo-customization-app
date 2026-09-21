"""Purchase / approval request — deterministic seed for staff-submit + manager-approve prompts."""

from __future__ import annotations

import copy
from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def purchase_request_pack() -> dict[str, Any]:
    state = _sel(
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("refused", "Refused"),
    )

    return {
        "technical_name": "purchase_request",
        "display_name": "Purchase Requests",
        "depends": ["base", "mail", "hr"],
        "domain_pack": "purchase_request",
        "document_shape": "transactional_header",
        "tags": [
            "purchase request",
            "purchase requisition",
            "requisition",
            "spending",
            "budget request",
            "procurement",
        ],
        "anti_patterns": [
            "Do NOT reuse stock purchase.order — this is a lightweight staff approval form",
            "Do NOT create x_requester or x_manager as standalone models — use hr.employee / res.users relations",
            "Do NOT add x_agreement, x_expense, or subsidiary models — single document only",
            "Requester links to hr.employee, Manager links to res.users for activity assignment",
        ],
        "models": [
            {
                "model": "x_purchase_request",
                "description": "Purchase Request",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_state",
                    "transitions": [
                        ["draft", "submitted"],
                        ["submitted", "approved"],
                        ["submitted", "refused"],
                    ],
                    "states": ["draft", "submitted", "approved", "refused"],
                    "statusbar_visible": ["draft", "submitted", "approved", "refused"],
                },
                "fields": [
                    {
                        "name": "x_name",
                        "ttype": "char",
                        "string": "Reference",
                        "required": True,
                        "help": "Auto-numbered via ir.sequence (PR/00001)",
                    },
                    {
                        "name": "x_subject",
                        "ttype": "char",
                        "string": "Subject",
                        "required": True,
                        "help": "Short description of the purchase request.",
                    },
                    {
                        "name": "x_requester_id",
                        "ttype": "many2one",
                        "string": "Requester",
                        "relation": "hr.employee",
                        "required": True,
                        "help": "Employee who submitted this request — link-only to HR.",
                    },
                    {
                        "name": "x_manager_id",
                        "ttype": "many2one",
                        "string": "Manager",
                        "relation": "res.users",
                        "required": True,
                        "help": "Manager responsible for approving or refusing the request.",
                    },
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "string": "Currency",
                        "relation": "res.currency",
                        "required": True,
                        "help": "Currency for the requested amount.",
                    },
                    {
                        "name": "x_amount",
                        "ttype": "monetary",
                        "string": "Amount",
                        "required": True,
                        "currency_field": "x_currency_id",
                        "widget": "monetary",
                        "help": "Requested purchase amount.",
                    },
                    {
                        "name": "x_state",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": state,
                        "required": True,
                        "default": "draft",
                        "tracking": True,
                    },
                    {
                        "name": "x_description",
                        "ttype": "text",
                        "string": "Description",
                        "help": "Detailed justification for the purchase.",
                    },
                    {
                        "name": "x_date_request",
                        "ttype": "date",
                        "string": "Request Date",
                    },
                    {
                        "name": "x_date_approved",
                        "ttype": "date",
                        "string": "Approved Date",
                    },
                ],
                "is_mail_thread": True,
                "is_mail_activity": True,
            },
        ],
        "views": [
            {
                "model": "x_purchase_request",
                "type": "form",
                "arch_sections": {
                    "header": [
                        {"button": "Submit", "transition": "submitted", "from_states": ["draft"]},
                        {"button": "Approve", "transition": "approved", "from_states": ["submitted"], "class": "btn-primary"},
                        {"button": "Refuse", "transition": "refused", "from_states": ["submitted"], "class": "btn-danger"},
                    ],
                    "sheet": [
                        {
                            "group": "IDENTITY",
                            "fields": ["x_name", "x_subject"],
                        },
                        {
                            "group": "REQUEST DETAILS",
                            "col_left": ["x_requester_id", "x_date_request"],
                            "col_right": ["x_manager_id", "x_date_approved"],
                        },
                        {
                            "group": "AMOUNT",
                            "col_left": ["x_amount", "x_currency_id"],
                        },
                        {
                            "group": None,
                            "fields": ["x_description"],
                        },
                    ],
                },
            },
            {
                "model": "x_purchase_request",
                "type": "list",
                "fields": [
                    "x_name",
                    "x_subject",
                    "x_requester_id",
                    "x_manager_id",
                    "x_amount",
                    "x_currency_id",
                    "x_state",
                    "x_date_request",
                ],
            },
        ],
        "actions": [
            {
                "name": "Purchase Requests",
                "model": "x_purchase_request",
                "view_mode": "list,form",
                "technical_name": "action_x_purchase_request",
            },
        ],
        "menus": [
            {
                "name": "Purchase Requests",
                "technical_name": "menu_purchase_request_root",
                "sequence": 10,
            },
            {
                "name": "Requests",
                "action_xml_id": "action_x_purchase_request",
                "parent_xml_id": "menu_purchase_request_root",
                "sequence": 10,
                "technical_name": "menu_purchase_requests",
            },
        ],
        "automations": [
            {
                "name": "Notify manager on submit",
                "model": "x_purchase_request",
                "trigger": "on_state_change",
                "trigger_state": "submitted",
                "safe_actions": [
                    {
                        "kind": "next_activity",
                        "summary": "Approve or refuse this purchase request",
                        "activity_type_xml_id": "mail.mail_activity_data_todo",
                        "user_type": "specific",
                        "user_field_name": "x_manager_id",
                    }
                ],
                "_approval_flow": {"kind": "community_button_gate"},
            },
        ],
        "_approval_flow": {"kind": "community_button_gate"},
        "reuse_hints": [
            {
                "model": "hr.employee",
                "reason": "Requester on purchase requests — do not invent x_requester",
            },
            {
                "model": "res.users",
                "reason": "Manager for approval — do not invent x_manager model",
            },
        ],
        "reuse_stock": [
            {
                "model": "hr.employee",
                "reason": "Purchase requester",
                "forbid_parallel": ["x_requester", "x_requesters", "x_staff", "x_employee"],
            },
        ],
    }


_PURCHASE_REQUEST_INTENT_RE = None


def purchase_request_intent(prompt: str) -> bool:
    """True when the brief is a staff purchase / spend / budget requisition.

    Bare «manager approve» is NOT enough — that phrase appears on Vehicle Request
    and any residual approval workflow. Align with match_domain_pack regex: require
    purchase/spend/budget/requisition/approval-request cues. Fleet/vehicle/visitor
    residuals without those cues never adopt the purchase pack surface.
    """
    global _PURCHASE_REQUEST_INTENT_RE
    if _PURCHASE_REQUEST_INTENT_RE is None:
        import re

        _PURCHASE_REQUEST_INTENT_RE = re.compile(
            r"(?i)\b(?:"
            r"purchase\s+requests?|purchase\s+requisitions?|"
            r"spend(?:ing)?\s+(?:request|approval)|"
            r"budget\s+(?:request|approval)|"
            r"requisitions?|procurement"
            # Never bare «manager approve» / «approval request» — those steal
            # Vehicle / Visitor / Approval Workflow residuals.
            r")"
        )
    text = prompt or ""
    if not _PURCHASE_REQUEST_INTENT_RE.search(text):
        return False
    # Residual fleet/vehicle/visitor nouns without purchase cues → not purchase.
    import re

    residual_foreign = re.search(
        r"(?i)\b(?:fleet|vehicle|visitor|reservation|dining\s+table|punch\s*card)\b",
        text,
    )
    purchase_cue = re.search(
        r"(?i)\b(?:purchase|spend(?:ing)?|budget|requisition|procurement)\b",
        text,
    )
    if residual_foreign and not purchase_cue:
        return False
    return True


def _is_purchase_request_draft(draft: dict[str, Any], prompt: str) -> bool:
    text = prompt or str(draft.get("_user_prompt") or "")
    if purchase_request_intent(text):
        return True
    # Stamped domain_pack alone is not enough — weak Jaccard can label a Vehicle
    # residual as purchase_request. Only trust the stamp when the residual noun
    # itself reads as purchase/spend/budget.
    if str(draft.get("domain_pack") or "") != "purchase_request":
        return False
    try:
        from app.ai_document_shape import naming_from_residual

        residual_name, _slug = naming_from_residual(text)
    except Exception:  # noqa: BLE001
        residual_name = ""
    rn = (residual_name or "").strip().lower()
    return bool(rn) and any(k in rn for k in ("purchase", "requisition", "spend", "budget"))


def scrub_purchase_request_prompt_fit(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """One purchase-request document — no invented Agreements/Expenses/Requester apps."""
    text = prompt or str(draft.get("_user_prompt") or "")

    def _residual_is_foreign_to_purchase() -> bool:
        try:
            from app.ai_document_shape import naming_from_residual

            residual_name, _residual_slug = naming_from_residual(text)
        except Exception:  # noqa: BLE001
            residual_name = ""
        rn = (residual_name or "").strip().lower()
        return bool(rn) and not any(
            k in rn for k in ("purchase", "requisition", "spend", "budget")
        )

    # Always peel a wrongly stamped purchase pack when residual noun diverges
    # (Vehicle / Visitor / …), even when intent is already false.
    if _residual_is_foreign_to_purchase() and str(draft.get("domain_pack") or "") == "purchase_request":
        draft.pop("domain_pack", None)
        draft.pop("_pack_model_ids", None)
        if not _is_purchase_request_draft(draft, text):
            return ["purchase_request: cleared foreign domain_pack stamp"]

    if not _is_purchase_request_draft(draft, text):
        return []
    if _residual_is_foreign_to_purchase():
        return []

    notes: list[str] = []
    pack = purchase_request_pack()
    allowed = {
        str(m.get("model") or "")
        for m in (pack.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    }
    removed = {
        str(m.get("model") or "")
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("model") or "") not in allowed
    }
    if removed:
        from app.ai_domain_packs import _purge_draft_artifacts_for_models

        try:
            from app.ai_odoo_app_bar import _retarget_removed_relations

            notes.extend(_retarget_removed_relations(draft, removed))
        except Exception:  # noqa: BLE001
            pass
        _purge_draft_artifacts_for_models(draft, removed)
        notes.append("purchase_request: dropped " + ", ".join(sorted(removed)))

    header = next(
        (
            m
            for m in (draft.get("models") or [])
            if isinstance(m, dict) and str(m.get("model") or "") == "x_purchase_request"
        ),
        None,
    )
    if header is None:
        draft.setdefault("models", []).append(copy.deepcopy(pack["models"][0]))
        notes.append("purchase_request: seeded x_purchase_request")
        header = draft["models"][-1]

    pack_header = pack["models"][0]
    pack_fields = {
        str(f.get("name") or ""): f
        for f in (pack_header.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }
    existing = {
        str(f.get("name") or ""): f
        for f in (header.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }
    for fname, pf in pack_fields.items():
        if fname not in existing:
            header.setdefault("fields", []).append(copy.deepcopy(pf))
            notes.append(f"purchase_request: added field {fname}")
        else:
            df = existing[fname]
            if pf.get("required") and not df.get("required"):
                df["required"] = True
            if pf.get("relation") and str(df.get("relation") or "") != str(pf.get("relation")):
                df["relation"] = pf["relation"]
                notes.append(
                    f"purchase_request: retargeted {fname} → {pf['relation']}"
                )
            if pf.get("ttype") and str(df.get("ttype") or "") != str(pf.get("ttype")):
                if pf["ttype"] == "monetary":
                    df["ttype"] = "monetary"
                    if pf.get("currency_field"):
                        df["currency_field"] = pf["currency_field"]
                    notes.append(f"purchase_request: {fname} is monetary")

    # Drop one2many/many2many tabs that are not in the seed (Agreements / Expenses).
    keep_rel = set(pack_fields)
    header["fields"] = [
        f
        for f in (header.get("fields") or [])
        if not (
            isinstance(f, dict)
            and str(f.get("ttype") or "") in {"one2many", "many2many"}
            and str(f.get("name") or "") not in keep_rel
        )
    ]

    if str(draft.get("display_name") or "") in {
        "",
        "Named In Brief",
        "Named Briefs",
        "Named In Briefs",
        "Custom App",
    } or "named in brief" in str(draft.get("display_name") or "").lower():
        draft["display_name"] = pack["display_name"]
        notes.append("purchase_request: restored display_name")
    if str(draft.get("technical_name") or "") in {"", "named_in_brief", "custom_app"}:
        draft["technical_name"] = pack["technical_name"]
        notes.append("purchase_request: restored technical_name")

    draft["domain_pack"] = "purchase_request"
    if not draft.get("_approval_flow"):
        draft["_approval_flow"] = copy.deepcopy(pack["_approval_flow"])
    if not draft.get("automations") and pack.get("automations"):
        draft["automations"] = copy.deepcopy(pack["automations"])
        notes.append("purchase_request: seeded manager to-do automation")

    depends = [str(d) for d in (draft.get("depends") or []) if d]
    for dep in pack.get("depends") or []:
        if dep not in depends:
            depends.append(dep)
    draft["depends"] = depends

    return notes


__all__ = [
    "purchase_request_intent",
    "purchase_request_pack",
    "scrub_purchase_request_prompt_fit",
]
