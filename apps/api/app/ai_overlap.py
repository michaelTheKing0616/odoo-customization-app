"""AI-9 — overlap / already-exists detection before draft generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Callable

from odoo_client.client import OdooClient, OdooClientError

from app.ai_grain import Grain, classify_grain, discover_hosts, grain_display
from app.component_gallery import list_gallery

# Drop semantic matches below this — false positives are worse than misses (AI-9 card).
SEMANTIC_CONFIDENCE_FLOOR = 0.72

# Curated keyword → Odoo module capability map (~40 common apps).
MODULE_KEYWORDS: dict[str, dict[str, Any]] = {
    "project": {
        "label": "Project",
        "keywords": (
            "project tracker",
            "task",
            "tasks",
            "kanban",
            "timesheet",
            "milestone",
            "track tasks",
            "per client",
        ),
        "summary": "Odoo Project covers tasks, kanban, timesheets, and milestones.",
    },
    "sale": {
        "label": "Sales",
        "keywords": ("sales", "quotation", "quote", "sale order", "pipeline", "crm lite"),
        "summary": "Odoo Sales covers quotations, orders, and basic CRM pipeline.",
    },
    "crm": {
        "label": "CRM",
        "keywords": ("lead", "opportunity", "pipeline", "prospect"),
        "summary": "Odoo CRM covers leads, opportunities, and pipeline stages.",
    },
    "purchase": {
        "label": "Purchase",
        "keywords": ("purchase order", "vendor", "procurement", "rfq"),
        "summary": "Odoo Purchase covers RFQs and vendor purchase orders.",
    },
    "stock": {
        "label": "Inventory",
        "keywords": ("inventory", "warehouse", "stock move", "delivery order"),
        "summary": "Odoo Inventory covers warehouses, moves, and deliveries.",
    },
    "account": {
        "label": "Accounting",
        "keywords": ("invoice", "accounting", "journal entry", "ledger"),
        "summary": "Odoo Accounting covers invoices, journals, and reconciliation.",
    },
    "hr": {
        "label": "Employees",
        "keywords": ("employee", "hr", "leave", "attendance", "payroll"),
        "summary": "Odoo HR covers employees, leave, and attendance.",
    },
    "helpdesk": {
        "label": "Helpdesk",
        "keywords": ("ticket", "helpdesk", "support desk", "sla"),
        "summary": "Odoo Helpdesk covers tickets and SLA tracking.",
    },
    "website": {
        "label": "Website",
        "keywords": ("website", "landing page", "blog", "ecommerce shop"),
        "summary": "Odoo Website covers pages, blogs, and eCommerce storefronts.",
    },
    "mrp": {
        "label": "Manufacturing",
        "keywords": ("manufacturing", "bom", "work order", "mrp"),
        "summary": "Odoo Manufacturing covers BOMs and work orders.",
    },
}

PROMPT_FIELD_HINTS: list[tuple[str, str, str]] = [
    ("warranty", "x_warranty", "sale.order"),
    ("warranty end", "x_warranty_end", "sale.order"),
    ("inspection", "x_inspection", "project.task"),
    ("compliance", "x_compliance", "res.partner"),
    ("expiry", "x_expiry", "res.partner"),
]


@dataclass
class OverlapFinding:
    id: str
    source: str
    title: str
    evidence: str
    confidence: float
    artifact_type: str
    artifact_ref: dict[str, Any] = field(default_factory=dict)
    deep_link: str | None = None
    extend_host_model: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 3),
            "artifact_type": self.artifact_type,
            "artifact_ref": self.artifact_ref,
            "deep_link": self.deep_link,
            "extend_host_model": self.extend_host_model,
            "options": ["use", "extend", "build_anyway"],
        }


SemanticFn = Callable[[str, list[OverlapFinding]], list[OverlapFinding]]


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _prompt_tokens(prompt: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", (prompt or "").lower()) if len(t) > 2}


def _scan_instance_fields(
    prompt: str,
    *,
    client: OdooClient | None,
    host_model: str | None,
    project_name_by_field: dict[str, str],
) -> list[OverlapFinding]:
    if client is None:
        return []
    text = (prompt or "").lower()
    findings: list[OverlapFinding] = []
    models = [host_model] if host_model else []
    if not models:
        for host in discover_hosts(prompt):
            models.append(host.model)
    models = list(dict.fromkeys(m for m in models if m))[:4]

    for model in models:
        try:
            rows = client.execute_kw(
                "ir.model.fields",
                "search_read",
                [[("model", "=", model), ("name", "like", "x_%")]],
                {"fields": ["name", "field_description", "model"], "limit": 200},
            )
        except OdooClientError:
            continue
        for row in rows:
            fname = str(row.get("name") or "")
            label = str(row.get("field_description") or fname)
            score = max(_similar(text, label), _similar(text, fname.replace("_", " ")))
            for hint, prefix, hint_model in PROMPT_FIELD_HINTS:
                if hint_model == model and hint in text and prefix in fname:
                    score = max(score, 0.88)
            if score < 0.55:
                continue
            proj = project_name_by_field.get(f"{model}.{fname}")
            evidence = f"Field {fname} already on {model.replace('.', ' ').title()} — {label}"
            if proj:
                evidence += f" (project {proj!r})"
            findings.append(
                OverlapFinding(
                    id=f"field-{model}-{fname}",
                    source="instance",
                    title=f"Existing field on {model}",
                    evidence=evidence,
                    confidence=min(0.95, score),
                    artifact_type="field",
                    artifact_ref={"model": model, "field": fname, "label": label},
                    deep_link=f"/connections/{{connection_id}}/designer?model={model}",
                    extend_host_model=model,
                )
            )
    return findings


def _scan_installed_modules(prompt: str, installed: list[str] | None) -> list[OverlapFinding]:
    if not installed:
        return []
    text = (prompt or "").lower()
    installed_set = {m.lower() for m in installed}
    out: list[OverlapFinding] = []
    for mod, meta in MODULE_KEYWORDS.items():
        if mod not in installed_set:
            continue
        hits = [kw for kw in meta["keywords"] if kw in text]
        if not hits and mod == "project" and re.search(r"\b(track|tracker|tasks?)\b", text):
            hits = ["project tracker"]
        if not hits:
            continue
        out.append(
            OverlapFinding(
                id=f"installed-{mod}",
                source="installed_module",
                title=f"{meta['label']} is already installed",
                evidence=f"{meta['summary']} (matched: {', '.join(hits[:3])})",
                confidence=0.86 if len(hits) > 1 else 0.78,
                artifact_type="module",
                artifact_ref={"module": mod, "installed": True},
                deep_link=f"/connections/{{connection_id}}/overview",
            )
        )
    return out


def _scan_available_modules(
    prompt: str,
    *,
    installed: list[str] | None,
    available_modules: list[str] | None,
) -> list[OverlapFinding]:
    """Recommend installing stock Odoo app instead of building knockoff."""
    if not available_modules:
        return []
    text = (prompt or "").lower()
    installed_set = {m.lower() for m in (installed or [])}
    available_set = {m.lower() for m in available_modules}
    out: list[OverlapFinding] = []
    for mod, meta in MODULE_KEYWORDS.items():
        if mod in installed_set or mod not in available_set:
            continue
        hits = [kw for kw in meta["keywords"] if kw in text]
        if not hits:
            continue
        out.append(
            OverlapFinding(
                id=f"available-{mod}",
                source="available_module",
                title=f"Install {meta['label']} instead of rebuilding",
                evidence=f"{meta['summary']} Module {mod!r} is available but not installed.",
                confidence=0.74,
                artifact_type="module",
                artifact_ref={"module": mod, "installed": False},
                deep_link=f"/connections/{{connection_id}}/overview",
            )
        )
    return out


def _scan_workspace_and_gallery(
    prompt: str,
    *,
    projects: list[dict[str, Any]],
    gallery: list[dict[str, Any]] | None = None,
) -> list[OverlapFinding]:
    text = (prompt or "").lower()
    tokens = _prompt_tokens(prompt)
    out: list[OverlapFinding] = []
    for proj in projects:
        name = str(proj.get("name") or "")
        spec = proj.get("spec_json") if isinstance(proj.get("spec_json"), dict) else {}
        display = str(spec.get("display_name") or spec.get("technical_name") or name)
        score = max(_similar(text, name), _similar(text, display))
        if score < 0.58:
            continue
        updated = proj.get("updated_at")
        when = ""
        if isinstance(updated, datetime):
            when = updated.strftime("%d %b")
        elif updated:
            when = str(updated)[:10]
        out.append(
            OverlapFinding(
                id=f"project-{proj.get('id')}",
                source="workspace_project",
                title=f"Workspace project {name!r}",
                evidence=f"Project {name!r} may already cover this ask"
                + (f" — updated {when}" if when else ""),
                confidence=min(0.9, score),
                artifact_type="project",
                artifact_ref={"project_id": proj.get("id"), "name": name},
                deep_link=f"/connections/{{connection_id}}/projects/{proj.get('id')}",
            )
        )
    for item in gallery or list_gallery():
        name = str(item.get("name") or "")
        desc = f"{name} {item.get('description')}"
        score = _similar(text, desc)
        if any(tok in text for tok in name.lower().split() if len(tok) > 3):
            score = max(score, 0.8)
        if score < 0.55:
            continue
        out.append(
            OverlapFinding(
                id=f"gallery-{item.get('id')}",
                source="gallery",
                title=f"Gallery: {item.get('name')}",
                evidence=str(item.get("description") or ""),
                confidence=min(0.85, score),
                artifact_type="gallery",
                artifact_ref={"gallery_id": item.get("id"), "host_slot": item.get("host_slot")},
                deep_link=f"/connections/{{connection_id}}/wizard",
                extend_host_model=str(item.get("host_slot") or ""),
            )
        )
    return out


def _rank_and_cap(findings: list[OverlapFinding], limit: int = 5) -> list[OverlapFinding]:
    dedup: dict[str, OverlapFinding] = {}
    for f in findings:
        if f.id not in dedup or f.confidence > dedup[f.id].confidence:
            dedup[f.id] = f
    ranked = sorted(dedup.values(), key=lambda x: (-x.confidence, x.title))
    return ranked[:limit]


def default_semantic_filter(prompt: str, findings: list[OverlapFinding]) -> list[OverlapFinding]:
    """Optional reasoning pass — drops low-confidence matches; no-op when LLM disabled."""
    if not findings:
        return []
    kept: list[OverlapFinding] = []
    for f in findings:
        if f.confidence >= SEMANTIC_CONFIDENCE_FLOOR:
            kept.append(f)
            continue
        # Attempt lightweight LLM confirm for borderline hits only
        try:
            from app.settings import settings

            if settings.ai_assist == "off":
                continue
            from app.llm_provider import LlmProvider

            provider = LlmProvider()
            msg = (
                "You confirm whether an Odoo overlap finding is valid for the user prompt.\n"
                f"Prompt: {prompt}\nFinding: {f.title}\nEvidence: {f.evidence}\n"
                'Reply JSON only: {"match": true|false, "confidence": 0.0-1.0, "rationale": "..."}'
            )
            raw = provider.generate_text(msg, temperature=0.1, max_tokens=200)
            payload = json.loads(raw.strip().split("\n")[-1])
            if payload.get("match") and float(payload.get("confidence", 0)) >= SEMANTIC_CONFIDENCE_FLOOR:
                f.confidence = float(payload["confidence"])
                kept.append(f)
        except Exception:  # noqa: BLE001
            continue
    return kept


def check_overlap(
    prompt: str,
    *,
    grain: Grain | None = None,
    host_model: str | None = None,
    connection_id: str | None = None,
    client: OdooClient | None = None,
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    available_odoo_modules: list[str] | None = None,
    projects: list[dict[str, Any]] | None = None,
    semantic_fn: SemanticFn | None = None,
) -> dict[str, Any]:
    """Deterministic scan first; semantic pass only when shortlist non-empty."""
    g = grain or classify_grain(prompt)
    hosts = discover_hosts(prompt, available_models=available_models)
    host = host_model or (hosts[0].model if hosts else None)

    project_name_by_field: dict[str, str] = {}
    for proj in projects or []:
        spec = proj.get("spec_json") if isinstance(proj.get("spec_json"), dict) else {}
        pname = str(proj.get("name") or "project")
        for m in spec.get("models") or []:
            if not isinstance(m, dict):
                continue
            model = str(m.get("model") or "")
            for f in m.get("fields") or []:
                if isinstance(f, dict) and f.get("name"):
                    project_name_by_field[f"{model}.{f['name']}"] = pname

    deterministic: list[OverlapFinding] = []
    deterministic.extend(
        _scan_instance_fields(
            prompt,
            client=client,
            host_model=host,
            project_name_by_field=project_name_by_field,
        )
    )
    deterministic.extend(_scan_installed_modules(prompt, installed_modules))
    deterministic.extend(
        _scan_available_modules(
            prompt,
            installed=installed_modules,
            available_modules=available_odoo_modules,
        )
    )
    deterministic.extend(
        _scan_workspace_and_gallery(prompt, projects=projects or [], gallery=list_gallery())
    )

    shortlist = _rank_and_cap(deterministic)
    if not shortlist:
        return {
            "ok": True,
            "grain": g,
            "grain_label": grain_display(g, hosts[0] if hosts else None),
            "findings": [],
            "semantic_pass_ran": False,
            "requires_review": False,
        }

    fn = semantic_fn or default_semantic_filter
    filtered = _rank_and_cap(fn(prompt, shortlist))
    for f in filtered:
        if f.deep_link and connection_id:
            f.deep_link = f.deep_link.replace("{connection_id}", connection_id)

    return {
        "ok": True,
        "grain": g,
        "grain_label": grain_display(g, hosts[0] if hosts else None),
        "findings": [f.as_dict() for f in filtered],
        "semantic_pass_ran": True,
        "requires_review": len(filtered) > 0,
    }


def record_overlap_choice(
    draft_meta: dict[str, Any],
    *,
    finding_id: str | None,
    choice: str,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach audit record when user picks Use / Extend / Build anyway."""
    meta = dict(draft_meta)
    meta["overlap_audit"] = {
        "finding_id": finding_id,
        "choice": choice,
        "findings_count": len(findings or []),
    }
    return meta
