"""Compiler grounding: schema-client tool targets and the existing RAG index."""

from app.grounding.rag import index_root, retrieve, retrieve_from_existing_index
from app.grounding.tools import ToolTarget, accept_tool_target, offer_tool_targets

__all__ = [
    "ToolTarget",
    "accept_tool_target",
    "index_root",
    "offer_tool_targets",
    "retrieve",
    "retrieve_from_existing_index",
]
