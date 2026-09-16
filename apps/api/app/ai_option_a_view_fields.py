"""View ↔ Python field consistency for LLM-authored Option A modules.

Catches the OWL killer: form arch references ``markup_percentage`` while the
registry only has ``x_markup_percent`` (or nothing). Fail closed before zip;
sandbox RPC smoke re-checks against ``fields_get`` after install.
"""

from __future__ import annotations

import ast
import re
from typing import Any

# Meta ir.ui.view record fields — not model columns.
_VIEW_META_NAMES = frozenset(
    {
        "model",
        "name",
        "inherit_id",
        "arch",
        "mode",
        "priority",
        "type",
        "groups",
        "key",
        "active",
        "arch_fs",
        "xml_id",
    }
)

# Anchors commonly left in xpath *expr* or rare accidental inserts — not custom.
_STOCK_SAFE: dict[str, frozenset[str]] = {
    "sale.order": frozenset(
        {
            "partner_id",
            "partner_invoice_id",
            "partner_shipping_id",
            "date_order",
            "validity_date",
            "pricelist_id",
            "payment_term_id",
            "order_line",
            "note",
            "client_order_ref",
            "user_id",
            "team_id",
            "company_id",
            "currency_id",
            "tax_totals",
            "amount_total",
            "amount_untaxed",
            "amount_tax",
            "state",
            "invoice_status",
            "fiscal_position_id",
            "warehouse_id",
            "incoterm",
            "require_signature",
            "require_payment",
            "signature",
            "signed_by",
            "signed_on",
            "commitment_date",
            "expected_date",
            "tag_ids",
            "origin",
            "name",
            "display_name",
            "create_date",
            "write_date",
        }
    ),
    "sale.order.line": frozenset(
        {
            "product_id",
            "product_template_id",
            "name",
            "product_uom_qty",
            "product_uom",
            "price_unit",
            "discount",
            "tax_ids",
            "tax_id",
            "price_subtotal",
            "price_total",
            "price_tax",
            "company_id",
            "currency_id",
            "order_id",
            "sequence",
            "display_type",
            "product_packaging_id",
            "customer_lead",
            "qty_delivered",
            "qty_invoiced",
        }
    ),
    "account.move": frozenset(
        {
            "partner_id",
            "invoice_date",
            "invoice_date_due",
            "invoice_line_ids",
            "tax_totals",
            "amount_total",
            "amount_untaxed",
            "amount_tax",
            "currency_id",
            "company_id",
            "state",
            "move_type",
            "name",
            "ref",
            "payment_reference",
            "invoice_payment_term_id",
            "fiscal_position_id",
            "narration",
            "invoice_origin",
        }
    ),
    "stock.picking": frozenset(
        {
            "partner_id",
            "location_id",
            "location_dest_id",
            "move_ids_without_package",
            "move_ids",
            "scheduled_date",
            "date_done",
            "origin",
            "name",
            "state",
            "picking_type_id",
            "company_id",
            "note",
            "owner_id",
        }
    ),
}

_XPATH_BLOCK_RE = re.compile(r"<xpath\b[^>]*>(.*?)</xpath>", re.I | re.S)
_FIELD_NAME_ATTR_RE = re.compile(r"""<field\b[^>]*\bname\s*=\s*["']([^"']+)["']""", re.I)
_MODEL_FIELD_RE = re.compile(
    r"""<field\s+name=["']model["']\s*>([^<]+)</field>""",
    re.I,
)
_INHERIT_REF_RE = re.compile(
    r"""inherit_id=["']([^"']+)["']|ref\(["']([^"']+)["']\)""",
    re.I,
)
# Only scan OWL form/list arches — never security/data record fields (implied_ids, etc.).
_ARCH_BLOB_RE = re.compile(
    r"""<field\s+name=["']arch["'][^>]*>(.*?)</field>""",
    re.I | re.S,
)
_VIEW_RECORD_RE = re.compile(
    r"""<record\b([^>]*)>(.*?)</record>""",
    re.I | re.S,
)
_RECORD_MODEL_ATTR_RE = re.compile(r"""\bmodel\s*=\s*["']([^"']+)["']""", re.I)


