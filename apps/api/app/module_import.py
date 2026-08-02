"""Code → ModuleSpec: parse our .meta.json, Odoo XML views, and Python model AST.

Partial fidelity by design: unmapped custom logic is preserved as ``unmapped``
entries (view-as-code), never silently dropped.
"""

from __future__ import annotations

import ast
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET


@dataclass
class ImportResult:
    spec: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    unmapped: list[dict[str, Any]] = field(default_factory=list)
    source: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        out = dict(self.spec)
        if self.unmapped:
            out["unmapped"] = self.unmapped
        out["_import"] = {
            "source": self.source,
            "warnings": self.warnings,
            "unmapped_count": len(self.unmapped),
        }
        return out


_FIELD_CTOR = {
    "Char": "char",
    "Text": "text",
    "Html": "html",
    "Integer": "integer",
    "Float": "float",
    "Boolean": "boolean",
    "Date": "date",
    "Datetime": "datetime",
    "Binary": "binary",
    "Selection": "selection",
    "Many2one": "many2one",
    "One2many": "one2many",
    "Many2many": "many2many",
    "Monetary": "monetary",
}


def _kw_str(kwargs: dict[str, Any], key: str, default: Any = None) -> Any:
    return kwargs.get(key, default)


def _call_kwargs(node: ast.Call) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kw in node.keywords:
        if kw.arg is None:
            continue
        try:
            out[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, TypeError):
            if isinstance(kw.value, ast.Constant):
                out[kw.arg] = kw.value.value
            elif isinstance(kw.value, ast.Name):
                out[kw.arg] = kw.value.id
            else:
                out[kw.arg] = None
    # positional: Many2one('res.partner', string='…')
    if node.args:
        try:
            first = ast.literal_eval(node.args[0])
            out.setdefault("comodel_name", first)
            out.setdefault("relation", first)
        except (ValueError, TypeError):
            if isinstance(node.args[0], ast.Constant):
                out.setdefault("comodel_name", node.args[0].value)
                out.setdefault("relation", node.args[0].value)
    return out


def _selection_to_odoo_str(sel: Any) -> str | None:
    if sel is None:
        return None
    if isinstance(sel, str):
        return sel
    if isinstance(sel, (list, tuple)):
        parts = []
        for item in sel:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                parts.append(f"('{item[0]}', '{item[1]}')")
        return "[" + ", ".join(parts) + "]" if parts else None
    return None


def parse_python_models(source: str, *, filename: str = "<model>") -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """AST-parse Odoo model classes. Returns (models, unmapped, warnings)."""
    models: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        warnings.append(f"{filename}: syntax error — {exc}")
        unmapped.append(
            {
                "kind": "python_file",
                "path": filename,
                "reason": "syntax_error",
                "source": source,
            }
        )
        return models, unmapped, warnings

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        # Detect models.Model / Model subclass heuristically
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Attribute):
                bases.append(f"{getattr(b.value, 'id', '')}.{b.attr}")
            elif isinstance(b, ast.Name):
                bases.append(b.id)
        is_model = any("Model" in b or "TransientModel" in b for b in bases)
        if not is_model:
            continue

        model_name: str | None = None
        description: str | None = None
        inherit: str | list[str] | None = None
        mixins: list[str] = []
        fields: list[dict[str, Any]] = []
        method_sources: list[str] = []

        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    name = target.id
                    if name == "_name":
                        try:
                            model_name = ast.literal_eval(stmt.value)
                        except (ValueError, TypeError):
                            pass
                    elif name == "_description":
                        try:
                            description = str(ast.literal_eval(stmt.value))
                        except (ValueError, TypeError):
                            pass
                    elif name == "_inherit":
                        try:
                            inherit = ast.literal_eval(stmt.value)
                        except (ValueError, TypeError):
                            pass
                    elif name.startswith("x_") or not name.startswith("_"):
                        # field assignment: x_foo = fields.Char(...)
                        if isinstance(stmt.value, ast.Call):
                            field_def = _parse_field_call(name, stmt.value)
                            if field_def:
                                fields.append(field_def)
                            else:
                                method_sources.append(ast.get_source_segment(source, stmt) or name)
                        elif name.startswith("x_"):
                            warnings.append(f"{filename}:{name} field not a fields.* call")
            elif isinstance(stmt, ast.FunctionDef):
                # Preserve methods as unmapped custom logic
                seg = ast.get_source_segment(source, stmt)
                method_sources.append(seg or f"def {stmt.name}(...)")

        if inherit and not model_name:
            model_name = inherit if isinstance(inherit, str) else (inherit[0] if inherit else None)
            mode = "inherit"
        else:
            mode = "new"

        if isinstance(inherit, list):
            mixins = [i for i in inherit if isinstance(i, str) and i.startswith("mail.")]
            if len(inherit) == 1 and not mixins:
                inherit = inherit[0]
            elif mixins and model_name:
                inherit = None

        if not model_name:
            warnings.append(f"{filename}: class {node.name} has no _name/_inherit — skipped")
            continue

        # Custom models via RPC must be x_*; keep stock inherits as inherit mode
        entry: dict[str, Any] = {
            "model": model_name,
            "description": description or node.name,
            "mode": mode if mode == "inherit" or not str(model_name).startswith("x_") else "new",
            "fields": fields,
        }
        if mode == "inherit" or (
            isinstance(inherit, str) and not str(model_name).startswith("x_")
        ):
            entry["mode"] = "inherit"
            entry["inherit"] = inherit if isinstance(inherit, str) else model_name
        if mixins:
            entry["mixins"] = mixins
        models.append(entry)

        if method_sources:
            unmapped.append(
                {
                    "kind": "python_methods",
                    "model": model_name,
                    "path": filename,
                    "reason": "custom_logic_not_editable_visually",
                    "snippets": method_sources[:20],
                }
            )

    return models, unmapped, warnings


