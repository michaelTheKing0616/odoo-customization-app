"""Visual QWeb report designer — block spec ↔ QWeb compiler (CMP-4)."""

from __future__ import annotations

import html
import re
from typing import Any, Literal

from module_generator import ReportSpec

from app.report_export import qweb_arch_to_body_html, template_xml_id_from_key

BlockType = Literal[
    "heading",
    "field",
    "label_field",
    "o2m_table",
    "image",
    "divider",
    "text",
    "page_break",
]

InheritPosition = Literal["inside", "after", "before", "replace"]

BLOCK_PALETTE: list[dict[str, str]] = [
    {"type": "heading", "label": "Heading", "hint": "Section title (H1–H3)"},
    {"type": "field", "label": "Field value", "hint": "t-field on model field"},
    {"type": "label_field", "label": "Label + field", "hint": "Two-column label row"},
    {"type": "o2m_table", "label": "Lines table", "hint": "t-foreach over o2m/m2m lines"},
    {"type": "image", "label": "Image", "hint": "Company logo or record image field"},
    {"type": "divider", "label": "Divider", "hint": "Horizontal rule"},
    {"type": "text", "label": "Free text", "hint": "Static paragraph"},
    {"type": "page_break", "label": "Page break", "hint": "Force new printed page"},
]


def _esc(text: str) -> str:
    return html.escape(text or "")


def _field_expr(field: str | None, *, record_var: str = "doc") -> str:
    path = (field or "display_name").strip() or "display_name"
    if path.startswith(f"{record_var}."):
        return path
    return f"{record_var}.{path}"


def emit_block(block: dict[str, Any], *, record_var: str = "doc") -> str:
    """Render one designer block to QWeb fragment."""
    kind = str(block.get("type") or "text")
    if kind == "heading":
        level = max(1, min(3, int(block.get("level") or 2)))
        text = _esc(str(block.get("text") or "Section"))
        return f"<h{level}>{text}</h{level}>"
    if kind == "field":
        expr = _field_expr(block.get("field"), record_var=record_var)
        return f'<p><span t-field="{expr}"/></p>'
    if kind == "label_field":
        label = _esc(str(block.get("label") or block.get("field") or "Label"))
        expr = _field_expr(block.get("field"), record_var=record_var)
        return (
            f'<div class="row mb-2"><div class="col-3"><strong>{label}</strong></div>'
            f'<div class="col-9"><span t-field="{expr}"/></div></div>'
        )
    if kind == "o2m_table":
        o2m = _field_expr(block.get("o2m_field") or block.get("field"), record_var=record_var)
        line_var = str(block.get("line_var") or "line")
        columns = block.get("columns") or []
        if not isinstance(columns, list) or not columns:
            columns = [{"field": "display_name", "label": "Line"}]
        headers = "".join(
            f"<th>{_esc(str(c.get('label') or c.get('field') or 'Col'))}</th>"
            for c in columns
            if isinstance(c, dict)
        )
        cells = "".join(
            f'<td><span t-field="{line_var}.{c.get("field") or "display_name"}"/></td>'
            for c in columns
            if isinstance(c, dict)
        )
        return (
            f'<table class="table table-sm o_report_table"><thead><tr>{headers}</tr></thead>'
            f'<tbody><tr t-foreach="{o2m}" t-as="{line_var}">{cells}</tr></tbody></table>'
        )
    if kind == "image":
        src = str(block.get("image_src") or block.get("field") or "company_logo")
        if src == "company_logo":
            return (
                '<img t-if="company.logo" '
                't-att-src="image_data_uri(company.logo)" '
                'class="report-logo" style="max-height:48px"/>'
            )
        expr = _field_expr(src, record_var=record_var)
        return f'<img t-if="{expr}" t-field="{expr}" style="max-width:200px"/>'
    if kind == "divider":
        return "<hr/>"
    if kind == "page_break":
        return '<p style="page-break-before: always;"/>'
    # text / default
    text = _esc(str(block.get("text") or ""))
    return f"<p>{text}</p>" if text else "<p/>"


def compile_blocks_inner(
    blocks: list[dict[str, Any]],
    *,
    record_var: str = "doc",
    t_lang: str | None = None,
) -> str:
    body = "\n".join(emit_block(b, record_var=record_var) for b in blocks if isinstance(b, dict))
    if t_lang:
        return f'<t t-lang="{_esc(t_lang)}">\n{body}\n</t>'
    return body


