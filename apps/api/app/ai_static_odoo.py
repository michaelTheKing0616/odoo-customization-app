"""Deterministic static Odoo analyzers — beat LLM review for syntax/security smells."""

from __future__ import annotations

import ast
import re
from typing import Any


_REF_RE = re.compile(r"""ref\(['\"]([^'\"]+)['\"]\)""")
_XPATH_EXPR_RE = re.compile(r"""expr=['\"]([^'\"]+)['\"]""")


def _finding(
    rule: str,
    message: str,
    *,
    severity: str = "medium",
    file: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    return {
        "rule": rule,
        "message": message,
        "severity": severity,
        **({"file": file} if file else {}),
        **({"line": line} if line is not None else {}),
    }


def _line_justified(content: str, lineno: int | None, markers: tuple[str, ...]) -> bool:
    """True when a nearby comment documents why a smell is intentional."""
    if not lineno or not content:
        return False
    lines = content.splitlines()
    idx = lineno - 1
    window = lines[max(0, idx - 3) : min(len(lines), idx + 1)]
    blob = "\n".join(window)
    return any(m in blob for m in markers)


def analyze_python_ast(content: str, *, source_file: str = "models/custom.py") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        tree = ast.parse(content or "", filename=source_file)
    except SyntaxError as exc:
        return [
            _finding(
                "syntax_error",
                f"{exc.msg} (line {exc.lineno})",
                severity="critical",
                file=source_file,
                line=exc.lineno,
            )
        ]

    src = content or ""

    for node in ast.walk(tree):
        # sudo()
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "sudo":
                if not _line_justified(src, getattr(node, "lineno", None), ("SUDO-JUSTIFIED",)):
                    findings.append(
                        _finding(
                            "sudo_call",
                            "sudo() without documented justification — ACL bypass risk",
                            severity="high",
                            file=source_file,
                            line=getattr(node, "lineno", None),
                        )
                    )
            # cr.execute / env.cr.execute
            if isinstance(func, ast.Attribute) and func.attr == "execute":
                findings.append(
                    _finding(
                        "raw_sql",
                        "cr.execute / raw SQL — prefer ORM; justify if required",
                        severity="critical",
                        file=source_file,
                        line=getattr(node, "lineno", None),
                    )
                )

    # N+1: search/create/write inside For loops
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While)):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr in {
                "search",
                "create",
                "write",
                "browse",
                "search_read",
            }:
                findings.append(
                    _finding(
                        "orm_in_loop",
                        f"{func.attr}() inside loop — possible N+1",
                        severity="medium",
                        file=source_file,
                        line=getattr(child, "lineno", None),
                    )
                )
                break
    return findings


def analyze_manifest_deps(
    depends: list[str],
    *,
    xml_blobs: list[str],
    python_blobs: list[str],
) -> list[dict[str, Any]]:
    """Best-effort: external module refs should appear in depends."""
    findings: list[dict[str, Any]] = []
    dep_set = {str(d).strip() for d in depends if str(d).strip()}
    # Always implied
    dep_set |= {"base"}
    refs: set[str] = set()
    for blob in xml_blobs:
        for m in _REF_RE.finditer(blob or ""):
            xmlid = m.group(1)
            if "." in xmlid:
                refs.add(xmlid.split(".", 1)[0])
    for blob in python_blobs:
        for m in re.finditer(r"""['\"]([a-z0-9_]+)\.([a-z0-9_.]+)['\"]""", blob or ""):
            # weak: module.xmlid style strings
            mod = m.group(1)
            if mod not in {"self", "env", "odoo", "fields", "models", "api"}:
                refs.add(mod)

    known_core = {
        "base",
        "web",
        "mail",
        "portal",
        "account",
        "sale",
        "purchase",
        "stock",
        "hr",
        "project",
        "crm",
        "product",
        "contacts",
        "uom",
        "payment",
        "ir",  # xmlid namespace ir.model / ir.actions — not a depends module
        "base_setup",
    }
    for mod in sorted(refs):
        if mod in dep_set or mod in known_core:
            continue
        # only flag if looks like odoo module name
        if re.fullmatch(r"[a-z][a-z0-9_]*", mod):
            findings.append(
                _finding(
                    "manifest_dep_missing",
                    f"ref/import suggests module '{mod}' not listed in depends",
                    severity="high",
                    file="__manifest__.py",
                )
            )
    return findings


