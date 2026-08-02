"""Portable ModuleSpec factories for app wizard templates (Phase P1–P4)."""

from __future__ import annotations

from . import (
    ActionSpec,
    CronJobSpec,
    FieldSpec,
    MailTemplateSpec,
    MenuSpec,
    ModelSpec,
    ModuleSpec,
    PythonAutomationSpec,
    RecordRuleSpec,
    ReportSpec,
    ViewSpec,
)

# Shared snippet for automations UI + generated library module (Option A).
LIBRARY_FINE_AUTOMATION_CODE = """\
# Library fine on return — Option A (state=code in generated module / sandbox).
# Available: env, model, record, records, time, datetime, dateutil, timezone, log, Warning
for record in records:
    if not record.x_returned or not record.x_due_date:
        continue
    today = datetime.date.today()
    due = record.x_due_date
    days = max((today - due).days, 0)
    rate = (record.x_book_id.x_fine_rate if record.x_book_id else 0.0) or 0.0
    record.write({
        'x_days_overdue': days,
        'x_fine_amount': float(days) * float(rate),
    })
"""

_LOAN_EXTRA_PYTHON = '''
    def action_compute_fine(self):
        """Compute days overdue and fine from book fine rate when returned."""
        today = fields.Date.context_today(self)
        for record in self:
            if not record.x_returned or not record.x_due_date:
                record.write({"x_days_overdue": 0, "x_fine_amount": 0.0})
                continue
            days = max((today - record.x_due_date).days, 0)
            rate = (record.x_book_id.x_fine_rate if record.x_book_id else 0.0) or 0.0
            record.write({
                "x_days_overdue": days,
                "x_fine_amount": float(days) * float(rate),
            })
        return True

    def cron_send_overdue_reminders(self):
        """Daily: email members — overdue loans and loans due within 2 days."""
        today = fields.Date.context_today(self)
        overdue_tpl = self.env.ref(
            "__MODULE__.mail_template_loan_overdue",
            raise_if_not_found=False,
        )
        due_soon_tpl = self.env.ref(
            "__MODULE__.mail_template_loan_due_soon",
            raise_if_not_found=False,
        )
        if overdue_tpl:
            overdue = self.search([
                ("x_returned", "=", False),
                ("x_due_date", "<", today),
            ])
            for loan in overdue:
                if loan.x_member_id and loan.x_member_id.email:
                    overdue_tpl.send_mail(loan.id, force_send=False)
        if due_soon_tpl:
            from datetime import timedelta
            soon = today + timedelta(days=2)
            due_soon = self.search([
                ("x_returned", "=", False),
                ("x_due_date", ">=", today),
                ("x_due_date", "<=", soon),
            ])
            for loan in due_soon:
                if loan.x_member_id and loan.x_member_id.email:
                    due_soon_tpl.send_mail(loan.id, force_send=False)
        return True
'''

# Standard multi-company domain (Odoo ir.rule special variable company_ids).
_COMPANY_DOMAIN = (
    "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]"
)


def _company_field() -> FieldSpec:
    return FieldSpec(
        name="company_id",
        ttype="many2one",
        string="Company",
        relation="res.company",
        on_delete="restrict",
    )


