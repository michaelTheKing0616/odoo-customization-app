"""User roster — logins + group xmlids, never passwords."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from app.config_packet import rpc
from app.config_packet.schema import ConfigUser

_SKIP_LOGINS = frozenset({"admin", "admin@example.com", "odoo", "demo", "portal"})
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

# Role needle → xml id. Missing groups are skipped, not invented.
ROLE_GROUPS: tuple[tuple[str, str], ...] = (
    ("sales", "sales_team.group_sale_salesman"),
    ("accountant", "account.group_account_invoice"),
    ("warehouse", "stock.group_stock_user"),
    ("hr", "hr.group_hr_user"),
    ("purchase", "purchase.group_purchase_user"),
    ("project", "project.group_project_user"),
    ("pos", "point_of_sale.group_pos_user"),
    ("crm", "sales_team.group_sale_salesman"),
)


def parse_roster_csv(text: str) -> list[ConfigUser]:
    """Parse users.csv: login/email, name, groups (comma xmlids or role needles)."""
    raw = (text or "").lstrip("\ufeff")
    if not raw.strip():
        return []
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        return []
    headers = {str(h or "").strip().lower(): str(h or "") for h in reader.fieldnames}
    users: list[ConfigUser] = []
    for row in reader:
        if not isinstance(row, dict):
            continue
        login = (
            _cell(row, headers, "login")
            or _cell(row, headers, "email")
            or _cell(row, headers, "work_email")
        ).strip().lower()
        if not login or login in _SKIP_LOGINS:
            continue
        name = _cell(row, headers, "name") or login.split("@")[0]
        email = _cell(row, headers, "email") or (login if "@" in login else "")
        groups_raw = _cell(row, headers, "groups") or _cell(row, headers, "group_xmlids") or _cell(
            row, headers, "roles"
        )
        group_xmlids = _parse_groups(groups_raw)
        users.append(
            ConfigUser(
                login=login,
                name=name,
                email=email or login,
                group_xmlids=group_xmlids,
            )
        )
    return users[:50]


def users_from_emails(emails: list[str], *, roles: list[str] | None = None) -> list[ConfigUser]:
    xmlids = role_xmlids(roles or [])
    out: list[ConfigUser] = []
    for raw in emails:
        login = str(raw or "").strip().lower()
        if not login or "@" not in login or login in _SKIP_LOGINS:
            continue
        out.append(
            ConfigUser(
                login=login,
                name=login.split("@")[0],
                email=login,
                group_xmlids=list(xmlids),
            )
        )
    return out[:12]


def role_xmlids(roles: list[str]) -> list[str]:
    blob = " ".join(roles).lower()
    ids: list[str] = ["base.group_user"]
    for needle, xmlid in ROLE_GROUPS:
        if needle in blob:
            ids.append(xmlid)
    return list(dict.fromkeys(ids))


def provision_users(client: Any, users: list[ConfigUser]) -> tuple[int, int, list[str]]:
    """Create missing logins. Never sets password. Odoo 19 uses group_ids."""
    warnings: list[str] = []
    if not rpc.exists(client, "res.users"):
        return 0, 0, ["res.users missing"]
    field = rpc.user_groups_field(client)
    created = 0
    existing = 0
    for user in users:
        login = (user.login or "").strip().lower()
        if not login or login in _SKIP_LOGINS:
            continue
        found = rpc.search_ids(client, "res.users", [("login", "=", login)], limit=1)
        if found:
            existing += 1
            continue
        group_ids = _resolve_groups(client, user.group_xmlids)
        vals: dict[str, Any] = {
            "name": user.name or login.split("@")[0],
            "login": login,
            "email": user.email or login,
        }
        if group_ids:
            vals[field] = [(6, 0, group_ids)]
        try:
            client.execute_kw("res.users", "create", [vals])
            created += 1
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"User {login} skipped: {exc}")
    return created, existing, warnings


def _resolve_groups(client: Any, xmlids: list[str]) -> list[int]:
    ids: list[int] = []
    for xmlid in xmlids or ["base.group_user"]:
        gid = rpc.xml_id(client, xmlid)
        if gid:
            ids.append(gid)
    return list(dict.fromkeys(ids))


def _parse_groups(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return ["base.group_user"]
    parts = [p.strip() for p in re.split(r"[,;|]", text) if p.strip()]
    xmlids: list[str] = ["base.group_user"]
    for part in parts:
        if "." in part and " " not in part:
            xmlids.append(part)
        else:
            xmlids.extend(role_xmlids([part]))
    return list(dict.fromkeys(xmlids))


def _cell(row: dict[str, Any], headers: dict[str, str], key: str) -> str:
    src = headers.get(key)
    if src is None:
        return ""
    return str(row.get(src) or "").strip()


def looks_like_user_roster(filename: str, headers: list[str] | None = None) -> bool:
    name = (filename or "").lower()
    if re.search(r"\b(users?|logins?)\.(csv|xlsx|xls)\b", name) or "users.csv" in name:
        return True
    hdrs = {h.lower() for h in (headers or [])}
    return "login" in hdrs and ("groups" in hdrs or "group_xmlids" in hdrs or "roles" in hdrs)


def emails_in_text(text: str) -> list[str]:
    found: list[str] = []
    for match in _EMAIL_RE.finditer(text or ""):
        email = match.group(0).lower()
        if email not in _SKIP_LOGINS and email not in found:
            found.append(email)
    return found


USERS_CSV_TEMPLATE = (
    "login,name,email,groups\n"
    "ada@studio.test,Ada Lovelace,ada@studio.test,\"base.group_user,sales\"\n"
    "warehouse@studio.test,Warehouse User,warehouse@studio.test,warehouse\n"
)


def users_csv_template() -> str:
    """Spreadsheet header matching ``parse_roster_csv``. Never includes a password column."""
    return USERS_CSV_TEMPLATE
