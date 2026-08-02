"""Unit tests for module zip generation."""

import zipfile
from io import BytesIO

from module_generator import (
    FieldSpec,
    ModelSpec,
    ModuleSpec,
    PythonAutomationSpec,
    ViewSpec,
    build_module_zip,
    library_module_spec,
    render_module_files,
)


def test_library_module_spec_has_three_models_and_menus() -> None:
    spec = library_module_spec("library_mgmt", "Library Management")
    assert len(spec.models) == 4
    assert {m.model for m in spec.models} == {
        "x_lib_category",
        "x_lib_author",
        "x_lib_book",
        "x_lib_loan",
    }
    assert "contacts" in spec.depends
    assert "mail" in spec.depends
    book = next(m for m in spec.models if m.model == "x_lib_book")
    loan = next(m for m in spec.models if m.model == "x_lib_loan")
    assert book.mixins == ["mail.thread", "mail.activity.mixin"]
    assert loan.mixins == ["mail.thread", "mail.activity.mixin"]
    assert any(f.name == "x_loan_ids" for f in book.fields)
    author_field = next(f for f in book.fields if f.name == "x_author_id")
    assert author_field.relation == "x_lib_author"
    assert any(v.type == "kanban" and v.model == "x_lib_loan" for v in spec.views)
    assert any(a.name == "Active Loans" for a in spec.actions)
    assert any(a.domain and "x_returned" in a.domain for a in spec.actions)
    assert {m.name for m in spec.menus} >= {
        "Library",
        "Books",
        "Authors",
        "Loans",
        "Active Loans",
        "Categories",
    }
    files = render_module_files(spec)
    assert "library_mgmt/views/menus.xml" in files
    menus_xml = files["library_mgmt/views/menus.xml"]
    assert "Active Loans" in menus_xml
    assert "Books" in menus_xml
    assert "Authors" in menus_xml
    assert "Categories" in menus_xml
    # Domain may be XML-entity-escaped (&apos;) by the menus template filter.
    assert "x_returned" in menus_xml and "False" in menus_xml
    book_py = files["library_mgmt/models/x_lib_book.py"]
    assert "x_lib_author" in book_py
    assert "library_mgmt/models/x_lib_author.py" in files
    book_form = next(v for v in spec.views if v.name == "x_lib_book.form")
    assert 'group string="Identity"' in book_form.arch
    assert 'group string="Catalog"' in book_form.arch
    assert "x_lib_book" in files["library_mgmt/models/x_lib_book.py"]
    book_py = files["library_mgmt/models/x_lib_book.py"]
    assert "mail.thread" in book_py
    assert "mail.activity.mixin" in book_py
    assert "x_loan_ids" in book_py
    assert "ondelete='restrict'" in files["library_mgmt/models/x_lib_loan.py"]
    assert "default_group_by" in files["library_mgmt/views/views.xml"]
    assert "decoration-danger" in files["library_mgmt/views/views.xml"]
    assert 'widget="barcode"' in files["library_mgmt/views/views.xml"]
    assert "action_compute_fine" in files["library_mgmt/models/x_lib_loan.py"]
    assert "library_mgmt/data/automations.xml" in files
    assert "library_mgmt/data/mail_templates.xml" in files
    assert "library_mgmt/data/reminders.xml" in files
    assert "library_mgmt/report/reports.xml" in files
    mail_xml = files["library_mgmt/data/mail_templates.xml"]
    assert "mail_template_loan_due_soon" in mail_xml
    assert "mail_template_loan_overdue" in mail_xml
    assert "CDATA" not in mail_xml  # type=html needs real element children (Odoo 19 RNG)
    assert 'type="html"' in mail_xml
    reminders = files["library_mgmt/data/reminders.xml"]
    assert "numbercall" not in reminders  # removed in Odoo 19 ir.cron
    assert "report_loan_receipt_doc" in files["library_mgmt/report/reports.xml"]
    assert "mail_template_loan_due_soon" in files["library_mgmt/models/x_lib_loan.py"]
    assert any(a.technical_name == "action_x_lib_book_by_barcode" for a in spec.actions)
    assert spec.python_automations
    assert spec.mail_templates
    assert spec.cron_jobs
    raw = build_module_zip(spec)
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        names = zf.namelist()
    assert any(n.endswith("x_lib_loan.py") for n in names)
    assert any(n.endswith("menus.xml") for n in names)
    assert any(n.endswith("mail_templates.xml") for n in names)


