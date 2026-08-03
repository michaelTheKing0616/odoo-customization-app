"""Draft → candidate domain-pack generalizer (AI-6).

Deterministic structure extraction + optional LLM tags/anti-patterns.
Output is response/download only — never auto-registers packs.
"""

from __future__ import annotations

import ast
import copy
import json
import re
from typing import Any

from app.llm_provider import LLMError, LLMProvider, get_llm_provider

_PACK_KEYS = (
    "technical_name",
    "display_name",
    "depends",
    "domain_pack",
    "tags",
    "anti_patterns",
    "models",
    "smart_buttons",
    "automations",
    "reuse_hints",
)

_STRIP_SPEC_KEYS = frozenset(
    {
        "_retrieval",
        "trace",
        "raw_response",
        "views",
        "menus",
        "actions",
        "data",
        "security",
        "reports",
    }
)

_DEFAULT_ANTI_PATTERNS = [
    "Do NOT emit Python code automations (state=code)",
    "Do NOT invent mini-CRM customer models — use res.partner + role links",
    "Party/role-link models are NOT is_workflow",
    "Billing/payment stubs are link-only — no payment gateway logic",
]


def _slugify(text: str, *, fallback: str = "custom") -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (text or "").lower()).strip("_")
    return (slug[:40] or fallback).strip("_")


def _json_to_python(obj: Any, indent: int = 0) -> str:
    """Render JSON-compatible object as Python literal source."""
    pad = " " * indent
    inner = " " * (indent + 4)
    if obj is None:
        return "None"
    if obj is True:
        return "True"
    if obj is False:
        return "False"
    if isinstance(obj, str):
        return repr(obj)
    if isinstance(obj, (int, float)):
        return repr(obj)
    if isinstance(obj, list):
        if not obj:
            return "[]"
        lines = [f"{inner}{_json_to_python(v, indent + 4)}" for v in obj]
        return "[\n" + ",\n".join(lines) + ",\n" + pad + "]"
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = [
            f"{inner}{repr(k)}: {_json_to_python(v, indent + 4)}"
            for k, v in obj.items()
        ]
        return "{\n" + ",\n".join(lines) + ",\n" + pad + "}"
    return repr(obj)


def _rewrite_value(val: Any, rename: dict[str, str]) -> Any:
    if isinstance(val, str):
        out = val
        for old, new in sorted(rename.items(), key=lambda x: -len(x[0])):
            out = out.replace(old, new)
        return out
    if isinstance(val, list):
        return [_rewrite_value(v, rename) for v in val]
    if isinstance(val, dict):
        return {k: _rewrite_value(v, rename) for k, v in val.items()}
    return val


