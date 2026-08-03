"""EXP-4 Expert evaluation harness — deterministic CI + optional live scoring."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.ask import ExpertAskResult, ask_expert  # noqa: E402
from app.expert.grounding import GroundingBundle  # noqa: E402
from app.expert.retrieval import RetrievedChunk  # noqa: E402
from app.llm_provider import LLMProvider  # noqa: E402
from app.protected_modules import community_manifest_for_version, manifest_to_json  # noqa: E402

EVAL_SET_PATH = Path(__file__).parent / "expert_eval" / "eval_set.jsonl"


class _FakeDb:
    pass


class _EvalFakeLLM(LLMProvider):
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    @property
    def name(self) -> str:
        return "eval-fake-llm"

    def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
        return True, "ok"

    def generate_json(self, prompt: str, **kwargs: Any) -> str:
        return json.dumps(self._payload)


@dataclass
class EvalScore:
    id: str
    category: str
    passed: bool
    reasons: list[str] = field(default_factory=list)
    grounded: bool = False
    declined: bool = False
    citation_count: int = 0


def load_eval_set() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in EVAL_SET_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def _chunks_from_item(item: dict[str, Any]) -> list[RetrievedChunk]:
    out: list[RetrievedChunk] = []
    for i, raw in enumerate(item.get("mock_chunks") or []):
        out.append(
            RetrievedChunk(
                chunk_id=f"eval-chunk-{item['id']}-{i}",
                source=str(raw.get("source", "odoo_docs")),
                version=str(raw.get("version", item.get("version_scope") or "19.0")),
                breadcrumb=str(raw.get("breadcrumb", "Eval")),
                text=str(raw.get("text", "")),
                score=float(raw.get("score", 0.8)),
                method="eval",
            )
        )
    return out


def _bundle_from_item(item: dict[str, Any]) -> GroundingBundle:
    raw = item.get("mock_grounding") or {}
    return GroundingBundle(
        retrieval_version=item.get("version_scope"),
        instance_summary=dict(raw.get("instance_summary") or {}),
        capability_highlights=list(raw.get("capability_highlights") or []),
        ui_context=dict(raw.get("ui_context") or item.get("ui_context") or {}),
        protected_flags=list(raw.get("protected_flags") or []),
        error_diagnostics=list(raw.get("error_diagnostics") or []),
        suggested_tools=list(raw.get("suggested_tools") or []),
        sections=dict(raw.get("sections") or {}),
    )


def _connection_row() -> SimpleNamespace:
    manifest = community_manifest_for_version("19.0")
    return SimpleNamespace(
        id="eval-conn-1",
        url="http://127.0.0.1:8069",
        server_version="19.0",
        protected_manifest_json=manifest_to_json(manifest),
        protected_manifest_version="19.0",
    )


def run_eval_item(item: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> ExpertAskResult:
    chunks = _chunks_from_item(item)
    bundle = _bundle_from_item(item)

    monkeypatch.setattr("app.expert.ask.retrieve_expert_chunks", lambda *a, **k: chunks)
    monkeypatch.setattr("app.expert.ask.assemble_context", lambda *a, **k: bundle)

    if item.get("connection_id"):
        monkeypatch.setattr(
            "app.odoo_service.get_connection_or_404",
            lambda db, cid: _connection_row(),
        )

    provider: LLMProvider | None = None
    fake = item.get("fake_response")
    if fake and not item.get("tier1_refusal"):
        provider = _EvalFakeLLM(fake)

    return ask_expert(
        _FakeDb(),  # type: ignore[arg-type]
        question=str(item["question"]),
        connection_id=item.get("connection_id"),
        ui_context=item.get("ui_context"),
        provider=provider,
    )


def score_eval_item(item: dict[str, Any], result: ExpertAskResult) -> EvalScore:
    reasons: list[str] = []
    answer = result.answer_markdown.lower()

    if item.get("expect_decline"):
        if not result.declined:
            reasons.append("expected decline")
    elif not item.get("tier1_refusal"):
        if result.declined:
            reasons.append("unexpected decline")

    if item.get("expect_caution") and not result.caution_flags:
        reasons.append("expected caution_flags")

    if item.get("tier1_refusal"):
        if "pcm_consistent_refusal" not in result.caution_flags:
            reasons.append("missing pcm_consistent_refusal")

    for term in item.get("must_contain") or []:
        if str(term).lower() not in answer:
            reasons.append(f"missing must_contain: {term}")

    for term in item.get("must_not_contain") or []:
        if str(term).lower() in answer:
            reasons.append(f"hit must_not_contain: {term}")

    if item.get("require_citations") and not item.get("expect_decline") and not item.get("tier1_refusal"):
        if not result.citations:
            reasons.append("missing citations")

    expect_tool = item.get("expect_tool")
    if expect_tool:
        tool_ids = {t.get("id") for t in result.suggested_tools}
        if expect_tool not in tool_ids:
            reasons.append(f"missing suggested tool: {expect_tool}")

    return EvalScore(
        id=str(item["id"]),
        category=str(item.get("category", "unknown")),
        passed=not reasons,
        reasons=reasons,
        grounded=result.grounded,
        declined=result.declined,
        citation_count=len(result.citations),
    )


def summarize_scores(scores: list[EvalScore]) -> dict[str, Any]:
    total = len(scores)
    passed = sum(1 for s in scores if s.passed)
    by_cat: dict[str, list[EvalScore]] = {}
    for s in scores:
        by_cat.setdefault(s.category, []).append(s)
    category_rates = {
        cat: round(sum(1 for s in rows if s.passed) / len(rows), 3) for cat, rows in by_cat.items()
    }
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "grounding_rate": round(sum(1 for s in scores if s.grounded) / total, 3) if total else 0.0,
        "decline_correct": round(
            sum(1 for s in scores if s.declined and s.passed) / max(1, sum(1 for s in scores if s.declined)),
            3,
        ),
        "citation_presence": round(
            sum(1 for s in scores if s.citation_count > 0) / total, 3 if total else 1.0,
        ),
        "category_pass_rate": category_rates,
        "failures": [{"id": s.id, "reasons": s.reasons} for s in scores if not s.passed],
    }


@pytest.fixture
def eval_items() -> list[dict[str, Any]]:
    items = load_eval_set()
    assert len(items) >= 40, f"eval set must have ≥40 items, got {len(items)}"
    return items


def test_eval_set_coverage(eval_items: list[dict[str, Any]]) -> None:
    cats = {str(i.get("category")) for i in eval_items}
    required = {
        "doc_grounded",
        "instance_grounded",
        "protected_caution",
        "should_decline",
        "version_diff",
        "bulk_routing",
    }
    assert required.issubset(cats)
    counts = {}
    for item in eval_items:
        cat = str(item.get("category"))
        counts[cat] = counts.get(cat, 0) + 1
    assert counts["doc_grounded"] >= 15
    assert counts["instance_grounded"] >= 5
    assert counts["protected_caution"] >= 5
    assert counts["should_decline"] >= 5
    assert counts["version_diff"] >= 5
    assert counts["bulk_routing"] >= 5


def test_expert_eval_ci_deterministic(
    eval_items: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    scores = [score_eval_item(item, run_eval_item(item, monkeypatch)) for item in eval_items]
    summary = summarize_scores(scores)
    assert summary["failures"] == [], summary


@pytest.mark.skipif(os.getenv("EXPERT_EVAL_LIVE") != "1", reason="set EXPERT_EVAL_LIVE=1 for live eval")
def test_expert_eval_live_report(
    eval_items: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live mode: score real model output; informational only (no hard fail)."""
    from app.expert.ask import expert_assist_enabled

    if not expert_assist_enabled():
        pytest.skip("AI_ASSIST must be enabled for live eval")

    # Live path uses real retrieval/LLM — only run a small stratified sample
    sample_ids = {
        "doc-xpath-inherit-1",
        "decline-niche-1",
        "prot-account-move-1",
        "bulk-mass-edit-1",
        "ver-19-property-1",
    }
    subset = [i for i in eval_items if i["id"] in sample_ids]

    scores: list[EvalScore] = []
    for item in subset:
        monkeypatch.setattr("app.expert.ask.retrieve_expert_chunks", _chunks_from_item(item))
        result = ask_expert(
            _FakeDb(),  # type: ignore[arg-type]
            question=str(item["question"]),
            connection_id=item.get("connection_id"),
            ui_context=item.get("ui_context"),
        )
        scores.append(score_eval_item(item, result))

    summary = summarize_scores(scores)
    print("\nEXPERT_EVAL_LIVE summary:", json.dumps(summary, indent=2))
