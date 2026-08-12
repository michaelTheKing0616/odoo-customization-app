"""EXP-2 grounding assembly tests (fake caches; optional live smoke)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.grounding import (  # noqa: E402
    GroundingBundle,
    assemble_context,
    cross_check_schema,
    extract_model_field_refs,
    looks_like_rpc_error,
    match_capability_highlights,
    route_bulk_tools,
    serialize_bundle,
)
from app.protected_modules import community_manifest_for_version, manifest_to_json  # noqa: E402


class _FakeClient:
    def __init__(self) -> None:
        self.models = {"x_matter", "account.move", "res.partner"}
        self.fields: dict[str, set[str]] = {
            "x_matter": {"x_status", "x_name", "x_invoice_ids"},
            "account.move": {"name", "state"},
        }

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def field_exists(self, model: str, name: str) -> bool:
        return name in self.fields.get(model, set())

    def list_fields(self, model: str):
        from types import SimpleNamespace

        return [SimpleNamespace(name=n) for n in sorted(self.fields.get(model, set()))]

    def execute_kw(self, model: str, method: str, args, kwargs=None):
        if model == "ir.model" and method == "search_read":
            return [{"model": m} for m in sorted(self.models)]
        return []


def test_extract_model_field_refs() -> None:
    refs = extract_model_field_refs("AccessError on x_matter.x_status and account.move")
    assert ("x_matter", "x_status") in refs
    assert ("account.move", None) in refs


def test_extract_ir_ui_view_full_model() -> None:
    refs = extract_model_field_refs("inherit ir.ui.view with mode=extension")
    assert ("ir.ui.view", None) in refs
    assert ("ir", None) not in refs


def test_looks_like_rpc_error() -> None:
    assert looks_like_rpc_error("KeyError: x_mattr does not exist")
    assert looks_like_rpc_error("AccessError: not allowed")
    assert looks_like_rpc_error("<Fault 2: 'Model not found: x_ticket'>")
    assert looks_like_rpc_error("Error while validating view near:\nModel not found: x_ticket")
    assert not looks_like_rpc_error("How do I add a custom field?")
    assert not looks_like_rpc_error(
        "Explain ir.ui.view extension vs primary form for x_rental.contract"
    )


def test_looks_like_conceptual_question() -> None:
    from app.expert.grounding import looks_like_conceptual_question

    assert looks_like_conceptual_question(
        "Explain the difference between extension and primary form views"
    )
    assert not looks_like_conceptual_question(
        "Diagnose this error\n\nError log:\nModel not found: x_ticket"
    )


def test_extract_model_not_found_ref() -> None:
    refs = extract_model_field_refs("Model not found: x_ticket")
    assert ("x_ticket", None) in refs


def test_merge_question_with_pasted_error() -> None:
    from app.expert.grounding import merge_question_with_pasted_error

    merged = merge_question_with_pasted_error(
        "Diagnose this error",
        {"pasted_error": "AccessError on res.partner"},
    )
    assert "Error log:" in merged
    assert "AccessError on res.partner" in merged
    assert merge_question_with_pasted_error(merged, {"pasted_error": "AccessError on res.partner"}) == merged


def test_route_bulk_tools_mass_edit() -> None:
    tools = route_bulk_tools(
        "How do I mass edit x_name for many records?",
        connection_id="conn-1",
    )
    assert tools
    assert tools[0]["id"] == "mass_edit"
    assert "/connections/conn-1/bulk-suite" in tools[0]["deep_link"]


def test_route_bulk_tools_transition_id() -> None:
    tools = route_bulk_tools(
        "Bulk transition many x_matter records to done state?",
        connection_id="conn-1",
    )
    assert any(t["id"] == "transition" for t in tools)


def test_route_bulk_tools_suite_hub() -> None:
    tools = route_bulk_tools(
        "Where is the bulk RPC suite in the app?",
        connection_id="conn-1",
    )
    assert tools
    assert tools[0]["id"] == "mass_edit"


def test_match_capability_highlights_bulk() -> None:
    rows = match_capability_highlights(
        "Can I run bulk transitions on many records?",
        url="http://127.0.0.1:8069",
        server_version="19.0",
        installed_modules=["base", "account"],
    )
    assert any(r["key"] == "bulk_rpc_suite" for r in rows)


def test_cross_check_typo_suggestion() -> None:
    client = _FakeClient()
    diags = cross_check_schema(
        client,
        [("x_matter", "x_staus"), ("x_matter", "x_status")],
    )
    bad = next(d for d in diags if d.get("field") == "x_staus")
    good = next(d for d in diags if d.get("field") == "x_status")
    assert bad["status"] == "field_missing"
    assert "x_status" in bad.get("suggestion", "")
    assert good["status"] == "ok"


def test_cross_check_no_spurious_custom_model_suggestion() -> None:
    class _WideClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.models.add("ir.model.constraint")

    diags = cross_check_schema(_WideClient(), [("x_rental.contract", None)])
    missing = diags[0]
    assert missing["status"] == "model_missing"
    assert "suggestion" not in missing or "ir.model.constraint" not in missing.get(
        "suggestion", ""
    )


def test_serialize_bundle_token_estimate() -> None:
    bundle = GroundingBundle(
        instance_summary={
            "server_version": "19.0",
            "edition": "community",
            "hosting": "self_hosted",
            "module_count": 120,
            "notable_modules": ["account", "base_automation"],
            "notable_flags": {"account": True},
        },
        capability_highlights=[
            {
                "key": "bulk_rpc_suite",
                "label": "Bulk RPC suite",
                "available": "yes",
                "reason": "ok",
            }
        ],
    )
    out = serialize_bundle(bundle)
    assert out.sections.get("instance")
    assert out.token_estimate > 0


def test_assemble_context_offline_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = community_manifest_for_version("19.0")
    row = SimpleNamespace(
        id="test-conn",
        url="http://127.0.0.1:8069",
        server_version="19.0",
        protected_manifest_json=manifest_to_json(manifest),
        protected_manifest_version="19.0",
    )

    class _FakeDb:
        def get(self, _model, _id):
            return row if _id == "test-conn" else None

    monkeypatch.setattr(
        "app.odoo_service.get_connection_or_404",
        lambda db, cid: row if cid == "test-conn" else (_ for _ in ()).throw(LookupError(cid)),
    )

    bundle = assemble_context(
        _FakeDb(),  # type: ignore[arg-type]
        connection_id="test-conn",
        question="Explain account.move tier-1 constraints for bulk edit",
        ui_context={"route": "/builder", "model": "account.move"},
    )
    assert bundle.retrieval_version == "19.0"
    assert bundle.instance_summary.get("hosting") == "self_hosted"
    assert any(p["model"] == "account.move" for p in bundle.protected_flags)
    assert bundle.sections


def test_assemble_context_no_connection_note() -> None:
    class _FakeDb:
        pass

    bundle = assemble_context(_FakeDb(), question="What is xpath inheritance?")  # type: ignore[arg-type]
    assert bundle.retrieval_version is None
    assert bundle.no_connection_note


@pytest.mark.integration
def test_assemble_context_live_odoo19() -> None:
    """RPC smoke: grounding bundle for a local docker Odoo 19 connection."""
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection
    from app.odoo_service import client_from_connection

    init_db()
    db = SessionLocal()
    try:
        row = db.query(OdooConnection).order_by(OdooConnection.created_at.desc()).first()
        if row is None or not row.server_version:
            pytest.skip("No probed connection in app DB")
        client = client_from_connection(row)
        bundle = assemble_context(
            db,
            connection_id=row.id,
            question="AccessError on x_matter.x_status — bulk edit many records",
            ui_context={"route": "/builder", "model": "x_matter"},
            client=client,
        )
        assert bundle.retrieval_version
        assert bundle.instance_summary
    finally:
        db.close()
