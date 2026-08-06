"""Stage 4 — dependency graph + topological commit order (ING-6)."""

from __future__ import annotations

from collections import defaultdict

from app.ingest.constants import MODEL_DEPENDENCY_EDGES
from app.ingest.schema import IngestBatch, IngestGap, IngestPlan, IngestPlanStep, IngestRef


class IngestOrderError(ValueError):
    pass


def _models_in_batch(batch: IngestBatch) -> set[str]:
    return {t.model for t in batch.tables}


def _build_adjacency(models: set[str]) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Return adjacency list: parent -> set(children that depend on parent)."""
    adj: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {m: 0 for m in models}
    for parent, child in MODEL_DEPENDENCY_EDGES:
        if parent in models and child in models:
            adj[parent].add(child)
            indegree[child] = indegree.get(child, 0) + 1
            indegree.setdefault(parent, indegree.get(parent, 0))
    return adj, indegree


def _topo_levels(models: set[str]) -> list[list[str]]:
    adj, indegree = _build_adjacency(models)
    ready = sorted(m for m in models if indegree.get(m, 0) == 0)
    levels: list[list[str]] = []
    visited = 0
    while ready:
        level = sorted(ready)
        levels.append(level)
        visited += len(level)
        next_ready: list[str] = []
        for node in level:
            for child in adj.get(node, set()):
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_ready.append(child)
        ready = sorted(next_ready)
    if visited != len(models):
        raise IngestOrderError("Circular dependency detected in ingest batch models")
    return levels


def _table_ids_for_models(batch: IngestBatch, models: list[str]) -> list[str]:
    model_set = set(models)
    return [t.id for t in batch.tables if t.model in model_set]


def _gaps_from_refs(refs: list[IngestRef]) -> list[IngestGap]:
    gaps: list[IngestGap] = []
    for ref in refs:
        if ref.resolved:
            continue
        gaps.append(
            IngestGap(
                model=ref.to_model,
                field=ref.field,
                value=ref.to_value,
                message=ref.note or f"Unresolved reference to {ref.to_model}: {ref.to_value!r}",
            )
        )
    return gaps


def build_plan(batch: IngestBatch) -> IngestPlan:
    models = _models_in_batch(batch)
    if not models:
        return IngestPlan(steps=[], gaps=_gaps_from_refs(batch.refs) + list(batch.gaps))

    levels = _topo_levels(models)
    steps: list[IngestPlanStep] = []
    for idx, level in enumerate(levels):
        table_ids = _table_ids_for_models(batch, level)
        parallel_ok = len(level) > 1 and len(table_ids) > 1
        steps.append(
            IngestPlanStep(
                step_index=idx,
                table_ids=table_ids,
                models=level,
                parallel_ok=parallel_ok,
            )
        )
    gaps = _gaps_from_refs(batch.refs) + list(batch.gaps)
    return IngestPlan(steps=steps, gaps=gaps)
