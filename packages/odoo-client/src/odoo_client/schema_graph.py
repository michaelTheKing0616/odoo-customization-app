"""Schema graph over the read plane. It never writes and it never calls a model."""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

from odoo_client.read_plane import ReadPlane
from odoo_client.schema_fingerprint import schema_fingerprint

ROW_CAP = 200
SAMPLE_CAP = 5
_USAGE_MODELS = (
    ("ir.ui.view", "arch_db", ("model",)),
    ("base.automation", "filter_domain", ("model_name",)),
    ("ir.rule", "domain_force", ("model_id",)),
    ("ir.actions.server", "code", ("model_name",)),
    ("mail.template", "body_html", ("model",)),
    ("ir.filters", "domain", ("model_id",)),
)


def _mentions(text: str, field: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(field)}(?![\w])", text) is not None


def _declared_models(row: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for key in ("model", "model_name"):
        value = row.get(key)
        if isinstance(value, str) and value:
            found.add(value)
    model_id = row.get("model_id")
    if isinstance(model_id, (list, tuple)) and len(model_id) > 1 and isinstance(model_id[1], str):
        found.add(model_id[1])
    return found


def xpath_matches(arch: str, selector: str) -> int:
    if "<!DOCTYPE" in arch.upper() or "<!ENTITY" in arch.upper():
        raise ValueError("entities are disabled")
    root = ElementTree.fromstring(arch)
    path = selector if selector.startswith(".//") or selector.startswith("/") else f".//{selector}"
    return len(root.findall(path))


class SchemaGraph:
    def __init__(self, plane: ReadPlane) -> None:
        self._plane = plane

    def describe_model(self, model: str) -> dict[str, Any]:
        fields = self._plane.call(model, "fields_get", [], {"attributes": ["type", "relation", "string"]})
        if not isinstance(fields, dict):
            raise TypeError("fields_get must return a dict")
        relations = {
            name: meta.get("relation")
            for name, meta in fields.items()
            if isinstance(meta, dict) and meta.get("type") in {"many2one", "one2many", "many2many"} and meta.get("relation")
        }
        described = {"model": model, "fields": sorted(fields), "relations": relations}
        described["fingerprint"] = schema_fingerprint(described)
        return described

    def search_read(self, model: str, domain: list[Any], fields: list[str]) -> dict[str, Any]:
        rows = self._plane.call(
            model,
            "search_read",
            [],
            {"domain": domain, "fields": fields, "limit": ROW_CAP + 1},
        )
        if not isinstance(rows, list):
            raise TypeError("search_read must return a list")
        truncated = len(rows) > ROW_CAP
        return {"rows": rows[:ROW_CAP], "truncated": truncated}

    def sample_rows(self, model: str, domain: list[Any], fields: list[str]) -> list[dict[str, Any]]:
        """Return at most SAMPLE_CAP rows. The search itself still stops at ROW_CAP."""
        page = self.search_read(model, domain, fields)
        return list(page["rows"][:SAMPLE_CAP])

    def find_usages(self, model: str, field: str) -> list[dict[str, str]]:
        hits: list[dict[str, str]] = []
        for usage_model, column, model_fields in _USAGE_MODELS:
            page = self.search_read(usage_model, [], ["id", "name", column, *model_fields])
            for row in page["rows"]:
                if not isinstance(row, dict):
                    continue
                if _declared_models(row) != {model}:
                    continue
                text = str(row.get(column) or "")
                if _mentions(text, field):
                    hits.append(
                        {
                            "model": usage_model,
                            "id": str(row.get("id") or ""),
                            "name": str(row.get("name") or ""),
                            "column": column,
                        }
                    )
        return hits

    def combined_arch(self, model: str, view_type: str = "form") -> str:
        result = self._plane.call(model, "get_view", [], {"view_type": view_type})
        if not isinstance(result, dict) or not isinstance(result.get("arch"), str):
            raise TypeError("get_view must return an arch string")
        return result["arch"]