def _parse_field_call(name: str, call: ast.Call) -> dict[str, Any] | None:
    func = call.func
    ctor = None
    if isinstance(func, ast.Attribute):
        ctor = func.attr
    elif isinstance(func, ast.Name):
        ctor = func.id
    if ctor not in _FIELD_CTOR:
        return None
    kwargs = _call_kwargs(call)
    ttype = _FIELD_CTOR[ctor]
    field: dict[str, Any] = {
        "name": name if name.startswith("x_") or True else f"x_{name}",
        "ttype": ttype,
        "string": _kw_str(kwargs, "string") or name,
    }
    # Keep original name for stock fields on inherit; normalize custom
    if not str(field["name"]).startswith("x_") and not str(field["name"]).startswith("_"):
        # stock field on inherit model — keep as-is for inherit mode
        pass
    if kwargs.get("required"):
        field["required"] = bool(kwargs["required"])
    if kwargs.get("readonly"):
        field["readonly"] = bool(kwargs["readonly"])
    rel = kwargs.get("comodel_name") or kwargs.get("relation")
    if rel:
        field["relation"] = rel
    if kwargs.get("inverse_name"):
        field["relation_field"] = kwargs["inverse_name"]
    sel = _selection_to_odoo_str(kwargs.get("selection"))
    if sel:
        field["selection"] = sel
    if kwargs.get("help"):
        field["help"] = kwargs["help"]
    return field


