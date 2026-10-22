"""DOC-QWEB — general ir.ui.view type=qweb block compile / parse / gate.

Paper-desk sibling of Reports / Mail / Website. Reuses ``qweb_unsafe_gate``
(PDF-05) for script / t-raw / t-out / XXE. t-call: stock layout allowlist plus
grandfathered targets already present on the loaded arch (no invent of new
non-allowlisted calls). Complements RT-22 ``refuse_root_replace`` on inherit.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal

from app.qweb_unsafe_gate import (
    QWEB_T_CALL_ALLOWLIST,
    arch_has_xxe,
    refuse_unsafe_block_text,
)
# Local RT-22 mirror (avoid importing report_design → module_generator).
_ROOT_REPLACE_EXPRS = frozenset(
    {
        "/",
        "/*",
        "/t",
        "/t[1]",
        "//t",
        "/template",
        "//template",
        ".",
        "//*",
    }
)


def refuse_root_replace(xpath: str, position: str) -> None:
    """Raise ValueError for RT-22 root/large replace before inherit emit."""
    if str(position).strip().lower() != "replace":
        return
    norm = "".join(str(xpath).split())
    if norm in _ROOT_REPLACE_EXPRS or norm in {"//form", "//sheet", "//list", "//tree", "//div", "//page"}:
        raise ValueError("xpath replaces the root or a large subtree")


BlockKind = Literal[
    "heading",
    "paragraph",
    "field",
    "divider",
    "locked",
]

_T_CALL_RE = re.compile(
    r"""\bt-call\s*=\s*(?P<q>['"])(?P<target>.*?)(?P=q)""",
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_RE = re.compile(r"<\s*script\b", re.IGNORECASE)
_T_RAW_RE = re.compile(r"""\bt-raw\b""", re.IGNORECASE)
_T_OUT_RE = re.compile(r"""\bt-out\b""", re.IGNORECASE)
_EVENT_ATTR_RE = re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE)
_JS_URL_RE = re.compile(
    r"""(?:href|src)\s*=\s*(['"])\s*javascript:""", re.IGNORECASE
)
_DATA_HTML_RE = re.compile(
    r"""(?:href|src)\s*=\s*(['"])\s*data:\s*text/html""", re.IGNORECASE
)

@dataclass
class QwebViewBlock:
    id: str
    kind: BlockKind
    text: str = ""
    field: str = ""
    level: int = 2
    locked_xml: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "field": self.field,
            "level": self.level,
            "locked_xml": self.locked_xml,
        }


def extract_t_call_targets(arch: str) -> frozenset[str]:
    """Return every t-call target in arch (for grandfathering on save)."""
    if not arch:
        return frozenset()
    out: set[str] = set()
    for match in _T_CALL_RE.finditer(arch):
        target = (match.group("target") or "").strip()
        if target:
            out.add(target)
    return frozenset(out)


def refuse_unsafe_qweb_view_arch(
    arch: str,
    *,
    allow_existing_t_calls: Iterable[str] | None = None,
) -> None:
    """Raise ValueError when general QWeb arch is unsafe.

    Always refuses t-raw / t-out / script / XXE / on* / javascript: /
    data:text/html. t-call targets must be on the stock layout allowlist or
    in ``allow_existing_t_calls`` (loaded-arch grandfather).
    """
    if not arch:
        return
    if _T_RAW_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: t-raw is not allowed in general QWeb views"
        )
    if _T_OUT_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: t-out is not allowed in general QWeb views "
            "(use grounded t-field blocks instead)"
        )
    if _SCRIPT_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: <script> is not allowed in general QWeb views"
        )
    if arch_has_xxe(arch):
        raise ValueError(
            "Unsafe QWeb refused: XML external entities "
            "(DOCTYPE / ENTITY) are not allowed"
        )
    if _EVENT_ATTR_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: inline event handlers (on*) are not allowed"
        )
    if _JS_URL_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: javascript: URLs are not allowed"
        )
    if _DATA_HTML_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: data:text/html URLs are not allowed"
        )

    allowed = set(QWEB_T_CALL_ALLOWLIST)
    if allow_existing_t_calls:
        allowed.update(t for t in allow_existing_t_calls if t)

    for match in _T_CALL_RE.finditer(arch):
        target = (match.group("target") or "").strip()
        if not target:
            raise ValueError("Unsafe QWeb refused: empty t-call target")
        if target not in allowed:
            raise ValueError(
                f"Unsafe QWeb refused: t-call to {target!r} is not on the "
                f"allowlist and was not present on the loaded arch "
                f"({', '.join(sorted(QWEB_T_CALL_ALLOWLIST))})"
            )


