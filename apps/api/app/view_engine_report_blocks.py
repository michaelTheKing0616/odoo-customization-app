"""Report and email designer, stage 2b: blocks anywhere, line tables with totals,
conditional blocks, QR/barcode/signature/watermark/page breaks, page checks,
before/after compare, starter gallery and email bodies built from the same blocks.

Pure code. Every emitted attribute is fixed or built from a validated field path;
user text is escaped and refused when it looks like QWeb.
"""

from __future__ import annotations

import html
import io
import re
import xml.etree.ElementTree as ET
from typing import Any

from app.qweb_unsafe_gate import _BLOCK_QWEB_RE, gate_report_arch
from app.report_design import emit_o2m_table
from app.view_engine import LAYER_PREFIX, EngineError

BLOCK_TYPES = frozenset({"text", "heading", "field", "label_field", "divider", "spacer", "line_table", "qr", "barcode",
                         "signature", "image_field", "watermark", "page_break"})
EMAIL_BLOCK_TYPES = frozenset({"text", "heading", "field", "label_field", "divider", "spacer", "line_table", "image_field"})
FIELD_PATH_RE = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*){0,2}$")
NUMERIC = frozenset({"integer", "float", "monetary"})
WATERMARK_COLOURS = {"red": "rgba(200,0,0,0.14)", "grey": "rgba(0,0,0,0.10)", "blue": "rgba(0,60,200,0.12)", "green": "rgba(0,140,60,0.12)"}
SPACER_MM = {"small": 4, "medium": 8, "large": 16}
BLOCK_CLASS = f"{LAYER_PREFIX}_block"
MAX_PLACEMENTS = 12
MAX_BLOCKS = 40
EMAIL_MARK = "data-ingenium-block"

# ----------------------------------------------------------------------------
# Places to add content: anywhere with a stable locator in the document template
# ----------------------------------------------------------------------------

_SLOT_TAGS = frozenset({"div", "table", "p", "section", "h1", "h2", "h3", "h4", "address", "span", "strong"})


def _human(text: str) -> str:
    return re.sub(r"[_\-.]+", " ", text).strip().capitalize()


