"""EXP-3 Expert ask pipeline tests (fake provider; no live Ollama required)."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.ask import (  # noqa: E402
    DECLINE_LOW_CONFIDENCE,
    ask_expert,
    classify_expert_intent,
    detect_legal_tax_question,
    detect_tier1_logic_request,
)
from app.expert.grounding import GroundingBundle  # noqa: E402
from app.expert.retrieval import RetrievedChunk  # noqa: E402
from app.llm_provider import LLMProvider  # noqa: E402
from app.main import app  # noqa: E402
from app.protected_modules import (  # noqa: E402
    community_manifest_for_version,
    manifest_to_json,
    safe_alternative_for,
)
from app.settings import settings  # noqa: E402


class _FakeDb:
    pass


class _FakeLLM(LLMProvider):
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "fake-llm"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "ok"

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout_s: float = 120.0,
        reasoning: bool = False,
        temperature: float | None = None,
        format_schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "reasoning": reasoning,
                "temperature": temperature,
                "strict": "REMINDER" in prompt,
            }
        )
        return json.dumps(self._payload)


def _sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="chunk-1",
            source="odoo_docs",
            version="19.0",
            breadcrumb="Developer / Views",
            text="Use xpath inheritance to extend form views without replacing the arch.",
            score=0.82,
            method="jaccard",
        )
    ]


def _sample_bundle(**overrides: Any) -> GroundingBundle:
    bundle = GroundingBundle(
        retrieval_version="19.0",
        sections={"instance": "Odoo 19 Community, self-hosted"},
        suggested_tools=[
            {
                "id": "mass_edit",
                "label": "Mass edit",
                "deep_link": "/connections/c1/bulk-suite",
            }
        ],
    )
    for key, val in overrides.items():
        setattr(bundle, key, val)
    return bundle


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_classify_expert_intent() -> None:
    assert classify_expert_intent("What is xpath?", retrieval_chars=100) is False
    assert classify_expert_intent("Walk me through diagnosing AccessError", retrieval_chars=100) is True
    assert classify_expert_intent("KeyError: field does not exist", retrieval_chars=100) is True


def test_detect_legal_tax_question() -> None:
    assert detect_legal_tax_question("Is this GDPR compliant for my business?")
    assert not detect_legal_tax_question("How do I add a custom field?")


def test_tier1_logic_pcm_consistent_refusal() -> None:
    manifest = community_manifest_for_version("19.0")
    hit = detect_tier1_logic_request(
        "Write a server action to post account.move automatically",
        manifest,
    )
    assert hit is not None
    model, alt = hit
    assert model == "account.move"
    assert alt == safe_alternative_for("account.move")


def test_ask_declines_when_no_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.expert.ask.retrieve_expert_chunks", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: _sample_bundle(),
    )
    result = ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question="What is xpath inheritance?",
        provider=_FakeLLM({}),
    )
    assert result.declined
    assert not result.grounded
    assert DECLINE_LOW_CONFIDENCE in result.answer_markdown


def test_ask_grounded_with_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.expert.ask.retrieve_expert_chunks",
        lambda *a, **k: _sample_chunks(),
    )
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: _sample_bundle(),
    )
    llm = _FakeLLM(
        {
            "answer_markdown": "Use xpath to extend views [1].",
            "citation_ids": [1],
            "caution_flags": [],
        }
    )
    result = ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question="What is xpath inheritance for form views?",
        provider=llm,
    )
    assert result.grounded
    assert not result.declined
    assert result.citations
    assert result.citations[0].chunk_id == "chunk-1"
    assert result.suggested_tools
    assert result.suggested_tools[0]["id"] == "mass_edit"
    assert llm.calls[0]["temperature"] == pytest.approx(0.15)
    assert llm.calls[0]["reasoning"] is False


def test_ask_regenerates_on_uncited_paragraphs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.expert.ask.retrieve_expert_chunks",
        lambda *a, **k: _sample_chunks(),
    )
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: _sample_bundle(),
    )

    class _TwoShotLLM(_FakeLLM):
        def __init__(self) -> None:
            super().__init__({})
            self._n = 0

        def generate_json(self, prompt: str, **kwargs: Any) -> str:
            self.calls.append({"strict": "REMINDER" in prompt})
            self._n += 1
            if self._n == 1:
                return json.dumps(
                    {
                        "answer_markdown": "Uncited claim with no markers.",
                        "citation_ids": [],
                    }
                )
            return json.dumps(
                {
                    "answer_markdown": "Grounded answer with citation [1].",
                    "citation_ids": [1],
                }
            )

    llm = _TwoShotLLM()
    result = ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question="Explain xpath",
        provider=llm,
    )
    assert "[1]" in result.answer_markdown
    assert len(llm.calls) == 2
    assert llm.calls[1]["strict"] is True


def test_ask_tier1_refusal_with_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = community_manifest_for_version("19.0")
    row = SimpleNamespace(
        id="conn-1",
        protected_manifest_json=manifest_to_json(manifest),
    )

    monkeypatch.setattr(
        "app.odoo_service.get_connection_or_404",
        lambda db, cid: row,
    )

    result = ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question="Automate account.move posting with a server action write",
        connection_id="conn-1",
        provider=_FakeLLM({}),
    )
    assert "account.move" in result.answer_markdown
    assert safe_alternative_for("account.move") in result.answer_markdown
    assert "pcm_consistent_refusal" in result.caution_flags


def test_ask_legal_tax_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.expert.ask.retrieve_expert_chunks",
        lambda *a, **k: _sample_chunks(),
    )
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: _sample_bundle(),
    )
    llm = _FakeLLM(
        {
            "answer_markdown": "Odoo supports tax tags [1]; consult an advisor for jurisdiction rules.",
            "citation_ids": [1],
        }
    )
    result = ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question="Give me tax advice for filing taxes as a sole proprietor",
        provider=llm,
    )
    assert "legal_tax_deflection" in result.caution_flags


def test_expert_ask_endpoint_503_when_ai_off(client: TestClient) -> None:
    settings.ai_assist = "off"
    res = client.post("/api/expert/ask", json={"question": "What is xpath?"})
    assert res.status_code == 503


def test_expert_ask_endpoint_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.ai_assist = "ollama"
    monkeypatch.setattr(
        "app.expert.ask.retrieve_expert_chunks",
        lambda *a, **k: _sample_chunks(),
    )
    monkeypatch.setattr(
        "app.expert.ask.assemble_context",
        lambda *a, **k: _sample_bundle(),
    )
    monkeypatch.setattr(
        "app.expert.ask.get_llm_provider",
        lambda: _FakeLLM(
            {
                "answer_markdown": "XPath extends views [1].",
                "citation_ids": [1],
            }
        ),
    )
    res = client.post(
        "/api/expert/ask",
        json={"question": "How do xpath views work?"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["grounded"] is True
    assert body["citations"]
    assert body["citations"][0]["chunk_id"] == "chunk-1"