def extract_python_fields_by_model(content: str) -> dict[str, set[str]]:
    """Map ``_inherit`` / ``_name`` → field names assigned via ``fields.*``."""
    out: dict[str, set[str]] = {}
    try:
        tree = ast.parse(content or "")
    except SyntaxError:
        return out

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        models: list[str] = []
        fields: set[str] = set()
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
            if not targets:
                continue
            tname = targets[0].id
            val = stmt.value
            if tname in {"_inherit", "_name"}:
                mid = _ast_str(val)
                if mid:
                    models.append(mid)
                elif isinstance(val, (ast.List, ast.Tuple)):
                    for elt in val.elts:
                        s = _ast_str(elt)
                        if s:
                            models.append(s)
                continue
            if _is_fields_call(val):
                fields.add(tname)
        for mid in models:
            out.setdefault(mid, set()).update(fields)
    return out


def _ast_str(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_fields_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "fields"
    return False


def extract_inserted_arch_fields(xml: str) -> list[tuple[str | None, str]]:
    """Return ``(model_hint, field_name)`` for widgets inside ``ir.ui.view`` arches.

    Ignores security/data records (e.g. ``res.groups`` ``implied_ids``) — those are
    not OWL form Field nodes and must not fail the authoring gate.
    """
    blob = xml or ""
    if not blob.strip():
        return []
    # QWeb / report templates are not OWL form Field widgets.
    if "t-name=" in blob or "<t " in blob or "t-call" in blob:
        if "ir.ui.view" not in blob and "xpath" not in blob.lower():
            return []

    pairs: list[tuple[str | None, str]] = []
    for rec_attrs, rec_body in _VIEW_RECORD_RE.findall(blob):
        model_attr = _RECORD_MODEL_ATTR_RE.search(rec_attrs)
        record_model = (model_attr.group(1) if model_attr else "").strip()
        if record_model and record_model != "ir.ui.view":
            continue
        # Records without model= on the tag still may be views if they declare arch.
        arches = _ARCH_BLOB_RE.findall(rec_body)
        if not arches and record_model != "ir.ui.view":
            continue
        if not arches:
            # Bare inherit snippet sometimes puts xpath at record root without arch wrap.
            if "xpath" not in rec_body.lower():
                continue
            arches = [rec_body]
        model_hint = _model_hint_from_view_body(rec_body)
        for arch in arches:
            pairs.extend(_fields_from_arch_blob(arch, model_hint))

    # Snippet-only blocks (no <record>) used in unit tests / thin author output.
    if not pairs and "xpath" in blob.lower():
        model_hint = _model_hint_from_view_body(blob)
        for arch in _ARCH_BLOB_RE.findall(blob) or [blob]:
            pairs.extend(_fields_from_arch_blob(arch, model_hint))
    return pairs


def _model_hint_from_view_body(body: str) -> str | None:
    models = [m.strip() for m in _MODEL_FIELD_RE.findall(body or "") if m.strip()]
    if models:
        return models[0]
    return _model_from_inherit_ref(body or "")


def _fields_from_arch_blob(arch: str, model_hint: str | None) -> list[tuple[str | None, str]]:
    pairs: list[tuple[str | None, str]] = []
    blocks = _XPATH_BLOCK_RE.findall(arch or "")
    sources = blocks if blocks else [arch]
    for block in sources:
        for name in _FIELD_NAME_ATTR_RE.findall(block or ""):
            if name in _VIEW_META_NAMES:
                continue
            pairs.append((model_hint, name))
    return pairs


def _model_from_inherit_ref(blob: str) -> str | None:
    for m in _INHERIT_REF_RE.finditer(blob or ""):
        ref = (m.group(1) or m.group(2) or "").lower()
        if "sale" in ref and "line" in ref:
            return "sale.order.line"
        if "sale" in ref and ("order" in ref or "quotation" in ref):
            return "sale.order"
        if "account" in ref and "move" in ref:
            return "account.move"
        if "stock" in ref and "picking" in ref:
            return "stock.picking"
    return None


def collect_draft_python_fields(draft: dict[str, Any]) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {}
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "")
        kind = str(block.get("kind") or "")
        if not (path.endswith(".py") or kind == "python"):
            continue
        for mid, names in extract_python_fields_by_model(str(block.get("content") or "")).items():
            merged.setdefault(mid, set()).update(names)
    return merged


