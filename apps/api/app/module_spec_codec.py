"""ModuleSpec dict ↔ module_generator codec + custom_code_blocks helpers (AI-7)."""

from __future__ import annotations

import copy
from typing import Any

from module_generator import (
    ActionSpec,
    FieldSpec,
    GroupSpec,
    MenuSpec,
    ModelSpec,
    ModuleSpec,
    RecordRuleSpec,
    ReportSpec,
    ViewSpec,
    build_module_zip,
    render_module_files,
)
from odoo_client.image_pipeline import name_suggests_image


def merge_custom_code_blocks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return canonical custom_code_blocks, migrating legacy ``unmapped`` if needed."""
    blocks = spec.get("custom_code_blocks")
    if isinstance(blocks, list) and blocks:
        return [b for b in blocks if isinstance(b, dict)]
    from app.module_import import unmapped_to_custom_code_blocks

    legacy = spec.get("unmapped")
    if isinstance(legacy, list) and legacy:
        return unmapped_to_custom_code_blocks(legacy)
    return []


def merge_module_spec_fragment(
    base: dict[str, Any],
    fragment: dict[str, Any],
) -> dict[str, Any]:
    """Deep-merge a product fragment (e.g. invoicing §19) into a ModuleSpec-like draft."""
    out = copy.deepcopy(base)

    deps = list(out.get("depends") or ["base"])
    for dep in fragment.get("depends_add") or []:
        if dep and dep not in deps:
            deps.append(str(dep))
    out["depends"] = deps

    models_by_name: dict[str, dict[str, Any]] = {}
    for m in out.get("models") or []:
        if isinstance(m, dict) and m.get("model"):
            models_by_name[str(m["model"])] = m

    for fm in fragment.get("models") or []:
        if not isinstance(fm, dict) or not fm.get("model"):
            continue
        mid = str(fm["model"])
        if mid in models_by_name:
            existing = models_by_name[mid]
            field_names = {
                str(f["name"])
                for f in (existing.get("fields") or [])
                if isinstance(f, dict) and f.get("name")
            }
            for ff in fm.get("fields") or []:
                if isinstance(ff, dict) and ff.get("name") and ff["name"] not in field_names:
                    existing.setdefault("fields", []).append(ff)
                    field_names.add(str(ff["name"]))
            for key in ("mode", "inherit", "description"):
                if not existing.get(key) and fm.get(key):
                    existing[key] = fm[key]
        else:
            out.setdefault("models", []).append(fm)
            models_by_name[mid] = fm

    sb = fragment.get("smart_button")
    if isinstance(sb, dict):
        entry = {
            "on_model": sb.get("source_model"),
            "related_model": sb.get("target_model"),
            "relation_field": sb.get("relation_field"),
            "one2many_field": sb.get("one2many_field"),
            "label": sb.get("name") or "Related",
        }
        existing_buttons = out.setdefault("smart_buttons", [])
        if not any(
            isinstance(b, dict)
            and b.get("on_model") == entry["on_model"]
            and b.get("related_model") == entry["related_model"]
            for b in existing_buttons
        ):
            existing_buttons.append(entry)

    sa = fragment.get("server_action")
    if isinstance(sa, dict):
        existing_actions = out.setdefault("server_actions", [])
        if not any(
            isinstance(a, dict)
            and a.get("model") == sa.get("model")
            and a.get("name") == sa.get("name")
            for a in existing_actions
        ):
            existing_actions.append(sa)

    note = fragment.get("review_note")
    if note:
        notes = list(out.get("review_notes") or [])
        if note not in notes:
            notes.append(str(note))
        out["review_notes"] = notes

    for auto in fragment.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        existing_autos = out.setdefault("automations", [])
        if not any(
            isinstance(a, dict)
            and a.get("model") == auto.get("model")
            and a.get("name") == auto.get("name")
            for a in existing_autos
        ):
            existing_autos.append(auto)

    folder_id = fragment.get("documents_folder_id")
    if folder_id is not None:
        out["documents_folder_id"] = folder_id

    return out


def draft_dict_to_module_spec(draft: dict[str, Any]) -> ModuleSpec:
    """Build ModuleSpec from ModuleSpec-like JSON (projects / AI draft / import)."""
    models: list[ModelSpec] = []
    for m in draft.get("models") or []:
        if not isinstance(m, dict) or not m.get("model"):
            continue
        fields = [
            FieldSpec(
                name=str(f.get("name") or ""),
                ttype=str(f.get("ttype") or "char"),
                string=str(f.get("string") or f.get("name") or ""),
                required=bool(f.get("required")),
                readonly=bool(f.get("readonly")),
                relation=f.get("relation"),
                relation_field=f.get("relation_field"),
                selection=f.get("selection"),
                help=f.get("help"),
                on_delete=f.get("on_delete"),
                is_image=bool(f.get("is_image"))
                or name_suggests_image(str(f.get("name") or "")),
                image_role=f.get("image_role"),
                definition_record=f.get("definition_record"),
                definition_record_field=f.get("definition_record_field"),
            )
            for f in (m.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        ]
        models.append(
            ModelSpec(
                model=str(m["model"]),
                description=str(m.get("description") or m["model"]),
                mode=str(m.get("mode") or "new"),
                inherit=m.get("inherit"),
                mixins=list(m.get("mixins") or []),
                is_workflow=bool(m.get("is_workflow") or m.get("state_field")),
                state_field=m.get("state_field") if isinstance(m.get("state_field"), dict) else None,
                extra_python=m.get("extra_python"),
                fields=fields,
            )
        )

    views: list[ViewSpec] = []
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or not v.get("model") or not v.get("arch"):
            continue
        views.append(
            ViewSpec(
                name=str(v.get("name") or f"{v['model']}.{v.get('type', 'form')}"),
                model=str(v["model"]),
                type=str(v.get("type") or "form"),
                arch=str(v["arch"]),
                priority=int(v.get("priority") or 16),
                inherit_xml_id=v.get("inherit_xml_id"),
                mode=str(v.get("mode") or "primary"),
            )
        )

    actions: list[ActionSpec] = []
    for a in draft.get("actions") or []:
        if not isinstance(a, dict) or not a.get("model"):
            continue
        actions.append(
            ActionSpec(
                name=str(a.get("name") or a["model"]),
                model=str(a["model"]),
                view_mode=str(a.get("view_mode") or "list,form"),
                domain=a.get("domain"),
                context=a.get("context"),
                technical_name=a.get("technical_name"),
            )
        )

    menus: list[MenuSpec] = []
    for mu in draft.get("menus") or []:
        if not isinstance(mu, dict) or not mu.get("name"):
            continue
        menus.append(
            MenuSpec(
                name=str(mu["name"]),
                action_xml_id=mu.get("action_xml_id"),
                parent_xml_id=mu.get("parent_xml_id"),
                sequence=int(mu.get("sequence") or 10),
                technical_name=mu.get("technical_name"),
                group_xml_ids=[
                    str(g)
                    for g in (mu.get("groups") or mu.get("group_xml_ids") or [])
                    if g
                ],
            )
        )

    groups: list[GroupSpec] = []
    for g in draft.get("groups") or []:
        if not isinstance(g, dict) or not g.get("id"):
            continue
        groups.append(
            GroupSpec(
                id=str(g["id"]),
                name=str(g.get("name") or g["id"]),
                category_id=g.get("category_id"),
                implied_ids=[str(i) for i in (g.get("implied_ids") or []) if i],
            )
        )

    access_rules: list = []
    from module_generator import AccessRuleSpec

    for ar in draft.get("access_rules") or []:
        if not isinstance(ar, dict) or not ar.get("model"):
            continue
        access_rules.append(
            AccessRuleSpec(
                id=str(ar.get("id") or f"access_{ar['model']}"),
                name=str(ar.get("name") or ar["model"]),
                model=str(ar["model"]),
                group=str(ar.get("group") or ar.get("group_xml_id") or "base.group_user"),
                perm_read=int(ar.get("perm_read", 1)),
                perm_write=int(ar.get("perm_write", 1)),
                perm_create=int(ar.get("perm_create", 1)),
                perm_unlink=int(ar.get("perm_unlink", 1)),
            )
        )

    record_rules: list[RecordRuleSpec] = []
    for rr in draft.get("record_rules") or []:
        if not isinstance(rr, dict) or not rr.get("domain_force"):
            continue
        model = str(rr.get("model") or "")
        xml_id = str(rr.get("model_xml_id") or f"model_{model.replace('.', '_')}")
        record_rules.append(
            RecordRuleSpec(
                name=str(rr.get("name") or f"Multi-company ({model})"),
                model_xml_id=xml_id,
                domain_force=str(rr["domain_force"]),
                group_xml_ids=list(rr.get("group_xml_ids") or []),
                technical_name=rr.get("technical_name"),
            )
        )

    reports: list[ReportSpec] = []
    for rep in draft.get("reports") or []:
        if not isinstance(rep, dict) or not rep.get("model"):
            continue
        reports.append(
            ReportSpec(
                name=str(rep.get("name") or rep["model"]),
                model=str(rep["model"]),
                report_name=str(rep.get("report_name") or rep.get("template_xml_id") or "report"),
                template_xml_id=str(rep.get("template_xml_id") or "report_template"),
                body_html=str(rep.get("body_html") or "<p/>"),
                print_report_name=rep.get("print_report_name"),
                t_lang=rep.get("t_lang"),
                technical_name=rep.get("technical_name"),
            )
        )

    blocks = merge_custom_code_blocks(draft)
    include_barcode = bool(draft.get("include_barcode_scan_widget"))
    if draft.get("multi_company"):
        from app.multi_company_pack import apply_multi_company_to_draft

        draft = apply_multi_company_to_draft(draft)
        record_rules = []
        for rr in draft.get("record_rules") or []:
            if not isinstance(rr, dict) or not rr.get("domain_force"):
                continue
            model = str(rr.get("model") or "")
            xml_id = str(rr.get("model_xml_id") or f"model_{model.replace('.', '_')}")
            record_rules.append(
                RecordRuleSpec(
                    name=str(rr.get("name") or f"Multi-company ({model})"),
                    model_xml_id=xml_id,
                    domain_force=str(rr["domain_force"]),
                    group_xml_ids=list(rr.get("group_xml_ids") or []),
                    technical_name=rr.get("technical_name"),
                )
            )
    return ModuleSpec(
        technical_name=str(draft.get("technical_name") or "custom_module"),
        display_name=str(draft.get("display_name") or "Custom Module"),
        depends=list(draft.get("depends") or ["base"]),
        models=models,
        views=views,
        actions=actions,
        menus=menus,
        groups=groups,
        access_rules=access_rules,
        record_rules=record_rules,
        reports=reports,
        custom_code_blocks=blocks,
        include_barcode_scan_widget=include_barcode,
    )


def export_draft_module_zip(draft: dict[str, Any], *, odoo_major: int | None = None) -> bytes:
    spec = draft_dict_to_module_spec(draft)
    return build_module_zip(spec, odoo_major=odoo_major)


__all__ = [
    "draft_dict_to_module_spec",
    "export_draft_module_zip",
    "merge_custom_code_blocks",
    "merge_module_spec_fragment",
    "render_module_files",
]