# Community 17–19 sale.order form totals are the `tax_totals` widget — not amount_tax.
_SALE_FORM_GHOST_FIELDS = {
    "amount_tax": "tax_totals",
    "amount_untaxed": "tax_totals",
}
_SALE_FORM_XPATH_FIELD_RE = re.compile(
    r"""(field\[@name=['\"])(amount_tax|amount_untaxed)(['\"])"""
)
# sale.order.line taxes are Many2many ``tax_ids`` — never singular ``tax_id``.
_SALE_LINE_TAX_ID_STR_RE = re.compile(r"""(['"])tax_id\1""")
_SALE_LINE_TAX_ID_ATTR_RE = re.compile(r"""\.tax_id\b""")
# Stock pricing compute — LLM often redeclares this with Enterprise tax_id and kills install.
_COMPUTE_AMOUNT_BLOCK_RE = re.compile(
    r"(?:^[ \t]*@api\.depends\([^)]*\)\s*\n)?"
    r"^[ \t]*def _compute_amount\s*\([^)]*\):\n"
    r"(?:^[ \t]+.*\n?)*",
    re.MULTILINE,
)
_PRICE_SUBTOTAL_FIELD_RE = re.compile(
    r"^[ \t]*price_subtotal\s*=\s*fields\.[^\n]+\n",
    re.MULTILINE,
)


def rewrite_stock_inherit_xpaths(content: str) -> str:
    """Retarget inherit xpaths that miss on stock Community forms."""
    blob = content or ""
    if "sale.order" not in blob and "sale.view_order_form" not in blob:
        return blob
    return _SALE_FORM_XPATH_FIELD_RE.sub(
        lambda m: f"{m.group(1)}{_SALE_FORM_GHOST_FIELDS.get(m.group(2), m.group(2))}{m.group(3)}",
        blob,
    )


def rewrite_stock_python_field_deps(content: str) -> str:
    """Fix known wrong stock field names in Python inherits (CE 17–19)."""
    blob = content or ""
    sale_lineish = (
        "sale.order.line" in blob
        or ("_compute_amount" in blob and "tax_id" in blob)
        or ("price_subtotal" in blob and "tax_id" in blob)
    )
    if not sale_lineish:
        return blob
    # Wrong @depends('…', 'tax_id') and line.tax_id on price_subtotal / _compute_amount.
    blob = _SALE_LINE_TAX_ID_STR_RE.sub(r"\1tax_ids\1", blob)
    blob = _SALE_LINE_TAX_ID_ATTR_RE.sub(".tax_ids", blob)
    return blob


def sanitize_sale_stock_compute_overrides(content: str) -> str:
    """Drop stock ``_compute_amount`` / ``price_subtotal`` field redefs on sale inherits.

    Prefer x_* markup computes. Redeclaring stock pricing is the #1 CE sandbox killer.
    """
    blob = content or ""
    if "sale.order" not in blob:
        return blob
    if "_inherit" not in blob:
        return blob
    if "def _compute_amount" not in blob and "price_subtotal = fields." not in blob:
        return blob
    cleaned = _COMPUTE_AMOUNT_BLOCK_RE.sub("", blob)
    cleaned = _PRICE_SUBTOTAL_FIELD_RE.sub("", cleaned)
    # Collapse leftover blank runs from removed methods.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def harden_authored_python(content: str) -> str:
    """Deterministic CE fixes for LLM Python — free, no repair budget."""
    blob = rewrite_stock_python_field_deps(content or "")
    blob = sanitize_sale_stock_compute_overrides(blob)
    try:
        from app.ai_option_a_acceptance import ensure_python_field_strings

        blob = ensure_python_field_strings(blob)
    except Exception:  # noqa: BLE001
        pass
    return blob


