"""DEV-2 — custom_code_blocks authoring, lint, skeleton helpers."""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from typing import Any

from app.module_spec_codec import merge_custom_code_blocks


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
                issues.append(
                    {
                        "code": "import_forbidden",
                        "message": f"Import {alias.name} — module code should use Odoo APIs only",
                        "line": str(node.lineno),
                    }
                )
        if isinstance(node, ast.ImportFrom):
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
    return {"ok": ok, "blocks": results}


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
