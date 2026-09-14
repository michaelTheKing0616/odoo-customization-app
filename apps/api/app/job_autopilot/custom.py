"""Custom residual only: pack/skeleton seed + closer + live apply + zip."""

from __future__ import annotations

import base64
import copy
import re
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai_live_apply_contract import attach_live_apply_contract
from app.job_autopilot.packet import CustomApplyReport, CustomResidual, JobPacket
from app.spec_apply_ui import apply_module_spec_ui

ProgressFn = Callable[[str], None]


def _residual_prompt(packet: JobPacket) -> str:
    lines = [
        "Custom residual only. Do not create parallel invoices, partners, employees, "
        "warehouses, or products — those are stock Odoo.",
        f"Original brief: {packet.prompt}",
    ]
    if packet.grounding:
        lines.append("Client-document grounding:")
        lines.extend(f"- {g}" for g in packet.grounding[:8])
    lines.append("Build only these documents:")
    for r in packet.custom_residuals:
        lines.append(f"- {r.model} ({r.key}): {r.reason}")
    lines.append(f"Stock apps already chosen: {', '.join(packet.stock_apps)}")
    return "\n".join(lines)


def _has_python_blocks(spec: dict[str, Any]) -> bool:
    blocks = spec.get("custom_code_blocks") or spec.get("python_files") or []
    if not isinstance(blocks, list):
        return False
    return any(isinstance(b, dict) and (b.get("code") or b.get("content")) for b in blocks)


def _label_from_model(model: str) -> str:
    leaf = re.sub(r"^x_", "", model or "").replace("_", " ").strip()
    return leaf.title() or "Record"


def _skeleton_model(residual: CustomResidual) -> dict[str, Any]:
    """Generic workflow header: name, stock contact (res.partner), status. No vertical FKs."""
    label = _label_from_model(residual.model)
    return {
        "model": residual.model,
        "description": residual.reason or label,
        "mode": "new",
        "is_workflow": True,
        "fields": [
            {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
            {
                "name": "x_partner_id",
                "ttype": "many2one",
                "string": "Contact",
                "relation": "res.partner",
            },
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": "[('draft','Draft'),('open','Open'),('done','Done'),('cancel','Cancelled')]",
                "default": "draft",
            },
        ],
    }


def _wanted_models(packet: JobPacket, spec: dict[str, Any] | None = None) -> set[str]:
    """Packet residual (+ line/party), plus the matched pack floor and stock inherit."""
    wanted = {r.model for r in packet.custom_residuals if r.model}
    extra: set[str] = set()
    for name in list(wanted):
        extra.add(f"{name}_line")
        extra.add(f"{name}_party")
    wanted |= extra
    if isinstance(spec, dict):
        for mid in spec.get("_pack_model_ids") or []:
            if mid:
                wanted.add(str(mid))
        for row in spec.get("models") or []:
            if not isinstance(row, dict):
                continue
            mid = str(row.get("model") or "")
            if str(row.get("mode") or "new") == "inherit" and mid:
                wanted.add(mid)
    return wanted


def _keep_stock_inherit(model: dict[str, Any], wanted: set[str]) -> bool:
    """Keep inherit rows that only hang residual FKs on stock documents."""
    if str(model.get("mode") or "new") != "inherit":
        return False
    mid = str(model.get("model") or "")
    if not mid or mid.startswith("x_"):
        return False
    for field in model.get("fields") or []:
        if not isinstance(field, dict):
            continue
        rel = str(field.get("relation") or "")
        if rel in wanted:
            return True
    return False


def seed_residual_spec(packet: JobPacket) -> dict[str, Any]:
    """Deterministic ModuleSpec for packet residuals — never the full-app LLM pipeline."""
    technical = "x_autopilot_residual"
    display = packet.domain_label or "Operations"
    depends = ["mail", "contacts"]
    models: list[dict[str, Any]] = []
    try:
        from app.ai_domain_packs import match_domain_pack

        matched = match_domain_pack(packet.prompt)
    except Exception:  # noqa: BLE001
        matched = None
    if matched:
        _pack_id, pack = matched
        if isinstance(pack, dict) and pack.get("models"):
            seeded = copy.deepcopy(pack)
            seeded["_user_prompt"] = packet.prompt
            seeded["_autopilot_seed"] = True
            seeded["grain"] = "feature_slice"
            seeded["domain_pack"] = pack.get("domain_pack") or _pack_id
            clipped = clip_spec_to_residuals(seeded, packet)
            if clipped.get("models"):
                return clipped
    if not models:
        models = [_skeleton_model(r) for r in packet.custom_residuals]
    return {
        "technical_name": re.sub(r"[^a-z0-9_]", "_", technical.lower())[:64]
        or "x_autopilot_residual",
        "display_name": display,
        "depends": depends,
        "models": models,
        "grain": "feature_slice",
        "_user_prompt": packet.prompt,
        "_autopilot_seed": True,
    }


def _ping(on_progress: ProgressFn | None, label: str) -> None:
    if on_progress:
        on_progress(label)


