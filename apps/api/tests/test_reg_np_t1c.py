"""REG-NP-T1c — date family stays. Uncued Type/Priority/Rate/Severity/Channel/Stage drop.

Origin 38008ed1 drops those six families when the brief has no cue. The no-op
scrub contradicted that contract (x_severity, x_vehicle_type, x_type kept).
"""

from __future__ import annotations

import os

os.environ["AI_INTENT_LLM"] = "off"

import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_brief_cues import (  # noqa: E402
    _scrub_uncued_invent_must_do_partition,
    honor_stated_brief_cues,
    scrub_uncued_invent_must_do_rows,
)
from app.ai_conversation.understand import APPROVED_CRAFT_KEYS  # noqa: E402

_PROMPT = "tickets"
_ROWS = [
    "Field: Type",
    "Field: Priority",
    "Field: Unit",
    "Field: Rate Unit",
    "Field: Severity",
    "Selection field: Channel",
    "Field: Stage",
    "Due date",
    "Date",
    "Start date",
    "End date",
    "Deadline",
]


_DATE_ROWS = [
    "Due date",
    "Date",
    "Start date",
    "End date",
    "Deadline",
]


def test_ac1_uncued_rows_kept_and_removed_empty() -> None:
    """Date family stays. Uncued Type/Priority/Rate/Severity/Channel/Stage rows drop."""
    kept, removed = _scrub_uncued_invent_must_do_partition(_ROWS, prompt=_PROMPT)
    assert kept == _DATE_ROWS
    assert set(removed) == set(_ROWS) - set(_DATE_ROWS)
    assert scrub_uncued_invent_must_do_rows(_ROWS, prompt=_PROMPT) == _DATE_ROWS


def test_ac1_honor_keeps_uncued_invent_on_draft_and_must_do() -> None:
    """Uncued invent fields drop. Due date stays on the draft and in must-do."""
    prompt = "tickets"
    fields = [
        {
            "name": "x_type",
            "ttype": "selection",
            "string": "Type",
            "selection": "[('a','A')]",
            "source": "density",
        },
        {
            "name": "x_priority",
            "ttype": "selection",
            "string": "Priority",
            "selection": "[('0','Low')]",
            "source": "pack_default",
        },
        {
            "name": "x_rate_unit",
            "ttype": "selection",
            "string": "Rate Unit",
            "selection": "[('day','Day')]",
            "source": "llm",
        },
        {
            "name": "x_severity",
            "ttype": "selection",
            "string": "Severity",
            "selection": "[('low','Low')]",
            "source": "flash",
        },
        {
            "name": "x_channel",
            "ttype": "selection",
            "string": "Channel",
            "selection": "[('email','Email')]",
            "source": "density",
        },
        {
            "name": "x_stage",
            "ttype": "selection",
            "string": "Stage",
            "selection": "[('new','New')]",
            "source": "llm",
        },
        {
            "name": "x_due_date",
            "ttype": "date",
            "string": "Due date",
            "source": "flash",
        },
    ]
    draft = {
        "display_name": "Ticket",
        "_user_prompt": prompt,
        "models": [{"model": "x_support_ticket", "mode": "new", "fields": list(fields)}],
    }
    honor_stated_brief_cues(draft, prompt=prompt)
    stayed = [str(f.get("name")) for f in draft["models"][0]["fields"]]
    assert stayed == ["x_due_date"]
    rows = [f"Field: {f['string']}" for f in fields]
    kept, removed = _scrub_uncued_invent_must_do_partition(rows, prompt=prompt)
    assert kept == ["Field: Due date"]
    assert "Field: Due date" not in removed
    assert len(removed) == len(rows) - 1


def test_ac2_date_datetime_and_money_are_approved_craft() -> None:
    assert "date_slots" in APPROVED_CRAFT_KEYS
    assert "datetime_over_date" in APPROVED_CRAFT_KEYS
    assert "money_slots" in APPROVED_CRAFT_KEYS