def test_model_mixins_emit_inherit_list_and_mail_depends() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_mixins",
            display_name="Demo Mixins",
            depends=["base"],
            models=[
                ModelSpec(
                    model="x_chatter",
                    description="Chatter Thing",
                    mixins=["mail.thread", "mail.activity.mixin"],
                    fields=[
                        FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                    ],
                )
            ],
        )
    )
    py = files["demo_mixins/models/x_chatter.py"]
    assert "_name =" in py
    assert "_inherit =" in py
    assert "mail.thread" in py
    assert "mail.activity.mixin" in py
    manifest = files["demo_mixins/__manifest__.py"]
    assert "'mail'" in manifest or '"mail"' in manifest


def test_library_module_spec_can_skip_fines_and_reminders() -> None:
    spec = library_module_spec(
        "library_lite",
        "Library Lite",
        include_fines=False,
        include_reminders=False,
    )
    assert not spec.python_automations
    assert not spec.mail_templates
    assert not spec.cron_jobs
    files = render_module_files(spec)
    assert "library_lite/data/automations.xml" not in files
    assert "library_lite/data/mail_templates.xml" not in files


def test_library_module_spec_multi_company() -> None:
    spec = library_module_spec("library_mc", "Library MC", multi_company=True)
    for model in spec.models:
        assert any(f.name == "company_id" for f in model.fields)
    assert len(spec.record_rules) == 4
    assert all("company_ids" in r.domain_force for r in spec.record_rules)
    files = render_module_files(spec)
    assert "company_id" in files["library_mc/models/x_lib_book.py"]
    assert "security/record_rules.xml" in files["library_mc/__manifest__.py"]
    rules = files["library_mc/security/record_rules.xml"]
    assert "company_ids" in rules


def test_render_contains_code_automation() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_auto",
            display_name="Demo Auto",
            python_automations=[
                PythonAutomationSpec(
                    name="Set something",
                    model="res.partner",
                    trigger="on_create",
                    code="record.write({'x_auto_note': 'hi'})",
                )
            ],
        )
    )
    assert "demo_auto/__manifest__.py" in files
    assert '<field name="state">code</field>' in files["demo_auto/data/automations.xml"]
    assert "record.write" in files["demo_auto/data/automations.xml"]
    assert "security/ir.model.access.csv" not in files["demo_auto/__manifest__.py"]


def test_render_models_views_and_security() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_models",
            display_name="Demo Models",
            models=[
                ModelSpec(
                    model="x_ticket",
                    description="Ticket",
                    fields=[
                        FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                        FieldSpec(
                            name="x_partner_id",
                            ttype="many2one",
                            string="Partner",
                            relation="res.partner",
                        ),
                    ],
                )
            ],
            views=[
                ViewSpec(
                    name="x_ticket.form",
                    model="x_ticket",
                    type="form",
                    arch='<form><sheet><group><field name="x_name"/></group></sheet></form>',
                )
            ],
        )
    )
    assert "demo_models/models/x_ticket.py" in files
    model_py = files["demo_models/models/x_ticket.py"]
    assert "_name =" in model_py and "x_ticket" in model_py
    assert "fields.Many2one" in model_py
    assert "security/ir.model.access.csv" in files["demo_models/__manifest__.py"]
    assert "access_x_ticket" in files["demo_models/security/ir.model.access.csv"]
    assert "demo_models/views/views.xml" in files
    assert "views/views.xml" in files["demo_models/__manifest__.py"]


