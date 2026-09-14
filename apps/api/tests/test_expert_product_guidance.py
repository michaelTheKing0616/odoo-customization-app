"""Expert product UI guidance (in-app how-to)."""

from __future__ import annotations

from app.expert.grounding import GroundingBundle
from app.expert.product_guidance import (
    route_product_tools,
    try_rule_based_product_guidance,
)


def test_route_product_tools_designer() -> None:
    tools = route_product_tools(
        "How do I use the View Designer to add a field on invoices?",
        connection_id="abc",
    )
    assert any(t["id"] == "designer" for t in tools)
    assert "/connections/abc/designer" in tools[0]["deep_link"]


def test_product_guidance_account_move_not_module() -> None:
    bundle = GroundingBundle()
    out = try_rule_based_product_guidance(
        "I loaded account in the View Designer and the layout is wrong — how do I add fields to invoices?",
        bundle,
        connection_id="conn-1",
    )
    assert out is not None
    assert "rule_based_product_guidance" in (out.get("caution_flags") or [])
    md = out["answer_markdown"]
    assert "account.move" in md
    assert "not `account`" in md or "not an Apps module" in md.lower() or "module" in md.lower()
    tools = out.get("suggested_tools") or []
    assert any(t.get("id") == "designer" for t in tools)


def test_product_guidance_draft_studio_option_a() -> None:
    bundle = GroundingBundle()
    out = try_rule_based_product_guidance(
        "How do I use Draft Studio for click-to-pay on the invoice PDF?",
        bundle,
        connection_id="c2",
    )
    assert out is not None
    assert "Option A" in out["answer_markdown"] or "Sandbox" in out["answer_markdown"]
    assert any(t.get("id") == "wizard" for t in (out.get("suggested_tools") or []))


def test_product_guidance_ignores_unrelated() -> None:
    bundle = GroundingBundle()
    assert (
        try_rule_based_product_guidance(
            "What is the difference between many2one and many2many?",
            bundle,
            connection_id="c3",
        )
        is None
    )


def test_product_guidance_field_properties() -> None:
    bundle = GroundingBundle()
    out = try_rule_based_product_guidance(
        "How do I use Field properties for required when and barcode widget?",
        bundle,
        connection_id="conn-1",
    )
    assert out is not None
    md = out["answer_markdown"].lower()
    assert "field properties" in md
    assert "widget" in md
    assert "required" in md


def test_product_guidance_unlink_view() -> None:
    bundle = GroundingBundle()
    out = try_rule_based_product_guidance(
        "How do I unlink a view?",
        bundle,
        connection_id="conn-1",
    )
    assert out is not None
    md = out["answer_markdown"].lower()
    assert "unlink" in md
    assert "designer" in md
    assert "technical" in md


def test_product_guidance_duplicate_chrome() -> None:
    bundle = GroundingBundle()
    out = try_rule_based_product_guidance(
        "My bill form has Send|Send and Other Info twice — how do I fix duplicate chrome?",
        bundle,
        connection_id="conn-1",
    )
    assert out is not None
    assert "Fix duplicate chrome" in out["answer_markdown"] or "fix duplicate" in out[
        "answer_markdown"
    ].lower()


def test_priority_project_docs_include_feature_guide() -> None:
    from app.expert.ingest import _PRIORITY_PROJECT_DOCS, _project_doc_paths

    assert any("OPERATOR-FEATURE-DEMO-GUIDE.md" in p for p in _PRIORITY_PROJECT_DOCS)
    paths = _project_doc_paths()
    names = {p.name for p in paths}
    assert "OPERATOR-FEATURE-DEMO-GUIDE.md" in names
    assert "USER-GUIDE.md" in names
    assert "app-studio-host-install.md" in names
    assert any("docs/expert/product/app-studio-host-install.md" in p for p in _PRIORITY_PROJECT_DOCS)
