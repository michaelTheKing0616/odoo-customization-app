"""DEV-2 — custom_code_blocks authoring, lint, skeleton helpers."""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from typing import Any

from app.module_spec_codec import merge_custom_code_blocks

# Option A gold may fetch public HTTP (CBN) or parse JSON. Still forbid os/subprocess.
_STDLIB_IMPORT_ALLOW = frozenset(
    {
        "json",
        "logging",
        "re",
        "math",
        "decimal",
        "datetime",
        "urllib",
        "html",
        "xml",
    }
)


def _import_module_allowed(name: str) -> bool:
    top = (name or "").split(".", 1)[0]
    return top in _STDLIB_IMPORT_ALLOW


def normalize_block(block: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_file": str(block.get("source_file") or block.get("path") or "models/custom.py"),
        "kind": str(block.get("kind") or "python"),
        "content": str(block.get("content") or block.get("source") or ""),
        "reason": str(block.get("reason") or "authoring"),
        **({"model": str(block["model"])} if block.get("model") else {}),
    }


def lint_python(content: str, *, source_file: str = "block.py") -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    try:
        tree = ast.parse(content or "", filename=source_file)
    except SyntaxError as exc:
        return [
            {
                "code": "syntax_error",
                "message": f"{exc.msg} (line {exc.lineno})",
                "line": str(exc.lineno or 0),
            }
        ]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _import_module_allowed(alias.name):
                    continue
                issues.append(
                    {
                        "code": "import_forbidden",
                        "message": f"Import {alias.name} — module code should use Odoo APIs only",
                        "line": str(node.lineno),
                    }
                )
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level and node.level > 0:
                # Relative imports (models/__init__.py) are required in Odoo modules.
                continue
            if mod == "odoo" or mod.startswith("odoo."):
                continue
            if _import_module_allowed(mod):
                continue
            issues.append(
                {
                    "code": "import_forbidden",
                    "message": f"Import from {node.module} — prefer Odoo model APIs",
                    "line": str(node.lineno),
                }
            )
    builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
    odoo_ok = {"self", "fields", "api", "models", "ValidationError", "UserError", "_"}
    for name in sorted(names):
        if name.startswith("_") or name in builtins or name in odoo_ok:
            continue
        if name[0].isupper():
            continue
    return issues


def lint_xml(content: str) -> list[dict[str, str]]:
    try:
        ET.fromstring(content or "<odoo/>")
        return []
    except ET.ParseError as exc:
        return [{"code": "xml_malformed", "message": str(exc), "line": "0"}]


def lint_custom_code_blocks(spec: dict[str, Any]) -> dict[str, Any]:
    blocks = [normalize_block(b) for b in merge_custom_code_blocks(spec)]
    results: list[dict[str, Any]] = []
    ok = True
    for i, block in enumerate(blocks):
        content = block.get("content") or ""
        kind = str(block.get("kind") or "")
        if kind.startswith("xml") or block.get("source_file", "").endswith(".xml"):
            issues = lint_xml(content)
        elif str(block.get("source_file") or "").endswith(".pot"):
            issues = []
        else:
            issues = lint_python(content, source_file=str(block.get("source_file")))
        if issues:
            ok = False
        results.append(
            {
                "index": i,
                "source_file": block.get("source_file"),
                "kind": kind,
                "issues": issues,
            }
        )
    # Phase 4 — fold deterministic static analyzers into lint payload
    static_findings: list[dict[str, Any]] = []
    try:
        from app.ai_static_odoo import analyze_draft_static

        static = analyze_draft_static(spec)
        static_findings = list(static.get("findings") or [])
        # Critical static findings fail lint (gate zip/sandbox)
        if int(static.get("critical_count") or 0) > 0:
            ok = False
        for f in static_findings:
            if not isinstance(f, dict):
                continue
            sev = str(f.get("severity") or "medium").lower()
            # Only fail lint surface on critical static (syntax/raw SQL). High/medium stay on _static_odoo.
            if sev != "critical":
                continue
            path = str(f.get("file") or "")
            matched = False
            for row in results:
                if path and str(row.get("source_file")) == path:
                    row.setdefault("issues", []).append(
                        {
                            "code": str(f.get("rule") or "static"),
                            "message": str(f.get("message") or ""),
                            "line": str(f.get("line") or "0"),
                            "severity": f.get("severity"),
                        }
                    )
                    matched = True
                    break
            if not matched:
                results.append(
                    {
                        "index": len(results),
                        "source_file": path or "__manifest__.py",
                        "kind": "static",
                        "issues": [
                            {
                                "code": str(f.get("rule") or "static"),
                                "message": str(f.get("message") or ""),
                                "line": str(f.get("line") or "0"),
                            }
                        ],
                    }
                )
    except Exception:  # noqa: BLE001
        static_findings = []
    return {"ok": ok, "blocks": results, "static_findings": static_findings}


def model_class_skeleton(spec: dict[str, Any], model_name: str) -> str:
    models = spec.get("models") or []
    target = next((m for m in models if isinstance(m, dict) and m.get("model") == model_name), None)
    if not target:
        return f"# Model {model_name!r} not found in spec\n"
    fields = target.get("fields") or []
    lines = [
        "from odoo import api, fields, models",
        "",
        f"class {''.join(p.title() for p in model_name.replace('.', '_').split('_') if p)}(models.Model):",
        f"    _name = {model_name!r}",
        f"    _description = {target.get('description') or model_name!r}",
        "",
    ]
    for f in fields:
        if not isinstance(f, dict):
            continue
        fname = f.get("name")
        ttype = f.get("ttype") or "char"
        label = f.get("string") or fname
        if not fname or fname.startswith("_"):
            continue
        if ttype == "char":
            lines.append(f"    {fname} = fields.Char(string={label!r})")
        elif ttype == "integer":
            lines.append(f"    {fname} = fields.Integer(string={label!r})")
        elif ttype == "boolean":
            lines.append(f"    {fname} = fields.Boolean(string={label!r})")
        elif ttype == "float":
            lines.append(f"    {fname} = fields.Float(string={label!r})")
        elif ttype == "many2one":
            rel = f.get("relation") or "res.partner"
            lines.append(f"    {fname} = fields.Many2one({rel!r}, string={label!r})")
    lines.extend(
        [
            "",
            "    @api.depends()  # TODO: set depends to computed field sources",
            "    def _compute_example(self):",
            "        for rec in self:",
            "            rec.x_example = False",
            "",
            "    @api.constrains()  # TODO: field names",
            "    def _check_example(self):",
            "        for rec in self:",
            "            pass",
            "",
        ]
    )
    return "\n".join(lines)
