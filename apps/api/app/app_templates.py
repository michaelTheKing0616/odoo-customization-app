"""App wizard templates — scaffold live Odoo metadata via odoo-client (Phase P1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from odoo_client import (
    CreateAutomationRequest,
    CreateFieldRequest,
    CreateModelRequest,
    CreateRecordRuleRequest,
    FieldType,
    OdooClient,
    UpdateFieldAction,
)
from odoo_client.automation import AutomationTrigger
from odoo_client.client import OdooClientError

# Live RPC custom fields must be x_*; zip/python path uses company_id (see library_module_spec).
_LIVE_COMPANY_DOMAIN = (
    "['|', ('x_company_id', '=', False), ('x_company_id', 'in', company_ids)]"
)


@dataclass
class FieldDef:
    name: str
    field_description: str
    ttype: FieldType
    required: bool = False
    readonly: bool = False
    relation: str | None = None
    selection: str | None = None
    help: str | None = None
    inject: bool = True  # inject into form/list/search after create
    on_delete: str | None = None


@dataclass
class ModelDef:
    model: str
    name: str
    fields: list[FieldDef] = field(default_factory=list)


@dataclass
class AppTemplateMeta:
    id: str
    name: str
    description: str


@dataclass
class ScaffoldResult:
    template_id: str
    models: list[str] = field(default_factory=list)
    models_created: list[str] = field(default_factory=list)
    models_skipped: list[str] = field(default_factory=list)
    fields_created: int = 0
    view_injects: int = 0
    menus_created: int = 0
    warnings: list[str] = field(default_factory=list)
    message: str = ""


def _resolve_model_name(
    fixed: str, technical_prefix: str | None, *, suffix: str
) -> str:
    """Return fixed names, or ``x_{prefix}_{suffix}`` when prefix is set."""
    if not technical_prefix or not technical_prefix.strip():
        return fixed
    prefix = technical_prefix.strip().rstrip("_")
    if not prefix.startswith("x_"):
        prefix = f"x_{prefix}"
    return f"{prefix}_{suffix}"


def _library_models(
    technical_prefix: str | None,
    *,
    multi_company: bool = False,
) -> list[ModelDef]:
    cat = _resolve_model_name("x_lib_category", technical_prefix, suffix="category")
    author = _resolve_model_name("x_lib_author", technical_prefix, suffix="author")
    book = _resolve_model_name("x_lib_book", technical_prefix, suffix="book")
    loan = _resolve_model_name("x_lib_loan", technical_prefix, suffix="loan")
    status_sel = (
        "[('available','Available'),('loaned','Loaned'),('lost','Lost')]"
    )
    def _company() -> FieldDef:
        return FieldDef(
            "x_company_id",
            "Company",
            FieldType.MANY2ONE,
            relation="res.company",
            on_delete="restrict",
            inject=True,
        )

    cat_fields: list[FieldDef] = []
    author_fields: list[FieldDef] = [
        FieldDef(
            "x_notes",
            "Bio / Notes",
            FieldType.TEXT,
            help="Optional author biography",
            inject=True,
        ),
    ]
    book_fields: list[FieldDef] = [
        FieldDef("x_isbn", "ISBN", FieldType.CHAR, inject=True),
        FieldDef("x_barcode", "Barcode", FieldType.CHAR, inject=True),
        FieldDef("x_copies", "Copies", FieldType.INTEGER, inject=True),
        FieldDef("x_available", "Available", FieldType.BOOLEAN, inject=True),
        FieldDef(
            "x_status",
            "Status",
            FieldType.SELECTION,
            selection=status_sel,
            inject=True,
        ),
        FieldDef(
            "x_category_id",
            "Category",
            FieldType.MANY2ONE,
            relation=cat,
            inject=True,
        ),
        FieldDef(
            "x_author_id",
            "Author",
            FieldType.MANY2ONE,
            relation=author,
            inject=True,
        ),
        FieldDef("x_fine_rate", "Fine Rate", FieldType.FLOAT, inject=True),
        FieldDef(
            "x_notes",
            "Notes",
            FieldType.TEXT,
            help="Free-form notes (future: fine rules, etc.)",
            inject=False,
        ),
    ]
    loan_fields: list[FieldDef] = [
        FieldDef(
            "x_book_id",
            "Book",
            FieldType.MANY2ONE,
            relation=book,
            required=True,
            on_delete="restrict",
            inject=True,
        ),
        FieldDef(
            "x_member_id",
            "Member",
            FieldType.MANY2ONE,
            relation="res.partner",
            required=True,
            on_delete="restrict",
            inject=True,
        ),
        FieldDef("x_loan_date", "Loan Date", FieldType.DATE, inject=True),
        FieldDef("x_due_date", "Due Date", FieldType.DATE, inject=True),
        FieldDef("x_returned", "Returned", FieldType.BOOLEAN, inject=True),
        FieldDef("x_fine_amount", "Fine Amount", FieldType.FLOAT, inject=True),
        FieldDef("x_days_overdue", "Days Overdue", FieldType.INTEGER, inject=True),
        FieldDef(
            "x_notes",
            "Notes",
            FieldType.TEXT,
            help="Loan notes (future: reminder log)",
            inject=False,
        ),
    ]
    if multi_company:
        cat_fields.append(_company())
        author_fields.append(_company())
        book_fields.append(_company())
        loan_fields.append(_company())
    return [
        ModelDef(model=cat, name="Categories", fields=cat_fields),
        ModelDef(model=author, name="Authors", fields=author_fields),
        ModelDef(model=book, name="Books", fields=book_fields),
        ModelDef(model=loan, name="Loans", fields=loan_fields),
    ]


def _crm_lite_models(technical_prefix: str | None) -> list[ModelDef]:
    model = _resolve_model_name(
        "x_crm_lead_lite", technical_prefix, suffix="crm_lead_lite"
    )
    stage = "[('new','New'),('qualified','Qualified'),('won','Won'),('lost','Lost')]"
    return [
        ModelDef(
            model=model,
            name="CRM Lead (Lite)",
            fields=[
                FieldDef(
                    "x_partner_id",
                    "Partner",
                    FieldType.MANY2ONE,
                    relation="res.partner",
                    inject=True,
                ),
                FieldDef(
                    "x_stage",
                    "Stage",
                    FieldType.SELECTION,
                    selection=stage,
                    inject=True,
                ),
            ],
        )
    ]


def _inventory_lite_models(technical_prefix: str | None) -> list[ModelDef]:
    model = _resolve_model_name("x_inv_item", technical_prefix, suffix="inv_item")
    return [
        ModelDef(
            model=model,
            name="Inventory Item (Lite)",
            fields=[
                FieldDef("x_qty", "Quantity", FieldType.FLOAT, inject=True),
                FieldDef("x_location", "Location", FieldType.CHAR, inject=True),
            ],
        )
    ]


def _ensure_model(
    client: OdooClient,
    model_def: ModelDef,
    result: ScaffoldResult,
) -> None:
    result.models.append(model_def.model)
    if client.model_exists(model_def.model):
        result.models_skipped.append(model_def.model)
        result.warnings.append(
            f"Model {model_def.model!r} already exists — skipped create; adding missing fields"
        )
        # Still ensure default ACL for usability if somehow missing
        try:
            client.ensure_default_model_access(model_def.model)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"ACL ensure failed for {model_def.model}: {exc}")
        return
    try:
        client.create_model(
            CreateModelRequest(name=model_def.name, model=model_def.model),
            with_defaults=True,
        )
        result.models_created.append(model_def.model)
    except OdooClientError as exc:
        result.warnings.append(f"Failed to create model {model_def.model}: {exc}")
        raise


def _ensure_field(
    client: OdooClient,
    model: str,
    field_def: FieldDef,
    result: ScaffoldResult,
) -> None:
    if client.field_exists(model, field_def.name):
        result.warnings.append(f"Field {model}.{field_def.name} already exists — skipped")
        return
    try:
        created = client.create_field(
            CreateFieldRequest(
                model=model,
                name=field_def.name,
                field_description=field_def.field_description,
                ttype=field_def.ttype,
                required=field_def.required,
                readonly=field_def.readonly,
                relation=field_def.relation,
                selection=field_def.selection,
                help=field_def.help,
                on_delete=field_def.on_delete,
            )
        )
        result.fields_created += 1
        if field_def.inject:
            try:
                views = client.inject_field_into_views(
                    model, created.name, strategy="inherit"
                )
                result.view_injects += len(views)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(
                    f"View inject failed for {model}.{field_def.name}: {exc}"
                )
    except OdooClientError as exc:
        result.warnings.append(f"Failed to create {model}.{field_def.name}: {exc}")


def _maybe_loan_returned_automation(
    client: OdooClient,
    loan_model: str,
    result: ScaffoldResult,
) -> None:
    """On loan create, set x_returned=False (idempotent by name)."""
    auto_name = f"Library: default returned False ({loan_model})"
    try:
        existing = client.list_automations(model=loan_model, limit=50)
        if any(a.name == auto_name for a in existing):
            result.warnings.append(f"Automation {auto_name!r} already exists — skipped")
            return
        if not client.field_exists(loan_model, "x_returned"):
            result.warnings.append(
                f"Skip automation: {loan_model}.x_returned missing"
            )
            return
        client.create_automation(
            CreateAutomationRequest(
                name=auto_name,
                model=loan_model,
                trigger=AutomationTrigger.ON_CREATE,
                action=UpdateFieldAction(field_name="x_returned", value="False"),
            )
        )
    except Exception as exc:  # noqa: BLE001 — optional nicety
        result.warnings.append(f"Loan returned automation skipped: {exc}")


def _maybe_multi_company_rules(
    client: OdooClient,
    models: list[str],
    result: ScaffoldResult,
) -> None:
    """Add company record rules for live x_company_id (idempotent by name)."""
    for model in models:
        if not client.field_exists(model, "x_company_id"):
            result.warnings.append(
                f"Skip multi-company rule: {model}.x_company_id missing"
            )
            continue
        rule_name = f"Library multi-company ({model})"
        try:
            existing = client.list_record_rules(model=model, limit=50)
            if any(r.name == rule_name for r in existing):
                result.warnings.append(f"Record rule {rule_name!r} exists — skipped")
                continue
            client.create_record_rule(
                CreateRecordRuleRequest(
                    model=model,
                    name=rule_name,
                    domain_force=_LIVE_COMPANY_DOMAIN,
                )
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Multi-company rule for {model} skipped: {exc}")


def scaffold_models(
    client: OdooClient,
    *,
    template_id: str,
    model_defs: list[ModelDef],
    display_name: str | None = None,
    with_loan_automation: bool = False,
    multi_company: bool = False,
) -> ScaffoldResult:
    result = ScaffoldResult(template_id=template_id)
    label = display_name or template_id
    for model_def in model_defs:
        _ensure_model(client, model_def, result)
        for field_def in model_def.fields:
            _ensure_field(client, model_def.model, field_def, result)

    if with_loan_automation and result.models:
        loan = next((m for m in result.models if m.endswith("_loan") or m == "x_lib_loan"), None)
        if loan:
            _maybe_loan_returned_automation(client, loan, result)

    if multi_company and result.models:
        _maybe_multi_company_rules(client, result.models, result)

    # Application-style root menu + per-model actions (live path parity with zip)
    try:
        entries = [(m, _menu_label_for_model(m, model_defs)) for m in result.models]
        menu_ids = client.ensure_app_menus(
            root_name=label if label else template_id.replace("_", " ").title(),
            model_entries=entries,
        )
        result.menus_created = len(menu_ids)
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"App menus skipped: {exc}")

    created_n = len(result.models_created)
    skipped_n = len(result.models_skipped)
    result.message = (
        f"Scaffolded {label}: {created_n} model(s) created, "
        f"{skipped_n} skipped, {result.fields_created} field(s) added, "
        f"{result.view_injects} view inject(s), {result.menus_created} menu(s)"
        + (" · multi-company" if multi_company else "")
    )
    return result


def _menu_label_for_model(model: str, model_defs: list[ModelDef]) -> str:
    for d in model_defs:
        if d.model == model:
            return d.name
    # x_lib_book → Books-ish
    leaf = model.rsplit(".", 1)[-1].removeprefix("x_").replace("_", " ")
    return leaf.title() or model


def _maybe_book_loan_o2m(
    client: OdooClient,
    book_model: str,
    loan_model: str,
    result: ScaffoldResult,
) -> None:
    """Ensure x_loan_ids on book → x_book_id on loan (idempotent)."""
    from odoo_client import CreateFieldRequest, FieldType

    try:
        if not client.field_exists(loan_model, "x_book_id"):
            client.create_field(
                CreateFieldRequest(
                    model=loan_model,
                    name="x_book_id",
                    field_description="Book",
                    ttype=FieldType.MANY2ONE,
                    required=True,
                    relation=book_model,
                    on_delete="restrict",
                )
            )
            result.fields_created += 1
        if not client.field_exists(book_model, "x_loan_ids"):
            created = client.create_field(
                CreateFieldRequest(
                    model=book_model,
                    name="x_loan_ids",
                    field_description="Loans",
                    ttype=FieldType.ONE2MANY,
                    relation=loan_model,
                    relation_field="x_book_id",
                )
            )
            result.fields_created += 1
            try:
                views = client.inject_field_into_views(
                    book_model, created.name, strategy="inherit"
                )
                result.view_injects += len(views)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"O2M view inject failed: {exc}")
        else:
            result.warnings.append(f"{book_model}.x_loan_ids already exists — skipped")
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Book↔Loan O2M skipped: {exc}")


def _ensure_book_author_relation(
    client: OdooClient,
    book_model: str,
    author_model: str,
    result: ScaffoldResult,
) -> None:
    """Point x_author_id at the Author model (recreate if it still targets res.partner)."""
    try:
        rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", book_model), ("name", "=", "x_author_id")]],
            {"fields": ["id", "relation"], "limit": 1},
        )
        if rows and rows[0].get("relation") == author_model:
            return
        if rows:
            # Odoo blocks field unlink while any view still references it.
            inject_ids = client.execute_kw(
                "ir.ui.view",
                "search",
                [[("name", "like", f"{book_model}.custom.x_author_id.")]],
            )
            if inject_ids:
                client.execute_kw("ir.ui.view", "unlink", [inject_ids])
            for vt in ("form", "list", "search"):
                primary = client.find_view(book_model, vt, primary_only=True)
                if primary is None:
                    primary = client.find_view(book_model, vt)
                if primary is None or not primary.arch:
                    continue
                if "x_author_id" not in primary.arch:
                    continue
                # Strip the field node so unlink is allowed; layout rewrite restores it.
                cleaned = primary.arch.replace(
                    '<field name="x_author_id" can_create="True" can_write="True"/>',
                    "",
                ).replace('<field name="x_author_id"/>', "")
                if cleaned != primary.arch:
                    client.update_view_arch(primary.id, cleaned)
            client.delete_field(int(rows[0]["id"]))
            result.warnings.append(
                f"Recreated {book_model}.x_author_id → {author_model} "
                f"(was {rows[0].get('relation')!r})"
            )
        created = client.create_field(
            CreateFieldRequest(
                model=book_model,
                name="x_author_id",
                field_description="Author",
                ttype=FieldType.MANY2ONE,
                relation=author_model,
            )
        )
        result.fields_created += 1
        try:
            views = client.inject_field_into_views(
                book_model, created.name, strategy="inherit"
            )
            result.view_injects += len(views)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Author field view inject failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Author relation ensure failed: {exc}")


def _dedupe_library_menus(
    client: OdooClient,
    root_name: str,
    keep_labels: set[str],
    result: ScaffoldResult,
) -> None:
    """Drop legacy Path A menu labels when friendly ones exist (e.g. Library Book → Books)."""
    try:
        roots = client.execute_kw(
            "ir.ui.menu",
            "search",
            [[("name", "=", root_name), ("parent_id", "=", False)]],
            {"limit": 1},
        )
        if not roots:
            return
        root_id = int(roots[0])
        children = client.execute_kw(
            "ir.ui.menu",
            "search_read",
            [[("parent_id", "=", root_id)]],
            {"fields": ["id", "name"]},
        )
        names = {c["name"] for c in children}
        legacy = {
            "Library Category": "Categories",
            "Library Book": "Books",
            "Library Loan": "Loans",
            "Library Author": "Authors",
        }
        to_unlink: list[int] = []
        for child in children:
            target = legacy.get(child["name"])
            if target and target in names and target in keep_labels:
                to_unlink.append(int(child["id"]))
        if to_unlink:
            client.execute_kw("ir.ui.menu", "unlink", [to_unlink])
            result.warnings.append(
                f"Removed {len(to_unlink)} legacy menu(s) under {root_name!r}"
            )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Menu dedupe skipped: {exc}")


def _library_blueprint(
    *,
    category_model: str,
    author_model: str,
    book_model: str,
    loan_model: str,
    multi_company: bool,
    display_name: str,
) -> "AppBlueprint":
    from odoo_client.blueprint import AppBlueprint, FormGroupLayout, ModelFormLayout

    company_fields = ["x_company_id"] if multi_company else []
    return AppBlueprint(
        display_name=display_name,
        field_labels={
            (book_model, "x_name"): "Title",
            (author_model, "x_name"): "Author Name",
            (category_model, "x_name"): "Category Name",
            (loan_model, "x_name"): "Reference",
        },
        form_layouts=[
            ModelFormLayout(
                model=category_model,
                string="Category",
                groups=[
                    FormGroupLayout(
                        string="Category",
                        fields=["x_name", *company_fields],
                    )
                ],
            ),
            ModelFormLayout(
                model=author_model,
                string="Author",
                groups=[
                    FormGroupLayout(
                        string="Author",
                        fields=["x_name", "x_notes", *company_fields],
                    )
                ],
            ),
            ModelFormLayout(
                model=book_model,
                string="Book",
                groups=[
                    FormGroupLayout(
                        string="Identity",
                        fields=["x_name", "x_author_id", "x_category_id"],
                    ),
                    FormGroupLayout(
                        string="Catalog",
                        fields=[
                            "x_isbn",
                            "x_barcode",
                            "x_copies",
                            "x_available",
                            "x_status",
                        ],
                        widgets={"x_barcode": "barcode"},
                    ),
                    FormGroupLayout(
                        string="Circulation",
                        fields=["x_fine_rate", "x_notes", *company_fields],
                    ),
                    FormGroupLayout(string="Loans", fields=["x_loan_ids"]),
                ],
                o2m_lists={
                    "x_loan_ids": [
                        "x_name",
                        "x_member_id",
                        "x_due_date",
                        "x_returned",
                    ]
                },
            ),
            ModelFormLayout(
                model=loan_model,
                string="Loan",
                groups=[
                    FormGroupLayout(
                        string="Loan",
                        fields=["x_name", "x_book_id", "x_member_id"],
                    ),
                    FormGroupLayout(
                        string="Dates & status",
                        fields=["x_loan_date", "x_due_date", "x_returned"],
                    ),
                    FormGroupLayout(
                        string="Fines",
                        fields=[
                            "x_fine_amount",
                            "x_days_overdue",
                            "x_notes",
                            *company_fields,
                        ],
                    ),
                ],
            ),
        ],
    )


def _apply_blueprint_layouts(
    client: OdooClient,
    blueprint: "AppBlueprint",
    result: ScaffoldResult,
) -> None:
    from odoo_client.blueprint import apply_blueprint

    try:
        out = apply_blueprint(client, blueprint)
        for layout_out in out.get("layouts", []):
            if layout_out.get("error"):
                result.warnings.append(
                    f"Form layout {layout_out.get('model')}: {layout_out['error']}"
                )
                continue
            removed = int(layout_out.get("injects_removed") or 0)
            if removed:
                result.warnings.append(
                    f"Removed {removed} custom form inject(s) on {layout_out.get('model')}"
                )
            if not layout_out.get("skipped"):
                result.view_injects += 1
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Blueprint layouts skipped: {exc}")


def _apply_auto_form_layouts(
    client: OdooClient,
    models: list[str],
    result: ScaffoldResult,
) -> None:
    """Labeled Identity/Details/Lines forms for non-library scaffolds."""
    from odoo_client.blueprint import (
        apply_form_layout,
        auto_form_layout_for_model,
    )

    layouts = []
    for model in models:
        layout = auto_form_layout_for_model(client, model, string=model)
        if layout:
            layouts.append(layout)
    if not layouts:
        return
    try:
        for layout in layouts:
            out = apply_form_layout(client, layout)
            if out.get("skipped"):
                continue
            removed = int(out.get("injects_removed") or 0)
            if removed:
                result.warnings.append(
                    f"Removed {removed} custom form inject(s) on {layout.model}"
                )
            result.view_injects += 1
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Auto form layouts skipped: {exc}")


def _maybe_loan_kanban(
    client: OdooClient,
    loan_model: str,
    result: ScaffoldResult,
) -> None:
    """Create a simple returned-grouped kanban for loans if missing."""
    from odoo_client import CreateViewRequest
    from odoo_client.view_arch import render_kanban_arch

    try:
        existing = client.find_view(loan_model, "kanban")
        if existing is not None:
            result.warnings.append(f"Kanban for {loan_model} exists — skipped")
            return
        arch = render_kanban_arch(
            string="Loans",
            records_fields=[
                "x_name",
                "x_book_id",
                "x_member_id",
                "x_due_date",
                "x_returned",
            ],
            default_group_by="x_returned",
        )
        client.create_view(
            CreateViewRequest(
                name=f"{loan_model}.kanban",
                model=loan_model,
                type="kanban",
                arch=arch,
            )
        )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"Loan kanban skipped: {exc}")


def scaffold_library(
    client: OdooClient,
    *,
    display_name: str | None = None,
    technical_prefix: str | None = None,
    multi_company: bool = False,
) -> ScaffoldResult:
    model_defs = _library_models(technical_prefix, multi_company=multi_company)
    result = scaffold_models(
        client,
        template_id="library",
        model_defs=model_defs,
        display_name=display_name or "Library",
        with_loan_automation=True,
        multi_company=multi_company,
    )
    cat = next(
        (m for m in result.models if m.endswith("_category") or m == "x_lib_category"),
        None,
    )
    author = next(
        (m for m in result.models if m.endswith("_author") or m == "x_lib_author"),
        None,
    )
    book = next(
        (m for m in result.models if m.endswith("_book") or m == "x_lib_book"),
        None,
    )
    loan = next(
        (m for m in result.models if m.endswith("_loan") or m == "x_lib_loan"),
        None,
    )
    if book and author:
        _ensure_book_author_relation(client, book, author, result)
    if book and loan:
        _maybe_book_loan_o2m(client, book, loan, result)
        _maybe_loan_kanban(client, loan, result)
    if cat and author and book and loan:
        bp = _library_blueprint(
            category_model=cat,
            author_model=author,
            book_model=book,
            loan_model=loan,
            multi_company=multi_company,
            display_name=display_name or "Library",
        )
        _apply_blueprint_layouts(client, bp, result)
    _dedupe_library_menus(
        client,
        display_name or "Library",
        {"Categories", "Authors", "Books", "Loans"},
        result,
    )
    return result


def scaffold_crm_lite(
    client: OdooClient,
    *,
    display_name: str | None = None,
    technical_prefix: str | None = None,
) -> ScaffoldResult:
    result = scaffold_models(
        client,
        template_id="crm_lite",
        model_defs=_crm_lite_models(technical_prefix),
        display_name=display_name or "CRM Lite",
    )
    _apply_auto_form_layouts(client, result.models, result)
    return result


def scaffold_inventory_lite(
    client: OdooClient,
    *,
    display_name: str | None = None,
    technical_prefix: str | None = None,
) -> ScaffoldResult:
    result = scaffold_models(
        client,
        template_id="inventory_lite",
        model_defs=_inventory_lite_models(technical_prefix),
        display_name=display_name or "Inventory Lite",
    )
    _apply_auto_form_layouts(client, result.models, result)
    return result


def _rewrite_pack_prefix(spec: dict, technical_prefix: str | None) -> dict:
    """Rewrite x_rent_* model names when a technical_prefix is provided."""
    import json

    if not technical_prefix or not technical_prefix.strip():
        return spec
    prefix = technical_prefix.strip().rstrip("_")
    if not prefix.startswith("x_"):
        prefix = f"x_{prefix}"
    # Map fixed x_rent_* → x_{prefix}_*
    mapping: dict[str, str] = {}
    for m in spec.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = m.get("model")
        if isinstance(mid, str) and mid.startswith("x_rent_"):
            mapping[mid] = f"{prefix}_{mid.removeprefix('x_rent_')}"

    raw = json.dumps(spec)
    for old, new in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        raw = raw.replace(old, new)
    return json.loads(raw)


def scaffold_car_rental(
    client: OdooClient,
    *,
    display_name: str | None = None,
    technical_prefix: str | None = None,
) -> ScaffoldResult:
    """Fleet + customers + contracts + pricing + payments/damages/maintenance shell."""
    from app.ai_domain_packs import car_rental_pack
    from app.ai_enrich import enrich_draft_module_spec
    from app.spec_apply_ui import apply_module_spec_ui

    draft, _warnings = enrich_draft_module_spec(car_rental_pack())
    draft = _rewrite_pack_prefix(draft, technical_prefix)
    if display_name:
        draft["display_name"] = display_name
    ui = apply_module_spec_ui(client, draft)
    result = ScaffoldResult(
        template_id="car_rental",
        models=[
            m["model"]
            for m in (draft.get("models") or [])
            if isinstance(m, dict) and m.get("model")
        ],
        models_created=ui.models_created,
        models_skipped=[s.split(":", 1)[-1] for s in ui.skipped if s.startswith("model:")],
        fields_created=ui.fields_created,
        view_injects=ui.views_created + ui.views_updated,
        menus_created=ui.menus_created,
        warnings=ui.warnings + _warnings,
        message=ui.message or "Car rental scaffolded",
    )
    return result


TEMPLATE_META: list[AppTemplateMeta] = [
    AppTemplateMeta(
        id="library",
        name="Library",
        description=(
            "Books, authors, categories, and loans — catalog + circulation shell "
            "(ISBN/barcode, status, fines stubs)"
        ),
    ),
    AppTemplateMeta(
        id="car_rental",
        name="Car Rental",
        description=(
            "Fleet, customers (Contacts), contracts, rates, payments stubs, "
            "damages & maintenance — menus, statusbars, smart buttons"
        ),
    ),
    AppTemplateMeta(
        id="crm_lite",
        name="CRM Lite",
        description="Minimal lead model with partner and stage selection",
    ),
    AppTemplateMeta(
        id="inventory_lite",
        name="Inventory Lite",
        description="Minimal item model with quantity and location",
    ),
]

TEMPLATES: dict[str, Callable[..., ScaffoldResult]] = {
    "library": scaffold_library,
    "car_rental": scaffold_car_rental,
    "crm_lite": scaffold_crm_lite,
    "inventory_lite": scaffold_inventory_lite,
}


def list_templates() -> list[dict[str, str]]:
    return [{"id": t.id, "name": t.name, "description": t.description} for t in TEMPLATE_META]


def run_scaffold(
    client: OdooClient,
    template_id: str,
    *,
    display_name: str | None = None,
    technical_prefix: str | None = None,
    multi_company: bool = False,
) -> ScaffoldResult:
    fn = TEMPLATES.get(template_id)
    if fn is None:
        known = ", ".join(sorted(TEMPLATES))
        raise KeyError(f"Unknown template_id {template_id!r}; known: {known}")
    kwargs: dict = {
        "display_name": display_name,
        "technical_prefix": technical_prefix,
    }
    if template_id == "library":
        kwargs["multi_company"] = multi_company
    return fn(client, **kwargs)


__all__ = [
    "ScaffoldResult",
    "TEMPLATES",
    "TEMPLATE_META",
    "list_templates",
    "run_scaffold",
    "scaffold_library",
    "scaffold_car_rental",
    "scaffold_crm_lite",
    "scaffold_inventory_lite",
]
