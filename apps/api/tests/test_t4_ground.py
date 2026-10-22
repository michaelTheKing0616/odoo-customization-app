"""T4-GROUND: schema-client tool targets and the existing RAG index."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.ai_schema_client import DenySchemaClient, FakeSchemaClient
from app.grounding.rag import index_root, retrieve, retrieve_from_existing_index
from app.grounding.tools import ToolTarget, accept_tool_target, offer_tool_targets

pytestmark = pytest.mark.no_app_db

_GROUNDING_DIR = Path(__file__).resolve().parents[1] / "app" / "grounding"
_FORBIDDEN_RAG_ROOTS = (
    "ai_rag2",
    "ai_rag_v2",
    "compiler_rag",
    "embedding_store",
    "rag_corpus",
    "rag_index",
)


def _sale_client() -> FakeSchemaClient:
    return FakeSchemaClient(
        models={"sale.order"},
        fields={
            "sale.order": {
                "partner_id": {"type": "many2one", "ttype": "many2one", "relation": "res.partner"},
                "name": {"type": "char", "ttype": "char"},
            }
        },
        methods={"sale.order": {"action_confirm"}},
    )


def test_unknown_model_is_rejected_and_never_becomes_a_tool() -> None:
    client = _sale_client()
    unknown = ToolTarget(kind="model", model="x.unknown.nowhere")
    assert client.model_exists(unknown.model) is False
    assert accept_tool_target(client, unknown) is False
    offered = offer_tool_targets(
        client,
        [
            ToolTarget(kind="model", model="sale.order"),
            unknown,
            ToolTarget(kind="field", model="x.unknown.nowhere", name="name"),
            ToolTarget(kind="method", model="x.unknown.nowhere", name="create"),
        ],
    )
    assert offered == (ToolTarget(kind="model", model="sale.order"),)


def test_rejected_field_and_method_are_not_offered() -> None:
    client = _sale_client()
    offered = offer_tool_targets(
        client,
        [
            ToolTarget(kind="field", model="sale.order", name="partner_id"),
            ToolTarget(kind="field", model="sale.order", name="x_invented"),
            ToolTarget(kind="method", model="sale.order", name="action_confirm"),
            ToolTarget(kind="method", model="sale.order", name="invent_method"),
        ],
    )
    assert offered == (
        ToolTarget(kind="field", model="sale.order", name="partner_id"),
        ToolTarget(kind="method", model="sale.order", name="action_confirm"),
    )


def test_deny_schema_client_offers_no_targets() -> None:
    client = DenySchemaClient(reason="stale_or_missing_catalog_ts")
    offered = offer_tool_targets(
        client,
        [
            ToolTarget(kind="model", model="sale.order"),
            ToolTarget(kind="field", model="sale.order", name="name"),
            ToolTarget(kind="method", model="sale.order", name="action_confirm"),
        ],
    )
    assert offered == ()


def test_tool_targets_resolve_through_schema_client() -> None:
    source = Path(_GROUNDING_DIR / "tools.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in {"model_exists", "fields_get", "method_exists"}:
            called.add(node.func.attr)
    assert called == {"model_exists", "fields_get", "method_exists"}


def test_rag_reads_existing_index() -> None:
    from app import ai_rag

    assert retrieve is ai_rag.retrieve_with_rag
    root = index_root()
    assert root == ai_rag._cache_dir()
    assert root.name == "ai_rag"
    assert root.parent.name == ".cache"


def test_retrieve_from_existing_index_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import ai_rag

    seen: list[str] = []

    def _fake(
        prompt: str,
        *,
        pack_loader,
        jaccard_retrieve,
        min_cosine=None,
    ):
        seen.append(prompt)
        return ("clinic", {"domain_pack": "clinic"}, 0.91, "embedding")

    monkeypatch.setattr(ai_rag, "retrieve_with_rag", _fake)
    pack_id, pack, score, method = retrieve_from_existing_index(
        "clinic visits",
        pack_loader=lambda: [],
        jaccard_retrieve=lambda _prompt: None,
    )
    assert seen == ["clinic visits"]
    assert pack_id == "clinic"
    assert pack["domain_pack"] == "clinic"
    assert score == 0.91
    assert method == "embedding"


def test_no_second_rag_root() -> None:
    for path in _GROUNDING_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_RAG_ROOTS:
            assert token not in text, f"{path.name} introduced {token}"
    tree = ast.parse((_GROUNDING_DIR / "rag.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.ai_rag":
            imported.update(alias.name for alias in node.names)
    assert "_cache_dir" in imported
    assert "retrieve_with_rag" in imported
