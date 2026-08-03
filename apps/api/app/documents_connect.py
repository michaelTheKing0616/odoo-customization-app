"""Documents folder attach config per model (CMP-11 §21)."""

from __future__ import annotations

import json
from typing import Any

from odoo_client.client import OdooClient, OdooClientError

FOLDER_MAP_KEY = "odoo_custom.documents.folder_map"


def documents_gate(client: OdooClient) -> dict[str, Any]:
    from app.ee_drivers import probe_ee_playbook_driver

    status = probe_ee_playbook_driver(
        client,
        driver_id="ee_playbook_documents",
        label="Documents folders",
        modules=["documents"],
        model="documents.document",
    )
    folder_model = (
        "documents.folder"
        if client.model_exists("documents.folder")
        else None
    )
    return {
        "ok": status.available,
        "available": status.available,
        "verify_state": status.verify_state,
        "folder_model": folder_model,
        "message": status.reason,
        "note": status.to_dict().get("note"),
    }


def _load_map(client: OdooClient) -> dict[str, int]:
    try:
        raw = client.execute_kw(
            "ir.config_parameter",
            "get_param",
            [FOLDER_MAP_KEY, "{}"],
        )
        data = json.loads(raw or "{}")
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()}
    except (OdooClientError, TypeError, ValueError):
        pass
    return {}


def _save_map(client: OdooClient, mapping: dict[str, int]) -> None:
    client.execute_kw(
        "ir.config_parameter",
        "set_param",
        [FOLDER_MAP_KEY, json.dumps(mapping)],
    )


def get_folder_map(client: OdooClient) -> dict[str, Any]:
    return {"ok": True, "mapping": _load_map(client)}


def set_model_folder(client: OdooClient, *, model: str, folder_id: int | None) -> dict[str, Any]:
    if not model.startswith("x_"):
        raise OdooClientError("Documents folder map requires custom x_* model")
    mapping = _load_map(client)
    if folder_id is None:
        mapping.pop(model, None)
    else:
        mapping[model] = int(folder_id)
    _save_map(client, mapping)
    return {"ok": True, "model": model, "folder_id": folder_id, "mapping": mapping}


def module_spec_fragment(*, model: str, folder_id: int) -> dict[str, Any]:
    return {
        "depends_add": ["documents"],
        "review_note": (
            "Module path: attach business documents to Documents folder via server action / "
            "automation — our suggestion only; verify field names on your Odoo major."
        ),
        "automations": [
            {
                "name": f"Attach {model} to Documents",
                "model": model,
                "trigger": "on_create",
                "safe_actions": [
                    {
                        "kind": "create_activity",
                        "activity_summary": f"Review documents for {model}",
                    }
                ],
            }
        ],
        "documents_folder_id": folder_id,
    }
