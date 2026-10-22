"""Report side of the shared view engine (Builders stage 1).

Edits to a stock print layout are saved as one QWeb extension view (xpath,
never replace) on the document template, so the stock template is never written.
Pure helpers; the router owns RPC.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from app.qweb_unsafe_gate import gate_report_arch
from app.report_design import compile_blocks_inner
from app.view_engine import LAYER_PREFIX, EngineError

ALLOWED_BLOCKS = frozenset({"text", "heading", "field", "label_field", "divider"})
FIELD_PATH_RE = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*){0,2}$")


def document_template_key(main_key: str, main_arch: str) -> str:
    """The template that draws one record (e.g. account.report_invoice_document).

    The main report template usually loops records and t-calls a document
    template; edits belong there. Falls back to the main template.
    """
    for match in re.finditer(r't-call="([^"]+)"', main_arch or ""):
        key = match.group(1).strip()
        if key and not key.startswith("web.") and "{" not in key:
            return key
    return main_key


def draws_page(arch: str) -> bool:
    """True when this template itself draws the printed page (has div.page)."""
    return bool(re.search(r'<div\b[^>]*\bclass="(?:[^"]*\s)?page(?:\s[^"]*)?"', arch or ""))


def record_var(document_arch: str) -> str:
    text = document_arch or ""
    if re.search(r"\bo\.", text):
        return "o"
    if re.search(r"\bdoc\.", text):
        return "doc"
    return "o"


def _has_class(el: ET.Element, cls: str) -> bool:
    return cls in (el.get("class") or "").split()


def slots_for(document_arch: str) -> list[dict[str, str]]:
    """Plain-named places a user can add content, resolved against the real template."""
    try:
        root = ET.fromstring(document_arch)
    except ET.ParseError:
        return []
    pages = [el for el in root.iter() if el.tag == "div" and _has_class(el, "page")]
    if len(pages) != 1:
        return []
    expr = "//div[hasclass('page')]"
    return [
        {"id": "top", "label": "Top of the document", "xpath": expr, "position": "before"},
        {"id": "bottom", "label": "Bottom of the document", "xpath": expr, "position": "inside"},
    ]


def validate_blocks(blocks: Any, fields: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(blocks, list) or not blocks:
        raise EngineError("Add at least one block to the layout.")
    if len(blocks) > 30:
        raise EngineError("Too many blocks at once.")
    clean: list[dict[str, Any]] = []
    for raw in blocks:
        if not isinstance(raw, dict):
            raise EngineError("A block could not be read.")
        kind = str(raw.get("type") or "")
        if kind not in ALLOWED_BLOCKS:
            raise EngineError(f"'{kind}' blocks come in a later stage.")
        block: dict[str, Any] = {"type": kind}
        if kind in {"text", "heading"}:
            text = str(raw.get("text") or "").strip()
            if not text or len(text) > 500:
                raise EngineError("Text blocks need 1 to 500 characters.")
            block["text"] = text
            if kind == "heading":
                block["level"] = max(1, min(3, int(raw.get("level") or 3)))
        if kind in {"field", "label_field"}:
            path = str(raw.get("field") or "").strip()
            head = path.split(".")[0]
            if not FIELD_PATH_RE.match(path) or head not in fields:
                raise EngineError(f"There is no field called '{path}' on this record type.")
            block["field"] = path
            if kind == "label_field":
                block["label"] = str(raw.get("label") or fields[head].get("string") or head)[:80]
        clean.append(block)
    return clean


def compile_report_layer(slot: dict[str, str], blocks: list[dict[str, Any]], var: str) -> str:
    inner = compile_blocks_inner(blocks, record_var=var)
    marker = f'<div class="{LAYER_PREFIX}_block">{inner}</div>'
    arch = (
        "<data>"
        f'<xpath expr="{slot["xpath"]}" position="{slot["position"]}">{marker}</xpath>'
        "</data>"
    )
    ET.fromstring(arch)  # well-formed or raise
    gate_report_arch(arch)
    return arch


def report_layer_name(document_key: str) -> str:
    return f"{LAYER_PREFIX} report {document_key}"


def expected_texts(blocks: list[dict[str, Any]]) -> list[str]:
    return [str(b.get("text")) for b in blocks if b.get("type") in {"text", "heading"} and b.get("text")]


def pdf_page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf or b""))


def compile_report_draft(slot: dict[str, str], blocks: list[dict[str, Any]], var: str, token: str, *, hide_published: bool) -> str:
    """Draft layer: blocks render only when the request context carries ``token``;
    the published Ingenium block is hidden for that same request."""
    if not re.fullmatch(r"[0-9a-f]{8,32}", token or ""):
        raise EngineError("Draft token is not valid.")
    cond = f"{var}.env.context.get('ingenium_draft') == '{token}'"
    parts: list[str] = []
    if hide_published:
        parts.append(
            f"<xpath expr=\"//div[hasclass('{LAYER_PREFIX}_block')]\" position=\"attributes\">"
            f"<attribute name=\"t-if\">{var}.env.context.get('ingenium_draft') != '{token}'</attribute></xpath>"
        )
    if blocks:
        inner = compile_blocks_inner(blocks, record_var=var)
        parts.append(
            f'<xpath expr="{slot["xpath"]}" position="{slot["position"]}">'
            f'<div class="{LAYER_PREFIX}_draft" t-if="{cond}">{inner}</div></xpath>'
        )
    if not parts:
        raise EngineError("There's nothing to preview yet.")
    arch = "<data>" + "".join(parts) + "</data>"
    ET.fromstring(arch)
    gate_report_arch(arch)
    return arch