_BLOCK_FIELD_UNSAFE = re.compile(r"[^\w.]")


def refuse_unsafe_qweb_view_blocks(blocks: list[QwebViewBlock]) -> None:
    """Gate editable block text + locked XML before compile/persist."""
    for b in blocks:
        if b.kind == "locked" and b.locked_xml:
            refuse_unsafe_qweb_view_arch(b.locked_xml)
        if b.text:
            refuse_unsafe_block_text(
                {"blocks": [{"type": b.kind, "text": b.text}]}
            )
        if b.field and _BLOCK_FIELD_UNSAFE.search(b.field):
            raise ValueError(
                "Unsafe QWeb refused: field path must be a grounded token "
                "(letters, digits, underscore, dots)"
            )


def gate_qweb_view_save(
    blocks: list[QwebViewBlock] | None,
    arch: str,
    *,
    allow_existing_t_calls: Iterable[str] | None = None,
    inherit_xpath: str | None = None,
    inherit_position: str | None = None,
) -> None:
    """Run block + arch + inherit root-replace gates before persist."""
    if blocks:
        refuse_unsafe_qweb_view_blocks(blocks)
    refuse_unsafe_qweb_view_arch(
        arch, allow_existing_t_calls=allow_existing_t_calls
    )
    if inherit_xpath is not None and inherit_position is not None:
        refuse_root_replace(inherit_xpath, inherit_position)


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _field_expr(field: str, *, record_var: str = "doc") -> str:
    path = (field or "display_name").strip() or "display_name"
    if path.startswith(f"{record_var}."):
        return path
    return f"{record_var}.{path}"


def compile_qweb_view_blocks(
    blocks: list[QwebViewBlock],
    *,
    wrap_external_layout: bool = False,
    record_var: str = "doc",
) -> str:
    """Compile grounded blocks to a QWeb fragment (optionally layout-wrapped)."""
    parts: list[str] = ['<div class="page">']
    for b in blocks:
        if b.kind == "heading":
            level = 1 if b.level == 1 else 2 if b.level == 2 else 3
            parts.append(f"<h{level}>{_esc(b.text)}</h{level}>")
        elif b.kind == "paragraph":
            parts.append(f"<p>{_esc(b.text)}</p>")
        elif b.kind == "field":
            expr = _field_expr(b.field, record_var=record_var)
            parts.append(f'<span t-field="{_esc(expr)}"/>')
        elif b.kind == "divider":
            parts.append("<hr/>")
        elif b.kind == "locked" and b.locked_xml:
            parts.append(b.locked_xml)
    parts.append("</div>")
    inner = "\n".join(parts)
    if not wrap_external_layout:
        return inner
    return (
        '<t t-name="ingenium.qweb_view_primary">\n'
        '  <t t-call="web.external_layout">\n'
        f"    {inner}\n"
        "  </t>\n"
        "</t>"
    )


def compile_inherit_fragment(
    blocks: list[QwebViewBlock],
    *,
    xpath: str,
    position: str = "inside",
    record_var: str = "doc",
) -> str:
    """Compile blocks into a ``<data><xpath>`` inherit arch (RT-22 gated)."""
    refuse_root_replace(xpath, position)
    body = compile_qweb_view_blocks(
        blocks, wrap_external_layout=False, record_var=record_var
    )
    # Drop outer page wrapper for inject — keep children only.
    body_inner = body
    if body_inner.startswith('<div class="page">') and body_inner.endswith(
        "</div>"
    ):
        body_inner = body_inner[len('<div class="page">') : -len("</div>")].strip()
    pos = (position or "inside").strip() or "inside"
    if any(c in pos for c in '<>&"'):
        raise ValueError("inherit position contains invalid characters")
    expr = (xpath or "").strip()
    if not expr:
        raise ValueError("inherit xpath is required")
    if '"' in expr or "<" in expr or "&" in expr:
        raise ValueError(
            "inherit xpath must not contain quotes, <, or & — "
            "use hasclass() / [@name=...] with single quotes"
        )
    return (
        f'<data>\n'
        f'  <xpath expr="{expr}" position="{pos}">\n'
        f"    {body_inner}\n"
        f"  </xpath>\n"
        f"</data>"
    )