def library_module_spec(
    technical_name: str = "library_mgmt",
    display_name: str = "Library Management",
    *,
    include_fines: bool = True,
    include_reminders: bool = True,
    multi_company: bool = False,
) -> ModuleSpec:
    """Full library shell: Category, Book, Loan + menus/reporting/ops extras.

    Depends on ``base``, ``contacts``, and ``mail``.
    When ``include_fines`` is True, adds Option A python automation on loan write.
    When ``include_reminders`` is True (default), adds mail template + ir.cron.
    When ``multi_company`` is True, adds ``company_id`` + company record rules.
    """
    status_sel = "[('available', 'Available'), ('loaned', 'Loaned'), ('lost', 'Lost')]"

    loan_extra = None
    if include_fines or include_reminders:
        loan_extra = _LOAN_EXTRA_PYTHON.replace("__MODULE__", technical_name)

    cat_fields = [
        FieldSpec(name="x_name", ttype="char", string="Category Name", required=True),
    ]
    author_fields = [
        FieldSpec(name="x_name", ttype="char", string="Author Name", required=True),
        FieldSpec(
            name="x_notes",
            ttype="text",
            string="Bio / Notes",
            help="Optional author biography",
        ),
    ]
    book_fields = [
        FieldSpec(name="x_name", ttype="char", string="Title", required=True),
        FieldSpec(name="x_isbn", ttype="char", string="ISBN"),
        FieldSpec(name="x_barcode", ttype="char", string="Barcode"),
        FieldSpec(name="x_copies", ttype="integer", string="Copies"),
        FieldSpec(name="x_available", ttype="boolean", string="Available"),
        FieldSpec(
            name="x_status",
            ttype="selection",
            string="Status",
            selection=status_sel,
        ),
        FieldSpec(
            name="x_category_id",
            ttype="many2one",
            string="Category",
            relation="x_lib_category",
        ),
        FieldSpec(
            name="x_author_id",
            ttype="many2one",
            string="Author",
            relation="x_lib_author",
        ),
        FieldSpec(name="x_fine_rate", ttype="float", string="Fine Rate"),
        FieldSpec(
            name="x_notes",
            ttype="text",
            string="Notes",
            help="Free-form notes (future: fine rules, etc.)",
        ),
        FieldSpec(
            name="x_loan_ids",
            ttype="one2many",
            string="Loans",
            relation="x_lib_loan",
            relation_field="x_book_id",
        ),
    ]
    loan_fields = [
        FieldSpec(name="x_name", ttype="char", string="Reference", required=True),
        FieldSpec(
            name="x_book_id",
            ttype="many2one",
            string="Book",
            relation="x_lib_book",
            required=True,
            on_delete="restrict",
        ),
        FieldSpec(
            name="x_member_id",
            ttype="many2one",
            string="Member",
            relation="res.partner",
            required=True,
            on_delete="restrict",
        ),
        FieldSpec(name="x_loan_date", ttype="date", string="Loan Date"),
        FieldSpec(name="x_due_date", ttype="date", string="Due Date"),
        FieldSpec(name="x_returned", ttype="boolean", string="Returned"),
        FieldSpec(name="x_fine_amount", ttype="float", string="Fine Amount"),
        FieldSpec(name="x_days_overdue", ttype="integer", string="Days Overdue"),
        FieldSpec(
            name="x_notes",
            ttype="text",
            string="Notes",
            help="Loan notes (future: reminder log)",
        ),
    ]
    if multi_company:
        cat_fields.append(_company_field())
        author_fields.append(_company_field())
        book_fields.append(_company_field())
        loan_fields.append(_company_field())

    category = ModelSpec(
        model="x_lib_category",
        description="Library Category",
        fields=cat_fields,
    )
    author = ModelSpec(
        model="x_lib_author",
        description="Library Author",
        fields=author_fields,
    )
    book = ModelSpec(
        model="x_lib_book",
        description="Library Book",
        mixins=["mail.thread", "mail.activity.mixin"],
        fields=book_fields,
    )
    loan = ModelSpec(
        model="x_lib_loan",
        description="Library Loan",
        mixins=["mail.thread", "mail.activity.mixin"],
        fields=loan_fields,
        extra_python=loan_extra,
    )

    company_form = '<field name="company_id"/>' if multi_company else ""
    company_list = (
        '<field name="company_id" optional="show"/>' if multi_company else ""
    )

    # List views are authored 19-primary; zip/export rewrites via normalize_module_spec_list_views.
    views = [
        ViewSpec(
            name="x_lib_category.list",
            model="x_lib_category",
            type="list",
            arch=(
                f'<list string="Categories"><field name="x_name"/>{company_list}</list>'
            ),
        ),
        ViewSpec(
            name="x_lib_category.form",
            model="x_lib_category",
            type="form",
            arch=(
                '<form string="Category"><sheet><group string="Category">'
                f'<field name="x_name"/>{company_form}'
                "</group></sheet></form>"
            ),
        ),
        ViewSpec(
            name="x_lib_author.list",
            model="x_lib_author",
            type="list",
            arch=(
                f'<list string="Authors"><field name="x_name"/>'
                f'<field name="x_notes"/>{company_list}</list>'
            ),
        ),
        ViewSpec(
            name="x_lib_author.form",
            model="x_lib_author",
            type="form",
            arch=(
                '<form string="Author"><sheet><group string="Author">'
                f'<field name="x_name"/>'
                f'<field name="x_notes"/>{company_form}'
                "</group></sheet></form>"
            ),
        ),
        ViewSpec(
            name="x_lib_book.list",
            model="x_lib_book",
            type="list",
            arch=(
                '<list string="Books">'
                '<field name="x_name"/>'
                '<field name="x_isbn"/>'
                '<field name="x_barcode"/>'
                '<field name="x_copies"/>'
                '<field name="x_available"/>'
                '<field name="x_status"/>'
                '<field name="x_category_id"/>'
                '<field name="x_author_id"/>'
                f"{company_list}"
                "</list>"
            ),
        ),
        ViewSpec(
            name="x_lib_book.form",
            model="x_lib_book",
            type="form",
            arch=(
                '<form string="Book"><sheet>'
                '<group string="Identity">'
                '<field name="x_name"/>'
                '<field name="x_author_id"/>'
                '<field name="x_category_id"/>'
                "</group>"
                '<group string="Catalog">'
                '<field name="x_isbn"/>'
                '<field name="x_barcode" widget="barcode"/>'
                '<field name="x_copies"/>'
                '<field name="x_available"/>'
                '<field name="x_status"/>'
                "</group>"
                '<group string="Circulation">'
                '<field name="x_fine_rate"/>'
                '<field name="x_notes"/>'
                f"{company_form}"
                "</group>"
                '<group string="Loans">'
                '<field name="x_loan_ids">'
                "<list>"
                '<field name="x_name"/>'
                '<field name="x_member_id"/>'
                '<field name="x_due_date"/>'
                '<field name="x_returned"/>'
                "</list>"
                "</field>"
                "</group>"
                "</sheet></form>"
            ),
        ),
        ViewSpec(
            name="x_lib_book.search",
            model="x_lib_book",
            type="search",
            arch=(
                '<search string="Books">'
                '<field name="x_name"/>'
                '<field name="x_isbn"/>'
                '<field name="x_barcode"/>'
                '<field name="x_status"/>'
                "</search>"
            ),
        ),
        ViewSpec(
            name="x_lib_loan.list",
            model="x_lib_loan",
            type="list",
            arch=(
                '<list string="Loans" decoration-danger="not x_returned">'
                '<field name="x_name"/>'
                '<field name="x_book_id"/>'
                '<field name="x_member_id"/>'
                '<field name="x_loan_date"/>'
                '<field name="x_due_date"/>'
                '<field name="x_returned"/>'
                '<field name="x_fine_amount"/>'
                '<field name="x_days_overdue"/>'
                f"{company_list}"
                "</list>"
            ),
        ),
        ViewSpec(
            name="x_lib_loan.form",
            model="x_lib_loan",
            type="form",
            arch=(
                '<form string="Loan"><sheet>'
                '<group string="Loan">'
                '<field name="x_name"/>'
                '<field name="x_book_id"/>'
                '<field name="x_member_id"/>'
                "</group>"
                '<group string="Dates &amp; status">'
                '<field name="x_loan_date"/>'
                '<field name="x_due_date"/>'
                '<field name="x_returned"/>'
                "</group>"
                '<group string="Fines">'
                '<field name="x_fine_amount"/>'
                '<field name="x_days_overdue"/>'
                '<field name="x_notes"/>'
                f"{company_form}"
                "</group>"
                "</sheet></form>"
            ),
        ),
        ViewSpec(
            name="x_lib_loan.search",
            model="x_lib_loan",
            type="search",
            arch=(
                '<search string="Loans">'
                '<field name="x_name"/>'
                '<field name="x_book_id"/>'
                '<field name="x_member_id"/>'
                '<field name="x_returned"/>'
                '<filter name="filter_active" string="Active" '
                'domain="[(\'x_returned\', \'=\', False)]"/>'
                '<filter name="filter_returned" string="Returned" '
                'domain="[(\'x_returned\', \'=\', True)]"/>'
                "</search>"
            ),
        ),
        ViewSpec(
            name="x_lib_loan.kanban",
            model="x_lib_loan",
            type="kanban",
            arch=(
                '<kanban string="Loans" default_group_by="x_returned">'
                "<templates>"
                '<t t-name="card">'
                '<field name="x_name"/>'
                '<field name="x_book_id"/>'
                '<field name="x_member_id"/>'
                '<field name="x_due_date"/>'
                '<field name="x_returned"/>'
                "</t>"
                "</templates>"
                "</kanban>"
            ),
        ),
    ]

    python_automations: list[PythonAutomationSpec] = []
    if include_fines:
        python_automations.append(
            PythonAutomationSpec(
                name="Library fine on return",
                model="x_lib_loan",
                trigger="on_write",
                code=LIBRARY_FINE_AUTOMATION_CODE,
                filter_domain="[('x_returned', '=', True)]",
                technical_name="library_fine_on_return",
            )
        )

    mail_templates: list[MailTemplateSpec] = []
    cron_jobs: list[CronJobSpec] = []
    if include_reminders:
        mail_templates.append(
            MailTemplateSpec(
                xml_id="mail_template_loan_overdue",
                name="Library: Overdue Loan Reminder",
                model="x_lib_loan",
                subject="Overdue library loan: {{ object.x_name }}",
                body_html=(
                    "<p>Hello {{ object.x_member_id.name }},</p>"
                    "<p>Your loan <strong>{{ object.x_name }}</strong> "
                    "(book: {{ object.x_book_id.x_name }}) was due on "
                    "{{ object.x_due_date }} and is still open.</p>"
                    "<p>Please return the book or contact the library.</p>"
                ),
                email_to="{{ object.x_member_id.email }}",
                description="Overdue reminder to member email",
            )
        )
        mail_templates.append(
            MailTemplateSpec(
                xml_id="mail_template_loan_due_soon",
                name="Library: Due Soon Reminder",
                model="x_lib_loan",
                subject="Library loan due soon: {{ object.x_name }}",
                body_html=(
                    "<p>Hello {{ object.x_member_id.name }},</p>"
                    "<p>Your loan <strong>{{ object.x_name }}</strong> "
                    "(book: {{ object.x_book_id.x_name }}) is due on "
                    "{{ object.x_due_date }}.</p>"
                    "<p>Please return it on time to avoid fines.</p>"
                ),
                email_to="{{ object.x_member_id.email }}",
                description="Due-soon reminder (within 2 days)",
            )
        )
        cron_jobs.append(
            CronJobSpec(
                xml_id="ir_cron_library_overdue_reminders",
                name="Library: Send overdue and due-soon reminders",
                model="x_lib_loan",
                code=("model.cron_send_overdue_reminders()\n"),
                interval_number=1,
                interval_type="days",
            )
        )

    reports = [
        ReportSpec(
            name="Loan Receipt",
            model="x_lib_loan",
            report_name="library_loan_receipt",
            template_xml_id="report_loan_receipt_doc",
            print_report_name="'Loan-%s' % (object.x_name)",
            technical_name="loan_receipt",
            body_html=(
                "<h2>Library Loan Receipt</h2>\n"
                "<p><strong>Reference:</strong> <span t-field=\"o.x_name\"/></p>\n"
                "<p><strong>Book:</strong> <span t-field=\"o.x_book_id\"/></p>\n"
                "<p><strong>Member:</strong> <span t-field=\"o.x_member_id\"/></p>\n"
                "<p><strong>Loan date:</strong> <span t-field=\"o.x_loan_date\"/></p>\n"
                "<p><strong>Due date:</strong> <span t-field=\"o.x_due_date\"/></p>\n"
                "<p><strong>Returned:</strong> <span t-field=\"o.x_returned\"/></p>\n"
                "<p><strong>Fine:</strong> <span t-field=\"o.x_fine_amount\"/></p>\n"
            ),
        )
    ]

    # Explicit menus (Books / Loans / Active Loans / Categories) — skips ensure_default_menus.
    root = MenuSpec(
        name="Library",
        sequence=10,
        technical_name=f"root_{technical_name}",
    )
    action_books = ActionSpec(
        name="Books",
        model="x_lib_book",
        view_mode="list,form",
        technical_name="action_x_lib_book",
    )
    action_loans = ActionSpec(
        name="Loans",
        model="x_lib_loan",
        view_mode="list,form,kanban,pivot,graph",
        technical_name="action_x_lib_loan",
    )
    action_active = ActionSpec(
        name="Active Loans",
        model="x_lib_loan",
        view_mode="list,form,pivot",
        domain="[('x_returned','=',False)]",
        technical_name="action_x_lib_loan_active",
    )
    action_cats = ActionSpec(
        name="Categories",
        model="x_lib_category",
        view_mode="list,form",
        technical_name="action_x_lib_category",
    )
    action_authors = ActionSpec(
        name="Authors",
        model="x_lib_author",
        view_mode="list,form",
        technical_name="action_x_lib_author",
    )
    action_barcode = ActionSpec(
        name="Books by barcode",
        model="x_lib_book",
        view_mode="list,form",
        domain=(
            "[('x_barcode', '=', context.get('default_x_barcode') "
            "or context.get('barcode') or False)]"
        ),
        context="{'search_default_x_barcode': 1}",
        technical_name="action_x_lib_book_by_barcode",
    )
    menus = [
        root,
        MenuSpec(
            name="Books",
            action_xml_id=action_books.xml_id(),
            parent_xml_id=root.xml_id(),
            sequence=10,
            technical_name="x_lib_book",
        ),
        MenuSpec(
            name="Authors",
            action_xml_id=action_authors.xml_id(),
            parent_xml_id=root.xml_id(),
            sequence=15,
            technical_name="x_lib_author",
        ),
        MenuSpec(
            name="Loans",
            action_xml_id=action_loans.xml_id(),
            parent_xml_id=root.xml_id(),
            sequence=20,
            technical_name="x_lib_loan",
        ),
        MenuSpec(
            name="Active Loans",
            action_xml_id=action_active.xml_id(),
            parent_xml_id=root.xml_id(),
            sequence=30,
            technical_name="x_lib_loan_active",
        ),
        MenuSpec(
            name="Categories",
            action_xml_id=action_cats.xml_id(),
            parent_xml_id=root.xml_id(),
            sequence=40,
            technical_name="x_lib_category",
        ),
    ]

    record_rules: list[RecordRuleSpec] = []
    if multi_company:
        for model in (category, author, book, loan):
            record_rules.append(
                RecordRuleSpec(
                    name=f"{model.description} multi-company",
                    model_xml_id=model.model_xml_id(),
                    domain_force=_COMPANY_DOMAIN,
                    technical_name=f"rule_{model.module_basename()}_company",
                )
            )

    return ModuleSpec(
        technical_name=technical_name,
        display_name=display_name,
        depends=["base", "contacts", "mail"],
        models=[category, author, book, loan],
        views=views,
        actions=[
            action_books,
            action_authors,
            action_loans,
            action_active,
            action_cats,
            action_barcode,
        ],
        menus=menus,
        python_automations=python_automations,
        mail_templates=mail_templates,
        cron_jobs=cron_jobs,
        record_rules=record_rules,
        reports=reports,
    )


def library_fines_python_module_spec(
    technical_name: str = "library_fines",
    display_name: str = "Library Fines (Option A)",
) -> ModuleSpec:
    """Thin Option A zip: fine automation only (attach to existing library models)."""
    return ModuleSpec(
        technical_name=technical_name,
        display_name=display_name,
        depends=["base", "base_automation"],
        python_automations=[
            PythonAutomationSpec(
                name="Library fine on return",
                model="x_lib_loan",
                trigger="on_write",
                code=LIBRARY_FINE_AUTOMATION_CODE,
                filter_domain="[('x_returned', '=', True)]",
                technical_name="library_fine_on_return",
            )
        ],
    )


__all__ = [
    "LIBRARY_FINE_AUTOMATION_CODE",
    "library_module_spec",
    "library_fines_python_module_spec",
]