def test_zip_builds() -> None:
    raw = build_module_zip(
        ModuleSpec(
            technical_name="demo_auto",
            display_name="Demo Auto",
            python_automations=[
                PythonAutomationSpec(
                    name="X",
                    model="res.partner",
                    trigger="on_create",
                    code="True",
                )
            ],
        )
    )
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        names = zf.namelist()
    assert "demo_auto/__manifest__.py" in names


def test_data_mode_has_models_xml_not_python() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_data",
            display_name="Demo Data",
            install_mode="data",
            models=[
                ModelSpec(
                    model="x_data",
                    description="Data",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )
    assert "demo_data/data/models.xml" in files
    assert "demo_data/models/x_data.py" not in files
    assert "model_x_data" in files["demo_data/data/models.xml"]


def test_record_rules_xml_emitted() -> None:
    from module_generator import RecordRuleSpec

    files = render_module_files(
        ModuleSpec(
            technical_name="demo_rules",
            display_name="Demo Rules",
            install_mode="data",
            models=[
                ModelSpec(
                    model="x_owned",
                    description="Owned",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
            record_rules=[
                RecordRuleSpec(
                    name="Own records",
                    model_xml_id="model_x_owned",
                    domain_force="[('create_uid', '=', user.id)]",
                    group_xml_ids=["base.group_user"],
                )
            ],
        )
    )
    assert "demo_rules/security/record_rules.xml" in files
    rules_xml = files["demo_rules/security/record_rules.xml"]
    assert "ir.rule" in rules_xml
    assert "create_uid" in rules_xml
    assert "security/record_rules.xml" in files["demo_rules/__manifest__.py"]


def test_xml_escapes_adversarial_user_strings() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_escape",
            display_name='App <script>&"',
            install_mode="data",
            models=[
                ModelSpec(
                    model="x_evil",
                    description='Ticket <b>& "quotes"',
                    fields=[
                        FieldSpec(
                            name="x_name",
                            ttype="char",
                            string='Name <&> "x"',
                            help='Help <tag>&amp;',
                        )
                    ],
                )
            ],
            views=[
                ViewSpec(
                    name='evil <view> & name',
                    model="x_evil",
                    type="form",
                    arch='<form><sheet><group><field name="x_name"/></group></sheet></form>',
                )
            ],
            python_automations=[],
            record_rules=[],
        )
    )
    models_xml = files["demo_escape/data/models.xml"]
    assert "&lt;b&gt;" in models_xml or "Ticket &lt;b&gt;" in models_xml
    assert "&amp;" in models_xml
    assert "<b>" not in models_xml.split("field_description")[0] or "&lt;b&gt;" in models_xml

    views_xml = files["demo_escape/views/views.xml"]
    assert "evil &lt;view&gt; &amp; name" in views_xml
    # Arch must remain real XML, not entity-escaped tags
    assert '<field name="x_name"/>' in views_xml


def test_automation_code_cdata_and_name_escape() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_cdata",
            display_name="CDATA",
            python_automations=[
                PythonAutomationSpec(
                    name='Auto <danger> & "x"',
                    model="res.partner",
                    trigger="on_create",
                    code="if a < b and c & d:\n    record.write({'x': 1})",
                    filter_domain="[('name', 'ilike', 'a & b')]",
                )
            ],
        )
    )
    auto_xml = files["demo_cdata/data/automations.xml"]
    assert "Auto &lt;danger&gt; &amp; &quot;x&quot;" in auto_xml or (
        "Auto &lt;danger&gt;" in auto_xml and "&amp;" in auto_xml
    )
    assert "<![CDATA[" in auto_xml
    assert "if a < b and c & d:" in auto_xml
    assert "a &amp; b" in auto_xml or "a &amp; b" in auto_xml.replace("&quot;", "")


