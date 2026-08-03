"""Website page arch → editable block tree (UIX-7).

Recognized patterns become editable blocks; unrecognized snippets stay locked verbatim
(partial-fidelity contract, same philosophy as AI-7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

BlockKind = Literal["heading", "paragraph", "image", "link", "button", "section", "locked"]


@dataclass
class WebsiteBlock:
    id: str
    kind: BlockKind
    text: str = ""
    href: str = ""
    src: str = ""
    level: int = 2
    locked_xml: str = ""
    children: list["WebsiteBlock"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "href": self.href,
            "src": self.src,
            "level": self.level,
            "locked_xml": self.locked_xml,
            "children": [c.to_dict() for c in self.children],
        }


_HEADING_RE = re.compile(r"<h([1-6])([^>]*)>(.*?)</h\1>", re.I | re.S)
_PARA_RE = re.compile(r"<p([^>]*)>(.*?)</p>", re.I | re.S)
_IMG_RE = re.compile(
    r'<img([^>]*)\bsrc=["\']([^"\']+)["\'][^>]*/?>', re.I
)
_LINK_RE = re.compile(
    r'<a([^>]*)\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S
)
_BUTTON_RE = re.compile(r"<button([^>]*)>(.*?)</button>", re.I | re.S)
_BUTTON_HREF_RE = re.compile(
    r'\b(?:formaction|data-href|href)=["\']([^"\']+)["\']', re.I
)
_SECTION_RE = re.compile(r"<section([^>]*)>(.*?)</section>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", html)).strip()


def parse_website_arch(arch: str) -> list[WebsiteBlock]:
    """Parse QWeb/HTML arch into blocks; unknown regions → locked."""
    if not arch or not arch.strip():
        return []

    blocks: list[WebsiteBlock] = []
    cursor = 0
    seq = 0

    def next_id(prefix: str) -> str:
        nonlocal seq
        seq += 1
        return f"{prefix}-{seq}"

    patterns: list[tuple[re.Pattern[str], str]] = [
        (_SECTION_RE, "section"),
        (_HEADING_RE, "heading"),
        (_PARA_RE, "paragraph"),
        (_BUTTON_RE, "button"),
        (_LINK_RE, "link"),
        (_IMG_RE, "image"),
    ]

    while cursor < len(arch):
        best: tuple[int, int, str, re.Match[str]] | None = None
        for pattern, kind in patterns:
            m = pattern.search(arch, cursor)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), m.end(), kind, m)
        if best is None:
            tail = arch[cursor:].strip()
            if tail:
                blocks.append(
                    WebsiteBlock(id=next_id("locked"), kind="locked", locked_xml=tail)
                )
            break
        start, end, kind, m = best
        if start > cursor:
            snippet = arch[cursor:start].strip()
            if snippet:
                blocks.append(
                    WebsiteBlock(id=next_id("locked"), kind="locked", locked_xml=snippet)
                )
        if kind == "heading":
            level = int(m.group(1))
            blocks.append(
                WebsiteBlock(
                    id=next_id("h"),
                    kind="heading",
                    level=level,
                    text=_strip_tags(m.group(3)),
                )
            )
        elif kind == "paragraph":
            blocks.append(
                WebsiteBlock(
                    id=next_id("p"),
                    kind="paragraph",
                    text=_strip_tags(m.group(2)),
                )
            )
        elif kind == "button":
            attrs = m.group(1)
            href_m = _BUTTON_HREF_RE.search(attrs)
            blocks.append(
                WebsiteBlock(
                    id=next_id("btn"),
                    kind="button",
                    href=href_m.group(1) if href_m else "",
                    text=_strip_tags(m.group(2)),
                )
            )
        elif kind == "link":
            blocks.append(
                WebsiteBlock(
                    id=next_id("a"),
                    kind="link",
                    href=m.group(2),
                    text=_strip_tags(m.group(3)),
                )
            )
        elif kind == "image":
            blocks.append(
                WebsiteBlock(id=next_id("img"), kind="image", src=m.group(2))
            )
        elif kind == "section":
            inner = m.group(2)
            child_blocks = parse_website_arch(inner)
            blocks.append(
                WebsiteBlock(
                    id=next_id("sec"),
                    kind="section",
                    children=child_blocks,
                )
            )
        cursor = end

    return blocks


def render_website_arch(blocks: list[WebsiteBlock]) -> str:
    """Serialize blocks back to arch; locked blocks emit verbatim."""
    parts: list[str] = []
    for b in blocks:
        if b.kind == "locked":
            parts.append(b.locked_xml)
        elif b.kind == "heading":
            parts.append(f"<h{b.level}>{_escape(b.text)}</h{b.level}>")
        elif b.kind == "paragraph":
            parts.append(f"<p>{_escape(b.text)}</p>")
        elif b.kind == "link":
            parts.append(
                f'<a href="{_escape_attr(b.href)}">{_escape(b.text)}</a>'
            )
        elif b.kind == "button":
            href_attr = (
                f' formaction="{_escape_attr(b.href)}"' if b.href else ""
            )
            parts.append(f"<button{href_attr}>{_escape(b.text)}</button>")
        elif b.kind == "image":
            parts.append(f'<img src="{_escape_attr(b.src)}"/>')
        elif b.kind == "section":
            inner = render_website_arch(b.children)
            parts.append(f"<section>{inner}</section>")
    return "".join(parts)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _escape_attr(text: str) -> str:
    return text.replace('"', "&quot;").replace("'", "&#39;")


def blocks_from_dicts(raw: list[dict[str, Any]]) -> list[WebsiteBlock]:
    """Deserialize API block payloads (recursive children)."""

    def one(b: dict[str, Any], i: int) -> WebsiteBlock:
        children_raw = b.get("children") or []
        children = [
            one(c, j)
            for j, c in enumerate(children_raw)
            if isinstance(c, dict)
        ]
        return WebsiteBlock(
            id=str(b.get("id") or f"b-{i}"),
            kind=b.get("kind") or "locked",
            text=str(b.get("text") or ""),
            href=str(b.get("href") or ""),
            src=str(b.get("src") or ""),
            level=int(b.get("level") or 2),
            locked_xml=str(b.get("locked_xml") or ""),
            children=children,
        )

    return [one(b, i) for i, b in enumerate(raw) if isinstance(b, dict)]