def slots_anywhere(doc_arch: str, fields: dict[str, Any] | None = None, var: str = "o") -> list[dict[str, Any]]:
    """Plain-named places resolved against the real template: top/bottom of the
    page, plus before/after every element Odoo can find by a fixed name, id,
    field or unique class (never inside a per-line loop)."""
    fields = fields or {}
    try:
        root = ET.fromstring(doc_arch)
    except ET.ParseError:
        return []
    parents = {c: p for p in root.iter() for c in p}
    pages = [el for el in root.iter() if el.tag == "div" and "page" in (el.get("class") or "").split()]
    out: list[dict[str, Any]] = []
    if len(pages) == 1:
        expr = "//div[hasclass('page')]"
        out += [{"id": "top", "label": "Top of the document", "xpath": expr, "position": "before"},
                {"id": "bottom", "label": "Bottom of the document", "xpath": expr, "position": "inside"}]

    def in_loop(el: ET.Element) -> bool:
        cur = el
        while cur is not None:
            if cur.get("t-foreach"):
                return True
            cur = parents.get(cur)
        return False

    def conditional(el: ET.Element) -> bool:
        cur = el
        while cur is not None and cur is not root:
            if any(cur.get(a) is not None for a in ("t-if", "t-elif", "t-else")):
                return True
            cur = parents.get(cur)
        return False

    seen: set[str] = set()
    found: list[dict[str, Any]] = []
    all_els = list(root.iter())
    for el in all_els:
        if not isinstance(el.tag, str) or el.tag not in _SLOT_TAGS or el is root or in_loop(el):
            continue
        cand: tuple[str, str] | None = None
        if el.get("id") and re.fullmatch(r"[\w\-]{1,60}", el.get("id") or ""):
            cand = (f"//{el.tag}[@id='{el.get('id')}']", _human(el.get("id") or ""))
        elif el.get("name") and re.fullmatch(r"[\w\-]{1,60}", el.get("name") or ""):
            cand = (f"//{el.tag}[@name='{el.get('name')}']", _human(el.get("name") or ""))
        elif el.get("t-field") and re.fullmatch(rf"{var}\.[a-z_][a-z0-9_.]*", el.get("t-field") or ""):
            path = (el.get("t-field") or "").split(".", 1)[1]
            label = str((fields.get(path.split(".")[0]) or {}).get("string") or _human(path))
            cand = (f"//{el.tag}[@t-field='{el.get('t-field')}']", label)
        elif el.tag == "table":
            for cls in (el.get("class") or "").split():
                if cls.startswith("o_") and sum(1 for e in all_els if e.tag == "table" and cls in (e.get("class") or "").split()) == 1:
                    cand = (f"//table[hasclass('{cls}')]", "Lines table" if "main" in cls or "lines" in cls else _human(cls))
                    break
        if not cand:
            continue
        expr, label = cand
        if expr in seen:
            continue
        # unique in this template
        attr_m = re.search(r"\[@([\w-]+)='([^']+)'\]", expr)
        if attr_m and sum(1 for e in all_els if e.tag == el.tag and e.get(attr_m.group(1)) == attr_m.group(2)) != 1:
            continue
        seen.add(expr)
        key = re.sub(r"[^a-z0-9]+", "_", expr.lower()).strip("_")[:60]
        cond = conditional(el)
        note = " (only on some documents)" if cond else ""
        for pos in ("before", "after"):
            slot: dict[str, Any] = {"id": f"{pos}_{key}", "label": f"{pos.capitalize()} '{label}'{note}", "xpath": expr, "position": pos}
            if cond:
                slot["conditional"] = True
            found.append(slot)
    # Places that always print come first; ones inside Odoo's own conditions are marked.
    found.sort(key=lambda s: bool(s.get("conditional")))
    return out + found[: max(0, 80 - len(out))]


# ----------------------------------------------------------------------------
# Conditions (only print a block when...)
# ----------------------------------------------------------------------------

def _py(v: Any) -> str:
    return repr(v) if not isinstance(v, list) else "[" + ", ".join(_py(x) for x in v) + "]"


def condition_expr(cond: dict[str, Any], fields: dict[str, Any], var: str) -> str:
    """Validated tree (view_engine_logic.validate_condition) -> QWeb t-if on the record."""
    parts: list[str] = []
    for r in cond["rules"]:
        f, op, v = r["field"], r["op"], r.get("value")
        t = (fields.get(f) or {}).get("type")
        ref = f"{var}.{f}"
        if t in {"date", "datetime"} and op not in {"set", "not_set", "is_true", "is_false"}:
            raise EngineError("Print rules can check whether a date is filled in, not compare dates yet.")
        if t in {"many2many", "one2many"} and op not in {"set", "not_set"}:
            raise EngineError("Print rules can check whether lines exist, not compare them.")
        if t == "many2one" and op not in {"set", "not_set", "is_true", "is_false"}:
            ref = f"{var}.{f}.id"
        if op in {"is_true", "set"}:
            parts.append(ref)
        elif op in {"is_false", "not_set"}:
            parts.append(f"not {ref}")
        elif op == "is":
            parts.append(f"{ref} == {_py(v)}")
        elif op == "is_not":
            parts.append(f"{ref} != {_py(v)}")
        elif op == "in":
            parts.append(f"{ref} in {_py(list(v))}")
        elif op == "not_in":
            parts.append(f"{ref} not in {_py(list(v))}")
        elif op == "contains":
            parts.append(f"{_py(v)} in ({ref} or '')")
        else:
            sym = {"eq": "==", "ne": "!=", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}[op]
            parts.append(f"{ref} {sym} {_py(v)}")
    joiner = " or " if cond.get("match") == "any" else " and "
    return joiner.join(f"({p})" for p in parts) if len(parts) > 1 else parts[0]


