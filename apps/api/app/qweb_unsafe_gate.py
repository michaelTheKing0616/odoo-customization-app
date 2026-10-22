"""PDF-05 — centralized QWeb unsafe-arch gate for report design.

Used by report compile / save / preview / update before any arch is persisted
or sandbox-rendered. Complements RT-22 (root/large xpath replace) in
``report_design.refuse_root_replace`` / ``changeset.ui_ops``.

Allowlist (documented; refuse unknown ``t-call`` targets):
- ``web.external_layout`` — stock letterhead wrapper (primary default)
- ``web.html_container`` — minimal wrapper when external layout is off
- ``web.basic_layout`` — stock basic layout
- ``web.minimal_layout`` — stock minimal layout
- ``web.internal_layout`` — stock internal layout

Shared do-not: no ``t-raw`` of user HTML; no XXE; no ``<script``; no
non-allowlisted ``t-call``; block text must not be interpreted as QWeb.
"""

from __future__ import annotations

import re
from typing import Any

# Explicit stock layout keys the designer / pasted arch may t-call.
QWEB_T_CALL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "web.external_layout",
        "web.html_container",
        "web.basic_layout",
        "web.minimal_layout",
        "web.internal_layout",
    }
)

_SCRIPT_RE = re.compile(r"<\s*script\b", re.IGNORECASE)
_T_RAW_RE = re.compile(r"""\bt-raw\b""", re.IGNORECASE)
_T_OUT_RE = re.compile(r"""\bt-out\b""", re.IGNORECASE)
_T_CALL_RE = re.compile(
    r"""\bt-call\s*=\s*(?P<q>['"])(?P<target>.*?)(?P=q)""",
    re.IGNORECASE | re.DOTALL,
)
_DOCTYPE_RE = re.compile(r"<!DOCTYPE\b", re.IGNORECASE)
_ENTITY_RE = re.compile(r"<!ENTITY\b", re.IGNORECASE)
# External entity reference / SYSTEM/PUBLIC entity payloads
_EXTERNAL_ENTITY_RE = re.compile(
    r"""<!ENTITY\b[^>]*\b(?:SYSTEM|PUBLIC)\b"""
    r"""|SYSTEM\s+(?P<q>['"])[^'"]*(?P=q)""",
    re.IGNORECASE,
)

# Block / label text that would be interpreted (or looks like) QWeb / template.
_BLOCK_QWEB_RE = re.compile(
    r"(?is)"
    r"(<\s*t[\s>/])"
    r"|(\{\{)"
    r"|(\}\})"
    r"|(\bt-(?:raw|out|esc|call|foreach|as|if|elif|else|field|options|"
    r"att|attf|set|value|lang|name|nocache|js|debug|translation)\b)",
)


def arch_has_xxe(arch: str) -> bool:
    """True when arch declares DOCTYPE/ENTITY or an external entity payload.

    Inputs: raw QWeb/XML arch string.
    Outputs: bool. Side effects: none.
    """
    if not arch:
        return False
    if _DOCTYPE_RE.search(arch) or _ENTITY_RE.search(arch):
        return True
    if _EXTERNAL_ENTITY_RE.search(arch):
        return True
    return False


def refuse_unsafe_qweb_arch(arch: str) -> None:
    """Raise ValueError when pasted/compiled arch is unsafe (PDF-05).

    Inputs: QWeb arch about to be saved, previewed, or compiled.
    Outputs: none.
    Side effects: raises ValueError with a clear human message (no stack dump).
    """
    if not arch:
        return
    if _T_RAW_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: t-raw is not allowed in report templates"
        )
    if _T_OUT_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: t-out is not allowed in report templates "
            "(use grounded t-field blocks instead)"
        )
    if _SCRIPT_RE.search(arch):
        raise ValueError(
            "Unsafe QWeb refused: <script> is not allowed in report templates"
        )
    if arch_has_xxe(arch):
        raise ValueError(
            "Unsafe QWeb refused: XML external entities "
            "(DOCTYPE / ENTITY) are not allowed"
        )
    for match in _T_CALL_RE.finditer(arch):
        target = (match.group("target") or "").strip()
        if not target:
            raise ValueError("Unsafe QWeb refused: empty t-call target")
        if target not in QWEB_T_CALL_ALLOWLIST:
            raise ValueError(
                f"Unsafe QWeb refused: t-call to {target!r} is not on the "
                f"allowlist ({', '.join(sorted(QWEB_T_CALL_ALLOWLIST))})"
            )


def _text_looks_like_qweb(text: str) -> bool:
    return bool(text and _BLOCK_QWEB_RE.search(text))


def refuse_unsafe_block_text(spec: dict[str, Any]) -> None:
    """Refuse heading/text/label strings that look like QWeb directives.

    Prefer refuse over silent escape so pasted malicious text surfaces a clear
    error before save/compile. Escaping in ``emit_block`` remains a second line.

    Inputs: designer spec with ``blocks``.
    Outputs: none.
    Side effects: raises ValueError with a clear human message.
    """
    blocks = spec.get("blocks") or []
    if not isinstance(blocks, list):
        return
    for block in blocks:
        if not isinstance(block, dict):
            continue
        candidates: list[tuple[str, str]] = []
        for key in ("text", "label"):
            val = block.get(key)
            if isinstance(val, str) and val:
                candidates.append((key, val))
        columns = block.get("columns") or []
        if isinstance(columns, list):
            for col in columns:
                if not isinstance(col, dict):
                    continue
                label = col.get("label")
                if isinstance(label, str) and label:
                    candidates.append(("column.label", label))
        for where, text in candidates:
            if _text_looks_like_qweb(text):
                raise ValueError(
                    f"Unsafe QWeb refused: {where} must not contain QWeb "
                    f"directives or template markers"
                )


def gate_report_design_spec(spec: dict[str, Any]) -> None:
    """Run block-text unsafe gate on a designer spec (before compile)."""
    refuse_unsafe_block_text(spec)


def gate_report_arch(arch: str) -> None:
    """Run arch unsafe gate (before persist / preview write)."""
    refuse_unsafe_qweb_arch(arch)
