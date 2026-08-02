"""Generate installable Odoo 19 addon zips from project definitions (Phase 5)."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _templates_dir() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in (here / "templates", here.parent.parent / "templates"):
        if candidate.is_dir():
            return candidate
    return here.parent.parent / "templates"


ODOO_FIELD_MAP = {
    "char": "fields.Char",
    "text": "fields.Text",
    "html": "fields.Html",
    "integer": "fields.Integer",
    "float": "fields.Float",
    "boolean": "fields.Boolean",
    "date": "fields.Date",
    "datetime": "fields.Datetime",
    "binary": "fields.Binary",
    "selection": "fields.Selection",
    "many2one": "fields.Many2one",
    "one2many": "fields.One2many",
    "many2many": "fields.Many2many",
    "monetary": "fields.Monetary",
    "related": "fields.Char",
}

# Fields that belong to every model / framework — skip when exporting custom models.
SKIP_FIELD_NAMES = frozenset(
    {
        "id",
        "display_name",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "__last_update",
    }
)

# Fallback map: technical model → Odoo module name for depends inference.
MODEL_TO_MODULE: dict[str, str] = {
    "res.partner": "base",
    "res.users": "base",
    "res.company": "base",
    "mail.thread": "mail",
    "mail.activity.mixin": "mail",
    "sale.order": "sale",
    "sale.order.line": "sale",
    "account.move": "account",
    "account.move.line": "account",
    "product.product": "product",
    "product.template": "product",
    "project.task": "project",
    "crm.lead": "crm",
    "hr.employee": "hr",
    "stock.picking": "stock",
    "purchase.order": "purchase",
}

_XPATH_ROOT_BY_VIEW: dict[str, str] = {
    "form": "//sheet",
    "list": "//list",
    "tree": "//tree",
    "search": "//search",
}


def manifest_version_for_major(major: int) -> str:
    """One zip per connection major — series ``{major}.0.1.0.0`` (not multi-manifest)."""
    if major < 16:
        raise ValueError(f"Unsupported Odoo major for module export: {major}")
    return f"{major}.0.1.0.0"


def list_view_for_major(major: int) -> tuple[str, str]:
    """Return ``(ir.ui.view.type, arch root tag)`` for list views on ``major``.

    Odoo ≤17 stores listing views as ``tree`` / ``<tree>``; 18+ prefers
    ``list`` / ``<list>``. Callers building ModuleSpec views for a known major
    should use this instead of hard-coding ``type="list"``.
    """
    if major < 16:
        raise ValueError(f"Unsupported Odoo major for list views: {major}")
    if major <= 17:
        return ("tree", "tree")
    return ("list", "list")


def _rewrite_list_tree_tags(arch: str, *, root_tag: str) -> str:
    """Rewrite listing root/nested tags between ``list`` and ``tree``."""
    if root_tag == "tree":
        # Prefer list→tree so a second pass is a no-op.
        return (
            arch.replace("<list", "<tree")
            .replace("</list>", "</tree>")
            .replace("<list>", "<tree>")
        )
    return (
        arch.replace("<tree", "<list")
        .replace("</tree>", "</list>")
        .replace("<tree>", "<list>")
    )


def _normalize_view_mode_for_major(view_mode: str, major: int) -> str:
    """Rewrite act_window ``view_mode`` list↔tree for the target major."""
    parts = [p.strip() for p in (view_mode or "").split(",") if p.strip()]
    want_list, _ = list_view_for_major(major)
    if not parts:
        return f"{want_list},form"
    out: list[str] = []
    for p in parts:
        if p in {"list", "tree"}:
            out.append(want_list)
        else:
            out.append(p)
    # Dedupe consecutive duplicates from list/tree collapse
    deduped: list[str] = []
    for p in out:
        if not deduped or deduped[-1] != p:
            deduped.append(p)
    return ",".join(deduped)


def normalize_module_spec_list_views(spec: "ModuleSpec") -> "ModuleSpec":
    """Normalize list/tree view types, arches, and action view_mode for ``spec.odoo_major``.

    No-op when ``odoo_major`` is unset (Library templates stay 19-primary as authored).
    Mutates ``spec`` in place and returns it.
    """
    if spec.odoo_major is None:
        return spec
    major = int(spec.odoo_major)
    list_type, root_tag = list_view_for_major(major)
    for view in spec.views:
        if view.type in {"list", "tree"}:
            view.type = list_type
            if view.arch:
                view.arch = _rewrite_list_tree_tags(view.arch, root_tag=root_tag)
        elif view.arch and ("<list" in view.arch or "<tree" in view.arch):
            # Nested listing arches inside form/kanban (O2M editors, etc.).
            view.arch = _rewrite_list_tree_tags(view.arch, root_tag=root_tag)
    for action in spec.actions:
        action.view_mode = _normalize_view_mode_for_major(action.view_mode, major)
    return spec


def _field_tag(field_name: str, widget: str | None = None) -> str:
    if widget:
        return f'<field name="{field_name}" widget="{widget}"/>'
    return f'<field name="{field_name}"/>'


def render_xpath_field_inject(
    field_name: str, view_type: str, *, widget: str | None = None
) -> str:
    """Return inherit-view arch that injects one field via xpath."""
    expr = _XPATH_ROOT_BY_VIEW.get(view_type, "//sheet")
    tag = _field_tag(field_name, widget)
    return (
        "<data>\n"
        f'  <xpath expr="{expr}" position="inside">\n'
        f"    {tag}\n"
        "  </xpath>\n"
        "</data>"
    )


def render_xpath_fields_inject(
    field_names: list[str],
    view_type: str,
    *,
    widgets: dict[str, str] | None = None,
) -> str:
    """Return inherit-view arch that injects multiple fields via one xpath."""
    expr = _XPATH_ROOT_BY_VIEW.get(view_type, "//sheet")
    widgets = widgets or {}
    lines = [
        "<data>",
        f'  <xpath expr="{expr}" position="inside">',
    ]
    for name in field_names:
        lines.append(f"    {_field_tag(name, widgets.get(name))}")
    lines.extend(["  </xpath>", "</data>"])
    return "\n".join(lines)


@dataclass
class FieldSpec:
    name: str
    ttype: str
    string: str
    required: bool = False
    readonly: bool = False
    relation: str | None = None
    relation_field: str | None = None
    selection: str | None = None  # Python literal e.g. [('a','A')]
    help: str | None = None
    related: str | None = None
    currency_field: str | None = None
    on_delete: str | None = None  # many2one: set null | restrict | cascade

    def odoo_ttype(self) -> str:
        """Concrete Odoo ttype (related is not a real ttype)."""
        if self.ttype == "related":
            return "many2one" if self.relation else "char"
        return self.ttype

    def python_kwargs(self) -> str:
        parts: list[str] = []
        if self.ttype in {"many2one", "many2many"} and self.relation:
            parts.append(f"{self.relation!r}")
        elif self.ttype == "one2many" and self.relation and self.relation_field:
            parts.append(f"{self.relation!r}, {self.relation_field!r}")
        elif self.ttype == "related" and self.relation:
            parts.append(f"{self.relation!r}")

        parts.append(f"string={self.string!r}")
        if self.required:
            parts.append("required=True")
        if self.readonly or self.related:
            parts.append("readonly=True")
        if self.help:
            parts.append(f"help={self.help!r}")
        if self.related:
            parts.append(f"related={self.related!r}")
        if self.ttype == "selection" and self.selection:
            parts.append(f"selection={self.selection}")
        if self.ttype == "monetary" and self.currency_field:
            parts.append(f"currency_field={self.currency_field!r}")
        # Odoo 19: required many2one must not use ondelete='set null'
        if self.ttype == "many2one":
            ondelete = self.on_delete or ("restrict" if self.required else None)
            if ondelete:
                parts.append(f"ondelete={ondelete!r}")
        return ", ".join(parts)

    def python_assignment(self) -> str:
        if self.ttype == "related" and self.relation:
            cls = "fields.Many2one"
        else:
            cls = ODOO_FIELD_MAP.get(self.ttype, "fields.Char")
        return f"    {self.name} = {cls}({self.python_kwargs()})"


@dataclass
class ModelSpec:
    model: str  # x_thing or res.partner when extending
    description: str
    fields: list[FieldSpec] = field(default_factory=list)
    mode: str = "new"  # "new" | "inherit"
    inherit: str | None = None  # technical model to _inherit (e.g. res.partner)
    # Mixins for new models (e.g. mail.thread) — emitted as _inherit list with _name
    mixins: list[str] = field(default_factory=list)
    # Extra indented Python methods/helpers appended after fields in model.py.j2
    extra_python: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"new", "inherit"}:
            raise ValueError("ModelSpec.mode must be 'new' or 'inherit'")
        if self.mode == "inherit" and not self.inherit:
            self.inherit = self.model

    def is_inherit(self) -> bool:
        return self.mode == "inherit"

    def has_mixins(self) -> bool:
        return bool(self.mixins) and not self.is_inherit()

    def class_name(self) -> str:
        cleaned = self.model.replace(".", "_")
        parts = [p.capitalize() for p in cleaned.split("_") if p]
        return "".join(parts) or "XModel"

    def module_basename(self) -> str:
        return self.model.replace(".", "_")

    def model_xml_id(self) -> str:
        return "model_" + self.model.replace(".", "_")


@dataclass
class MailTemplateSpec:
    xml_id: str
    name: str
    model: str
    subject: str
    body_html: str
    email_to: str = "${object.x_member_id.email|safe}"
    description: str | None = None

    def resolved_xml_id(self) -> str:
        slug = re.sub(r"[^a-z0-9_]+", "_", self.xml_id.lower()).strip("_")
        return slug[:50] or "mail_template"


@dataclass
class CronJobSpec:
    xml_id: str
    name: str
    model: str
    code: str
    interval_number: int = 1
    interval_type: str = "days"
    numbercall: int = -1
    active: bool = True
    user_id_xml: str = "base.user_root"

    def resolved_xml_id(self) -> str:
        slug = re.sub(r"[^a-z0-9_]+", "_", self.xml_id.lower()).strip("_")
        return slug[:50] or "ir_cron"


@dataclass
class ViewSpec:
    name: str
    model: str
    type: str
    arch: str
    priority: int = 16
    inherit_xml_id: str | None = None  # e.g. base.view_partner_form
    mode: str = "primary"  # primary | extension

    def __post_init__(self) -> None:
        if self.mode not in {"primary", "extension"}:
            raise ValueError("ViewSpec.mode must be 'primary' or 'extension'")

    def xml_id(self) -> str:
        slug = re.sub(r"[^a-z0-9_]+", "_", self.name.lower()).strip("_")
        return f"view_{slug[:50] or 'custom'}"


@dataclass
class ActionSpec:
    name: str
    model: str
    view_mode: str = "list,form"
    domain: str | None = None
    context: str | None = None
    technical_name: str | None = None

    def xml_id(self) -> str:
        base = self.technical_name or f"action_{self.model}"
        slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_")
        return slug[:50] or "action_custom"


@dataclass
class MenuSpec:
    name: str
    action_xml_id: str | None = None
    parent_xml_id: str | None = None
    sequence: int = 10
    technical_name: str | None = None

    def xml_id(self) -> str:
        base = self.technical_name or self.name
        slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_")
        return f"menu_{slug[:40] or 'custom'}"


@dataclass
class PythonAutomationSpec:
    name: str
    model: str
    trigger: str
    code: str
    filter_domain: str | None = None
    technical_name: str | None = None

    def xml_id(self) -> str:
        base = self.technical_name or self.name
        slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_")
        return f"automation_{slug[:40] or 'custom'}"


@dataclass
class AccessRuleSpec:
    id: str
    name: str
    model: str  # xml id like model_x_thing (no module prefix)
    group: str = "base.group_user"  # xml id
    perm_read: int = 1
    perm_write: int = 1
    perm_create: int = 1
    perm_unlink: int = 1


@dataclass
class RecordRuleSpec:
    name: str
    model_xml_id: str  # model_x_thing
    domain_force: str
    group_xml_ids: list[str] = field(default_factory=list)  # empty = global
    perm_read: bool = True
    perm_write: bool = True
    perm_create: bool = True
    perm_unlink: bool = True
    technical_name: str | None = None

    def xml_id(self) -> str:
        base = self.technical_name or self.name
        slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_")
        return f"rule_{slug[:40] or 'custom'}"


@dataclass
class ReportSpec:
    """QWeb PDF report (ir.actions.report + template)."""

    name: str
    model: str
    report_name: str  # module.template_xml_id without module prefix — set full in template
    template_xml_id: str
    body_html: str  # inner QWeb for one record `o`
    print_report_name: str | None = None
    technical_name: str | None = None

    def action_xml_id(self) -> str:
        base = self.technical_name or self.name
        slug = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_")
        return f"action_report_{slug[:40] or 'custom'}"


@dataclass
class ModuleSpec:
    technical_name: str
    display_name: str
    version: str = "19.0.1.0.0"
    depends: list[str] = field(default_factory=lambda: ["base"])
    author: str = "Odoo Custom"
    # python = filesystem addon (sandbox / local docker); data = Studio-like XML for base_import_module
    install_mode: str = "python"
    # When set, render/zip normalizes list↔tree view types + arches for that major.
    # Library templates leave this unset (19-primary as authored).
    odoo_major: int | None = None
    models: list[ModelSpec] = field(default_factory=list)
    views: list[ViewSpec] = field(default_factory=list)
    actions: list[ActionSpec] = field(default_factory=list)
    menus: list[MenuSpec] = field(default_factory=list)
    python_automations: list[PythonAutomationSpec] = field(default_factory=list)
    access_rules: list[AccessRuleSpec] = field(default_factory=list)
    record_rules: list[RecordRuleSpec] = field(default_factory=list)
    mail_templates: list[MailTemplateSpec] = field(default_factory=list)
    cron_jobs: list[CronJobSpec] = field(default_factory=list)
    reports: list[ReportSpec] = field(default_factory=list)

    def infer_and_merge_depends(
        self,
        extra: list[str] | None = None,
        *,
        model_to_module: dict[str, str] | None = None,
    ) -> list[str]:
        """Infer module depends from inherit targets + relation fields; merge with extras.

        Always keeps ``base`` first. Dedupes preserving order.
        Unknown ``x_*`` peer models (not declared as mode=new here) are skipped.
        """
        mapping = {**MODEL_TO_MODULE, **(model_to_module or {})}
        new_models = {m.model for m in self.models if m.mode == "new"}
        ordered: list[str] = []

        def _add(mod: str | None) -> None:
            if not mod or mod in ordered:
                return
            ordered.append(mod)

        _add("base")
        for dep in self.depends:
            _add(dep)

        def _add_for_model(model_name: str) -> None:
            if model_name in mapping:
                _add(mapping[model_name])
                return
            if model_name.startswith("x_") and model_name not in new_models:
                # Peer custom module — caller must pass explicit depends.
                return

        for model in self.models:
            target = model.inherit if model.mode == "inherit" else None
            if target:
                _add_for_model(target)
            for mixin in model.mixins:
                if mixin.startswith("mail."):
                    _add("mail")
                else:
                    # Other mixin models (e.g. portal.mixin) map via MODEL_TO_MODULE when known
                    _add_for_model(mixin)
            for f in model.fields:
                if f.relation:
                    _add_for_model(f.relation)

        for view in self.views:
            if view.inherit_xml_id and "." in view.inherit_xml_id:
                _add(view.inherit_xml_id.split(".", 1)[0])

        if extra:
            for dep in extra:
                _add(dep)

        if self.python_automations:
            _add("base_automation")
        if self.mail_templates or self.cron_jobs:
            _add("mail")

        self.depends = ordered
        return ordered

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.technical_name):
            raise ValueError("technical_name must be lowercase python-module style")
        if self.install_mode not in {"python", "data"}:
            raise ValueError("install_mode must be 'python' or 'data'")
        if self.install_mode == "data" and self.python_automations:
            raise ValueError(
                "install_mode=data cannot include python_automations (code requires filesystem install)"
            )
        if self.install_mode == "data" and any(m.extra_python for m in self.models):
            raise ValueError(
                "install_mode=data cannot include ModelSpec.extra_python (code requires filesystem install)"
            )
        if self.install_mode == "data" and self.cron_jobs:
            raise ValueError(
                "install_mode=data cannot include cron_jobs that call Python methods"
            )
        for model in self.models:
            if model.mode not in {"new", "inherit"}:
                raise ValueError(f"Invalid ModelSpec.mode {model.mode!r}")
            if model.mode == "inherit" and not (model.inherit or model.model):
                raise ValueError(f"inherit model {model.model!r} requires inherit target")
        for view in self.views:
            if view.mode not in {"primary", "extension"}:
                raise ValueError(f"Invalid ViewSpec.mode {view.mode!r}")
        self.infer_and_merge_depends()

    def ensure_default_menus(self) -> None:
        """Add root menu + per-model act_window/menu when new models exist and menus empty."""
        new_models = [m for m in self.models if m.mode == "new"]
        if not new_models or self.menus or self.actions:
            return
        root = MenuSpec(
            name=self.display_name,
            sequence=10,
            technical_name=f"root_{self.technical_name}",
        )
        self.menus.append(root)
        for i, model in enumerate(new_models):
            action = ActionSpec(
                name=model.description or model.model,
                model=model.model,
                technical_name=f"action_{model.module_basename()}",
            )
            self.actions.append(action)
            self.menus.append(
                MenuSpec(
                    name=model.description or model.model,
                    action_xml_id=action.xml_id(),
                    parent_xml_id=root.xml_id(),
                    sequence=10 + i,
                    technical_name=f"menu_{model.module_basename()}",
                )
            )

def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir())),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["py"] = lambda v: repr(v)
    from xml.sax.saxutils import escape as xml_escape

    def _xml(value: object) -> str:
        if value is None:
            return ""
        return xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})

    env.filters["xml"] = _xml
    return env


def render_module_files(spec: ModuleSpec) -> dict[str, str]:
    normalize_module_spec_list_views(spec)
    spec.validate()
    spec.ensure_default_menus()
    # Default menus may introduce list,form actions — normalize again if major known.
    normalize_module_spec_list_views(spec)
    env = _env()
    root = spec.technical_name
    data_files: list[str] = []

    files: dict[str, str] = {}

    if spec.install_mode == "data":
        files[f"{root}/__init__.py"] = ""
        if spec.models:
            files[f"{root}/data/models.xml"] = env.get_template("models_data.xml.j2").render(
                spec=spec
            )
            data_files.append("data/models.xml")
    elif spec.models:
        files[f"{root}/__init__.py"] = "from . import models\n"
        files[f"{root}/models/__init__.py"] = env.get_template("models_init.py.j2").render(
            spec=spec
        )
        for model in spec.models:
            files[f"{root}/models/{model.module_basename()}.py"] = env.get_template(
                "model.py.j2"
            ).render(model=model)
    else:
        files[f"{root}/__init__.py"] = ""

    if spec.views:
        files[f"{root}/views/views.xml"] = env.get_template("views.xml.j2").render(spec=spec)
        data_files.append("views/views.xml")
    if spec.actions or spec.menus:
        files[f"{root}/views/menus.xml"] = env.get_template("menus.xml.j2").render(spec=spec)
        data_files.append("views/menus.xml")
    if spec.python_automations:
        files[f"{root}/data/automations.xml"] = env.get_template(
            "automations_code.xml.j2"
        ).render(spec=spec)
        data_files.append("data/automations.xml")
    if spec.mail_templates:
        files[f"{root}/data/mail_templates.xml"] = env.get_template(
            "mail_templates.xml.j2"
        ).render(spec=spec)
        data_files.append("data/mail_templates.xml")
    if spec.cron_jobs:
        files[f"{root}/data/reminders.xml"] = env.get_template("reminders.xml.j2").render(
            spec=spec
        )
        data_files.append("data/reminders.xml")
    if spec.reports:
        files[f"{root}/report/reports.xml"] = env.get_template("reports.xml.j2").render(
            spec=spec
        )
        data_files.append("report/reports.xml")

    rules = list(spec.access_rules)
    if not rules:
        for model in spec.models:
            if model.mode != "new":
                # Existing models already have ACL; do not invent model_* xmlids.
                continue
            xmlid = f"access_{model.model.replace('.', '_')}"
            rules.append(
                AccessRuleSpec(
                    id=xmlid,
                    name=f"{model.model}.all",
                    model=model.model_xml_id(),
                )
            )
    if rules:
        access_lines = [
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"
        ]
        for rule in rules:
            access_lines.append(
                f"{rule.id},{rule.name},{rule.model},{rule.group},"
                f"{rule.perm_read},{rule.perm_write},{rule.perm_create},{rule.perm_unlink}"
            )
        files[f"{root}/security/ir.model.access.csv"] = "\n".join(access_lines) + "\n"
        # models.xml must load before access CSV so model_* xmlids exist (data mode)
        if "data/models.xml" in data_files:
            data_files = [
                "data/models.xml",
                "security/ir.model.access.csv",
                *[f for f in data_files if f not in {"data/models.xml"}],
            ]
        else:
            data_files = ["security/ir.model.access.csv", *data_files]

    if spec.record_rules:
        files[f"{root}/security/record_rules.xml"] = env.get_template(
            "record_rules.xml.j2"
        ).render(spec=spec)
        # After access CSV so model xmlids exist
        if "security/ir.model.access.csv" in data_files:
            idx = data_files.index("security/ir.model.access.csv")
            data_files.insert(idx + 1, "security/record_rules.xml")
        elif "data/models.xml" in data_files:
            idx = data_files.index("data/models.xml")
            data_files.insert(idx + 1, "security/record_rules.xml")
        else:
            data_files.insert(0, "security/record_rules.xml")

    # Prefer application=True when we ship a root menu for new custom models
    is_app = bool(any(m.mode == "new" for m in spec.models) and spec.menus)
    files[f"{root}/__manifest__.py"] = env.get_template("manifest.py.j2").render(
        spec=spec, data_files=data_files, application=is_app
    )
    # Sidecar ModuleSpec for Code→UI reverse import (own output = trivial read-back)
    import dataclasses
    import json as _json

    files[f"{root}/.meta.json"] = _json.dumps(
        {
            "format": "odoo_custom_modulespec",
            "version": 1,
            "spec": dataclasses.asdict(spec),
        },
        indent=2,
        default=str,
    )
    return files


def build_module_zip(spec: ModuleSpec, *, odoo_major: int | None = None) -> bytes:
    """Build an installable zip. Optional ``odoo_major`` overrides ``spec.odoo_major``."""
    if odoo_major is not None:
        spec.odoo_major = odoo_major
    files = render_module_files(spec)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def zip_has_python_models(zip_bytes: bytes) -> bool:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return any(
            n.endswith(".py") and "/models/" in n.replace("\\", "/") and not n.endswith("__init__.py")
            for n in zf.namelist()
        )


def zip_technical_name(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if not names:
            raise ValueError("Empty zip")
        return names[0].split("/")[0]


# App wizard templates (imported late so FieldSpec/ModuleSpec are defined)
from .app_templates import (  # noqa: E402
    LIBRARY_FINE_AUTOMATION_CODE,
    library_fines_python_module_spec,
    library_module_spec,
)

__all__ = [
    "FieldSpec",
    "ModelSpec",
    "ViewSpec",
    "ActionSpec",
    "MenuSpec",
    "PythonAutomationSpec",
    "AccessRuleSpec",
    "RecordRuleSpec",
    "ReportSpec",
    "MailTemplateSpec",
    "CronJobSpec",
    "ModuleSpec",
    "manifest_version_for_major",
    "list_view_for_major",
    "normalize_module_spec_list_views",
    "render_xpath_field_inject",
    "render_xpath_fields_inject",
    "render_module_files",
    "build_module_zip",
    "zip_has_python_models",
    "zip_technical_name",
    "library_module_spec",
    "library_fines_python_module_spec",
    "LIBRARY_FINE_AUTOMATION_CODE",
    "MODEL_TO_MODULE",
    "SKIP_FIELD_NAMES",
    "ODOO_FIELD_MAP",
]