def parse_xml_views(source: str, *, filename: str = "<view>") -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Parse ir.ui.view records or bare form/list/kanban roots."""
    views: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        # Strip Odoo entities that break strict XML sometimes
        cleaned = re.sub(r"&\s+", "&amp; ", source)
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        warnings.append(f"{filename}: XML parse error — {exc}")
        unmapped.append(
            {
                "kind": "xml_file",
                "path": filename,
                "reason": "parse_error",
                "source": source,
            }
        )
        return views, unmapped, warnings

    records = root.findall(".//record") if root.tag != "record" else [root]
    if root.tag in {"form", "list", "tree", "kanban", "search"}:
        records = []
        views.append(
            {
                "name": filename,
                "model": "unknown",
                "type": "list" if root.tag == "tree" else root.tag,
                "arch": ET.tostring(root, encoding="unicode"),
                "mode": "primary",
            }
        )
        warnings.append(f"{filename}: bare view root — model unknown")

    for rec in records:
        model_attr = rec.get("model") or ""
        if model_attr and model_attr != "ir.ui.view":
            # non-view record — keep unmapped
            unmapped.append(
                {
                    "kind": "xml_record",
                    "path": filename,
                    "xml_id": rec.get("id"),
                    "model": model_attr,
                    "reason": "non_view_record",
                    "source": ET.tostring(rec, encoding="unicode"),
                }
            )
            continue
        fields_map: dict[str, str] = {}
        arch = ""
        for f in rec.findall("field"):
            fname = f.get("name") or ""
            if fname == "arch":
                if len(f):
                    arch = "".join(ET.tostring(c, encoding="unicode") for c in list(f))
                else:
                    arch = f.text or ""
            else:
                fields_map[fname] = (f.text or "").strip()
        vtype = fields_map.get("type") or "form"
        model = fields_map.get("model")
        vname = fields_map.get("name") or rec.get("id") or filename
        if not model:
            warnings.append(f"{filename}: view {vname} missing model")
            continue
        if vtype == "tree":
            vtype = "list"
        views.append(
            {
                "name": vname,
                "model": model,
                "type": vtype,
                "arch": arch,
                "mode": "extension" if fields_map.get("inherit_id") else "primary",
                "inherit_xml_id": None,
            }
        )

    return views, unmapped, warnings


def parse_meta_json(data: dict[str, Any] | str) -> ImportResult:
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError(".meta.json must be an object")
    spec = data.get("spec") if isinstance(data.get("spec"), dict) else data
    if not isinstance(spec, dict):
        raise ValueError(".meta.json missing spec object")
    return ImportResult(spec=dict(spec), source="meta.json", warnings=["loaded from .meta.json sidecar"])


def import_module_archive(content: bytes, *, filename: str = "module.zip") -> ImportResult:
    """Import a zip (or single file bytes if filename ends with .py/.xml/.json)."""
    warnings: list[str] = []
    unmapped: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    views: list[dict[str, Any]] = []
    technical_name = "imported_module"
    display_name = "Imported Module"
    depends = ["base"]

    lower = filename.lower()
    if lower.endswith(".json"):
        text = content.decode("utf-8")
        return parse_meta_json(text)

    if lower.endswith(".py"):
        ms, um, w = parse_python_models(content.decode("utf-8"), filename=filename)
        models.extend(ms)
        unmapped.extend(um)
        warnings.extend(w)
        return ImportResult(
            spec={
                "technical_name": technical_name,
                "display_name": display_name,
                "depends": depends,
                "models": models,
                "views": views,
            },
            warnings=warnings,
            unmapped=unmapped,
            source="python",
        )

    if lower.endswith(".xml"):
        vs, um, w = parse_xml_views(content.decode("utf-8"), filename=filename)
        views.extend(vs)
        unmapped.extend(um)
        warnings.extend(w)
        return ImportResult(
            spec={
                "technical_name": technical_name,
                "display_name": display_name,
                "depends": depends,
                "models": models,
                "views": views,
            },
            warnings=warnings,
            unmapped=unmapped,
            source="xml",
        )

    # Zip
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Not a valid zip: {exc}") from exc

    names = zf.namelist()
    # Prefer .meta.json
    meta_paths = [n for n in names if n.endswith(".meta.json") or n.endswith("/.meta.json")]
    if meta_paths:
        raw = zf.read(meta_paths[0]).decode("utf-8")
        result = parse_meta_json(raw)
        result.warnings.append(f"preferred {meta_paths[0]}")
        result.source = "zip+meta.json"
        return result

    # Infer technical name from top-level folder
    tops = {n.split("/")[0] for n in names if "/" in n}
    if len(tops) == 1:
        technical_name = next(iter(tops))
        display_name = technical_name.replace("_", " ").title()

    for name in names:
        if name.endswith("/"):
            continue
        base = name.rsplit("/", 1)[-1]
        try:
            data = zf.read(name)
        except KeyError:
            continue
        if base == "__manifest__.py" or base == "__openerp__.py":
            try:
                tree = ast.parse(data.decode("utf-8"))
                for node in tree.body:
                    value = None
                    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                        value = node.value
                    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
                        value = node.value
                    if value is None:
                        continue
                    manifest = ast.literal_eval(value)
                    if isinstance(manifest, dict):
                        display_name = str(manifest.get("name") or display_name)
                        deps = manifest.get("depends")
                        if isinstance(deps, list):
                            depends = [str(d) for d in deps]
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"manifest parse soft-fail: {exc}")
            continue
        if "/models/" in name.replace("\\", "/") and name.endswith(".py"):
            ms, um, w = parse_python_models(data.decode("utf-8", errors="replace"), filename=name)
            models.extend(ms)
            unmapped.extend(um)
            warnings.extend(w)
        elif name.endswith(".xml"):
            vs, um, w = parse_xml_views(data.decode("utf-8", errors="replace"), filename=name)
            views.extend(vs)
            unmapped.extend(um)
            warnings.extend(w)
        elif name.endswith(".csv") and "security" in name:
            unmapped.append(
                {
                    "kind": "security_csv",
                    "path": name,
                    "reason": "access_csv_preserved",
                    "source": data.decode("utf-8", errors="replace")[:4000],
                }
            )

    # Dedupe models by model name (merge fields)
    by_model: dict[str, dict[str, Any]] = {}
    for m in models:
        mid = m.get("model")
        if not mid:
            continue
        if mid not in by_model:
            by_model[mid] = m
            continue
        existing = {f.get("name") for f in by_model[mid].get("fields") or []}
        for f in m.get("fields") or []:
            if f.get("name") not in existing:
                by_model[mid].setdefault("fields", []).append(f)

    if not by_model and not views:
        warnings.append("No models or views detected — check module layout")

    return ImportResult(
        spec={
            "technical_name": re.sub(r"[^a-z0-9_]", "_", technical_name.lower()).strip("_")
            or "imported_module",
            "display_name": display_name,
            "depends": depends,
            "models": list(by_model.values()),
            "views": views,
        },
        warnings=warnings,
        unmapped=unmapped,
        source="zip",
    )


__all__ = [
    "ImportResult",
    "import_module_archive",
    "parse_meta_json",
    "parse_python_models",
    "parse_xml_views",
]
