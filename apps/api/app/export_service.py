"""Build ModuleSpec from live Odoo connection metadata (Phase 5 deepen)."""

from __future__ import annotations

import re

from module_generator import (
    SKIP_FIELD_NAMES,
    AccessRuleSpec,
    CronJobSpec,
    FieldSpec,
    MailTemplateSpec,
    ModelSpec,
    ModuleSpec,
    PythonAutomationSpec,
    RecordRuleSpec,
    ReportSpec,
    ViewSpec,
    build_module_zip,
    manifest_version_for_major,
    render_xpath_fields_inject,
)
from odoo_client import OdooClient

from app.report_export import (
    find_qweb_arch,
    report_row_to_spec,
    should_export_report,
)
# Keep in sync with list_* defaults used below — warn when results may be truncated.
_MODELS_LIMIT = 200
_VIEWS_PER_MODEL_LIMIT = 20
_ACCESS_LIMIT = 50
_RECORD_RULES_LIMIT = 50
_EXTENSION_MODELS_LIMIT = 200


def _field_specs_for_model(client: OdooClient, model_name: str) -> list[FieldSpec]:
    fields = client.list_fields(model_name)
    field_specs: list[FieldSpec] = []
    for f in fields:
        if f.name in SKIP_FIELD_NAMES:
            continue
        # Prefer manual/custom fields; still export x_* from base if present
        if not f.name.startswith("x_") and f.state != "manual":
            continue
        field_specs.append(
            FieldSpec(
                name=f.name,
                ttype=f.ttype,
                string=f.field_description or f.name,
                required=bool(f.required),
                readonly=bool(f.readonly),
                relation=f.relation,
                relation_field=f.relation_field,
                selection=f.selection,
                help=f.help,
                related=f.related,
                currency_field=f.currency_field,
            )
        )
    return field_specs


def _export_inherit_views(
    client: OdooClient,
    *,
    model_name: str,
    field_names: list[str],
    warnings: list[str],
) -> list[ViewSpec]:
    """Build xpath inherit views for form/list/search when inherit_xml_id resolves."""
    if not field_names:
        return []
    out: list[ViewSpec] = []
    wanted = {"form", "list", "tree", "search"}
    # Prefer the list/tree type this major accepts on create (tree on ≤17).
    list_type = client._views_adapter().list_type_fallbacks("list")[0]
    model_views = client.list_views(model_name, limit=_VIEWS_PER_MODEL_LIMIT)
    by_type: dict[str, list] = {}
    for v in model_views:
        if v.type not in wanted:
            continue
        norm = "list" if v.type == "tree" else v.type
        by_type.setdefault(norm, []).append(v)

    for view_type in ("form", "list", "search"):
        candidates = by_type.get(view_type, [])
        inherit_xml_id: str | None = None
        for v in candidates:
            resolved = client.find_xml_id("ir.ui.view", v.id)
            if resolved:
                inherit_xml_id = resolved
                break
        if not inherit_xml_id:
            warnings.append(
                f"Skipped inherit view for {model_name} ({view_type}): "
                "no ir.model.data xml id found"
            )
            continue
        export_type = list_type if view_type == "list" else view_type
        out.append(
            ViewSpec(
                name=f"{model_name}.{view_type}.extension",
                model=model_name,
                type=export_type,
                arch=render_xpath_fields_inject(field_names, export_type),
                inherit_xml_id=inherit_xml_id,
                mode="extension",
                priority=99,
            )
        )
    return out