def compile_report_design(spec: dict[str, Any]) -> dict[str, str]:
    """Compile a visual design spec to live QWeb arch + module body_html."""
    report_key = str(spec.get("report_key") or "custom.report_custom")
    blocks = [b for b in (spec.get("blocks") or []) if isinstance(b, dict)]
    use_layout = bool(spec.get("use_external_layout", True))
    t_lang = spec.get("t_lang")
    mode = str(spec.get("mode") or "primary")
    record_var = "doc"

    inner = compile_blocks_inner(blocks, record_var=record_var, t_lang=t_lang if t_lang else None)
    page = f'<div class="page">\n{inner}\n</div>'

    if mode == "inherit":
        inherit = spec.get("inherit") if isinstance(spec.get("inherit"), dict) else {}
        base_key = str(inherit.get("base_report_key") or inherit.get("base_key") or "")
        xpath = str(inherit.get("xpath") or "//div[@class='page']")
        position = str(inherit.get("position") or "inside")
        if not base_key:
            raise ValueError("inherit.base_report_key is required for inherit mode")
        inherit_name = str(spec.get("inherit_template_name") or f"{report_key}_inherit")
        arch = (
            f'<t t-name="{inherit_name}" t-inherit="{base_key}" t-inherit-mode="extension">\n'
            f'  <xpath expr="{xpath}" position="{position}">\n'
            f"    {inner}\n"
            f"  </xpath>\n"
            f"</t>"
        )
    else:
        wrapper = "web.external_layout" if use_layout else "web.html_container"
        arch = (
            f'<t t-name="{report_key}">\n'
            f'  <t t-call="{wrapper}">\n'
            f'    <t t-foreach="docs" t-as="{record_var}">\n'
            f"      {page}\n"
            f"    </t>\n"
            f"  </t>\n"
            f"</t>"
        )

    body_html = qweb_arch_to_body_html(arch)
    return {"arch": arch, "body_html": body_html}


def design_to_module_report(spec: dict[str, Any]) -> dict[str, Any]:
    """Fragment for ModuleSpec merge / export."""
    compiled = compile_report_design(spec)
    model = str(spec.get("model") or "")
    report_key = str(spec.get("report_key") or "custom.report_custom")
    name = str(spec.get("name") or "Custom report")
    template_id = template_xml_id_from_key(report_key, report_id=0)
    report_spec = ReportSpec(
        name=name,
        model=model,
        report_name=report_key,
        template_xml_id=template_id,
        body_html=compiled["body_html"],
        print_report_name=spec.get("print_report_name"),
        t_lang=spec.get("t_lang"),
    )
    return {
        "reports": [
            {
                "name": report_spec.name,
                "model": report_spec.model,
                "report_name": report_spec.report_name,
                "template_xml_id": report_spec.template_xml_id,
                "body_html": report_spec.body_html,
                "print_report_name": report_spec.print_report_name,
                "t_lang": report_spec.t_lang,
            }
        ],
        "review_note": (
            "Report from visual designer — sandbox-render before promote. "
            "t-lang variant: set partner language field on ReportSpec when needed."
        ),
    }


def parse_qweb_anchors(arch: str) -> list[dict[str, str]]:
    """Suggest xpath anchors from an existing QWeb template (inherit picker)."""
    anchors: list[dict[str, str]] = []
    if not arch:
        return anchors
    for match in re.finditer(
        r"<(div|table|h[1-6]|p|span|t)[^>]*>",
        arch,
        flags=re.IGNORECASE,
    ):
        tag = match.group(1).lower()
        snippet = arch[match.start() : match.start() + 80].replace("\n", " ")
        if 'class="' in snippet or "t-field" in snippet or tag == "table":
            expr = f"//{tag}"
            if 'class="' in snippet:
                cls = re.search(r'class="([^"]+)"', snippet)
                if cls:
                    first = cls.group(1).split()[0]
                    expr = f'//{tag}[@class="{first}"]'
            anchors.append({"xpath": expr, "label": snippet[:60]})
        if len(anchors) >= 12:
            break
    if not anchors:
        anchors.append({"xpath": "//div[@class='page']", "label": "Default page container"})
    return anchors
