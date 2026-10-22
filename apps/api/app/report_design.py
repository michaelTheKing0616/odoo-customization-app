"""Visual QWeb report designer — block spec ↔ QWeb compiler (CMP-4)."""

from __future__ import annotations

import html
import math
import re
from typing import Any, Literal

from module_generator import ReportSpec

from app.report_export import qweb_arch_to_body_html, template_xml_id_from_key
from app.qweb_unsafe_gate import (
    _BLOCK_QWEB_RE,
    gate_report_arch,
    gate_report_design_spec,
)

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

# PDF-03 slot → single xpath/position (never replace). Keep in sync with
# apps/web/src/components/reports/reportInheritSlots.ts.
INHERIT_SLOT_MAP: dict[str, tuple[str, InheritPosition]] = {
    "header": ("//div[@class='header']", "inside"),
    "before_body": ("//div[@class='page']", "before"),
    "after_body": ("//div[@class='page']", "after"),
    "footer": ("//div[@class='footer']", "inside"),
}

_ROOT_REPLACE_EXPRS = frozenset(
    {
        "/",
        "/*",
        "//",
        "//*",
        "//t",
        "//div[@class='page']",
        '//div[@class="page"]',
        "//div[@class='article']",
        '//div[@class="article"]',
    }
)


def resolve_inherit_anchor(inherit: dict[str, Any]) -> tuple[str, str]:
    """Map slot (preferred) or raw xpath/position to one anchor.

    Inputs: inherit dict from the design spec.
    Outputs: (xpath, position). Slot wins over free-form xpath.
    Side effects: none.
    """
    slot = str(inherit.get("slot") or "").strip()
    if slot in INHERIT_SLOT_MAP:
        xpath, position = INHERIT_SLOT_MAP[slot]
        return xpath, position
    xpath = str(inherit.get("xpath") or "//div[@class='page']")
    position = str(inherit.get("position") or "inside")
    return xpath, position


def refuse_root_replace(xpath: str, position: str) -> None:
    """Raise ValueError for RT-22 root/large replace before compile emits arch."""
    if str(position).strip().lower() != "replace":
        return
    norm = "".join(str(xpath).split())
    if norm in _ROOT_REPLACE_EXPRS or norm in {"//form", "//sheet", "//list", "//tree"}:
        raise ValueError("xpath replaces the root or a large subtree")

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
        return emit_o2m_table(block, record_var=record_var)
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



# --------------------------------------------------------------------------
# Table Inspector (PDF-07) — grounded column presentation for ``o2m_table``.
# Keep in sync with apps/web/src/components/reports/reportTableColumns.ts.
#
# Column schema (all keys optional except ``field``; old specs stay valid):
#   field  — related-model field name (grounded via fields_get)
#   label  — header text (escaped; PDF-05 refuses QWeb-looking text)
#   align  — "left" | "center" | "right"; default left, right for numeric ttype
#   width  — number (percent) | "25%" | "2fr" (fr shares what % leaves)
#   sum    — bool; only numeric related fields (integer/float/monetary)
#   ttype  — schema hint (server re-annotates from fields_get when grounding)
# Block keys: ``totals_row`` (bool), ``totals_label`` (str, default "Total").
#
# Every emitted class/style value comes from a fixed allowlist or a parsed
# number — user strings never reach a style attribute.
# --------------------------------------------------------------------------

TABLE_ALIGNS: tuple[str, ...] = ("left", "center", "right")
NUMERIC_FIELD_TYPES: frozenset[str] = frozenset({"integer", "float", "monetary"})
DEFAULT_TOTALS_LABEL = "Total"
_ALIGN_CLASS = {"center": "text-center", "right": "text-end"}
_FIELD_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WIDTH_PCT_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,4})?)\s*%?$")
_WIDTH_FR_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,4})?)\s*fr$")
_FLOAT_TOTAL_OPTIONS = '{"widget": "float", "precision": 2}'


def is_numeric_field_type(ttype: Any) -> bool:
    """True for fields_get types a totals row may sum (integer/float/monetary)."""
    return str(ttype or "").strip().lower() in NUMERIC_FIELD_TYPES


def column_default_align(ttype: Any) -> str:
    """Right-align numbers when the schema type is known; else left."""
    return "right" if is_numeric_field_type(ttype) else "left"


def resolve_column_align(column: dict[str, Any]) -> str:
    """Explicit valid ``align`` wins; otherwise the type default."""
    raw = str(column.get("align") or "").strip().lower()
    if raw in TABLE_ALIGNS:
        return raw
    return column_default_align(column.get("ttype"))


