"""GEN2-13 draft validators — XML arch + cross-metadata consistency."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from app.ai_depth import compute_depth_metrics

_EMPTY_FIELD_RE = re.compile(r"<field\b(?![^>]*\bname=)[^>]*/>", re.I)
_FILLER_FILTER_NAMES = frozenset({"all", "has_name"})


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f.get("name"))
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


def _parse_arch_root(arch: str) -> ET.Element | None:
    text = str(arch or "").strip()
    if not text:
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        try:
            return ET.fromstring(f"<wrapper>{text}</wrapper>")
        except ET.ParseError:
            return None


def _walk_arch_fields(
    node: ET.Element,
    *,
    model_names: set[str],
    mid: str,
    vtype: str,
    findings: list[dict[str, Any]],
    in_o2m: bool = False,
) -> None:
    for child in node:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "field":
            fname = child.get("name")
            embedded = any(
                (g.tag.split("}")[-1] if "}" in g.tag else g.tag) in {"list", "tree", "kanban"}
                for g in child
            )
            if embedded:
                _walk_arch_fields(child, model_names=model_names, mid=mid, vtype=vtype, findings=findings, in_o2m=True)
            elif not in_o2m and fname and fname not in model_names:
                findings.append(
                    {
                        "validator": "xml",
                        "element": f"{mid}.{fname}",
                        "detail": "arch references unknown field",
                    }
                )
            elif in_o2m or fname:
                _walk_arch_fields(child, model_names=model_names, mid=mid, vtype=vtype, findings=findings, in_o2m=in_o2m)
        else:
            _walk_arch_fields(child, model_names=model_names, mid=mid, vtype=vtype, findings=findings, in_o2m=in_o2m)


def validate_view_archs(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse view arches — empty fields, unknown names, statusbar/button refs."""
    findings: list[dict[str, Any]] = []
    by_id = _models_index(draft)
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        mid = str(view.get("model") or "")
        vtype = str(view.get("type") or "")
        arch = str(view.get("arch") or "")
        if not arch:
            continue
        model = by_id.get(mid)
        names = _field_names(model) if model else set()
        for match in _EMPTY_FIELD_RE.finditer(arch):
            findings.append(
                {
                    "validator": "xml",
                    "element": f"{mid}.{vtype}",
                    "detail": f"empty field tag: {match.group(0)!r}",
                }
            )
        root = _parse_arch_root(arch)
        if root is None:
            findings.append(
                {
                    "validator": "xml",
                    "element": f"{mid}.{vtype}",
                    "detail": "arch XML parse error",
                }
            )
            continue
        state_keys: set[str] = set()
        if model:
            sf = model.get("state_field") if isinstance(model.get("state_field"), dict) else {}
            for key in sf.get("states") or []:
                state_keys.add(str(key))
            for f in model.get("fields") or []:
                if isinstance(f, dict) and f.get("name") == "x_status":
                    sel = f.get("selection")
                    if isinstance(sel, str):
                        state_keys.update(re.findall(r"\('([^']+)'\s*,", sel))
        _walk_arch_fields(root, model_names=names, mid=mid, vtype=vtype, findings=findings)
        for node in root.iter("field"):
            fname = node.get("name")
            if node.get("widget") == "statusbar" and fname and fname not in names:
                findings.append(
                    {
                        "validator": "xml",
                        "element": f"{mid}.{fname}",
                        "detail": "statusbar field missing on model",
                    }
                )
        for node in root.iter("button"):
            state_to = node.get("data-state") or node.get("name")
            if state_to and state_keys and str(state_to) not in state_keys:
                # transition buttons often use name=action — skip generic buttons
                if node.get("type") == "object" and "status" in str(node.get("name") or "").lower():
                    findings.append(
                        {
                            "validator": "xml",
                            "element": f"{mid}.button",
                            "detail": f"button references unknown state {state_to!r}",
                        }
                    )
    return findings


def validate_consistency(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Cross-check counts, depth metrics order, duplicate parent m2o, live field naming."""
    findings: list[dict[str, Any]] = []
    by_id = _models_index(draft)
    models = list(by_id.keys())
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    if meta.get("model_count") is not None and int(meta["model_count"]) != len(models):
        findings.append(
            {
                "validator": "consistency",
                "element": "_meta.model_count",
                "detail": f"_meta.model_count={meta.get('model_count')} vs models={len(models)}",
            }
        )
    depth = draft.get("_depth") if isinstance(draft.get("_depth"), dict) else {}
    metrics = depth.get("metrics") if isinstance(depth.get("metrics"), dict) else {}
    metrics_ns = (
        depth.get("metrics_without_seeds")
        if isinstance(depth.get("metrics_without_seeds"), dict)
        else {}
    )
    if metrics and metrics_ns:
        with_seeds = int(metrics.get("model_count") or 0)
        without = int(metrics_ns.get("model_count") or 0)
        if without > with_seeds:
            findings.append(
                {
                    "validator": "consistency",
                    "element": "_depth",
                    "detail": "metrics_without_seeds.model_count exceeds metrics.model_count",
                }
            )
    live_all = compute_depth_metrics(draft, exclude_depth_seed=False)
    live_ns = compute_depth_metrics(draft, exclude_depth_seed=True)
    if int(live_ns["model_count"]) > int(live_all["model_count"]):
        findings.append(
            {
                "validator": "consistency",
                "element": "_depth",
                "detail": "recomputed depth counts inverted (without_seeds > all)",
            }
        )
    for mid, model in by_id.items():
        if not mid.startswith("x_"):
            continue
        names = _field_names(model)
        if "company_id" in names and "x_company_id" not in names:
            findings.append(
                {
                    "validator": "consistency",
                    "element": mid,
                    "detail": "live draft uses company_id without x_ prefix",
                }
            )
        if not mid.endswith("_line"):
            continue
        parent_m2os = [
            str(f.get("name"))
            for f in (model.get("fields") or [])
            if isinstance(f, dict)
            and f.get("ttype") == "many2one"
            and str(f.get("relation") or "") in by_id
            and not str(f.get("relation") or "").endswith("_line")
        ]
        if len(parent_m2os) > 1:
            findings.append(
                {
                    "validator": "consistency",
                    "element": mid,
                    "detail": f"duplicate parent m2o fields: {', '.join(parent_m2os)}",
                }
            )
    for rule in draft.get("record_rules") or []:
        if not isinstance(rule, dict):
            continue
        dom = str(rule.get("domain_force") or "")
        if "x_branch_id.x_manager_id" in dom and "user.id" in dom:
            model = str(rule.get("model") or "")
            groups = rule.get("group_xml_ids") or []
            user_group = any("user" in str(g).lower() and "manager" not in str(g).lower() for g in groups)
            if not groups or user_group:
                findings.append(
                    {
                        "validator": "consistency",
                        "element": model or "record_rule",
                        "detail": "branch-manager scope on USER group locks out plain staff",
                    }
                )
    return findings


def run_draft_validators(draft: dict[str, Any]) -> dict[str, Any]:
    xml_findings = validate_view_archs(draft)
    consistency_findings = validate_consistency(draft)
    return {
        "xml_findings": xml_findings,
        "consistency_findings": consistency_findings,
        "xml_ok": not xml_findings,
        "consistency_ok": not consistency_findings,
        "all_green": not xml_findings and not consistency_findings,
    }


__all__ = [
    "run_draft_validators",
    "validate_consistency",
    "validate_view_archs",
]
