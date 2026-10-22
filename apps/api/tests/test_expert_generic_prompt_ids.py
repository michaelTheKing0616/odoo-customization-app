"""The web Expert tip dot (touch 110) treats these ids as generic. Keep them in step."""
from app.expert.suggested_prompts import suggested_prompts_for_context


def test_generic_prompts_are_modules_and_security():
    ids = {p["id"] for p in suggested_prompts_for_context(route="/connections/x/overview")}
    assert ids == {"modules", "security"}


def test_page_prompts_differ():
    ids = {p["id"] for p in suggested_prompts_for_context(route="/connections/x/automations")}
    assert ids - {"modules", "security"}
