"""DEV-1 — per-instance probe for live state=code server actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from odoo_client.client import OdooClient


def _selection_values(fields_get: dict[str, Any], field: str) -> set[str]:
    meta = fields_get.get(field) or {}
    sel = meta.get("selection")
    if not sel:
        return set()
    out: set[str] = set()
    for item in sel:
        if isinstance(item, (list, tuple)) and item:
            out.add(str(item[0]))
    return out


def probe_code_server_actions(client: OdooClient) -> dict[str, Any]:
    """Verify ir.actions.server accepts state=code via selection + create/run/unlink round-trip."""
    major = int(getattr(client.capabilities, "major", 19) or 19)
    result: dict[str, Any] = {
        "key": "code_server_actions",
        "major": major,
        "supported": False,
        "state_in_selection": False,
        "round_trip_ok": False,
        "error": None,
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "source": "live",
    }
    action_id: int | None = None
    try:
        fg = client.execute_kw(
            "ir.actions.server",
            "fields_get",
            [],
            {"attributes": ["selection", "type"]},
        )
        states = _selection_values(fg, "state")
        result["state_in_selection"] = "code" in states
        if not result["state_in_selection"]:
            result["error"] = "ir.actions.server.state selection does not include 'code'"
            return result

        partner_model_id = client.execute_kw(
            "ir.model",
            "search",
            [[("model", "=", "res.partner")]],
            {"limit": 1},
        )
        if not partner_model_id:
            result["error"] = "res.partner model not found for probe"
            return result

        action_id = int(
            client.execute_kw(
                "ir.actions.server",
                "create",
                [
                    {
                        "name": "OC Code Studio probe (ephemeral)",
                        "model_id": partner_model_id[0],
                        "state": "code",
                        "code": "x = 1",
                    }
                ],
            )
        )
        try:
            client.execute_kw(
                "ir.actions.server",
                "run",
                [[action_id]],
                {"context": {}},
            )
            result["round_trip_ok"] = True
            result["supported"] = True
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"run failed: {exc}"
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    finally:
        if action_id is not None:
            try:
                client.execute_kw("ir.actions.server", "unlink", [[action_id]])
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_error"] = str(cleanup_exc)
    return result


def parse_stored_probe(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def probe_supported(probe: dict[str, Any] | None) -> bool:
    return bool(probe and probe.get("supported"))