def rewrite_draft_stock_xpaths(draft: dict[str, Any]) -> int:
    """Rewrite ghost stock xpaths / field deps / compute overrides. Returns files changed."""
    changed = 0
    blocks = draft.get("custom_code_blocks")
    if not isinstance(blocks, list):
        return 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or block.get("path") or "")
        content = str(block.get("content") or "")
        if not content:
            continue
        kind = str(block.get("kind") or "")
        rewritten = content
        if path.endswith(".xml") or kind in {"xml", "qweb"}:
            rewritten = rewrite_stock_inherit_xpaths(rewritten)
            try:
                from app.ai_option_a_acceptance import rewrite_note_xpath_to_tax_totals

                rewritten = rewrite_note_xpath_to_tax_totals(rewritten)
            except Exception:  # noqa: BLE001
                pass
        if path.endswith(".py") or kind == "python":
            rewritten = harden_authored_python(rewritten)
        if rewritten != content:
            block["content"] = rewritten
            changed += 1
    try:
        from app.ai_option_a_view_fields import align_draft_view_fields_to_python

        changed += align_draft_view_fields_to_python(draft)
    except Exception:  # noqa: BLE001
        pass
    return changed


def analyze_xpath_best_effort(
    content: str,
    *,
    source_file: str = "views/inherit.xml",
    known_field_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    known = known_field_names or set()
    for m in _XPATH_EXPR_RE.finditer(content or ""):
        expr = m.group(1)
        # field[@name='x']
        fm = re.search(r"""field\[@name=['\"]([^'\"]+)['\"]\]""", expr)
        if fm and known and fm.group(1) not in known:
            findings.append(
                _finding(
                    "xpath_unknown_field",
                    f"xpath targets field '{fm.group(1)}' not in known primary arch fields",
                    severity="medium",
                    file=source_file,
                )
            )
        if "//" not in expr and not expr.startswith("/"):
            findings.append(
                _finding(
                    "xpath_expr_shape",
                    f"unusual xpath expr: {expr[:80]}",
                    severity="low",
                    file=source_file,
                )
            )
    return findings


def analyze_draft_static(
    draft: dict[str, Any],
    *,
    known_fields_by_model: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    xml_blobs: list[str] = []
    py_blobs: list[str] = []
    depends = [str(d) for d in (draft.get("depends") or []) if str(d).strip()]

    for b in draft.get("custom_code_blocks") or []:
        if not isinstance(b, dict):
            continue
        path = str(b.get("source_file") or b.get("path") or "block")
        content = str(b.get("content") or "")
        kind = str(b.get("kind") or "")
        if path.endswith(".py") or kind == "python":
            py_blobs.append(content)
            findings.extend(analyze_python_ast(content, source_file=path))
        elif path.endswith(".xml") or kind in {"xml", "qweb"}:
            xml_blobs.append(content)
            model_guess = str(b.get("model") or "")
            known = (known_fields_by_model or {}).get(model_guess) if model_guess else None
            findings.extend(
                analyze_xpath_best_effort(
                    content, source_file=path, known_field_names=known
                )
            )
        elif kind == "xml" or "<odoo" in content[:200]:
            xml_blobs.append(content)

    # Also scan view arches in ModuleSpec
    for v in draft.get("views") or []:
        if not isinstance(v, dict):
            continue
        arch = str(v.get("arch") or "")
        if not arch:
            continue
        xml_blobs.append(arch)
        mid = str(v.get("model") or "")
        known = (known_fields_by_model or {}).get(mid) if mid else None
        findings.extend(
            analyze_xpath_best_effort(
                arch,
                source_file=f"views/{v.get('id') or mid}.xml",
                known_field_names=known,
            )
        )

    findings.extend(
        analyze_manifest_deps(depends, xml_blobs=xml_blobs, python_blobs=py_blobs)
    )

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    return {
        "findings": findings,
        "critical_count": critical,
        "ok": critical == 0,
    }


def stamp_static_odoo(draft: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    result = analyze_draft_static(draft, **kwargs)
    draft["_static_odoo"] = result
    try:
        from app.ai_failure_ir import failures_from_static, stamp_failures

        stamp_failures(draft, failures_from_static(result))
    except Exception:  # noqa: BLE001
        pass
    return result


__all__ = [
    "analyze_draft_static",
    "analyze_manifest_deps",
    "analyze_python_ast",
    "analyze_xpath_best_effort",
    "harden_authored_python",
    "rewrite_draft_stock_xpaths",
    "rewrite_stock_inherit_xpaths",
    "rewrite_stock_python_field_deps",
    "sanitize_sale_stock_compute_overrides",
    "stamp_static_odoo",
]