def clip_spec_to_residuals(spec: dict[str, Any], packet: JobPacket) -> dict[str, Any]:
    """Drop Expert siblings that are not the packet residual, pack floor, or stock inherit."""
    wanted = _wanted_models(packet, spec)
    working = copy.deepcopy(spec)
    present = {
        str(m.get("model") or "")
        for m in (working.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    keep = set(wanted)
    for row in working.get("models") or []:
        if isinstance(row, dict) and _keep_stock_inherit(row, wanted):
            keep.add(str(row.get("model") or ""))
    removed = {name for name in present if name not in keep}
    if not removed:
        return working
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    _purge_draft_artifacts_for_models(working, removed)
    working["_autopilot_clipped"] = sorted(removed)
    return working


def _expert_fix(working: dict[str, Any], packet: JobPacket, report: CustomApplyReport) -> dict[str, Any]:
    try:
        from app.expert.draft_review import review_draft

        reviewed = review_draft(
            working,
            user_prompt=packet.prompt,
            apply_fixes=True,
            include_narratives=False,
        )
        report.expert_score_before = float(reviewed.score_before)
        if reviewed.score_after is not None:
            report.expert_score_after = float(reviewed.score_after)
        if reviewed.repairs:
            report.warnings.extend(str(n) for n in reviewed.repairs[:12])
        if isinstance(reviewed.draft, dict) and reviewed.draft.get("models"):
            return reviewed.draft
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"Expert-fix skipped: {exc}")
        try:
            from app.ai_odoo_app_bar import close_odoo_architecture

            notes = close_odoo_architecture(working, user_prompt=packet.prompt)
            report.warnings.extend(str(n) for n in notes if n)
        except Exception as close_exc:  # noqa: BLE001
            report.warnings.append(f"Architecture closer skipped: {close_exc}")
    return working


def _attach_zip(working: dict[str, Any], report: CustomApplyReport) -> None:
    try:
        from app.module_spec_codec import export_draft_module_zip

        zip_bytes = export_draft_module_zip(working)
        report.zip_base64 = base64.b64encode(zip_bytes).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"Module zip export skipped: {exc}")


def apply_custom_residual(
    client: Any,
    packet: JobPacket,
    *,
    spec: dict[str, Any] | None = None,
    db: Session | None = None,
    connection_id: str | None = None,
    draft_fn: Any | None = None,
    skip_expert: bool = False,
    on_progress: ProgressFn | None = None,
) -> CustomApplyReport:
    """Apply ModuleSpec only when the packet has a custom residual.

    Default path seeds from the domain pack / a skeleton. It does **not** run
    ``draft_module_from_prompt`` (full-app LLM). Pass ``draft_fn`` only in tests.
    """
    if not packet.has_custom_residual:
        return CustomApplyReport(
            skipped=True,
            reason="Packet has no custom residual — stock + data only.",
        )
    report = CustomApplyReport()
    working = spec
    if working is None and draft_fn is not None:
        _ping(on_progress, "custom: draft")
        try:
            draft, _raw, warnings, _refusals = draft_fn(_residual_prompt(packet))
        except Exception as exc:  # noqa: BLE001
            report.warnings.append(f"Draft generation failed: {exc}")
            report.reason = str(exc)
            return report
        working = draft if isinstance(draft, dict) else None
        if warnings:
            report.warnings.extend(str(w) for w in warnings)
    elif working is None:
        _ping(on_progress, "custom: seed")
        working = seed_residual_spec(packet)
    if not isinstance(working, dict) or not working.get("models"):
        report.warnings.append("No ModuleSpec models after residual seed — skip apply.")
        report.reason = "empty_spec"
        return report
    if not skip_expert:
        _ping(on_progress, "custom: closer")
        working = _expert_fix(working, packet, report)
    clipped = clip_spec_to_residuals(working, packet)
    dropped = list(clipped.get("_autopilot_clipped") or [])
    if dropped and clipped.get("models"):
        report.warnings.append(
            "Residual clip dropped non-packet models: " + ", ".join(str(n) for n in dropped[:12])
        )
        working = clipped
    try:
        report.warnings.extend(attach_live_apply_contract(working))
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"Live-apply stamp skipped: {exc}")
    _ping(on_progress, "custom: apply")
    try:
        applied = apply_module_spec_ui(client, working)
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"Apply failed: {exc}")
        report.reason = str(exc)
        report.spec = working
        _attach_zip(working, report)
        return report
    report.apply_message = applied.message
    report.models_created = list(applied.models_created)
    report.fields_created = int(applied.fields_created)
    report.fields_relaxed = int(getattr(applied, "fields_relaxed", 0) or 0)
    report.root_menu_id = getattr(applied, "root_menu_id", None)
    report.open_action_id = getattr(applied, "open_action_id", None)
    report.warnings.extend(list(applied.warnings or []))
    report.spec = working
    _ping(on_progress, "custom: zip")
    _attach_zip(working, report)
    if (not skip_expert) and _has_python_blocks(working) and db is not None and connection_id:
        _ping(on_progress, "custom: elite")
        try:
            from app.ai_elite_promote import run_elite_autopilot

            report.elite = run_elite_autopilot(db, connection_id=connection_id, spec=working)
            if not report.elite.get("ok"):
                report.warnings.append(
                    report.elite.get("message") or "Elite sandbox zip skipped (not a go-live fail)."
                )
            elite_zip = (report.elite or {}).get("zip_base64")
            if elite_zip:
                report.zip_base64 = str(elite_zip)
        except Exception as exc:  # noqa: BLE001
            report.warnings.append(f"Elite substep skipped: {exc}")
    return report


__all__ = ["apply_custom_residual", "clip_spec_to_residuals", "seed_residual_spec"]