def module_spec_from_connection(
    client: OdooClient,
    *,
    technical_name: str,
    display_name: str,
    include_custom_models: bool = True,
    include_extensions: bool = True,
    include_views: bool = True,
    include_access: bool = True,
    include_record_rules: bool = True,
    include_menus: bool = True,
    include_automations: bool = True,
    include_mail_templates: bool = True,
    include_crons: bool = True,
    include_reports: bool = True,
    model_filter: list[str] | None = None,
    extend_models: list[str] | None = None,
    depends: list[str] | None = None,
    install_mode: str = "python",
) -> tuple[ModuleSpec, list[str]]:
    """Return (ModuleSpec, warnings) from live Odoo metadata.

    Custom ``x_*`` models are exported as mode=new. Stock / non-custom models that
    carry manual ``x_*`` fields are exported as mode=inherit when
    ``include_extensions`` is true (optionally limited by ``extend_models``).
    """
    models_out: list[ModelSpec] = []
    views_out: list[ViewSpec] = []
    access_out: list[AccessRuleSpec] = []
    record_out: list[RecordRuleSpec] = []
    warnings: list[str] = []
    custom_model_names: set[str] = set()

    if include_custom_models:
        customs = client.list_models(custom_only=True, limit=_MODELS_LIMIT)
        if len(customs) >= _MODELS_LIMIT:
            warnings.append(
                f"Custom model list may be truncated (limit={_MODELS_LIMIT}). "
                "Pass model_filter to export specific models."
            )
        if model_filter:
            allow = set(model_filter)
            customs = [m for m in customs if m.model in allow]
        for m in customs:
            custom_model_names.add(m.model)
            field_specs = _field_specs_for_model(client, m.model)
            models_out.append(
                ModelSpec(
                    model=m.model,
                    description=m.name or m.model,
                    fields=field_specs,
                    mode="new",
                )
            )
            if include_views:
                model_views = client.list_views(m.model, limit=_VIEWS_PER_MODEL_LIMIT)
                if len(model_views) >= _VIEWS_PER_MODEL_LIMIT:
                    warnings.append(
                        f"Views for {m.model} may be truncated "
                        f"(limit={_VIEWS_PER_MODEL_LIMIT})."
                    )
                for v in model_views:
                    if v.type not in {"form", "list", "tree", "search"} or not v.arch:
                        continue
                    views_out.append(
                        ViewSpec(
                            name=v.name,
                            model=v.model,
                            # Keep native type; normalize_module_spec_list_views
                            # rewrites list↔tree when ModuleSpec.odoo_major is set.
                            type=v.type,
                            arch=v.arch,
                        )
                    )
            if include_access:
                rights = client.list_access_rights(model=m.model, limit=_ACCESS_LIMIT)
                if len(rights) >= _ACCESS_LIMIT:
                    warnings.append(
                        f"Access rights for {m.model} may be truncated "
                        f"(limit={_ACCESS_LIMIT})."
                    )
                for right in rights:
                    group_xml = "base.group_user"
                    if right.group_id:
                        resolved = client.find_xml_id("res.groups", right.group_id)
                        if resolved:
                            group_xml = resolved
                    slug = re.sub(r"[^a-z0-9_]+", "_", right.name.lower()).strip("_")[:40]
                    access_out.append(
                        AccessRuleSpec(
                            id=f"access_export_{slug or right.id}",
                            name=right.name,
                            model="model_" + m.model.replace(".", "_"),
                            group=group_xml,
                            perm_read=1 if right.perm_read else 0,
                            perm_write=1 if right.perm_write else 0,
                            perm_create=1 if right.perm_create else 0,
                            perm_unlink=1 if right.perm_unlink else 0,
                        )
                    )
            if include_record_rules:
                rules = client.list_record_rules(model=m.model, limit=_RECORD_RULES_LIMIT)
                if len(rules) >= _RECORD_RULES_LIMIT:
                    warnings.append(
                        f"Record rules for {m.model} may be truncated "
                        f"(limit={_RECORD_RULES_LIMIT})."
                    )
                for rule in rules:
                    if not rule.domain_force:
                        continue
                    group_xmls: list[str] = []
                    for gid in rule.group_ids:
                        resolved = client.find_xml_id("res.groups", gid)
                        if resolved:
                            group_xmls.append(resolved)
                    slug = re.sub(r"[^a-z0-9_]+", "_", rule.name.lower()).strip("_")[:40]
                    record_out.append(
                        RecordRuleSpec(
                            name=rule.name,
                            model_xml_id="model_" + m.model.replace(".", "_"),
                            domain_force=rule.domain_force,
                            group_xml_ids=group_xmls,
                            perm_read=rule.perm_read,
                            perm_write=rule.perm_write,
                            perm_create=rule.perm_create,
                            perm_unlink=rule.perm_unlink,
                            technical_name=f"{m.model}_{slug or rule.id}",
                        )
                    )

    if include_extensions:
        if extend_models is not None:
            extension_targets = list(dict.fromkeys(extend_models))
        else:
            extension_targets = client.list_extension_models(
                exclude=custom_model_names, limit=_EXTENSION_MODELS_LIMIT
            )
            if len(extension_targets) >= _EXTENSION_MODELS_LIMIT:
                warnings.append(
                    f"Extension model list may be truncated "
                    f"(limit={_EXTENSION_MODELS_LIMIT}). "
                    "Pass extend_models to export specific stock models."
                )
        if model_filter:
            # Also allow filter entries that are stock models (not in customs).
            allow = set(model_filter)
            extension_targets = [m for m in extension_targets if m in allow] + [
                m
                for m in model_filter
                if m not in custom_model_names
                and m not in extension_targets
                and not m.startswith("x_")
            ]
            extension_targets = list(dict.fromkeys(extension_targets))

        for model_name in extension_targets:
            if model_name in custom_model_names:
                continue
            field_specs = _field_specs_for_model(client, model_name)
            if not field_specs:
                warnings.append(f"No manual x_* fields on {model_name}; skipped extension")
                continue
            models_out.append(
                ModelSpec(
                    model=model_name,
                    description=model_name,
                    fields=field_specs,
                    mode="inherit",
                    inherit=model_name,
                )
            )
            if include_views:
                views_out.extend(
                    _export_inherit_views(
                        client,
                        model_name=model_name,
                        field_names=[f.name for f in field_specs],
                        warnings=warnings,
                    )
                )

    initial_depends = ["base", *(depends or [])]
    python_autos: list[PythonAutomationSpec] = []
    mail_templates: list[MailTemplateSpec] = []
    cron_jobs: list[CronJobSpec] = []

    export_models = {m.model for m in models_out if m.mode == "new"} | {
        m.model for m in models_out
    }
    if include_automations and export_models:
        try:
            for auto in client.list_automations(limit=200):
                if auto.model not in export_models and auto.model not in custom_model_names:
                    continue
                code: str | None = None
                for sid in auto.action_server_ids or []:
                    rows = client.execute_kw(
                        "ir.actions.server",
                        "read",
                        [[sid]],
                        {"fields": ["state", "code", "name"]},
                    )
                    if rows and rows[0].get("state") == "code" and rows[0].get("code"):
                        code = rows[0]["code"]
                        break
                if not code:
                    warnings.append(
                        f"Skipped automation {auto.name!r} on {auto.model}: "
                        "no state=code server action (safe actions stay live-only)"
                    )
                    continue
                python_autos.append(
                    PythonAutomationSpec(
                        name=auto.name,
                        model=auto.model,
                        trigger=auto.trigger,
                        code=code,
                        filter_domain=auto.filter_domain,
                        technical_name=f"auto_{auto.id}",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Automations export skipped: {exc}")

    if include_mail_templates and export_models:
        try:
            for model_name in sorted(export_models | custom_model_names):
                for tpl in client.list_mail_templates(model=model_name, limit=50):
                    body = tpl.get("body_html") or "<p></p>"
                    # Ensure element children for RNG
                    if isinstance(body, str) and not body.strip().startswith("<"):
                        body = f"<p>{body}</p>"
                    slug = re.sub(
                        r"[^a-z0-9_]+", "_", str(tpl.get("name") or tpl["id"]).lower()
                    ).strip("_")[:40]
                    mail_templates.append(
                        MailTemplateSpec(
                            xml_id=f"mail_tpl_{tpl['id']}_{slug or 'x'}",
                            name=str(tpl.get("name") or f"Template {tpl['id']}"),
                            model=str(tpl.get("model") or model_name),
                            subject=str(tpl.get("subject") or ""),
                            body_html=body if isinstance(body, str) else "<p></p>",
                            email_to=str(tpl.get("email_to") or ""),
                            description=tpl.get("description"),
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Mail templates export skipped: {exc}")

    if include_crons and export_models:
        try:
            for model_name in sorted(export_models | custom_model_names):
                for cron in client.list_crons(model=model_name, limit=20):
                    code = cron.get("code") or ""
                    if not code:
                        warnings.append(
                            f"Skipped cron {cron.get('name')!r}: empty code"
                        )
                        continue
                    mid = cron.get("model_id")
                    tech = model_name
                    if isinstance(mid, (list, tuple)) and mid:
                        tech_rows = client.execute_kw(
                            "ir.model", "read", [[mid[0]]], {"fields": ["model"]}
                        )
                        if tech_rows:
                            tech = tech_rows[0]["model"]
                    slug = re.sub(
                        r"[^a-z0-9_]+",
                        "_",
                        str(cron.get("name") or cron["id"]).lower(),
                    ).strip("_")[:40]
                    cron_jobs.append(
                        CronJobSpec(
                            xml_id=f"ir_cron_{cron['id']}_{slug or 'x'}",
                            name=str(cron.get("name") or cron.get("cron_name") or "Cron"),
                            model=tech,
                            code=code if code.endswith("\n") else code + "\n",
                            interval_number=int(cron.get("interval_number") or 1),
                            interval_type=str(cron.get("interval_type") or "days"),
                            active=bool(cron.get("active", True)),
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Cron export skipped: {exc}")

    reports_out: list[ReportSpec] = []
    if include_reports and export_models:
        try:
            model_domain = list(sorted(export_models | custom_model_names))
            rows = client.execute_kw(
                "ir.actions.report",
                "search_read",
                [[("model", "in", model_domain), ("report_type", "=", "qweb-pdf")]],
                {
                    "fields": [
                        "name",
                        "model",
                        "report_type",
                        "report_name",
                        "print_report_name",
                    ],
                    "limit": 200,
                },
            )
            for row in rows:
                model = str(row.get("model") or "")
                report_key = str(row.get("report_name") or "")
                if not should_export_report(model=model, report_name=report_key):
                    continue
                arch = find_qweb_arch(client, report_key) if report_key else None
                if not arch:
                    warnings.append(
                        f"Skipped report {row.get('name')!r} ({report_key}): "
                        "QWeb view not found"
                    )
                    continue
                reports_out.append(report_row_to_spec(row, arch=arch))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Reports export skipped: {exc}")

    if python_autos or mail_templates or cron_jobs:
        if "mail" not in initial_depends and (mail_templates or cron_jobs):
            initial_depends.append("mail")
        if python_autos and "base_automation" not in initial_depends:
            initial_depends.append("base_automation")

    major = int(client.capabilities.major)
    version = manifest_version_for_major(major)
    if major != 19:
        warnings.append(
            f"Module manifest targets Odoo {major} ({version}). "
            f"Sandbox/run uses matching-major image odoo:{major} on :18069."
        )

    spec = ModuleSpec(
        technical_name=technical_name,
        display_name=display_name,
        version=version,
        depends=list(dict.fromkeys(initial_depends)),
        install_mode=install_mode,
        odoo_major=major,
        models=models_out,
        views=views_out,
        access_rules=access_out,
        record_rules=record_out,
        python_automations=python_autos,
        mail_templates=mail_templates,
        cron_jobs=cron_jobs,
        reports=reports_out,
    )
    spec.infer_and_merge_depends(extra=depends)
    if include_menus and any(m.mode == "new" for m in models_out):
        spec.ensure_default_menus()
    return spec, warnings


def export_connection_module_zip(
    client: OdooClient,
    *,
    technical_name: str,
    display_name: str,
    include_custom_models: bool = True,
    include_extensions: bool = True,
    include_views: bool = True,
    include_access: bool = True,
    include_record_rules: bool = True,
    include_menus: bool = True,
    include_automations: bool = True,
    include_mail_templates: bool = True,
    include_crons: bool = True,
    include_reports: bool = True,
    model_filter: list[str] | None = None,
    extend_models: list[str] | None = None,
    depends: list[str] | None = None,
    install_mode: str = "python",
) -> tuple[bytes, ModuleSpec, list[str]]:
    spec, warnings = module_spec_from_connection(
        client,
        technical_name=technical_name,
        display_name=display_name,
        include_custom_models=include_custom_models,
        include_extensions=include_extensions,
        include_views=include_views,
        include_access=include_access,
        include_record_rules=include_record_rules,
        include_menus=include_menus,
        include_automations=include_automations,
        include_mail_templates=include_mail_templates,
        include_crons=include_crons,
        include_reports=include_reports,
        model_filter=model_filter,
        extend_models=extend_models,
        depends=depends,
        install_mode=install_mode,
    )
    return build_module_zip(spec), spec, warnings