def parse_column_width(raw: Any) -> tuple[str, float] | None:
    """Parse a width hint into ("pct"|"fr", value) or None (auto).

    Accepts numbers (percent), ``"25"``, ``"25%"``, ``"2fr"``. Anything else —
    including CSS such as ``"10px; color:red"`` — is ignored (auto width).
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        unit, value = "pct", float(raw)
    else:
        text = str(raw).strip().lower()
        if not text:
            return None
        fr = _WIDTH_FR_RE.match(text)
        if fr:
            unit, value = "fr", float(fr.group(1))
        else:
            pct = _WIDTH_PCT_RE.match(text)
            if not pct:
                return None
            unit, value = "pct", float(pct.group(1))
    if not math.isfinite(value) or value <= 0 or value > 100:
        return None
    return unit, value


def resolve_column_widths(columns: list[Any]) -> list[float | None]:
    """Resolve each column to a percentage (or None = auto).

    Percent widths are kept as-is; ``fr`` weights share whatever percent the
    fixed columns leave (``100 - sum(pct)``). If nothing is left, fr columns
    fall back to auto.
    """
    parsed = [
        parse_column_width(c.get("width")) if isinstance(c, dict) else None
        for c in columns
    ]
    pct_total = sum(v for p in parsed if p and p[0] == "pct" for v in (p[1],))
    fr_total = sum(v for p in parsed if p and p[0] == "fr" for v in (p[1],))
    remaining = max(0.0, 100.0 - pct_total)
    out: list[float | None] = []
    for p in parsed:
        if p is None:
            out.append(None)
        elif p[0] == "pct":
            out.append(round(p[1], 2))
        elif remaining > 0 and fr_total > 0:
            out.append(round(remaining * p[1] / fr_total, 2))
        else:
            out.append(None)
    return out


def format_width_pct(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def column_sums(column: dict[str, Any]) -> bool:
    return column.get("sum") is True


def _cell_attrs(align: str, width_pct: float | None) -> str:
    classes: list[str] = []
    styles: list[str] = []
    if align in _ALIGN_CLASS:
        classes.append(_ALIGN_CLASS[align])
        # Inline text-align keeps Bootstrap 4/5 + wkhtmltopdf consistent.
        styles.append(f"text-align: {align};")
    if width_pct is not None:
        styles.append(f"width: {format_width_pct(width_pct)};")
    attrs = ""
    if classes:
        attrs += f' class="{" ".join(classes)}"'
    if styles:
        attrs += f' style="{" ".join(styles)}"'
    return attrs


def _safe_field_path(path: str, *, what: str) -> str:
    if not _FIELD_PATH_RE.match(path):
        raise ValueError(f"invalid {what}: {path!r}")
    return path


def table_columns(block: dict[str, Any]) -> list[dict[str, Any]]:
    columns = block.get("columns") or []
    if not isinstance(columns, list):
        columns = []
    cols = [c for c in columns if isinstance(c, dict)]
    return cols or [{"field": "display_name", "label": "Line"}]


def emit_o2m_table(block: dict[str, Any], *, record_var: str = "doc") -> str:
    """Emit a grounded line table with optional align / width / totals row.

    The totals footer is pure QWeb (``sum(<o2m>.mapped('<field>'))`` through
    ``t-esc`` + float widget) — no server Python, so it renders on Odoo Online.
    """
    o2m_raw = str(block.get("o2m_field") or block.get("field") or "").strip()
    o2m = _field_expr(o2m_raw or None, record_var=record_var)
    _safe_field_path(o2m, what="lines field")
    line_var = str(block.get("line_var") or "line").strip() or "line"
    if not _IDENT_RE.match(line_var) or line_var == record_var:
        raise ValueError(f"invalid line variable: {line_var!r}")
    cols = table_columns(block)
    widths = resolve_column_widths(cols)
    aligns = [resolve_column_align(c) for c in cols]
    fields = [
        _safe_field_path(str(c.get("field") or "display_name").strip() or "display_name",
                         what="column field")
        for c in cols
    ]

    headers = "".join(
        f"<th{_cell_attrs(aligns[i], widths[i])}>"
        f"{_esc(str(c.get('label') or c.get('field') or 'Col'))}</th>"
        for i, c in enumerate(cols)
    )
    cells = "".join(
        f'<td{_cell_attrs(aligns[i], widths[i])}><span t-field="{line_var}.{fields[i]}"/></td>'
        for i in range(len(cols))
    )
    footer = ""
    sum_idx = [i for i, c in enumerate(cols) if column_sums(c)]
    if block.get("totals_row") is True and sum_idx:
        label = str(block.get("totals_label") or "").strip() or DEFAULT_TOTALS_LABEL
        foot_cells: list[str] = []
        for i, c in enumerate(cols):
            attrs = _cell_attrs(aligns[i], None)
            if i in sum_idx:
                expr = f"sum({o2m}.mapped('{fields[i]}'))"
                ttype = str(c.get("ttype") or "").strip().lower()
                opts = "" if ttype == "integer" else f" t-options='{_FLOAT_TOTAL_OPTIONS}'"
                foot_cells.append(f'<td{attrs}><strong t-esc="{expr}"{opts}/></td>')
            elif i == 0:
                foot_cells.append(f"<td{attrs}><strong>{_esc(label)}</strong></td>")
            else:
                foot_cells.append(f"<td{attrs}/>")
        footer = f'<tfoot><tr class="o_report_table_total">{"".join(foot_cells)}</tr></tfoot>'
    return (
        f'<table class="table table-sm o_report_table"><thead><tr>{headers}</tr></thead>'
        f'<tbody><tr t-foreach="{o2m}" t-as="{line_var}">{cells}</tr></tbody>'
        f"{footer}</table>"
    )


def refuse_unsafe_table_text(spec: dict[str, Any]) -> None:
    """PDF-05 extension: ``totals_label`` must not look like QWeb either."""
    for block in spec.get("blocks") or []:
        if not isinstance(block, dict) or block.get("type") != "o2m_table":
            continue
        label = block.get("totals_label")
        if isinstance(label, str) and label and _BLOCK_QWEB_RE.search(label):
            raise ValueError(
                "Unsafe QWeb refused: totals_label must not contain QWeb "
                "directives or template markers"
            )


def annotate_column_types(
    spec: dict[str, Any],
    related_field_types: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Overwrite column ``ttype`` hints with the authoritative fields_get type.

    Inputs: design spec; o2m field → {field: ttype} from the related model.
    Outputs: the same spec with ``blocks`` replaced by annotated copies.
    Side effects: rebinds ``spec["blocks"]`` (request-local spec dict).
    """
    blocks = spec.get("blocks")
    if not isinstance(blocks, list):
        return spec
    out: list[Any] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "o2m_table":
            out.append(block)
            continue
        o2m = _strip_record_prefix(str(block.get("o2m_field") or block.get("field") or ""))
        types = related_field_types.get(o2m) or {}
        cols = block.get("columns")
        if not isinstance(cols, list):
            out.append(block)
            continue
        new_cols = []
        for col in cols:
            if isinstance(col, dict) and str(col.get("field") or "") in types:
                col = {**col, "ttype": types[str(col.get("field"))]}
            new_cols.append(col)
        out.append({**block, "columns": new_cols})
    spec["blocks"] = out
    return spec


