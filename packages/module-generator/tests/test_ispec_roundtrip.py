"""ISPEC round-trips ModuleSpec. The dataclass stays the only module IR."""

from __future__ import annotations

import ast
import copy
import dataclasses
import typing
from pathlib import Path
from typing import Any

import pytest

from module_generator import (
    AccessRuleSpec,
    ActionSpec,
    CronJobSpec,
    FieldSpec,
    GroupSpec,
    MailTemplateSpec,
    MenuSpec,
    ModelSpec,
    ModuleSpec,
    PythonAutomationSpec,
    RecordRuleSpec,
    ReportSpec,
    ViewSpec,
    ispec_to_module_spec,
    library_fines_python_module_spec,
    library_module_spec,
    module_spec_to_ispec,
)
from module_generator.ispec import ISPEC_HEADER, IspecError

# Strings that break a line-oriented or fence-terminated markdown parser.
_TRICKY: tuple[tuple[str, str], ...] = (
    ("empty", ""),
    ("null-word", "null"),
    ("true-word", "true"),
    ("false-word", "false"),
    ("zero-word", "0"),
    ("array-word", "[]"),
    ("object-word", "{}"),
    ("hash", "# heading"),
    ("section", "## models 0"),
    ("key", "key: value"),
    ("fence", "```"),
    ("fence-line", "```\n## models 0\n"),
    ("trailing-nl", "hello\n"),
    ("only-nl", "\n"),
    ("embedded-fence", "line\n```\nline"),
    ("quotes", 'say "hello" \\ path'),
    ("unicode", "café — 日本語"),
    ("spaces", "  spaced  "),
    ("tab", "tab\there"),
    ("text-marker", "text 3"),
    ("json-marker", "json"),
)

_NESTED_ARCH = """\
<form string="Rental">
  <sheet>
    <field name="x_status"/>
    <group invisible="x_status == 'draft'" groups="base.group_system">
      <field name="x_deposit"/>
      <field name="x_line_ids">
        <list>
          <field name="x_product_id"/>
          <field name="x_qty" invisible="parent.x_status == 'draft'"/>
        </list>
      </field>
    </group>
  </sheet>
</form>
"""

_EXTRA_PYTHON = """\
def _compute_deposit(self):
    # ## models 0
    token = '```'
    for record in self:
        record.x_deposit = 0
    return token
"""


def _minimal() -> ModuleSpec:
    return ModuleSpec(technical_name="demo_min", display_name="Demo Min")


