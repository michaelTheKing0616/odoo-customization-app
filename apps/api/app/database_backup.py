"""Database-level backup entry for the snapshot flow.

Odoo 20 removed the ``db`` service (``/web/database`` and ``dump_db``).
Odoo.sh and Odoo Online do not expose a scriptable database dump either.
This module is the only database-backup entry. It never opens those endpoints
and it does not invent a replacement dump protocol.

Inventory of former mentions (none of them call the service):

* ``OdooClient`` builds ``ServerProxy`` for ``xmlrpc/2/common`` and
  ``xmlrpc/2/object`` only. There is no ``xmlrpc/2/db`` proxy.
* ``snapshot_gate.require_production_snapshot`` can be asked for a
  ``/web/database`` backup. On major 20 that flag is cleared and a metadata
  snapshot id is accepted. The gate does not perform HTTP.
* ``rollback_tiers`` names tier 1 as ``/web/database`` with ``live_restore``
  false. It does not restore.
"""

from __future__ import annotations

from typing import Any

MAJOR_20_HOST_BACKUP_MESSAGE = (
    "Odoo 20 has no database service. Take the database backup on the host "
    "(Odoo Online, Odoo.sh, or the server). This app does not call /web/database or dump_db."
)

ODOO_SH_AND_ONLINE_MESSAGE = (
    "Odoo.sh and Odoo Online do not get a database dump. Take the database backup "
    "on the host (Odoo Online, Odoo.sh, or the server). This app does not call "
    "/web/database or dump_db."
)

NO_DUMP_CLIENT_MESSAGE = (
    "Take the database backup on the server. This snapshot flow has no database "
    "dump client and does not call /web/database or dump_db."
)


def _normalize_hosting(value: str | None) -> str:
    raw = (value or "").strip().lower()
    compact = raw.replace("-", "_").replace(" ", "_").replace(".", "_")
    online_names = {"online", "odoo_online", "odoo_com"}
    if compact in online_names or raw == "odoo.com" or raw.endswith(".odoo.com"):
        return "online"
    if compact in {"odoo_sh", "sh"} or "odoo_sh" in compact or "odoo.sh" in raw:
        return "odoo_sh"
    return compact


def request_database_backup(
    *,
    odoo_major: int | None,
    hosting_hint: str | None = None,
    client: Any = None,
) -> dict[str, Any]:
    """Refuse a database dump and return the operator message.

    ``client`` is accepted so the snapshot flow can pass a live or fake client.
    This function does not read or call it, so a client that raises on
    ``/web/database`` or ``dump_db`` is never hit.
    """
    del client  # never dispatched; see module docstring
    hosting = _normalize_hosting(hosting_hint)
    if isinstance(odoo_major, int) and odoo_major >= 20:
        message = MAJOR_20_HOST_BACKUP_MESSAGE
    elif hosting in {"online", "odoo_sh"}:
        message = ODOO_SH_AND_ONLINE_MESSAGE
    else:
        message = NO_DUMP_CLIENT_MESSAGE
    return {
        "ok": False,
        "refused": True,
        "kind": "database",
        "called_db_service": False,
        "message": message,
    }