# ----------------------------------------------------------------------------
# Blocks
# ----------------------------------------------------------------------------

def _text(raw: Any, what: str, limit: int = 500) -> str:
    text = str(raw or "").strip()
    if not text or len(text) > limit:
        raise EngineError(f"{what} needs 1 to {limit} characters.")
    if _BLOCK_QWEB_RE.search(text):
        raise EngineError("Text can't contain template code.")
    return text


def _path(raw: Any, fields: dict[str, Any], types: set[str] | None = None) -> str:
    path = str(raw or "").strip()
    head = path.split(".")[0]
    if not FIELD_PATH_RE.match(path) or head not in fields:
        raise EngineError(f"There is no field called '{path}' on this record type.")
    if types is not None and "." not in path and (fields[head].get("type") not in types):
        raise EngineError(f"'{fields[head].get('string') or head}' can't be used for this block.")
    return path


def validate_blocks(blocks: Any, fields: dict[str, Any], related: dict[str, dict[str, Any]] | None = None,
                    *, email: bool = False, record_names: dict[str, dict[int, str]] | None = None) -> list[dict[str, Any]]:
    from app import view_engine_logic as vl

    if not isinstance(blocks, list) or not blocks:
        raise EngineError("Add at least one block.")
    if len(blocks) > MAX_BLOCKS:
        raise EngineError("Too many blocks in one place.")
    allowed = EMAIL_BLOCK_TYPES if email else BLOCK_TYPES
    related = related or {}
    clean: list[dict[str, Any]] = []
    for raw in blocks:
        if not isinstance(raw, dict):
            raise EngineError("A block couldn't be read.")
        kind = str(raw.get("type") or "")
        if kind not in allowed:
            raise EngineError(f"'{kind}' blocks aren't available {'in emails' if email else 'here'}.")
        b: dict[str, Any] = {"type": kind}
        if kind in {"text", "heading"}:
            b["text"] = _text(raw.get("text"), "Text")
            if kind == "heading":
                b["level"] = max(1, min(4, int(raw.get("level") or 3)))
        elif kind in {"field", "label_field"}:
            b["field"] = _path(raw.get("field"), fields)
            if kind == "label_field":
                head = b["field"].split(".")[0]
                b["label"] = _text(raw.get("label") or fields[head].get("string") or head, "Label", 80)
        elif kind == "spacer":
            b["size"] = raw.get("size") if raw.get("size") in SPACER_MM else "medium"
        elif kind == "line_table":
            o2m = _path(raw.get("field"), fields, {"one2many", "many2many"})
            sub = related.get(o2m)
            if sub is None:
                raise EngineError("Load the line fields first.")
            cols_in = raw.get("columns") or []
            if not isinstance(cols_in, list) or not cols_in or len(cols_in) > 10:
                raise EngineError("Pick 1 to 10 columns for the lines table.")
            cols = []
            for c in cols_in:
                if not isinstance(c, dict):
                    raise EngineError("A column couldn't be read.")
                cf = str(c.get("field") or "")
                if cf not in sub or not FIELD_PATH_RE.match(cf):
                    raise EngineError(f"The lines don't have a field called '{cf}'.")
                ttype = sub[cf].get("type")
                total = bool(c.get("sum"))
                if total and ttype not in NUMERIC:
                    raise EngineError("Only number columns can show a total.")
                col = {"field": cf, "label": _text(c.get("label") or sub[cf].get("string") or cf, "Column title", 60), "ttype": ttype, "sum": total}
                if c.get("align") in {"left", "center", "right"}:
                    col["align"] = c["align"]
                cols.append(col)
            b.update({"field": o2m, "columns": cols, "totals_row": any(c["sum"] for c in cols)})
            if raw.get("totals_label"):
                b["totals_label"] = _text(raw.get("totals_label"), "Totals label", 40)
        elif kind in {"qr", "barcode"}:
            b["field"] = _path(raw.get("field"), fields, {"char"})
        elif kind in {"signature", "image_field"}:
            b["field"] = _path(raw.get("field"), fields, {"binary", "image"})
            if kind == "signature":
                b["label"] = _text(raw.get("label") or "Signature", "Label", 60)
                if raw.get("signed_by"):
                    b["signed_by"] = _path(raw.get("signed_by"), fields, {"char"})
        elif kind == "watermark":
            b["text"] = _text(raw.get("text"), "Watermark", 30)
            b["colour"] = raw.get("colour") if raw.get("colour") in WATERMARK_COLOURS else "grey"
        if raw.get("condition"):
            cond = vl.validate_condition(raw["condition"], fields, record_names=record_names)
            b["condition"] = cond
            condition_expr(cond, fields, "o")  # refuse unsupported comparisons now
        clean.append(b)
    return clean


