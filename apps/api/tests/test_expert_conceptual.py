"""Tests for dual-layer Expert answers and conceptual question routing."""

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

from app.expert.ask import ask_expert  # noqa: E402
from app.expert.field_constraint_guidance import (  # noqa: E402
    looks_like_required_field_question,
    try_rule_based_required_field_guidance,
)
from app.expert.grounding import GroundingBundle  # noqa: E402
from app.expert.instance_caveats import compose_dual_layer_answer  # noqa: E402
from app.expert.view_mode_guidance import (  # noqa: E402
    looks_like_view_mode_question,
    try_rule_based_view_mode_guidance,
)
from app.protected_modules import community_manifest_for_version, manifest_to_json  # noqa: E402
from tests.test_expert_ask import (  # noqa: E402
    _FakeDb,
    _FakeLLM,
    _sample_bundle,
    _sample_chunks,
)

VIEW_MODE_Q = (
    "Explain the difference between _inherit on ir.ui.view with mode=extension vs "
    "creating a new primary form view for x_rental.contract. When would each approach "
    "break on upgrade?"
)

REQUIRED_M2O_Q = (
    "What happens if I add a required Many2one from x_ticket → res.users without "
    "setting a default — will existing records block module install or view save?"
)


def _patch_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = community_manifest_for_version("19.0")
    row = SimpleNamespace(
        id="conn-1",
        url="http://127.0.0.1:8069",
        server_version="19.0",
        protected_manifest_json=manifest_to_json(manifest),
        protected_manifest_version="19.0",
    )
    monkeypatch.setattr(
        "app.odoo_service.get_connection_or_404",
        lambda db, cid: row,
    )


def test_view_mode_guidance_covers_extension_and_primary() -> None:
    assert looks_like_view_mode_question(VIEW_MODE_Q)
    payload = try_rule_based_view_mode_guidance(
        VIEW_MODE_Q,
        GroundingBundle(instance_summary={"server_version": "19.0"}),
        connection_id="conn-1",
    )
    assert payload is not None
    body = payload["answer_markdown"]
    assert "extension" in body.lower()
    assert "primary" in body.lower()
    assert "upgrade" in body.lower()
    assert "x_rental.contract" in body


def test_required_field_guidance_covers_existing_rows() -> None:
    assert looks_like_required_field_question(REQUIRED_M2O_Q)
    payload = try_rule_based_required_field_guidance(
        REQUIRED_M2O_Q,
        GroundingBundle(instance_summary={"server_version": "19.0"}),
        connection_id="conn-1",
    )
    assert payload is not None
    body = payload["answer_markdown"]
    assert "x_ticket" in body
    assert "res.users" in body
    assert "default" in body.lower()


def test_compose_dual_layer_appends_instance_caveats() -> None:
    bundle = GroundingBundle(
        instance_summary={"server_version": "19.0"},
        error_diagnostics=[
            {"status": "model_missing", "model": "x_ticket", "field": None},
            {"status": "model_ok", "model": "res.users", "field": None},
        ],
    )
    general = "Generic guidance about required Many2one fields."
    answer, flags = compose_dual_layer_answer(
        general,
        bundle,
        connection_id="abc-123",
    )
    assert "## Answer" in answer
    assert "## On your connection" in answer
    assert "x_ticket" in answer
    assert "instance_caveats" in flags


def test_ask_conceptual_view_mode_with_live_caveats(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(monkeypatch)
    monkeypatch.setattr("app.expert.ask.retrieve_expert_chunks", lambda *a, **k: _sample_chunks())

    def _assemble(*a, **k):
        bundle = _sample_bundle()
        bundle.error_diagnostics = [
            {"status": "model_missing", "model": "x_rental.contract", "field": None},
        ]
        return bundle

    monkeypatch.setattr("app.expert.ask.assemble_context", _assemble)
    result = ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question=VIEW_MODE_Q,
        connection_id="conn-1",
        provider=_FakeLLM({}),
    )
    assert not result.declined
    assert "rule_based_view_mode_guidance" in result.caution_flags
    assert "instance_caveats" in result.caution_flags
    assert "## Answer" in result.answer_markdown
    assert "extension" in result.answer_markdown.lower()
    assert "x_rental.contract" in result.answer_markdown


def test_ask_required_many2one_not_error_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(monkeypatch)
    monkeypatch.setattr("app.expert.ask.retrieve_expert_chunks", lambda *a, **k: _sample_chunks())

    def _assemble(*a, **k):
        bundle = _sample_bundle()
        bundle.error_diagnostics = [
            {"status": "model_missing", "model": "x_ticket", "field": None},
            {"status": "model_ok", "model": "res.users", "field": None},
        ]
        return bundle

    monkeypatch.setattr("app.expert.ask.assemble_context", _assemble)
    result = ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question=REQUIRED_M2O_Q,
        connection_id="conn-1",
        provider=_FakeLLM({}),
    )
    assert not result.declined
    assert "rule_based_required_field_guidance" in result.caution_flags
    assert "rule_based_diagnosis" not in result.caution_flags
    assert "Root cause:" not in result.answer_markdown
    assert "x_ticket" in result.answer_markdown