_HEADING_RE = re.compile(r"<h([1-3])([^>]*)>(.*?)</h\1>", re.I | re.S)
_PARA_RE = re.compile(r"<p([^>]*)>(.*?)</p>", re.I | re.S)
_FIELD_RE = re.compile(
    r"""<\s*(?:span|div|t)\b[^>]*\bt-field\s*=\s*(['"])(?P<field>.*?)\1[^>]*/?\s*>""",
    re.I | re.S,
)
_HR_RE = re.compile(r"<hr\s*/?>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", s)).strip()


def try_parse_qweb_view_blocks(arch: str) -> list[QwebViewBlock] | None:
    """Best-effort parse of Ingenium-authored page fragments.

    Complex / foreign arches return None → editor stays on Source XML tab.
    """
    if not arch or not arch.strip():
        return []
    trimmed = arch.strip()
    # Strip common wrappers to reach the page body.
    inner = trimmed
    for pattern in (
        r"(?is)<t\b[^>]*t-call\s*=\s*['\"]web\.external_layout['\"][^>]*>(.*)</t>",
        r"(?is)<t\b[^>]*t-name\s*=\s*['\"][^'\"]+['\"][^>]*>(.*)</t>",
        r"(?is)<template\b[^>]*>(.*)</template>",
        r'(?is)<div\b[^>]*class=["\'][^"\']*\bpage\b[^"\']*["\'][^>]*>(.*)</div>',
    ):
        m = re.search(pattern, inner)
        if m:
            inner = m.group(1).strip()
            break

    if re.search(r"<(table|ul|ol|blockquote|xpath|data)\b", inner, re.I):
        return None

    blocks: list[QwebViewBlock] = []
    seq = 0

    def next_id(prefix: str) -> str:
        nonlocal seq
        seq += 1
        return f"{prefix}-{seq}"

    # Walk by finding the next recognized tag from cursor.
    cursor = 0
    while cursor < len(inner):
        rest = inner[cursor:]
        # Skip whitespace
        ws = re.match(r"^\s+", rest)
        if ws:
            cursor += ws.end()
            continue

        matched = False
        for regex, kind in (
            (_HEADING_RE, "heading"),
            (_PARA_RE, "paragraph"),
            (_FIELD_RE, "field"),
            (_HR_RE, "divider"),
        ):
            m = regex.match(rest)
            if not m:
                continue
            matched = True
            cursor += m.end()
            if kind == "heading":
                blocks.append(
                    QwebViewBlock(
                        id=next_id("h"),
                        kind="heading",
                        text=_strip_tags(m.group(3)),
                        level=int(m.group(1)),
                    )
                )
            elif kind == "paragraph":
                blocks.append(
                    QwebViewBlock(
                        id=next_id("p"),
                        kind="paragraph",
                        text=_strip_tags(m.group(2)),
                    )
                )
            elif kind == "field":
                raw = (m.group("field") or "").strip()
                field = raw.split(".", 1)[-1] if raw.startswith("doc.") else raw
                if field.startswith("o."):
                    field = field[2:]
                blocks.append(
                    QwebViewBlock(id=next_id("f"), kind="field", field=field)
                )
            elif kind == "divider":
                blocks.append(QwebViewBlock(id=next_id("hr"), kind="divider"))
            break

        if not matched:
            # Unrecognized → foreign body
            return None

    return blocks


def blocks_from_dicts(raw: list[dict[str, Any]]) -> list[QwebViewBlock]:
    out: list[QwebViewBlock] = []
    for i, item in enumerate(raw or []):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or item.get("type") or "paragraph")
        if kind not in {"heading", "paragraph", "field", "divider", "locked"}:
            kind = "locked"
        out.append(
            QwebViewBlock(
                id=str(item.get("id") or f"b-{i + 1}"),
                kind=kind,  # type: ignore[arg-type]
                text=str(item.get("text") or ""),
                field=str(item.get("field") or ""),
                level=int(item.get("level") or 2),
                locked_xml=str(item.get("locked_xml") or ""),
            )
        )
    return out


def default_qweb_view_blocks(title: str = "Document") -> list[QwebViewBlock]:
    return [
        QwebViewBlock(id="h-1", kind="heading", text=title, level=2),
        QwebViewBlock(
            id="p-1",
            kind="paragraph",
            text="Grounded QWeb document — edit blocks or open Source XML.",
        ),
        QwebViewBlock(id="f-1", kind="field", field="display_name"),
    ]
