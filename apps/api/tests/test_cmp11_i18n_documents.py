"""CMP-11: i18n probe/artifacts + documents connect."""

from __future__ import annotations

from typing import Any

from app.documents_connect import FOLDER_MAP_KEY, documents_gate, get_folder_map, set_model_folder
from app.i18n_artifacts import export_spec_translations_csv, import_spec_translations_csv
from app.i18n_probe import probe_i18n


class _FakeClient:
    def __init__(self, *, major: str = "19.0") -> None:
        self._major = major
        self._params: dict[str, str] = {}
        self._models = {
            "ir.model.fields",
            "res.partner",
            "x_case",
            "documents.document",
            "documents.folder",
        }
        self._modules = {"documents": "installed"}

    def server_version(self) -> dict[str, str]:
        return {"server_version": self._major}

    def model_exists(self, model: str) -> bool:
        return model in self._models

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None):
        kwargs = kwargs or {}
        if model == "ir.module.module" and method == "search_read":
            domain = args[0] if args else []
            name = domain[0][2] if domain else ""
            if name == "documents":
                return [{"name": "documents", "state": "installed"}]
            return []
        if model == "ir.model.fields" and method == "search_read":
            return [{"name": "x_name", "field_description": "Nom", "ttype": "char"}]
        if model == "ir.model.fields" and method == "search":
            return [42]
        if model == "ir.model.fields" and method == "write":
            return True
        if model == "ir.config_parameter" and method == "get_param":
            return self._params.get(args[0], args[1] if len(args) > 1 else None)
        if model == "ir.config_parameter" and method == "set_param":
            self._params[str(args[0])] = str(args[1])
            return True
        raise AssertionError(f"unexpected {model}.{method}")


def test_probe_i18n_context_lang() -> None:
    out = probe_i18n(_FakeClient())
    assert out["ok"] is True
    assert out["method"] == "context_lang"
    assert out["major"] == 19


def test_export_import_spec_translations_round_trip() -> None:
    client = _FakeClient()
    spec = {"models": [{"model": "x_case", "fields": []}]}
    csv_text = export_spec_translations_csv(client, spec=spec, lang="fr_FR")
    assert "x_case" in csv_text
    assert "Nom" in csv_text
    rows = [line.split(",") for line in csv_text.strip().splitlines()]
    dry = import_spec_translations_csv(client, rows=rows, dry_run=True)
    assert dry["updated"] == 0
    assert dry["preview"]
    live = import_spec_translations_csv(client, rows=rows, dry_run=False)
    assert live["updated"] == 1


def test_documents_folder_map_round_trip() -> None:
    client = _FakeClient()
    client._models.add("x_case")
    gate = documents_gate(client)
    assert gate["available"] is True
    set_model_folder(client, model="x_case", folder_id=7)
    mapping = get_folder_map(client)
    assert mapping["mapping"]["x_case"] == 7
    raw = client._params[FOLDER_MAP_KEY]
    assert "x_case" in raw
