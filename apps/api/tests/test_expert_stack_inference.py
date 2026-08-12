"""Rule-based module stack inference for setup questions without a playbook."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.stack_inference import (  # noqa: E402
    compose_setup_stack_answer,
    infer_odoo_stack,
    is_setup_stack_question,
    try_rule_based_stack_guidance,
)


def test_is_setup_stack_question() -> None:
    assert is_setup_stack_question("What do I need to setup a diamond mining Odoo DB?")
    assert not is_setup_stack_question("How do I add xpath to a form view?")


def test_infer_stack_unknown_domain_diamond_mining() -> None:
    q = "What do I need to setup a diamond mining company Odoo DB?"
    stack = infer_odoo_stack(q)
    assert stack is not None
    assert stack.source == "inferred"
    assert "maintenance" in stack.stock_modules or "project" in stack.stock_modules
    assert stack.custom_models
    assert stack.custom_models[0].startswith("x_")
    body = compose_setup_stack_answer(stack).lower()
    assert "x_real_estate" not in body
    assert "install **crm**" not in body and "property rental" not in body


def test_infer_stack_library_uses_catalog() -> None:
    q = "What do I need to setup a library management Odoo DB?"
    stack = infer_odoo_stack(q)
    assert stack is not None
    assert stack.source == "catalog"
    assert stack.catalog_id == "library_management"
    body = compose_setup_stack_answer(stack)
    assert "x_lib" in body or "library" in body.lower()
    assert "res.partner" in body.lower() or "reuse stock" in body.lower()


def test_try_rule_based_stack_guidance_inferred_domain() -> None:
    q = "What modules do I need for a satellite ground station operations Odoo database?"
    payload = try_rule_based_stack_guidance(q)
    assert payload is not None
    assert payload["grounded"] is True
    assert "[1]" in payload["answer_markdown"]
    assert payload["inferred_stack"].source == "inferred"
    assert "rule_based_stack_guidance" in payload["caution_flags"]
    assert "inferred_stack" in payload["caution_flags"]


def test_ask_setup_question_uses_stack_guidance_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.expert.ask import ask_expert  # noqa: E402
    from app.expert.grounding import GroundingBundle  # noqa: E402
    from app.expert.retrieval import RetrievedChunk  # noqa: E402
    from app.llm_provider import LLMProvider  # noqa: E402

    class _ShouldNotRunLLM(LLMProvider):
        @property
        def name(self) -> str:
            return "blocked"

        def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
            return True, "ok"

        def generate_json(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("LLM must not run for setup stack questions")

    bad_chunks = [
        RetrievedChunk(
            chunk_id="bad-1",
            source="vertical",
            version="all",
            breadcrumb="Vertical playbook: Real Estate > Rollout phases",
            text="Install CRM and x_real_estate_property for property rental.",
            score=0.95,
            method="jaccard",
        )
    ]

    monkeypatch.setattr(
        "app.expert.ask.retrieve_expert_chunks",
        lambda *a, **k: bad_chunks,
    )
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: GroundingBundle(retrieval_version="19.0"),
    )

    q = "What do I need to setup a diamond mining company Odoo DB?"
    result = ask_expert(
        object(),  # type: ignore[arg-type]
        question=q,
        provider=_ShouldNotRunLLM(),
    )
    assert not result.declined
    assert result.grounded
    assert "rule_based_stack_guidance" in result.caution_flags
    assert "x_real_estate" not in result.answer_markdown.lower()
    assert "property rental" not in result.answer_markdown.lower()
    assert result.citations
    assert result.citations[0].chunk_id == "stack-inference"