def collect_draft_arch_fields(draft: dict[str, Any]) -> list[tuple[str, str | None, str]]:
    """``(file, model_hint, field_name)`` from XML/QWeb blocks with xpath inserts."""
    rows: list[tuple[str, str | None, str]] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "views/unknown.xml")
        kind = str(block.get("kind") or "")
        if not (path.endswith(".xml") or kind in {"xml", "qweb"}):
            continue
        norm = path.replace("\\", "/")
        # Security/data XML is not a form arch (unless it somehow embeds ir.ui.view).
        content = str(block.get("content") or "")
        if "/security/" in f"/{norm}" and "ir.ui.view" not in content:
            continue
        for model_hint, fname in extract_inserted_arch_fields(content):
            rows.append((path, model_hint, fname))
    return rows


def _is_stock_safe(model: str | None, fname: str) -> bool:
    if not fname:
        return True
    if model and fname in _STOCK_SAFE.get(model, frozenset()):
        return True
    # Conservative: any model list may include common relational anchors.
    for names in _STOCK_SAFE.values():
        if fname in names:
            return True
    return False


def view_field_consistency_findings(draft: dict[str, Any]) -> list[dict[str, str]]:
    """Blocking findings when arch field names cannot resolve on the authored model."""
    py = collect_draft_python_fields(draft)
    all_py = set()
    for names in py.values():
        all_py.update(names)
    findings: list[dict[str, str]] = []

    # New fields on stock inherits must be x_* (LLM inventions like markup_percentage).
    # Curated gold packs may use a stable module namespace (cbn_* on res.company).
    _gold_ns = ("cbn_",)
    for mid, names in py.items():
        if mid.startswith("x_"):
            continue
        for fname in sorted(names):
            if fname.startswith("x_"):
                continue
            if fname.startswith("_"):
                continue
            if any(fname.startswith(p) for p in _gold_ns):
                continue
            findings.append(
                {
                    "code": "custom_field_not_x_prefix",
                    "message": (
                        f"{mid}.{fname} must be named x_* on a stock inherit "
                        "(OWL + upgrade safety). Rename the Python field and the view."
                    ),
                    "file": "models",
                }
            )

    for path, model_hint, fname in collect_draft_arch_fields(draft):
        if fname in all_py:
            continue
        if model_hint and fname in py.get(model_hint, set()):
            continue
        if fname.startswith("x_"):
            findings.append(
                {
                    "code": "view_field_undefined",
                    "message": (
                        f"View inserts <field name=\"{fname}\"/> but no Python "
                        f"fields.{fname} exists"
                        + (f" on {model_hint}" if model_hint else "")
                        + ". OWL will crash: field is undefined."
                    ),
                    "file": path,
                }
            )
            continue
        if _is_stock_safe(model_hint, fname):
            continue
        # Invented non-x_* custom (e.g. markup_percentage) — the live OWL failure mode.
        hint = ""
        fuzzy = _fuzzy_python_match(fname, all_py | (py.get(model_hint or "", set())))
        if fuzzy:
            hint = f" Did you mean {fuzzy}?"
        findings.append(
            {
                "code": "view_field_undefined",
                "message": (
                    f"View inserts <field name=\"{fname}\"/> which is not defined in "
                    f"authored Python and is not a known stock field"
                    + (f" on {model_hint}" if model_hint else "")
                    + f".{hint} Use an x_* field declared in models/*.py."
                ),
                "file": path,
            }
        )
    return findings


def _norm_field_token(name: str) -> str:
    s = (name or "").lower()
    if s.startswith("x_"):
        s = s[2:]
    s = re.sub(r"[^a-z0-9]", "", s)
    s = s.replace("percentage", "pct").replace("percent", "pct")
    return s


