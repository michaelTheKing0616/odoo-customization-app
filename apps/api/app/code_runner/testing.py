"""Script tests (item 27): run on a disposable copy of the database, then drop the copy.

The copy uses Odoo's own database manager (public /xmlrpc/2/db: duplicate_database, drop),
which needs the Odoo master password from the vault ("odoo_master_password", limited to this
connection). Where the manager is off (Odoo Online/.sh) or no password is set, the test runs as a
dry run on the live database instead, and says so.
"""

from __future__ import annotations

import secrets as _rand
import xmlrpc.client
from typing import Any

from app.code_runner import runs as rr

COPY_PREFIX = "ingenium_test_"


def evaluate(run: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    fails = []
    if expect.get("no_error", True) and run.get("error"):
        fails.append(f"Stopped with an error: {run['error'].get('message')}")
    n = len(run.get("changes") or [])
    if expect.get("max_changes") is not None and n > int(expect["max_changes"]):
        fails.append(f"{n} changes, more than the allowed {expect['max_changes']}.")
    if expect.get("min_changes") is not None and n < int(expect["min_changes"]):
        fails.append(f"{n} changes, fewer than the expected {expect['min_changes']}.")
    rows = len(run.get("results") or [])
    if expect.get("min_rows") is not None and rows < int(expect["min_rows"]):
        fails.append(f"{rows} result rows, fewer than {expect['min_rows']}.")
    if expect.get("log_contains"):
        logs = " ".join(str(e.get("msg") or "") for e in run.get("events") or [])
        if expect["log_contains"] not in logs:
            fails.append(f"The log never said '{expect['log_contains']}'.")
    return fails


def _db(url: str) -> Any:
    return xmlrpc.client.ServerProxy(url.rstrip("/") + "/xmlrpc/2/db", allow_none=True)


def _web_db(url: str, action: str, data: dict[str, str]) -> None:
    """Odoo 20 dropped the XML-RPC db service; its web database manager form does the same job."""
    import urllib.parse
    import urllib.request

    req = urllib.request.Request(url.rstrip("/") + f"/web/database/{action}", data=urllib.parse.urlencode(data).encode(),
                                 method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310 - the connection's own Odoo URL
        resp.read(200)


def _copy_exists(conn: dict[str, Any], copy: str) -> bool:
    try:
        uid = xmlrpc.client.ServerProxy(conn["url"].rstrip("/") + "/xmlrpc/2/common").authenticate(
            copy, conn["username"], conn["password"], {})
        return bool(uid)
    except Exception:  # noqa: BLE001
        return False


def duplicate(conn: dict[str, Any], master: str, copy: str) -> None:
    try:
        _db(conn["url"]).duplicate_database(master, conn["db"], copy)
    except xmlrpc.client.Fault as exc:
        if "Invalid service name" not in str(exc):
            raise
        _web_db(conn["url"], "duplicate", {"master_pwd": master, "name": conn["db"], "new_name": copy})
    if not _copy_exists(conn, copy):
        raise RuntimeError("Odoo didn't make the copy (check the master password and that the database manager is on).")


def drop(conn: dict[str, Any], master: str, copy: str) -> None:
    if not copy.startswith(COPY_PREFIX):
        raise ValueError("Only Ingenium test copies can be dropped.")
    try:
        _db(conn["url"]).drop(master, copy)
    except xmlrpc.client.Fault as exc:
        if "Invalid service name" not in str(exc):
            raise
        _web_db(conn["url"], "drop", {"master_pwd": master, "name": copy})


def run_test(connection_id: str, conn: dict[str, Any], code: str, test: dict[str, Any], master: str | None,
             secrets: dict[str, str] | None = None) -> dict[str, Any]:
    params = test.get("params") or {}
    if master:
        copy = COPY_PREFIX + _rand.token_hex(4)
        try:
            duplicate(conn, master, copy)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            for s in [master, conn.get("password") or ""]:
                if s:
                    msg = msg.replace(s, "***")
            return {"where": "none", "passed": False, "failures": [f"Couldn't copy the database: {msg[:200]}"]}
        try:
            run = rr.start(connection_id, {**conn, "db": copy, "write_mode": "standard"}, code, mode="real",
                           name=f"Test {test.get('name', '')} on a copy", params=params, wait=True, secrets=secrets)
        finally:
            try:
                drop(conn, master, copy)
            except Exception:  # noqa: BLE001
                pass
        where = "copy"
    else:
        run = rr.start(connection_id, conn, code, mode="dry", name=f"Test {test.get('name', '')} (dry run)",
                       params=params, wait=True, secrets=secrets)
        where = "dry_run"
    fails = evaluate(run, test.get("expect") or {})
    return {"where": where, "passed": not fails, "failures": fails, "run_id": run["id"],
            "note": "" if where == "copy" else "No master password in the vault, so this ran as a dry run on the live database."}