def emit(block: dict[str, Any], var: str, fields: dict[str, Any], *, email: bool = False) -> str:
    kind = block["type"]
    esc = html.escape
    if kind == "heading":
        n = block.get("level", 3)
        out = f"<h{n}>{esc(block['text'])}</h{n}>"
    elif kind == "text":
        out = f"<p>{esc(block['text'])}</p>"
    elif kind == "field":
        out = f'<p><span t-field="{var}.{block["field"]}"/></p>'
    elif kind == "label_field":
        out = f'<p><strong>{esc(block["label"])}:</strong> <span t-field="{var}.{block["field"]}"/></p>'
    elif kind == "divider":
        out = "<hr/>"
    elif kind == "spacer":
        out = f'<div style="height:{SPACER_MM[block["size"]]}mm;"/>'
    elif kind == "line_table":
        out = emit_o2m_table({"o2m_field": block["field"], "columns": block["columns"], "totals_row": block.get("totals_row"),
                              "totals_label": block.get("totals_label") or "Total"}, record_var=var)
        if email:
            out = out.replace('class="table table-sm o_report_table"', 'style="border-collapse:collapse;width:100%;" cellpadding="4"')
    elif kind in {"qr", "barcode"}:
        sym, w, h, style = ("QR", 150, 150, "width:30mm;height:30mm;") if kind == "qr" else ("Code128", 600, 100, "width:70mm;height:12mm;")
        f = f"{var}.{block['field']}"
        out = (f'<div t-if="{f}" t-field="{f}" '
               f"t-options=\"{{'widget': 'barcode', 'symbology': '{sym}', 'width': {w}, 'height': {h}, 'img_style': '{style}'}}\"/>")
    elif kind in {"signature", "image_field"}:
        f = f"{var}.{block['field']}"
        img = f'<img t-if="{f}" t-att-src="image_data_uri({f})" style="max-height:30mm;max-width:70mm;"/>'
        if kind == "image_field":
            out = f"<div>{img}</div>"
        else:
            by = f' <span t-field="{var}.{block["signed_by"]}"/>' if block.get("signed_by") else ""
            out = (f'<div style="margin-top:6mm;">{img}<div style="border-top:1px solid #333;width:70mm;padding-top:1mm;">'
                   f"{esc(block['label'])}{by}</div></div>")
    elif kind == "watermark":
        out = (f'<div style="position:absolute;top:38%;left:8%;width:84%;text-align:center;font-size:96px;font-weight:bold;'
               f"color:{WATERMARK_COLOURS[block['colour']]};-webkit-transform:rotate(-30deg);transform:rotate(-30deg);"
               f'z-index:-1;">{esc(block["text"])}</div>')
    elif kind == "page_break":
        out = '<div style="page-break-before:always;"/>'
    else:  # pragma: no cover - validated earlier
        raise EngineError(f"Unknown block '{kind}'.")
    if block.get("condition"):
        out = f'<t t-if="{html.escape(condition_expr(block["condition"], fields, var), quote=True)}">{out}</t>'
    return out


