"""LLM column mapping fallback when header aliases miss (ING-3)."""

from __future__ import annotations

import json
from typing import Any

from odoo_client import OdooClient

from app.data_import import _field_meta, suggest_mapping
from app.llm_provider import LLMError, get_llm_provider


def _alias_coverage(model: str, headers: list[str], mapping: dict[str, str]) -> float:
    if not headers:
        return 0.0
    aliases = set(suggest_mapping(model, headers).values())
    hits = sum(1 for h in headers if mapping.get(h) and mapping[h] in aliases)
    return hits / len(headers)


def _llm_map_columns(
    *,
    model: str,
    headers: list[str],
    sample_rows: list[dict[str, str]],
    field_names: list[str],
) -> dict[str, str]:
    provider = get_llm_provider()
    if provider is None:
        return {}
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "mapping": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            }
        },
        "required": ["mapping"],
    }
    prompt = (
        f"Map CSV headers to Odoo model {model} fields.\n"
        f"Allowed target fields: {field_names[:80]}\n"
        f"Headers: {headers}\n"
        f"Sample rows: {json.dumps(sample_rows[:2], ensure_ascii=False)[:800]}\n"
        "Only map when confident; omit unknown headers."
    )
    try:
        raw = provider.generate_json(
            prompt,
            system="You map migration CSV columns to Odoo fields. Closed field list only.",
            temperature=0.1,
            format_schema=schema,
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        out = data.get("mapping") or {}
        return {str(k): str(v) for k, v in out.items() if v}
    except (LLMError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def enhance_mapping_with_llm(
    client: OdooClient | None,
    *,
    model: str,
    headers: list[str],
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    min_coverage: float = 0.45,
) -> tuple[dict[str, str], list[str]]:
    """Return (mapping, warnings). LLM used only when alias coverage is low."""
    warnings: list[str] = []
    coverage = _alias_coverage(model, headers, mapping)
    if coverage >= min_coverage:
        return mapping, warnings
    field_names: list[str] = []
    if client is not None and client.model_exists(model):
        meta = _field_meta(client, model)
        field_names = sorted(meta.keys())
    llm_map = _llm_map_columns(
        model=model,
        headers=headers,
        sample_rows=rows[:3],
        field_names=field_names,
    )
    if not llm_map:
        warnings.append("low alias coverage; LLM column map unavailable")
        return mapping, warnings
    merged = dict(mapping)
    for h, f in llm_map.items():
        if h in headers and f:
            merged[h] = f
    warnings.append(f"LLM column map applied (alias coverage was {coverage:.0%})")
    return merged, warnings
