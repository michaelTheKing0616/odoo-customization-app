"""Model registry. Ids come from config. A tier is never invented here."""

from __future__ import annotations

import ast
from dataclasses import dataclass

# Request placeholders. They are not product model ids.
_PLACEHOLDER_IDS = frozenset({"configured", "configured-at-runtime"})

# Product model ids. Empty until a probe and an eval record one.
# The source scan treats literals stored here as registry ids.
MODEL_IDS: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelRecord:
    provider: str
    model_id: str
    tier: str | None
    status: str


@dataclass(frozen=True, slots=True)
class ModelCaps:
    """Limits implied by a trust tier. Tier C is read-only and cannot submit a change-set."""

    read_only: bool
    can_submit_changeset: bool


# Most restrictive caps implied by Tier C.
TIER_C_CAPS = ModelCaps(read_only=True, can_submit_changeset=False)

# A tier that may plan can submit a change-set and is not limited to read-only.
_SUBMIT_CAPS = ModelCaps(read_only=False, can_submit_changeset=True)


@dataclass(frozen=True, slots=True)
class ModelLookup:
    record: ModelRecord | None
    caps: ModelCaps

    @property
    def tier(self) -> str | None:
        if self.record is None:
            return None
        return self.record.tier


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


def _caps_for_tier(tier: str | None) -> ModelCaps:
    if tier in {"A", "B"}:
        return _SUBMIT_CAPS
    return TIER_C_CAPS


def lookup(
    records: dict[tuple[str, str], ModelRecord],
    provider: str,
    model_id: str,
) -> ModelLookup:
    """Return the stored row. An unknown id stays untiered and uses Tier C caps."""
    record = records.get((provider, model_id))
    if record is None:
        return ModelLookup(None, TIER_C_CAPS)
    return ModelLookup(record, _caps_for_tier(record.tier))


def _assigned_model_ids(node: ast.stmt) -> ast.AST | None:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "MODEL_IDS":
        return node.value
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "MODEL_IDS":
                return node.value
    return None


def _string_elts(value: ast.AST | None) -> set[str]:
    if not isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        return set()
    found: set[str] = set()
    for elt in value.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str) and elt.value:
            found.add(elt.value)
    return found


def model_ids_in_source(source: str) -> frozenset[str]:
    """Product model ids stored in registry source. Placeholders are omitted."""
    tree = ast.parse(source)
    found: set[str] = set()
    for node in tree.body:
        found.update(_string_elts(_assigned_model_ids(node)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, val in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == "model_id"
                and isinstance(val, ast.Constant)
                and isinstance(val.value, str)
                and val.value
            ):
                found.add(val.value)
    return frozenset(model_id for model_id in found if model_id not in _PLACEHOLDER_IDS)
