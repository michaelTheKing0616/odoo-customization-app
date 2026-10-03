"""Model registry. Ids come from config. A tier is never invented here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelRecord:
    provider: str
    model_id: str
    tier: str | None
    status: str


def load_registry(rows: list[dict]) -> dict[tuple[str, str], ModelRecord]:
    records: dict[tuple[str, str], ModelRecord] = {}
    for row in rows:
        provider = str(row.get("provider") or "")
        model_id = str(row.get("model_id") or "")
        if not provider or not model_id:
            raise ValueError("provider and model_id are required")
        tier = row.get("tier")
        if tier not in {None, "A", "B", "C"}:
            raise ValueError("tier must be A, B, C, or unset")
        status = str(row.get("status") or "enabled")
        if status not in {"enabled", "deprecated", "disabled"}:
            raise ValueError("status")
        records[(provider, model_id)] = ModelRecord(provider, model_id, tier, status)
    return records