def validate_placements(placements: Any, slots: list[dict[str, str]], fields: dict[str, Any],
                        related: dict[str, dict[str, Any]] | None = None, **kw: Any) -> list[dict[str, Any]]:
    if not isinstance(placements, list):
        raise EngineError("The layout couldn't be read.")
    if len(placements) > MAX_PLACEMENTS:
        raise EngineError("Too many places at once. Publish what you have, then continue.")
    by_id = {s["id"]: s for s in slots}
    out = []
    total = 0
    for p in placements:
        if not isinstance(p, dict) or p.get("slot") not in by_id:
            raise EngineError("A place you picked isn't on this layout any more. Reload and pick it again.")
        blocks = validate_blocks(p.get("blocks"), fields, related, **kw)
        total += len(blocks)
        out.append({"slot": p["slot"], "blocks": blocks})
    if total > MAX_BLOCKS:
        raise EngineError("Too many blocks at once.")
    return out


def compile_layer(placements: list[dict[str, Any]], slots: list[dict[str, str]], var: str, fields: dict[str, Any],
                  *, token: str | None = None, hide_published: list[str] | None = None) -> str:
    """One QWeb extension (xpath only). Each place gets its own marked wrapper so a
    draft can hide exactly the published ones. With ``token`` everything only
    renders for the request carrying that draft token."""
    by_id = {s["id"]: s for s in slots}
    parts: list[str] = []
    if token is not None:
        if not re.fullmatch(r"[0-9a-f]{8,32}", token):
            raise EngineError("Draft token is not valid.")
        for cls in hide_published or []:
            parts.append(f"<xpath expr=\"//div[hasclass('{cls}')]\" position=\"attributes\">"
                         f"<attribute name=\"t-if\">{var}.env.context.get('ingenium_draft') != '{token}'</attribute></xpath>")
    for i, p in enumerate(placements, start=1):
        slot = by_id[p["slot"]]
        inner = "".join(emit(b, var, fields) for b in p["blocks"])
        if token is None:
            wrapper = f'<div class="{BLOCK_CLASS} {BLOCK_CLASS}_{i}">{inner}</div>'
        else:
            wrapper = f'<div class="{LAYER_PREFIX}_draft" t-if="{var}.env.context.get(\'ingenium_draft\') == \'{token}\'">{inner}</div>'
        parts.append(f'<xpath expr="{slot["xpath"]}" position="{slot["position"]}">{wrapper}</xpath>')
    arch = "<data>" + "".join(parts) + "</data>"
    try:
        ET.fromstring(arch)
    except ET.ParseError as exc:
        raise EngineError("The layout couldn't be built.") from exc
    try:
        gate_report_arch(arch)
    except ValueError as exc:
        raise EngineError(str(exc)) from exc
    if token is None and not placements:
        raise EngineError("There's nothing to publish.")
    return arch


def published_markers(layer_arch: str | None) -> list[str]:
    """Wrapper classes a draft must hide (stage 1 layers had one unnumbered wrapper)."""
    if not layer_arch:
        return []
    numbered = sorted(set(re.findall(rf"\b({BLOCK_CLASS}_\d+)\b", layer_arch)))
    if numbered:
        return numbered
    return [BLOCK_CLASS] if BLOCK_CLASS in layer_arch else []


def expected_texts(placements: list[dict[str, Any]]) -> list[str]:
    out = []
    for p in placements:
        for b in p["blocks"]:
            if b["type"] in {"text", "heading"} and not b.get("condition"):
                out.append(html.escape(b["text"], quote=False))
            if b["type"] == "line_table":
                out += [html.escape(c["label"], quote=False) for c in b["columns"]]
    return out


# ----------------------------------------------------------------------------
# Emails: same blocks inside a template copy's body
# ----------------------------------------------------------------------------

EMAIL_SLOTS = [{"id": "top", "label": "Top of the email", "xpath": "", "position": "top"},
               {"id": "bottom", "label": "Bottom of the email", "xpath": "", "position": "bottom"}]

_EMAIL_BLOCK_RE = re.compile(rf'<div {EMAIL_MARK}="[^"]*"[^>]*>.*?<!--/ingenium-->\s*</div>', re.S)


