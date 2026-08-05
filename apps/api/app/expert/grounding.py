"""Live-instance grounding for the Odoo Expert (EXP-2 / Doc 8 §4).

Assembles per-query context from cached connection metadata, tier matrix, UI state,
and capped live introspection — never credentials.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.capabilities import sample_installed_modules
from app.hosting import hosting_hint_from_url
from app.protected_enforcement import manifest_for_connection
from app.protected_modules import protected_models_for, safe_alternative_for
from app.tier_matrix import TIER_CAPABILITY_LABELS, TierCapabilityKey, evaluate_full_matrix

# Token budget caps (approx chars / 4) per serialized section
SECTION_CHAR_LIMITS: dict[str, int] = {
    "instance": 3200,
    "capabilities": 2400,
    "ui_context": 2000,
    "protected": 1600,
    "error_diagnostics": 2000,
    "tools": 1200,
}

_MAX_LIVE_FIELD_CHECKS = 8
_MAX_MODELS_FROM_TEXT = 12

_MODEL_FIELD_RE = re.compile(
    r"\b([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)\b", re.IGNORECASE
)
_MODEL_RE = re.compile(r"\b([a-z][a-z0-9_]{2,}\.[a-z][a-z0-9_]+)\b")
_ACCESS_ERROR_RE = re.compile(
    r"(?i)(access\s+error|accesserror|forbidden|not\s+allowed\s+to\s+access)"
)
_DOES_NOT_EXIST_RE = re.compile(
    r"(?i)(does\s+not\s+exist|unknown\s+comodel|invalid\s+field|no\s+such\s+field|keyerror)"
)
_FAULT_RE = re.compile(r"(?i)(?:<fault\s*\d+:|fault\s+\d+:)")
_MODEL_NOT_FOUND_RE = re.compile(
    r"(?i)(?:model not found|unknown model|no model named):\s*['\"]?([a-z][a-z0-9_]*)"
)
_VALIDATING_VIEW_RE = re.compile(r"(?i)error while validating view")
_TRACEBACK_RE = re.compile(r"(?i)traceback\s*\(")
_X_MODEL_RE = re.compile(r"\b(x_[a-z][a-z0-9_]*)\b")

_NOTABLE_MODULE_PREFIXES = ("l10n_",)
_NOTABLE_MODULE_EXACT = frozenset(
    {"account", "base_automation", "web_studio", "studio_customization", "documents", "sign"}
)

_CAPABILITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    TierCapabilityKey.BULK_RPC_SUITE.value: (
        "bulk",
        "mass edit",
        "many records",
        "duplicate",
        "dedupe",
        "transition",
        "recompute",
    ),
    TierCapabilityKey.BASE_AUTOMATION.value: (
        "automation",
        "automated action",
        "trigger",
        "base_automation",
    ),
    TierCapabilityKey.PROPERTY_FIELDS.value: ("property field", "properties field", "properties"),
    TierCapabilityKey.QWEB_REPORTS.value: ("qweb", "report template", "pdf report"),
    TierCapabilityKey.FINANCIAL_LINK_ONLY.value: (
        "invoice",
        "account.move",
        "accounting",
        "payment",
        "tier-1",
        "protected module",
    ),
    TierCapabilityKey.BARCODE_SCAN_MODULE.value: ("barcode", "scan", "scanner"),
    TierCapabilityKey.PYTHON_MODULE_INSTALL.value: ("python module", "custom code", "option a"),
}

_BULK_TOOL_ROUTES: tuple[dict[str, Any], ...] = (
    {
        "id": "mass_edit",
        "label": "Mass field edit",
        "keywords": ("mass edit", "bulk edit", "update many", "change field for all", "edit all"),
        "web_path": "/connections/{connection_id}/bulk-suite",
        "hint": "Use Bulk Suite → mass edit with domain or explicit ids.",
    },
    {
        "id": "transitions",
        "label": "Bulk state transition",
        "keywords": (
            "bulk transition",
            "change state",
            "workflow button",
            "many records",
            "status for all",
        ),
        "web_path": "/connections/{connection_id}/bulk-suite",
        "hint": "Discover object buttons then run bulk transition.",
    },
    {
        "id": "dedupe",
        "label": "Duplicate scan & merge",
        "keywords": ("duplicate", "dedupe", "merge records", "find duplicates"),
        "web_path": "/connections/{connection_id}/bulk-suite",
        "hint": "Scan duplicates, pick winner, merge with FK relink.",
    },
    {
        "id": "attachments",
        "label": "Attachment housekeeping",
        "keywords": ("orphan attachment", "duplicate file", "attachment clean"),
        "web_path": "/connections/{connection_id}/housekeeping",
        "hint": "Scan orphan/duplicate attachments before confirmed clean.",
    },
    {
        "id": "recompute",
        "label": "Stored computed field recompute",
        "keywords": ("recompute", "stored computed", "touch field", "refresh computed"),
        "web_path": "/connections/{connection_id}/bulk-suite",
        "hint": "Bulk touch technique for stored computed fields.",
    },
    {
        "id": "send_message",
        "label": "Bulk chatter message",
        "keywords": ("bulk message", "send message", "notify many", "chatter many"),
        "web_path": "/connections/{connection_id}/bulk-suite",
        "hint": "Threaded bulk send on selected records.",
    },
)


@dataclass
class GroundingBundle:
    """Structured grounding payload for Expert retrieval + generation."""

    retrieval_version: str | None = None
    no_connection_note: str | None = None
    instance_summary: dict[str, Any] = field(default_factory=dict)
    capability_highlights: list[dict[str, Any]] = field(default_factory=list)
    ui_context: dict[str, Any] = field(default_factory=dict)
    protected_flags: list[dict[str, Any]] = field(default_factory=list)
    error_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    suggested_tools: list[dict[str, Any]] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    token_estimate: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "retrieval_version": self.retrieval_version,
            "no_connection_note": self.no_connection_note,
            "instance_summary": dict(self.instance_summary),
            "capability_highlights": list(self.capability_highlights),
            "ui_context": dict(self.ui_context),
            "protected_flags": list(self.protected_flags),
            "error_diagnostics": list(self.error_diagnostics),
            "suggested_tools": list(self.suggested_tools),
            "sections": dict(self.sections),
            "token_estimate": self.token_estimate,
        }


def _normalize_version(server_version: str | None) -> str | None:
    if not server_version:
        return None
    m = re.match(r"^(\d+\.\d+)", str(server_version).strip())
    return m.group(1) if m else None


def _edition_from_version(server_version: str | None) -> str:
    raw = (server_version or "").lower()
    if "+e" in raw or "enterprise" in raw:
        return "enterprise"
    return "community"


def _installed_from_manifest(manifest: dict[str, Any]) -> list[str]:
    mods: set[str] = set()
    counts = manifest.get("module_counts") or {}
    live = manifest.get("live_instance") or {}
    for bucket_key in ("tier_1_never_generate_logic", "tier_2_extend_only"):
        bucket = manifest.get(bucket_key) or live.get(bucket_key) or {}
        if isinstance(bucket, dict):
            for items in bucket.values():
                if isinstance(items, list):
                    mods.update(str(m) for m in items)
    sample = manifest.get("unclassified_sample") or live.get("unclassified_sample") or []
    if isinstance(sample, list):
        mods.update(str(m) for m in sample)
    if counts.get("live_instance"):
        # Manifest may only have counts — caller can enrich via client
        pass
    return sorted(mods)


def _notable_flags(modules: set[str]) -> dict[str, bool]:
    flags = {
        "account": "account" in modules,
        "base_automation": "base_automation" in modules,
        "web_studio": bool(modules & {"web_studio", "studio_customization"}),
        "l10n_installed": any(m.startswith("l10n_") for m in modules),
    }
    for name in _NOTABLE_MODULE_EXACT:
        if name not in flags:
            flags[name] = name in modules
    return flags


def merge_question_with_pasted_error(
    question: str,
    ui_context: dict[str, Any] | None,
) -> str:
    """Combine main question with ui_context.pasted_error when not already embedded."""
    q = (question or "").strip()
    pasted = ""
    if ui_context:
        pasted = str(ui_context.get("pasted_error") or "").strip()
    if not pasted or pasted in q:
        return q
    if re.search(r"(?i)\nerror log:\n", q):
        return q
    return f"{q}\n\nError log:\n{pasted}" if q else pasted


def extract_model_field_refs(text: str) -> list[tuple[str, str | None]]:
    """Return unique (model, field|None) refs from question/error text."""
    if not text:
        return []
    seen: set[tuple[str, str | None]] = set()
    out: list[tuple[str, str | None]] = []

    def _add(model: str, fld: str | None) -> None:
        key = (model.lower(), fld.lower() if fld else None)
        if key not in seen and len(out) < _MAX_MODELS_FROM_TEXT:
            seen.add(key)
            out.append(key)

    for match in _MODEL_FIELD_RE.finditer(text):
        model, fld = match.group(1).lower().split(".", 1)
        _add(model, fld)
    for match in _MODEL_RE.finditer(text):
        token = match.group(1).lower()
        if "." not in token:
            continue
        _add(token.split(".", 1)[0], None)
    for match in _MODEL_NOT_FOUND_RE.finditer(text):
        _add(match.group(1), None)
    if looks_like_rpc_error(text):
        for match in _X_MODEL_RE.finditer(text):
            _add(match.group(1), None)
    return out[:_MAX_MODELS_FROM_TEXT]


def looks_like_rpc_error(text: str) -> bool:
    if not text:
        return False
    if _ACCESS_ERROR_RE.search(text):
        return True
    if _DOES_NOT_EXIST_RE.search(text):
        return True
    if _FAULT_RE.search(text):
        return True
    if _MODEL_NOT_FOUND_RE.search(text):
        return True
    if _VALIDATING_VIEW_RE.search(text):
        return True
    if _TRACEBACK_RE.search(text):
        return True
    return bool(_MODEL_FIELD_RE.search(text))


def match_capability_highlights(
    question: str,
    *,
    url: str | None,
    server_version: str | None,
    installed_modules: list[str] | None,
    connection_id: str | None = None,
) -> list[dict[str, Any]]:
    q = (question or "").lower()
    if not q or not server_version:
        return []
    evaluated = evaluate_full_matrix(
        url=url,
        server_version=server_version,
        installed_modules=installed_modules,
        connection_id=connection_id,
        use_cache=True,
    )
    by_key = {row.key: row for row in evaluated.capabilities}
    highlights: list[dict[str, Any]] = []
    for cap_key, keywords in _CAPABILITY_KEYWORDS.items():
        if not any(kw in q for kw in keywords):
            continue
        row = by_key.get(cap_key)
        if row is None:
            continue
        highlights.append(
            {
                "key": cap_key,
                "label": TIER_CAPABILITY_LABELS.get(cap_key, cap_key),
                "available": row.available,
                "reason": row.reason,
            }
        )
    return highlights[:8]


def route_bulk_tools(question: str, *, connection_id: str | None) -> list[dict[str, Any]]:
    q = (question or "").lower()
    if not q or not connection_id:
        return []
    if not any(
        phrase in q
        for phrase in (
            "many records",
            "bulk",
            "mass edit",
            "all records",
            "duplicate",
            "dedupe",
            "recompute",
            "housekeeping",
        )
    ):
        return []
    routes: list[dict[str, Any]] = []
    for route in _BULK_TOOL_ROUTES:
        if any(kw in q for kw in route["keywords"]):
            routes.append(
                {
                    "id": route["id"],
                    "label": route["label"],
                    "deep_link": route["web_path"].format(connection_id=connection_id),
                    "hint": route["hint"],
                }
            )
    return routes[:5]


def cross_check_schema(
    client: Any,
    refs: list[tuple[str, str | None]],
    *,
    max_checks: int = _MAX_LIVE_FIELD_CHECKS,
) -> list[dict[str, Any]]:
    """Capped live existence checks for models/fields mentioned in errors."""
    diagnostics: list[dict[str, Any]] = []
    for model, fld in refs[:max_checks]:
        entry: dict[str, Any] = {"model": model, "field": fld}
        try:
            model_ok = bool(client.model_exists(model))
        except Exception as exc:  # noqa: BLE001 — best-effort diagnostics
            entry["status"] = "check_failed"
            entry["detail"] = str(exc)
            diagnostics.append(entry)
            continue
        entry["model_exists"] = model_ok
        if not model_ok:
            close = difflib.get_close_matches(model, _known_models(client), n=3, cutoff=0.6)
            if close:
                entry["suggestion"] = f"Did you mean model {close[0]!r}?"
            entry["status"] = "model_missing"
            diagnostics.append(entry)
            continue
        if fld is None:
            entry["status"] = "model_ok"
            diagnostics.append(entry)
            continue
        try:
            field_ok = bool(client.field_exists(model, fld))
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "check_failed"
            entry["detail"] = str(exc)
            diagnostics.append(entry)
            continue
        entry["field_exists"] = field_ok
        if field_ok:
            entry["status"] = "ok"
        else:
            entry["status"] = "field_missing"
            try:
                names = [f.name for f in client.list_fields(model)[:200]]
            except Exception:  # noqa: BLE001
                names = []
            close = difflib.get_close_matches(fld, names, n=3, cutoff=0.55)
            if not close and fld.startswith("x_"):
                suffix = fld[2:]
                by_suffix = sorted(
                    names,
                    key=lambda n: difflib.SequenceMatcher(
                        None, suffix, n[2:] if n.startswith("x_") else n
                    ).ratio(),
                    reverse=True,
                )
                if by_suffix and difflib.SequenceMatcher(
                    None, suffix, by_suffix[0][2:] if by_suffix[0].startswith("x_") else by_suffix[0]
                ).ratio() >= 0.55:
                    close = [by_suffix[0]]
            if close:
                entry["suggestion"] = f"{model}.{fld} not found — similar: {', '.join(close)}"
            else:
                entry["suggestion"] = f"{model}.{fld} does not exist on this instance."
        diagnostics.append(entry)
    return diagnostics


def _known_models(client: Any) -> list[str]:
    try:
        rows = client.execute_kw("ir.model", "search_read", [[]], {"fields": ["model"], "limit": 400})
        return [str(r["model"]) for r in rows if r.get("model")]
    except Exception:  # noqa: BLE001
        return []


def _truncate_section(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def serialize_bundle(bundle: GroundingBundle) -> GroundingBundle:
    """Fill ``sections`` and ``token_estimate`` respecting token budget caps."""
    sections: dict[str, str] = {}
    inst = bundle.instance_summary
    if inst:
        lines = [
            f"Odoo {inst.get('server_version') or '?'} ({inst.get('edition', 'unknown')})",
            f"Hosting: {inst.get('hosting', 'unknown')}",
            f"Installed modules (sample/count): {inst.get('module_count', '?')} "
            f"({', '.join(inst.get('notable_modules', [])[:8])})",
        ]
        flags = inst.get("notable_flags") or {}
        flag_txt = ", ".join(k for k, v in flags.items() if v)
        if flag_txt:
            lines.append(f"Notable: {flag_txt}")
        sections["instance"] = _truncate_section("\n".join(lines), SECTION_CHAR_LIMITS["instance"])

    if bundle.capability_highlights:
        cap_lines = [
            f"- {c['label']}: {c['available']} — {c['reason']}"
            for c in bundle.capability_highlights
        ]
        sections["capabilities"] = _truncate_section(
            "\n".join(cap_lines), SECTION_CHAR_LIMITS["capabilities"]
        )

    if bundle.ui_context:
        ui = bundle.ui_context
        lines = [f"Route: {ui.get('route', '')}", f"Model: {ui.get('model', '')}"]
        if ui.get("draft_summary"):
            lines.append(f"Draft: {ui['draft_summary']}")
        if ui.get("fields"):
            lines.append(f"Fields: {', '.join(ui['fields'][:20])}")
        sections["ui_context"] = _truncate_section(
            "\n".join(l for l in lines if l.strip()),
            SECTION_CHAR_LIMITS["ui_context"],
        )

    if bundle.protected_flags:
        pf_lines = [
            f"- {p['model']}: {p['tier']} — {p.get('safe_alternative', '')}"
            for p in bundle.protected_flags
        ]
        sections["protected"] = _truncate_section(
            "\n".join(pf_lines), SECTION_CHAR_LIMITS["protected"]
        )

    if bundle.error_diagnostics:
        err_lines = []
        for d in bundle.error_diagnostics:
            bit = d.get("suggestion") or d.get("status") or ""
            err_lines.append(f"- {d.get('model')}.{d.get('field') or '*'}: {bit}")
        sections["error_diagnostics"] = _truncate_section(
            "\n".join(err_lines), SECTION_CHAR_LIMITS["error_diagnostics"]
        )

    if bundle.suggested_tools:
        tool_lines = [
            f"- {t['label']}: {t['deep_link']} — {t.get('hint', '')}"
            for t in bundle.suggested_tools
        ]
        sections["tools"] = _truncate_section(
            "\n".join(tool_lines), SECTION_CHAR_LIMITS["tools"]
        )

    if bundle.no_connection_note:
        sections["note"] = bundle.no_connection_note

    total_chars = sum(len(v) for v in sections.values())
    bundle.sections = sections
    bundle.token_estimate = max(1, total_chars // 4)
    return bundle


def _summarize_ui_context(
    ui_context: dict[str, Any] | None,
    *,
    client: Any | None,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    if not ui_context:
        return {}
    out = {
        "route": ui_context.get("route"),
        "model": ui_context.get("model"),
        "draft_summary": ui_context.get("draft_summary"),
    }
    model = str(ui_context.get("model") or "").strip()
    draft = ui_context.get("draft") or ui_context.get("module_spec")
    fields: list[str] = []
    if isinstance(draft, dict):
        for m in draft.get("models") or []:
            if not isinstance(m, dict):
                continue
            if model and str(m.get("model") or "") not in {model, ""}:
                continue
            for f in m.get("fields") or []:
                if isinstance(f, dict) and f.get("name"):
                    fields.append(str(f["name"]))
        if not fields and draft.get("models"):
            out["draft_summary"] = out.get("draft_summary") or f"{len(draft['models'])} model(s) in draft"
    if client and model and client.model_exists(model):
        try:
            live = [f.name for f in client.list_fields(model) if f.name.startswith("x_")][:30]
            fields = sorted(set(fields) | set(live))
        except Exception:  # noqa: BLE001
            pass
    if fields:
        out["fields"] = fields[:40]
    tier = protected_models_for(manifest, model) if model else None
    if tier:
        out["protected_tier"] = tier
    return out


def assemble_context(
    db: Session,
    *,
    connection_id: str | None = None,
    ui_context: dict[str, Any] | None = None,
    question: str | None = None,
    client: Any | None = None,
) -> GroundingBundle:
    """Build a grounding bundle for Expert retrieval + generation."""
    q = merge_question_with_pasted_error((question or "").strip(), ui_context)
    bundle = GroundingBundle()
    row = None
    manifest: dict[str, Any] = {}

    if connection_id:
        from app.odoo_service import get_connection_or_404

        try:
            row = get_connection_or_404(db, connection_id)
        except LookupError:
            bundle.no_connection_note = (
                f"Connection {connection_id} not found — retrieval will not be version-filtered."
            )
        else:
            manifest = manifest_for_connection(row)
            bundle.retrieval_version = _normalize_version(row.server_version)
            installed = _installed_from_manifest(manifest)
            if client is not None:
                live = sample_installed_modules(client, limit=80)
                if live:
                    installed = sorted(set(installed) | set(live))
            mod_set = set(installed)
            notable = sorted(
                m
                for m in mod_set
                if m in _NOTABLE_MODULE_EXACT or m.startswith(_NOTABLE_MODULE_PREFIXES)
            )
            bundle.instance_summary = {
                "connection_id": connection_id,
                "server_version": row.server_version,
                "retrieval_version": bundle.retrieval_version,
                "edition": _edition_from_version(row.server_version),
                "hosting": hosting_hint_from_url(row.url),
                "module_count": (manifest.get("module_counts") or {}).get("union")
                or len(installed),
                "notable_modules": notable[:12],
                "notable_flags": _notable_flags(mod_set),
            }
            bundle.capability_highlights = match_capability_highlights(
                q,
                url=row.url,
                server_version=row.server_version,
                installed_modules=installed,
                connection_id=connection_id,
            )
            bundle.suggested_tools = route_bulk_tools(q, connection_id=connection_id)
    else:
        bundle.no_connection_note = (
            "No connection_id — Expert retrieval is not version-filtered; "
            "answers may not match your instance."
        )

    bundle.ui_context = _summarize_ui_context(ui_context, client=client, manifest=manifest)

    refs = extract_model_field_refs(q)
    models_mentioned = sorted({m for m, _ in refs})
    if ui_context and ui_context.get("model"):
        models_mentioned = sorted(set(models_mentioned) | {str(ui_context["model"]).lower()})

    for model in models_mentioned:
        tier = protected_models_for(manifest, model) if manifest else None
        if tier:
            bundle.protected_flags.append(
                {
                    "model": model,
                    "tier": tier,
                    "safe_alternative": safe_alternative_for(model),
                }
            )

    if client is not None and refs and looks_like_rpc_error(q):
        bundle.error_diagnostics = cross_check_schema(client, refs)

    return serialize_bundle(bundle)


__all__ = [
    "GroundingBundle",
    "SECTION_CHAR_LIMITS",
    "assemble_context",
    "cross_check_schema",
    "extract_model_field_refs",
    "looks_like_rpc_error",
    "merge_question_with_pasted_error",
    "match_capability_highlights",
    "route_bulk_tools",
    "serialize_bundle",
]