def _fuzzy_python_match(name: str, py_fields: set[str]) -> str | None:
    if not name or not py_fields:
        return None
    if name in py_fields:
        return name
    if f"x_{name}" in py_fields:
        return f"x_{name}"
    bare = name[2:] if name.startswith("x_") else name
    hits = [f for f in py_fields if f == bare or f == f"x_{bare}"]
    if len(hits) == 1:
        return hits[0]
    norm = _norm_field_token(name)
    soft = [f for f in py_fields if _norm_field_token(f) == norm]
    if len(soft) == 1:
        return soft[0]
    # Unique suffix / containment on normalized tokens (markup_percentage ↔ x_markup_percent).
    contained = [
        f
        for f in py_fields
        if norm and (_norm_field_token(f).endswith(norm) or norm.endswith(_norm_field_token(f)))
    ]
    if len(contained) == 1:
        return contained[0]
    return None


def align_xml_field_names_to_python(xml: str, py_fields: set[str]) -> str:
    """Rewrite inserted arch field names to the matching Python x_* when unique."""
    if not xml or not py_fields:
        return xml or ""

    out = xml
    for fname in sorted({m.group(1) for m in _FIELD_NAME_ATTR_RE.finditer(xml)}):
        if fname in _VIEW_META_NAMES or fname in py_fields:
            continue
        if _is_stock_safe(None, fname):
            continue
        target = _fuzzy_python_match(fname, py_fields)
        if not target or target == fname:
            continue
        out = out.replace(f'name="{fname}"', f'name="{target}"')
        out = out.replace(f"name='{fname}'", f"name='{target}'")
    return out


def align_draft_view_fields_to_python(draft: dict[str, Any]) -> int:
    """Free rewrite: map invented view field names onto authored Python x_*."""
    py = collect_draft_python_fields(draft)
    all_py: set[str] = set()
    for names in py.values():
        all_py.update(names)
    if not all_py:
        return 0
    changed = 0
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "")
        kind = str(block.get("kind") or "")
        if not (path.endswith(".xml") or kind in {"xml", "qweb"}):
            continue
        content = str(block.get("content") or "")
        rewritten = align_xml_field_names_to_python(content, all_py)
        if rewritten != content:
            block["content"] = rewritten
            changed += 1
    return changed


def arch_fields_missing_from_registry(
    arch: str,
    fields_get: dict[str, Any] | None,
    *,
    model: str | None = None,
) -> list[str]:
    """Field names in arch that are absent from ``fields_get`` (OWL undefined)."""
    registry = set((fields_get or {}).keys())
    missing: list[str] = []
    for _hint, fname in extract_inserted_arch_fields(arch):
        if fname in registry:
            continue
        if _is_stock_safe(model or _hint, fname):
            # Still fail if fields_get was provided and stock name is truly absent —
            # but stock_safe without registry presence on a weird DB is rare; prefer
            # failing only non-stock / x_*.
            continue
        if fname.startswith("x_") or not _is_stock_safe(model or _hint, fname):
            missing.append(fname)
    return sorted(set(missing))


def files_view_field_findings(files: dict[str, str]) -> list[str]:
    """Structural zip helper — operator-facing strings."""
    draft = {
        "custom_code_blocks": [
            {
                "source_file": path,
                "kind": "python" if path.endswith(".py") else "xml",
                "content": content,
            }
            for path, content in files.items()
        ]
    }
    return [
        f"{row['code']}: {row['message']} [{row.get('file') or ''}]"
        for row in view_field_consistency_findings(draft)
    ]


__all__ = [
    "align_draft_view_fields_to_python",
    "align_xml_field_names_to_python",
    "arch_fields_missing_from_registry",
    "collect_draft_arch_fields",
    "collect_draft_python_fields",
    "extract_inserted_arch_fields",
    "extract_python_fields_by_model",
    "files_view_field_findings",
    "view_field_consistency_findings",
]