def _saturated() -> ModuleSpec:
    """One instance that sets every ModuleSpec field off its dataclass default.

    Relations are multi-level (line → rental → vehicle) and the form arch
    nests a list view under an invisible group. ``depends`` is intentionally
    not the inferred order.
    """
    probe = FieldSpec(
        name="x_probe",
        ttype="properties",
        string="Probe",
        required=True,
        readonly=True,
        relation="x_rental",
        relation_field="x_line_ids",
        relation_table="x_sat_link_rel",
        selection="[('a', 'A'), ('b', 'B')]",
        help="line1\n```\n## models 0\n",
        related="x_vehicle_id.x_name",
        currency_field="x_currency_id",
        on_delete="cascade",
        is_image=True,
        image_role="content",
        image_variant_of="x_photo",
        max_width=64,
        max_height=0,
        definition_record="x_rental",
        definition_record_field="x_props_def",
    )
    blank_help = FieldSpec(
        name="x_blank_help",
        ttype="char",
        string="Blank",
        help="",
        relation="",
    )
    line = ModelSpec(
        model="x_rental_line",
        description="Rental line",
        mode="new",
        inherit="",
        fields=[
            FieldSpec(
                name="x_rental_id",
                ttype="many2one",
                string="Rental",
                relation="x_rental",
                on_delete="cascade",
            ),
            FieldSpec(
                name="x_product_id",
                ttype="many2one",
                string="Product",
                relation="product.product",
            ),
            FieldSpec(name="x_qty", ttype="integer", string="Qty"),
            blank_help,
        ],
    )
    rental = ModelSpec(
        model="x_rental",
        description="Rental",
        mode="new",
        mixins=["mail.thread", "mail.activity.mixin"],
        is_workflow=True,
        state_field={
            "field": "x_status",
            "transitions": [["draft", "open"], ["open", "done"]],
            "labels": {"draft": "Draft", "open": "Open"},
        },
        extra_python=_EXTRA_PYTHON,
        fields=[
            probe,
            FieldSpec(
                name="x_status",
                ttype="selection",
                string="Status",
                selection="[('draft', 'Draft'), ('open', 'Open'), ('done', 'Done')]",
            ),
            FieldSpec(
                name="x_vehicle_id",
                ttype="many2one",
                string="Vehicle",
                relation="x_vehicle",
            ),
            FieldSpec(
                name="x_line_ids",
                ttype="one2many",
                string="Lines",
                relation="x_rental_line",
                relation_field="x_rental_id",
            ),
            FieldSpec(
                name="x_deposit",
                ttype="monetary",
                string="Deposit",
                currency_field="x_currency_id",
            ),
        ],
    )
    vehicle = ModelSpec(
        model="x_vehicle",
        description="Vehicle",
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
    partner = ModelSpec(
        model="res.partner",
        description="Partner vehicle host",
        mode="inherit",
        inherit="res.partner",
        fields=[
            FieldSpec(
                name="x_fleet_code",
                ttype="char",
                string="Fleet code",
            )
        ],
    )
    # line → rental → vehicle → partner, and not alphabetical, so order is part of the value.
    return ModuleSpec(
        technical_name="car_rental_ops",
        display_name="Car Rental",
        version="19.0.2.0.0",
        depends=["sale", "base"],
        author="Ingenium",
        install_mode="data",
        odoo_major=17,
        models=[line, rental, vehicle, partner],
        views=[
            ViewSpec(
                name="x_rental.form",
                model="x_rental",
                type="form",
                arch=_NESTED_ARCH,
                priority=32,
            ),
            ViewSpec(
                name="x_rental.tree",
                model="x_rental",
                type="tree",
                arch='<tree string="Rentals"><field name="x_status"/></tree>',
            ),
            ViewSpec(
                name="res.partner.form.fleet",
                model="res.partner",
                type="form",
                arch='<data><xpath expr="//sheet" position="inside">'
                '<field name="x_fleet_code" groups="base.group_system"/>'
                "</xpath></data>",
                inherit_xml_id="base.view_partner_form",
                mode="extension",
            ),
        ],
        actions=[
            ActionSpec(
                name="Rentals",
                model="x_rental",
                view_mode="tree,form",
                domain="[('x_status', '!=', 'done')]",
                context="{'default_x_status': 'draft'}",
                technical_name="action_x_rental",
            ),
            ActionSpec(name="Vehicles", model="res.partner"),
        ],
        menus=[
            MenuSpec(
                name="Car Rental",
                sequence=0,
                technical_name="root_car_rental_ops",
                web_icon="fa-car,#714B67",
                group_xml_ids=["car_rental_ops.group_agent"],
            ),
            MenuSpec(
                name="Rentals",
                action_xml_id="action_x_rental",
                parent_xml_id="menu_root_car_rental_ops",
                sequence=20,
                technical_name="menu_x_rental",
            ),
        ],
        groups=[
            GroupSpec(
                id="group_agent",
                name="Rental agent",
                category_id=None,
                implied_ids=["base.group_user"],
            ),
            GroupSpec(id="group_manager", name="Rental manager"),
        ],
        python_automations=[
            PythonAutomationSpec(
                name="Open rental",
                model="x_rental",
                trigger="on_write",
                code="for record in records:\n    record.x_status = 'open'\n",
                filter_domain="[('x_status', '=', 'draft')]",
                technical_name="open_rental",
            )
        ],
        access_rules=[
            AccessRuleSpec(
                id="access_x_rental_agent",
                name="x_rental.agent",
                model="model_x_rental",
                group="car_rental_ops.group_agent",
                perm_read=0,
                perm_write=0,
                perm_create=0,
                perm_unlink=0,
            ),
            AccessRuleSpec(
                id="access_x_rental_line",
                name="x_rental_line.all",
                model="model_x_rental_line",
            ),
        ],
        record_rules=[
            RecordRuleSpec(
                name="Rental own company",
                model_xml_id="model_x_rental",
                domain_force="[('company_id', 'in', company_ids)]",
                group_xml_ids=["car_rental_ops.group_agent"],
                perm_read=False,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
                technical_name="rule_x_rental_company",
            ),
            RecordRuleSpec(
                name="Rental global",
                model_xml_id="model_x_rental",
                domain_force="[(1, '=', 1)]",
            ),
        ],
        mail_templates=[
            MailTemplateSpec(
                xml_id="mail_rental_open",
                name="Rental opened",
                model="x_rental",
                subject="Rental {{ object.x_name }}",
                body_html="<p>Opened</p>\n<p>{{ object.x_name }}</p>\n",
                email_to="{{ object.x_partner_id.email }}",
                description="Notify the renter",
            )
        ],
        cron_jobs=[
            CronJobSpec(
                xml_id="ir_cron_close_rentals",
                name="Close finished rentals",
                model="x_rental",
                code="model.search([]).write({'x_status': 'done'})\n",
                interval_number=2,
                interval_type="hours",
                numbercall=0,
                active=False,
                user_id_xml="base.user_admin",
            )
        ],
        reports=[
            ReportSpec(
                name="Rental agreement",
                model="x_rental",
                report_name="report_rental_agreement",
                template_xml_id="report_rental_agreement",
                body_html="<t t-name='agreement'>\n  <t t-esc='o.x_name'/>\n</t>\n",
                print_report_name="'Agreement - %s' % (object.x_name)",
                t_lang="en_US",
                technical_name="rental_agreement",
            )
        ],
        custom_code_blocks=[
            {
                "kind": "python",
                "path": "models/x_rental.py",
                "content": "def _compute(self):\n    return '```'\n",
                "meta": {"lines": [1, 0], "flag": False, "n": None, "rate": 0.1},
            },
            {
                "kind": "xml",
                "content": "<data>\n  ## models 0\n</data>",
                "tags": ["a", "b"],
            },
        ],
        include_barcode_scan_widget=True,
    )


def _list_dataclass(tp: Any) -> type | None:
    if typing.get_origin(tp) is not list:
        return None
    args = typing.get_args(tp)
    if len(args) != 1:
        return None
    item = args[0]
    if isinstance(item, type) and dataclasses.is_dataclass(item):
        return item
    return None


def _string_kind(tp: Any) -> str | None:
    if tp is str:
        return "str"
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is typing.Union or getattr(origin, "__name__", "") == "UnionType":
        non_none = [arg for arg in args if arg is not type(None)]
        if non_none == [str]:
            return "opt_str"
        if len(non_none) == 1 and typing.get_origin(non_none[0]) is dict:
            return "opt_dict"
    if origin is list and args == (str,):
        return "list_str"
    if origin is list and len(args) == 1 and typing.get_origin(args[0]) is dict:
        return "list_dict"
    return None


def _replace_strings(node: Any, text: str) -> Any:
    if type(node) is dict:
        replaced = {
            key: text if type(value) is str else _replace_strings(value, text)
            for key, value in node.items()
        }
        if not any(type(value) is str for value in replaced.values()):
            replaced["s"] = text
        return replaced
    if type(node) is list:
        return [
            text if type(item) is str else _replace_strings(item, text) for item in node
        ]
    return node


def _inject(obj: Any, text: str) -> None:
    """Write ``text`` into every free string on the real dataclass tree."""
    hints = typing.get_type_hints(type(obj))
    for field in dataclasses.fields(type(obj)):
        if field.name == "mode":
            continue
        hint = hints[field.name]
        child = _list_dataclass(hint)
        if child is not None:
            for item in getattr(obj, field.name):
                _inject(item, text)
            continue
        kind = _string_kind(hint)
        if kind in {"str", "opt_str"}:
            if (
                type(obj) is ModelSpec
                and field.name == "inherit"
                and obj.mode == "inherit"
                and text == ""
            ):
                # ModelSpec.__post_init__ replaces a falsy inherit on inherit models.
                continue
            setattr(obj, field.name, text)
        elif kind == "list_str":
            setattr(obj, field.name, [text])
        elif kind == "opt_dict":
            current = getattr(obj, field.name)
            filled = {"s": text} if current is None else _replace_strings(current, text)
            setattr(obj, field.name, filled)
        elif kind == "list_dict":
            current = getattr(obj, field.name)
            setattr(
                obj,
                field.name,
                [_replace_strings(item, text) for item in current] or [{"s": text}],
            )


def _cases() -> list[tuple[str, ModuleSpec]]:
    saturated = _saturated()
    cases = [
        ("library", library_module_spec()),
        (
            "library-no-fines",
            library_module_spec(
                "library_plain",
                "Library",
                include_fines=False,
                include_reminders=False,
            ),
        ),
        (
            "library-multi-company",
            library_module_spec("library_mc", "Library MC", multi_company=True),
        ),
        ("library-fines", library_fines_python_module_spec()),
        ("minimal", _minimal()),
        ("saturated", saturated),
    ]
    for label, text in _TRICKY:
        spec = copy.deepcopy(saturated)
        _inject(spec, text)
        cases.append((f"tricky:{label}", spec))
    return cases


def _diff(left: Any, right: Any, prefix: str = "") -> list[str]:
    if dataclasses.is_dataclass(left) and dataclasses.is_dataclass(right):
        lines: list[str] = []
        for field in dataclasses.fields(left):
            lines.extend(
                _diff(getattr(left, field.name), getattr(right, field.name), f"{prefix}{field.name}.")
            )
        return lines
    if type(left) is list and type(right) is list:
        lines = []
        if len(left) != len(right):
            lines.append(f"{prefix[:-1]}: length {len(left)} != {len(right)}")
        for index, (item_l, item_r) in enumerate(zip(left, right)):
            lines.extend(_diff(item_l, item_r, f"{prefix[:-1]}[{index}]."))
        return lines
    if type(left) is dict and type(right) is dict:
        lines = []
        if set(left) != set(right):
            lines.append(f"{prefix[:-1]}: keys {sorted(left)} != {sorted(right)}")
        for key in left:
            if key in right:
                lines.extend(_diff(left[key], right[key], f"{prefix}{key}."))
        return lines
    if left != right or type(left) is not type(right):
        return [f"{prefix[:-1]}: {left!r} != {right!r}"]
    return []


def _inventory(cls: type) -> tuple[set[str], set[str]]:
    hints = typing.get_type_hints(cls)
    all_fields: set[str] = set()
    defaulted: set[str] = set()
    for field in dataclasses.fields(cls):
        key = f"{cls.__name__}.{field.name}"
        all_fields.add(key)
        has_default = (
            field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        )
        if has_default:
            defaulted.add(key)
        child = _list_dataclass(hints[field.name])
        if child is not None:
            nested_all, nested_defaulted = _inventory(child)
            all_fields |= nested_all
            defaulted |= nested_defaulted
    return all_fields, defaulted


def _observed(spec: ModuleSpec) -> tuple[set[str], set[str]]:
    seen: set[str] = set()
    nondefault: set[str] = set()

    def walk(obj: Any) -> None:
        cls = type(obj)
        for field in dataclasses.fields(cls):
            key = f"{cls.__name__}.{field.name}"
            seen.add(key)
            value = getattr(obj, field.name)
            if field.default_factory is not dataclasses.MISSING:
                default = field.default_factory()
            elif field.default is not dataclasses.MISSING:
                default = field.default
            else:
                default = dataclasses.MISSING
            if default is dataclasses.MISSING or value != default:
                nondefault.add(key)
            if type(value) is list:
                for item in value:
                    if dataclasses.is_dataclass(item):
                        walk(item)

    walk(spec)
    return seen, nondefault


def test_saturated_fixture_sets_every_module_spec_field() -> None:
    expected, defaulted = _inventory(ModuleSpec)
    seen, nondefault = _observed(_saturated())
    assert seen == expected
    missing = sorted(defaulted - nondefault)
    assert missing == []


def test_ispec_round_trip_property() -> None:
    cases = _cases()
    assert len(cases) >= 8
    for name, spec in cases:
        blob = module_spec_to_ispec(spec)
        assert blob.startswith(ISPEC_HEADER + "\n")
        again = ispec_to_module_spec(blob)
        assert type(again) is ModuleSpec
        assert again.__class__.__module__ == "module_generator"
        diffs = _diff(spec, again)
        assert diffs == [], f"{name}: " + "; ".join(diffs[:8])
        assert module_spec_to_ispec(again) == blob
        if name == "library":
            assert "x_lib_book" in blob
            assert "Library Management" in blob
            assert "action_compute_fine" in blob
        if name == "saturated":
            assert again.depends == ["sale", "base"]
            assert again.install_mode == "data"
            assert again.odoo_major == 17
            assert [model.model for model in again.models] == [
                "x_rental_line",
                "x_rental",
                "x_vehicle",
                "res.partner",
            ]
            assert again.views[0].arch == _NESTED_ARCH
            assert again.views[1].type == "tree"
            assert again.menus[0].web_icon == "fa-car,#714B67"
            assert any(model.extra_python == _EXTRA_PYTHON for model in again.models)
            meta = again.custom_code_blocks[0]["meta"]
            assert meta["rate"] == 0.1
            assert type(meta["rate"]) is float
            assert meta["flag"] is False
            assert meta["n"] is None
        if name == "tricky:fence":
            assert spec.display_name == "```"
            assert again.display_name == "```"


def test_ispec_does_not_define_a_second_ir() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "module_generator" / "ispec.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    forbidden = {
        "ModuleSpec",
        "ModelSpec",
        "FieldSpec",
        "ViewSpec",
        "ActionSpec",
        "MenuSpec",
        "GroupSpec",
        "PythonAutomationSpec",
        "AccessRuleSpec",
        "RecordRuleSpec",
        "MailTemplateSpec",
        "CronJobSpec",
        "ReportSpec",
    }
    assert forbidden.isdisjoint(class_names)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for deco in node.decorator_list:
            name = deco.id if isinstance(deco, ast.Name) else ""
            assert name != "dataclass"
    parsed = ispec_to_module_spec(module_spec_to_ispec(_minimal()))
    assert type(parsed) is ModuleSpec


def test_minimal_document_lists_every_scalar_field() -> None:
    spec = _minimal()
    blob = module_spec_to_ispec(spec)
    hints = typing.get_type_hints(ModuleSpec)
    for field in dataclasses.fields(ModuleSpec):
        if _list_dataclass(hints[field.name]) is not None:
            assert f"### {field.name} " not in blob
            continue
        assert any(line.startswith(f"{field.name}:") for line in blob.splitlines())


def test_dropped_field_is_refused() -> None:
    lines = [
        line
        for line in module_spec_to_ispec(_minimal()).splitlines()
        if not line.startswith("author:")
    ]
    with pytest.raises(IspecError, match="missing module.author"):
        ispec_to_module_spec("\n".join(lines) + "\n")


def test_unknown_field_is_refused() -> None:
    blob = module_spec_to_ispec(_minimal()).replace(
        "## module\n", "## module\nextra: 1\n", 1
    )
    with pytest.raises(IspecError, match="unknown field"):
        ispec_to_module_spec(blob)


def test_only_module_spec_serializes() -> None:
    with pytest.raises(TypeError, match="ModuleSpec"):
        module_spec_to_ispec(ModelSpec(model="x_a", description="A"))  # type: ignore[arg-type]