def strip_email_blocks(body: str) -> str:
    return _EMAIL_BLOCK_RE.sub("", body or "")


AI_MARK_STYLE = "outline:2px dashed #0f766e;outline-offset:3px;"  # teal accent; preview only, never saved


def email_body(body: str, placements: list[dict[str, Any]], fields: dict[str, Any],
               highlight: set[tuple[str, int]] | None = None) -> str:
    """Body with our blocks (marked, so they can be replaced later) at the top or bottom.
    Odoo's own text is kept as is."""
    base = strip_email_blocks(body or "")
    top, bottom = [], []
    for p in placements:
        inner = "".join(
            (f'<div data-ingenium-ai="1" title="Changed by Edit with AI" style="{AI_MARK_STYLE}">{emit(b, "object", fields, email=True)}</div>'
             if highlight and (p["slot"], i) in highlight else emit(b, "object", fields, email=True))
            for i, b in enumerate(p["blocks"]))
        chunk = f'<div {EMAIL_MARK}="{p["slot"]}" style="margin:0 0 12px 0;">{inner}<!--/ingenium--></div>'
        # Only our blocks are gated: Odoo's own template text legitimately uses t-out.
        try:
            gate_report_arch(chunk)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc
        (top if p["slot"] == "top" else bottom).append(chunk)
    m = re.match(r"\s*(<div[^>]*>)(.*)(</div>)\s*$", base, re.S)
    if m:
        return m.group(1) + "".join(top) + m.group(2) + "".join(bottom) + m.group(3)
    return "<div>" + "".join(top) + base + "".join(bottom) + "</div>"


# ----------------------------------------------------------------------------
# Page checks and compare (pypdf; no system tools needed)
# ----------------------------------------------------------------------------

def pdf_pages_text(pdf: bytes) -> list[dict[str, Any]]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    pages = []
    for page in reader.pages:
        width = float(page.mediabox.width)
        runs: list[tuple[str, float, float]] = []

        def visit(text: str, cm: Any, tm: Any, font_dict: Any, font_size: float, _runs: list = runs) -> None:
            if text and text.strip():
                x = float(tm[4]) * float(cm[0]) + float(cm[4])
                scale = abs(float(tm[0]) * float(cm[0])) or 1.0
                _runs.append((text, x, float(font_size or 10) * scale))

        text = page.extract_text(visitor_text=visit) or ""
        images = []
        try:
            images = [len(img.data) for img in page.images]
        except Exception:  # noqa: BLE001
            images = []
        pages.append({"text": text, "width": width, "runs": runs, "images": images})
    return pages


def page_checks(pdf: bytes, *, line_markers: list[str] | None = None, published_pages: int | None = None,
                max_image_bytes: int = 2 * 1024 * 1024) -> list[dict[str, Any]]:
    pages = pdf_pages_text(pdf)
    issues: list[dict[str, Any]] = []
    for i, p in enumerate(pages, start=1):
        for text, x, size in p["runs"]:
            right = x + len(text.rstrip()) * size * 0.5
            if x > p["width"] - 4 or right > p["width"] + 6:
                issues.append({"kind": "overflow", "level": "warning", "page": i,
                               "text": f"Text runs past the right edge on page {i} (\u201c{text.strip()[:30]}\u201d)."})
                break
        for size in p["images"]:
            if size > max_image_bytes:
                issues.append({"kind": "image", "level": "warning", "page": i,
                               "text": f"A picture on page {i} is {size // (1024 * 1024)} MB. Big pictures slow printing and emailing."})
    markers = [m for m in (line_markers or []) if m]
    if markers:
        hit_pages = [i for i, p in enumerate(pages, start=1) if any(m in p["text"] for m in markers)]
        if len(hit_pages) > 1:
            issues.append({"kind": "split", "level": "info", "page": hit_pages[1],
                           "text": f"The lines run over {len(hit_pages)} pages (from page {hit_pages[0]} to {hit_pages[-1]}). Check totals land where you expect."})
    if published_pages is not None and len(pages) != published_pages:
        issues.append({"kind": "pages", "level": "info", "page": None,
                       "text": f"This changes the page count from {published_pages} to {len(pages)}."})
    return issues