def _detect_shared_prefix(models: list[dict[str, Any]]) -> str | None:
    x_names = [
        str(m.get("model"))
        for m in models
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    if len(x_names) < 2:
        return None
    counts: dict[str, int] = {}
    for name in x_names:
        parts = name.split("_")
        if len(parts) >= 3 and parts[1]:
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    if not counts:
        return None
    best, n = max(counts.items(), key=lambda x: x[1])
    if n >= max(2, len(x_names) // 2):
        return best
    return None


def _strip_instance_prefixes(spec: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Map x_<prefix>_foo → x_foo when a shared prefix is detected."""
    warnings: list[str] = []
    models = [m for m in (spec.get("models") or []) if isinstance(m, dict)]
    prefix = _detect_shared_prefix(models)
    if not prefix:
        return spec, warnings
    rename: dict[str, str] = {}
    for m in models:
        mid = str(m.get("model") or "")
        if mid.startswith(f"x_{prefix}_"):
            rename[mid] = "x_" + mid[len(f"x_{prefix}_") :]
    if not rename:
        return spec, warnings
    out = _rewrite_value(copy.deepcopy(spec), rename)
    warnings.append(f"generalizer: stripped shared model prefix x_{prefix}_ ({len(rename)} models)")
    return out, warnings


def _normalize_spec(spec: dict[str, Any], slug: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    out = copy.deepcopy(spec)
    for key in list(out.keys()):
        if key in _STRIP_SPEC_KEYS:
            out.pop(key, None)
            warnings.append(f"generalizer: omitted non-pack key {key!r}")

    out, prefix_w = _strip_instance_prefixes(out)
    warnings.extend(prefix_w)

    models = [m for m in (out.get("models") or []) if isinstance(m, dict) and m.get("model")]
    if not models:
        raise ValueError("spec has no models — nothing to generalize")

    out["domain_pack"] = slug
    out.setdefault("technical_name", f"{slug}_management")
    out["technical_name"] = _slugify(str(out["technical_name"]), fallback=f"{slug}_management")
    if not out.get("display_name"):
        out["display_name"] = slug.replace("_", " ").title() + " Management"
    out.setdefault("depends", ["base", "contacts", "mail"])

    for m in models:
        if m.get("is_workflow") and isinstance(m.get("fields"), list):
            has_status = any(
                isinstance(f, dict) and f.get("name") == "x_status" for f in m["fields"]
            )
            if has_status and not isinstance(m.get("state_field"), dict):
                warnings.append(
                    f"generalizer: workflow model {m.get('model')} missing state_field.transitions"
                )

    return out, warnings


def _derive_tags_heuristic(spec: dict[str, Any], slug: str) -> list[str]:
    bag: set[str] = set()
    bag.add(slug.replace("_", " "))
    for part in slug.split("_"):
        if len(part) > 2:
            bag.add(part)
    bag |= {t for t in re.findall(r"[a-z0-9]+", str(spec.get("display_name") or "").lower()) if len(t) > 2}
    for m in spec.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "").replace("x_", "").replace("_", " ")
        for tok in mid.split():
            if len(tok) > 2:
                bag.add(tok)
        desc = str(m.get("description") or "").lower()
        for tok in re.findall(r"[a-z0-9]+", desc):
            if len(tok) > 2:
                bag.add(tok)
    existing = spec.get("tags") or []
    if isinstance(existing, list):
        for tag in existing:
            for tok in re.findall(r"[a-z0-9]+", str(tag).lower()):
                if len(tok) > 2:
                    bag.add(tok)
    ordered = sorted(bag)
    return ordered[:24]


def _llm_suggest_tags_and_antipatterns(
    provider: LLMProvider,
    spec: dict[str, Any],
    *,
    slug: str,
) -> tuple[list[str], list[str], list[str]]:
    warnings: list[str] = []
    models_summary = [
        {
            "model": m.get("model"),
            "description": m.get("description"),
            "is_workflow": bool(m.get("is_workflow")),
        }
        for m in (spec.get("models") or [])
        if isinstance(m, dict)
    ][:20]
    system = (
        "Suggest retrieval tags and anti_patterns for a candidate Odoo domain pack. "
        "Return JSON only: "
        '{"tags":["..."],"anti_patterns":["..."]}. '
        "Tags: 8-18 lowercase phrases for NL retrieval. "
        "Anti-patterns: 3-6 DO-NOT rules (no payment logic, no res.users assignees where "
        "staff model exists, party roles not workflows)."
    )
    prompt = json.dumps(
        {
            "domain_pack": slug,
            "display_name": spec.get("display_name"),
            "models": models_summary,
        },
        indent=2,
    )
    try:
        raw = provider.generate_json(prompt, system=system, reasoning=True, temperature=0.15)
        data = json.loads(raw.strip())
        if isinstance(data, str):
            data = json.loads(data)
        tags = [str(t).strip() for t in (data.get("tags") or []) if str(t).strip()]
        anti = [str(a).strip() for a in (data.get("anti_patterns") or []) if str(a).strip()]
        if not tags:
            warnings.append("generalizer: LLM returned no tags — using heuristic tags")
        return tags[:24], anti[:8], warnings
    except (LLMError, ValueError, json.JSONDecodeError, TypeError) as exc:
        warnings.append(f"generalizer: LLM tag suggestion failed ({exc})")
        return [], [], warnings


def _build_pack_dict(
    spec: dict[str, Any],
    *,
    slug: str,
    tags: list[str],
    anti_patterns: list[str],
) -> dict[str, Any]:
    pack: dict[str, Any] = {}
    for key in _PACK_KEYS:
        if key == "domain_pack":
            pack[key] = slug
        elif key == "tags":
            pack[key] = tags
        elif key == "anti_patterns":
            pack[key] = anti_patterns
        elif key in spec:
            pack[key] = copy.deepcopy(spec[key])
    pack.setdefault("models", [])
    pack.setdefault("depends", ["base", "contacts", "mail"])
    pack.setdefault("smart_buttons", spec.get("smart_buttons") or [])
    pack.setdefault("automations", spec.get("automations") or [])
    pack.setdefault("reuse_hints", spec.get("reuse_hints") or [])
    return pack


def render_candidate_pack_source(slug: str, pack: dict[str, Any]) -> str:
    fn_name = "candidate_pack"
    body = _json_to_python(pack, indent=4)
    display = str(pack.get("display_name") or slug).replace('"', "'")
    return (
        f'"""Candidate domain pack — {display} (human review required).\n\n'
        f"Generated by POST /api/ai/generalize-pack. NOT auto-registered.\n"
        f'"""\n\n'
        f"from __future__ import annotations\n\n"
        f"from typing import Any\n\n\n"
        f"def {fn_name}() -> dict[str, Any]:\n"
        f'    """Review before moving to ai_domain_pack_{slug}.py."""\n'
        f"    return {body}\n\n\n"
        f'__all__ = ["{fn_name}"]\n'
    )


def parse_candidate_pack_source(source: str) -> dict[str, Any]:
    """Parse + execute candidate source; used by tests."""
    tree = ast.parse(source)
    ns: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(tree, "<candidate_pack>", "exec"), ns)  # noqa: S102
    fn = ns.get("candidate_pack")
    if not callable(fn):
        raise ValueError("candidate source missing candidate_pack()")
    pack = fn()
    if not isinstance(pack, dict):
        raise ValueError("candidate_pack() must return dict")
    return pack


def generalize_spec_to_pack_candidate(
    spec: dict[str, Any],
    *,
    pack_slug: str | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Generalize a ModuleSpec draft into downloadable candidate pack source."""
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")

    slug = _slugify(pack_slug or spec.get("domain_pack") or spec.get("technical_name") or "custom")
    normalized, warnings = _normalize_spec(spec, slug)

    tags = _derive_tags_heuristic(normalized, slug)
    anti_patterns = list(_DEFAULT_ANTI_PATTERNS)

    llm_tags: list[str] = []
    if provider is not None:
        llm_tags, llm_anti, llm_w = _llm_suggest_tags_and_antipatterns(
            provider, normalized, slug=slug
        )
        warnings.extend(llm_w)
        if llm_tags:
            tags = list(dict.fromkeys(llm_tags + tags))[:24]
        if llm_anti:
            anti_patterns = list(dict.fromkeys(llm_anti + anti_patterns))[:10]

    pack = _build_pack_dict(normalized, slug=slug, tags=tags, anti_patterns=anti_patterns)
    source = render_candidate_pack_source(slug, pack)
    filename = f"ai_domain_pack_candidate_{slug}.py"

    return {
        "filename": filename,
        "source": source,
        "domain_pack": slug,
        "suggested_tags": tags,
        "anti_patterns": anti_patterns,
        "model_count": len(pack.get("models") or []),
        "warnings": warnings,
        "note": (
            "Download only — candidate pack is NOT registered. "
            "Human review required before committing to apps/api/app/."
        ),
    }


def generalize_with_optional_llm(
    spec: dict[str, Any],
    *,
    pack_slug: str | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    provider = None
    if use_llm:
        try:
            from app.ai_ollama import ai_assist_enabled

            if ai_assist_enabled():
                provider = get_llm_provider()
        except Exception:  # noqa: BLE001
            provider = None
    return generalize_spec_to_pack_candidate(spec, pack_slug=pack_slug, provider=provider)


def generalize_spec_to_component_template(
    spec: dict[str, Any],
    *,
    host_slot: str = "any",
    pack_slug: str | None = None,
) -> dict[str, Any]:
    """AI-8: generalize a component ModuleSpec into a reusable gallery candidate."""
    base = generalize_spec_to_pack_candidate(spec, pack_slug=pack_slug)
    cp = spec.get("connect_points") if isinstance(spec.get("connect_points"), dict) else {}
    slot = host_slot or cp.get("host_model") or "any"
    base["grain"] = spec.get("grain") or "feature_slice"
    base["host_slot"] = slot
    base["connect_points_template"] = {
        "form_xpath": cp.get("form_xpath", "//sheet"),
        "form_position": cp.get("form_position", "inside"),
        "menu_mode": cp.get("menu_mode", "sub"),
    }
    base["note"] = (
        f"Component template — attaches to host slot {slot!r}. "
        "Abstract anchors (e.g. partner_id) resolved at apply time."
    )
    return base


__all__ = [
    "generalize_spec_to_pack_candidate",
    "generalize_spec_to_component_template",
    "generalize_with_optional_llm",
    "parse_candidate_pack_source",
    "render_candidate_pack_source",
]
