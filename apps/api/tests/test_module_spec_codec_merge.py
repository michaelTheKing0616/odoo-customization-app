"""Tests for merge_module_spec_fragment."""

from __future__ import annotations

from app.invoicing_connect import module_spec_fragment
from app.module_spec_codec import merge_module_spec_fragment


def test_merge_invoicing_fragment_depends_and_smart_button() -> None:
    base = {
        "technical_name": "x_matter_app",
        "depends": ["base"],
        "models": [{"model": "x_matter", "fields": [{"name": "x_name", "ttype": "char"}]}],
    }
    frag = module_spec_fragment(model="x_matter")
    merged = merge_module_spec_fragment(base, frag)
    assert "account" in merged["depends"]
    assert any(m["model"] == "account.move" for m in merged["models"])
    assert merged["smart_buttons"][0]["on_model"] == "x_matter"
    assert any("review_note" in str(n) or "inverse" in str(n) for n in merged.get("review_notes", []))