def test_menus_and_actions_for_models() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_menus",
            display_name="Demo Menus",
            models=[
                ModelSpec(
                    model="x_ticket",
                    description="Ticket",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )
    assert "demo_menus/views/menus.xml" in files
    menus = files["demo_menus/views/menus.xml"]
    assert "ir.actions.act_window" in menus
    assert "menuitem" in menus
    assert "x_ticket" in menus
    assert "views/menus.xml" in files["demo_menus/__manifest__.py"]
    assert '"application": True' in files["demo_menus/__manifest__.py"]


def test_related_and_monetary_field_spec() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_rel",
            display_name="Demo Rel",
            models=[
                ModelSpec(
                    model="x_sale",
                    description="Sale",
                    fields=[
                        FieldSpec(
                            name="x_partner_name",
                            ttype="related",
                            string="Partner Name",
                            related="partner_id.name",
                        ),
                        FieldSpec(
                            name="x_amount",
                            ttype="monetary",
                            string="Amount",
                            currency_field="x_currency_id",
                        ),
                    ],
                )
            ],
        )
    )
    model_py = files["demo_rel/models/x_sale.py"]
    assert "related='partner_id.name'" in model_py or 'related="partner_id.name"' in model_py
    assert "currency_field=" in model_py
    assert "fields.Monetary" in model_py


def test_inherit_model_python_uses_inherit_not_name() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_ext",
            display_name="Demo Ext",
            models=[
                ModelSpec(
                    model="res.partner",
                    description="Partner",
                    mode="inherit",
                    inherit="res.partner",
                    fields=[
                        FieldSpec(name="x_loyalty", ttype="char", string="Loyalty"),
                    ],
                )
            ],
        )
    )
    model_py = files["demo_ext/models/res_partner.py"]
    assert "_inherit =" in model_py
    assert "res.partner" in model_py
    assert "_name =" not in model_py
    assert "x_loyalty" in model_py


def test_data_mode_extension_fields_without_ir_model() -> None:
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_partner_ext",
            display_name="Partner Ext",
            install_mode="data",
            models=[
                ModelSpec(
                    model="res.partner",
                    description="Partner",
                    mode="inherit",
                    inherit="res.partner",
                    fields=[
                        FieldSpec(name="x_note", ttype="char", string="Note"),
                    ],
                )
            ],
        )
    )
    models_xml = files["demo_partner_ext/data/models.xml"]
    assert 'model="ir.model"' not in models_xml
    assert "model_res_partner" not in models_xml or 'ref="model_res_partner"' not in models_xml
    assert "ir.model.fields" in models_xml
    assert "x_note" in models_xml
    assert "search=" in models_xml
    assert "res.partner" in models_xml


def test_depends_includes_sale_for_m2o_to_sale_order() -> None:
    spec = ModuleSpec(
        technical_name="demo_sale_dep",
        display_name="Sale Dep",
        models=[
            ModelSpec(
                model="x_ticket",
                description="Ticket",
                fields=[
                    FieldSpec(
                        name="x_order_id",
                        ttype="many2one",
                        string="Order",
                        relation="sale.order",
                    ),
                ],
            )
        ],
    )
    deps = spec.infer_and_merge_depends()
    assert deps[0] == "base"
    assert "sale" in deps


def test_inherit_view_xml_has_inherit_id() -> None:
    from module_generator import render_xpath_field_inject

    arch = render_xpath_field_inject("x_foo", "form")
    assert 'expr="//sheet"' in arch
    assert 'name="x_foo"' in arch

    files = render_module_files(
        ModuleSpec(
            technical_name="demo_inherit_view",
            display_name="Inherit View",
            models=[
                ModelSpec(
                    model="res.partner",
                    description="Partner",
                    mode="inherit",
                    inherit="res.partner",
                    fields=[FieldSpec(name="x_foo", ttype="char", string="Foo")],
                )
            ],
            views=[
                ViewSpec(
                    name="res.partner.form.extension",
                    model="res.partner",
                    type="form",
                    arch=arch,
                    inherit_xml_id="base.view_partner_form",
                    mode="extension",
                )
            ],
        )
    )
    views_xml = files["demo_inherit_view/views/views.xml"]
    assert 'name="inherit_id" ref="base.view_partner_form"' in views_xml
    assert '<field name="mode">extension</field>' in views_xml
    assert 'expr="//sheet"' in views_xml
    # Inherit-only module should not invent ACL for stock models
    assert not any("ir.model.access.csv" in path for path in files)