_RELATIONAL_LINE_TYPES = frozenset({"one2many", "many2many"})
_SPECIAL_IMAGE_SRCS = frozenset({"company_logo"})


def refuse_empty_design(spec: dict[str, Any]) -> None:
    """Raise when a design has no blocks — empty specs must not create a report."""
    blocks = [b for b in (spec.get("blocks") or []) if isinstance(b, dict)]
    if not blocks:
        raise ValueError("empty design does not create a report")


def _strip_record_prefix(field: str, *, record_var: str = "doc") -> str:
    path = (field or "").strip()
    prefix = f"{record_var}."
    if path.startswith(prefix):
        return path[len(prefix) :]
    return path


def collect_field_tokens(
    blocks: list[dict[str, Any]],
    *,
    record_var: str = "doc",
) -> list[dict[str, str]]:
    """Collect parent- and line-table field tokens from designer blocks.

    Inputs: designer blocks.
    Outputs: dicts with keys ``scope`` (parent|column), ``field``, and optional
    ``o2m_field`` for column tokens. ``company_logo`` image srcs are skipped.
    Side effects: none.
    """
    tokens: list[dict[str, str]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or "")
        if kind in {"field", "label_field"}:
            name = _strip_record_prefix(str(block.get("field") or ""), record_var=record_var)
            if name:
                tokens.append({"scope": "parent", "field": name})
        elif kind == "image":
            src = str(block.get("image_src") or block.get("field") or "").strip()
            if src and src not in _SPECIAL_IMAGE_SRCS:
                name = _strip_record_prefix(src, record_var=record_var)
                if name:
                    tokens.append({"scope": "parent", "field": name})
        elif kind == "o2m_table":
            o2m = _strip_record_prefix(
                str(block.get("o2m_field") or block.get("field") or ""),
                record_var=record_var,
            )
            if o2m:
                tokens.append({"scope": "parent", "field": o2m})
            columns = block.get("columns") or []
            if isinstance(columns, list):
                for col in columns:
                    if not isinstance(col, dict):
                        continue
                    col_field = str(col.get("field") or "").strip()
                    if col_field:
                        tokens.append(
                            {
                                "scope": "column",
                                "field": col_field,
                                "o2m_field": o2m or "",
                            }
                        )
    return tokens


