"""Pin P0-2-CL3.

Owner-facing pack-ambiguity copy is plain language. It does not say
ModuleSpec, Option A module, vertical pack, or which domain.
"""

from __future__ import annotations

import pytest

from app.ai_conversation.clarify import build_clarification
from app.ai_conversation.intent_gate import IntentAssessment

pytestmark = pytest.mark.no_app_db

_BANNED = ("modulespec", "option a module", "vertical pack", "which domain", "helpdesk")


def test_pack_ambiguity_owner_copy_is_plain_language() -> None:
    """Placement question stays plain and the first choice is an existing form.

    Fails if ``build_clarification`` drops ``Where should this live in Odoo?``
    or the first option ``on_existing_form`` / ``Add it to a form you already use``
    in ``app/ai_conversation/clarify.py``.
    """
    assessment = IntentAssessment(
        clear=False,
        triggers=["pack_ambiguity"],
        competing_pack_id="project_tracker",
        notes=["Ambiguous pack fit: project_tracker@0.31 vs restaurant@0.29"],
    )
    clarify = build_clarification(assessment, prompt="track our work this quarter")
    assert clarify is not None
    assert clarify["question"] == "Where should this live in Odoo?"
    assert "vendor bills or invoices" in str(clarify["help"])
    assert "brand-new record" in str(clarify["help"])
    options = list(clarify["options"])
    assert options[0]["id"] == "on_existing_form"
    assert str(options[0]["label"]).startswith("Add it to a form you already use")
    ids = [opt["id"] for opt in options]
    assert "transactional" in ids
    assert "helpdesk_tickets" not in ids
    blob = " ".join(
        [str(clarify.get("question") or ""), str(clarify.get("help") or "")]
        + [str(opt.get("label") or "") for opt in options]
    ).lower()
    for banned in _BANNED:
        assert banned not in blob