VISUAL_MAX_PAGES = 6


def _page_images(pdf: bytes, scale: float, max_pages: int) -> tuple[list[Any], int]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        total = len(doc)
        return [doc[i].render(scale=scale).to_pil().convert("L") for i in range(min(total, max_pages))], total
    finally:
        doc.close()


def _png_b64(img: Any) -> str:
    import base64

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def _where(top: float, bottom: float) -> str:
    mid = (top + bottom) / 2
    return "near the top" if mid < 0.33 else ("in the middle" if mid < 0.66 else "near the bottom")


def visual_compare(before: bytes, after: bytes, *, scale: float = 0.9, max_pages: int = VISUAL_MAX_PAGES) -> dict[str, Any]:
    """Page pictures of the published print and the draft, plus an overlay: the draft faded,
    what's new in green and what's gone in red. Pure pixels (pypdfium2 + Pillow), no system tools."""
    from PIL import Image, ImageChops, ImageFilter

    b_imgs, b_total = _page_images(before, scale, max_pages)
    a_imgs, a_total = _page_images(after, scale, max_pages)
    pages: list[dict[str, Any]] = []
    for i in range(max(len(b_imgs), len(a_imgs))):
        ref = (a_imgs[i] if i < len(a_imgs) else b_imgs[i])
        blank = Image.new("L", ref.size, 255)
        bi = b_imgs[i] if i < len(b_imgs) else blank
        ai = a_imgs[i] if i < len(a_imgs) else blank
        if bi.size != ai.size:
            bi = bi.resize(ai.size)
        # ink = dark pixels; added = ink only in the draft, removed = ink only in the published print
        b_ink = bi.point(lambda v: 255 if v < 160 else 0)
        a_ink = ai.point(lambda v: 255 if v < 160 else 0)
        added = ImageChops.subtract(a_ink, b_ink).filter(ImageFilter.MaxFilter(3))
        removed = ImageChops.subtract(b_ink, a_ink).filter(ImageFilter.MaxFilter(3))
        changed = ImageChops.lighter(added, removed)
        hist = changed.histogram()
        n_changed = sum(hist[128:])
        ratio = n_changed / float(changed.size[0] * changed.size[1])
        faded = ai.point(lambda v: 255 - (255 - v) * 35 // 100).convert("RGB")
        overlay = faded.copy()
        overlay.paste((22, 163, 74), mask=added)
        overlay.paste((220, 38, 38), mask=removed)
        box = changed.getbbox()
        page: dict[str, Any] = {
            "page": i + 1, "width": ai.size[0], "height": ai.size[1],
            "before_png": _png_b64(bi), "after_png": _png_b64(ai), "overlay_png": _png_b64(overlay),
            "changed_percent": round(ratio * 100, 2),
            "only_in": "draft" if i >= len(b_imgs) else ("published" if i >= len(a_imgs) else None),
        }
        if box and ratio > 0:
            top, bottom = box[1] / ai.size[1], box[3] / ai.size[1]
            page["box"] = {"left": round(box[0] / ai.size[0], 3), "top": round(top, 3), "right": round(box[2] / ai.size[0], 3), "bottom": round(bottom, 3)}
            page["summary"] = f"Page {i + 1}: {page['changed_percent']}% of the page changed, {_where(top, bottom)}."
        else:
            page["summary"] = f"Page {i + 1}: looks the same."
        pages.append(page)
    return {"pages": pages, "same": all(p["changed_percent"] == 0 for p in pages) and b_total == a_total,
            "page_counts": {"published": b_total, "draft": a_total},
            "truncated": max(b_total, a_total) > max_pages}


def compare_texts(before: bytes, after: bytes) -> dict[str, Any]:
    a, b = pdf_pages_text(before), pdf_pages_text(after)
    out = []
    for i in range(max(len(a), len(b))):
        la = {ln.strip() for ln in (a[i]["text"] if i < len(a) else "").splitlines() if ln.strip()}
        lb = {ln.strip() for ln in (b[i]["text"] if i < len(b) else "").splitlines() if ln.strip()}
        out.append({"page": i + 1, "added": sorted(lb - la)[:40], "removed": sorted(la - lb)[:40]})
    return {"pages_before": len(a), "pages_after": len(b), "pages": out, "same": all(not p["added"] and not p["removed"] for p in out)}


# ----------------------------------------------------------------------------
# Starter gallery (shown only where the app, report and fields exist)
# ----------------------------------------------------------------------------

STARTERS: list[dict[str, Any]] = [
    {"key": "invoice_payment_qr", "label": "Payment reference with QR code", "model": "account.move",
     "needs": {"payment_reference": {"char"}},
     "placements": [{"slot": "bottom", "blocks": [
         {"type": "heading", "text": "How to pay", "level": 4},
         {"type": "label_field", "field": "payment_reference", "label": "Payment reference"},
         {"type": "qr", "field": "payment_reference"}]}]},
    {"key": "invoice_thanks", "label": "Thank-you note", "model": "account.move", "needs": {},
     "placements": [{"slot": "bottom", "blocks": [{"type": "text", "text": "Thank you for your business."}]}]},
    {"key": "invoice_draft_watermark", "label": "'DRAFT' watermark until posted", "model": "account.move", "needs": {"state": {"selection"}},
     "placements": [{"slot": "bottom", "blocks": [{"type": "watermark", "text": "DRAFT", "colour": "red",
                                                       "condition": {"match": "all", "rules": [{"field": "state", "op": "is", "value": "draft"}]}}]}]},
    {"key": "sale_signature", "label": "Customer signature", "model": "sale.order", "needs": {"signature": {"binary"}, "signed_by": {"char"}},
     "placements": [{"slot": "bottom", "blocks": [{"type": "signature", "field": "signature", "label": "Signed by", "signed_by": "signed_by"}]}]},
    {"key": "sale_validity", "label": "Offer valid until", "model": "sale.order", "needs": {"validity_date": {"date"}},
     "placements": [{"slot": "bottom", "blocks": [{"type": "label_field", "field": "validity_date", "label": "This offer is valid until",
                                                   "condition": {"match": "all", "rules": [{"field": "validity_date", "op": "set"}]}}]}]},
    {"key": "purchase_lines_totals", "label": "Lines with totals", "model": "purchase.order", "needs": {"order_line": {"one2many"}},
     "lines": {"order_line": ["name", "product_qty", "price_subtotal"]},
     "placements": [{"slot": "bottom", "blocks": [{"type": "line_table", "field": "order_line", "columns": [
         {"field": "name", "label": "Description"}, {"field": "product_qty", "label": "Quantity", "sum": True},
         {"field": "price_subtotal", "label": "Amount", "sum": True}]}]}]},
    {"key": "picking_barcode", "label": "Reference as a barcode", "model": "stock.picking", "needs": {"name": {"char"}},
     "placements": [{"slot": "top", "blocks": [{"type": "barcode", "field": "name"}]}]},
]


def gallery_for(model: str, fields: dict[str, Any], related: dict[str, dict[str, Any]], slots: list[dict[str, str]]) -> list[dict[str, Any]]:
    slot_ids = {s["id"] for s in slots}
    out = []
    for s in STARTERS:
        if s["model"] != model:
            continue
        ok = all(f in fields and fields[f].get("type") in types for f, types in s["needs"].items())
        for o2m, cols in (s.get("lines") or {}).items():
            ok = ok and all(c in (related.get(o2m) or {}) for c in cols)
        ok = ok and all(p["slot"] in slot_ids for p in s["placements"])
        if ok:
            out.append({k: s[k] for k in ("key", "label", "placements")})
    return out