def validate_grounded_fields(
    spec: dict[str, Any],
    *,
    parent_fields: set[str] | frozenset[str],
    related_fields: dict[str, set[str]] | None = None,
    related_field_types: dict[str, dict[str, str]] | None = None,
) -> None:
    """Refuse unknown field tokens before compile writes them into the arch.

    Inputs: design spec; ``parent_fields`` from fields_get/list_fields on the
    bound model; ``related_fields`` maps each o2m/m2m field name to the related
    model's field names. ``related_field_types`` (optional) maps each o2m to
    {field: ttype}; when given, totals (``sum``) columns must be numeric.
    Outputs: none.
    Side effects: raises ValueError when a token is missing from the schema or
    a totals column is not integer/float/monetary.
    """
    blocks = [b for b in (spec.get("blocks") or []) if isinstance(b, dict)]
    related = related_fields or {}
    for token in collect_field_tokens(blocks):
        name = token["field"]
        if token["scope"] == "parent":
            if name not in parent_fields:
                raise ValueError(f"unknown field on model: {name}")
            continue
        o2m = token.get("o2m_field") or ""
        allowed = related.get(o2m)
        if allowed is None:
            raise ValueError(
                f"unknown related model for line table field {o2m!r}; "
                f"column {name!r} refused"
            )
        if name not in allowed:
            raise ValueError(
                f"unknown field on related model for {o2m}: {name}"
            )
    if related_field_types is None:
        return
    for block in blocks:
        if block.get("type") != "o2m_table":
            continue
        o2m = _strip_record_prefix(str(block.get("o2m_field") or block.get("field") or ""))
        types = related_field_types.get(o2m) or {}
        for col in block.get("columns") or []:
            if not isinstance(col, dict) or not column_sums(col):
                continue
            name = str(col.get("field") or "").strip()
            ttype = types.get(name)
            if not is_numeric_field_type(ttype):
                raise ValueError(
                    f"totals row can only sum numeric fields; "
                    f"{o2m}.{name} is {ttype or 'unknown'}"
                )


def relational_line_fields(
    parent_field_meta: list[dict[str, Any]] | list[Any],
) -> dict[str, str]:
    """Map o2m/m2m field name → comodel from list_fields / fields_get rows.

    Inputs: field metadata rows with ``name``, ``ttype``/``type``, ``relation``.
    Outputs: mapping used to load related-model fields for line tables.
    Side effects: none.
    """
    out: dict[str, str] = {}
    for row in parent_field_meta:
        if isinstance(row, dict):
            name = str(row.get("name") or "").strip()
            ttype = str(row.get("ttype") or row.get("type") or "").strip()
            relation = row.get("relation")
        else:
            name = str(getattr(row, "name", "") or "").strip()
            ttype = str(getattr(row, "ttype", getattr(row, "type", "")) or "").strip()
            relation = getattr(row, "relation", None)
        if name and ttype in _RELATIONAL_LINE_TYPES and relation:
            out[name] = str(relation)
    return out


def ground_design_against_schema(
    spec: dict[str, Any],
    *,
    parent_field_names: set[str] | frozenset[str],
    related_field_names: dict[str, set[str]] | None = None,
    require_blocks: bool = False,
    related_field_types: dict[str, dict[str, str]] | None = None,
) -> None:
    """Run empty-spec + field grounding gates used by create/compile/save.

    Inputs: design spec and schema name sets (from model_exists + fields_get).
    Outputs: none.
    Side effects: raises ValueError on empty (when required) or unknown fields.
    """
    if require_blocks:
        refuse_empty_design(spec)
    validate_grounded_fields(
        spec,
        parent_fields=set(parent_field_names),
        related_fields=related_field_names,
        related_field_types=related_field_types,
    )


def compile_report_design(spec: dict[str, Any]) -> dict[str, str]:
    """Compile a visual design spec to live QWeb arch + module body_html.

    PDF-05: refuses unsafe block text before emit and gates the resulting arch
    (t-raw / script / XXE / non-allowlisted t-call) before return.
    """
    gate_report_design_spec(spec)
    refuse_unsafe_table_text(spec)
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
        if not base_key:
            raise ValueError("inherit.base_report_key is required for inherit mode")
        known_keys = inherit.get("available_report_keys") or spec.get("available_report_keys")
        if isinstance(known_keys, list) and known_keys:
            allowed = {str(k).strip() for k in known_keys if str(k).strip()}
            if base_key not in allowed:
                raise ValueError(f"base report key does not exist: {base_key}")
        xpath, position = resolve_inherit_anchor(inherit)
        refuse_root_replace(xpath, position)
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

    gate_report_arch(arch)
    body_html = qweb_arch_to_body_html(arch)
    return {"arch": arch, "body_html": body_html}


def design_to_module_report(spec: dict[str, Any]) -> dict[str, Any]:
    """Fragment for app plan merge / export."""
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
            "Report from visual designer — sandbox-render before publish. "
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
