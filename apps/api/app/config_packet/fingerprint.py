"""Read-only instance fingerprint — skip work the client already has."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.config_packet import rpc
from app.config_packet.schema import ConfigMailHealth, InstanceFingerprint
from app.config_packet.settings import capture_settings

_SMTP_ACTION_XMLIDS = (
    "base.action_ir_mail_server_tree",
    "base.ir_mail_server_list",
)
_LOCK_DATE_FIELDS = ("period_lock_date", "fiscalyear_lock_date", "tax_lock_date")


def _sha(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def probe_mail_health(client: Any) -> ConfigMailHealth:
    warnings: list[str] = []
    smtp = 0
    aliases = 0
    if rpc.exists(client, "ir.mail_server"):
        smtp = len(rpc.search_ids(client, "ir.mail_server", [], limit=20))
        if smtp == 0:
            warnings.append(
                "No outgoing mail server. Paste SMTP on the client in Odoo Settings → "
                "Technical → Outgoing Mail Servers. Config Packet never stores the password."
            )
    else:
        warnings.append("ir.mail_server missing — mail module not installed.")
    if rpc.exists(client, "mail.alias.domain"):
        aliases = len(rpc.search_ids(client, "mail.alias.domain", [], limit=20))
        if aliases == 0:
            warnings.append("No alias domain — catchall/aliases will bounce until configured in Odoo.")
    ok = smtp > 0
    action_id, _xmlid = rpc.action_id_for_xmlids(client, _SMTP_ACTION_XMLIDS)
    if action_id is None:
        action_id = rpc.action_id_for_model(client, "ir.mail_server")
    return ConfigMailHealth(
        smtp_servers=smtp,
        alias_domains=aliases,
        ok=ok,
        warnings=warnings,
        action_id=action_id,
        odoo_model="ir.mail_server",
    )


def read_company_lock_dates(client: Any) -> dict[str, str | None]:
    """ISO dates from res.company. Empty when Accounting is not installed."""
    out: dict[str, str | None] = {k: None for k in _LOCK_DATE_FIELDS}
    if not rpc.exists(client, "res.company"):
        return out
    fields = [f for f in _LOCK_DATE_FIELDS if rpc.field_exists(client, "res.company", f)]
    if not fields:
        return out
    rows = rpc.search_read(client, "res.company", [], fields, limit=1)
    if not rows:
        return out
    row = rows[0]
    for key in _LOCK_DATE_FIELDS:
        raw = row.get(key)
        if raw:
            out[key] = str(raw)[:10]
    return out


def fingerprint_instance(client: Any) -> InstanceFingerprint:
    """RPC snapshot of stock config. Never writes."""
    warnings: list[str] = []
    modules: list[str] = []
    if rpc.exists(client, "ir.module.module"):
        rows = rpc.search_read(
            client,
            "ir.module.module",
            [("state", "=", "installed")],
            ["name"],
            limit=400,
        )
        modules = sorted(str(r.get("name") or "") for r in rows if r.get("name"))

    journal_types: list[str] = []
    journal_names: list[str] = []
    if rpc.exists(client, "account.journal"):
        rows = rpc.search_read(
            client,
            "account.journal",
            [],
            ["name", "type", "code"],
            limit=40,
        )
        journal_types = sorted({str(r.get("type") or "") for r in rows if r.get("type")})
        journal_names = [str(r.get("name") or "") for r in rows if r.get("name")]

    warehouse_codes: list[str] = []
    delivery_steps: str | None = None
    if rpc.exists(client, "stock.warehouse"):
        fields = ["code", "name"]
        if rpc.field_exists(client, "stock.warehouse", "delivery_steps"):
            fields.append("delivery_steps")
        rows = rpc.search_read(client, "stock.warehouse", [], fields, limit=8)
        warehouse_codes = [str(r.get("code") or "") for r in rows if r.get("code")]
        if rows:
            delivery_steps = str(rows[0].get("delivery_steps") or "") or None

    tax_xmlids: list[str] = []
    if rpc.exists(client, "account.tax"):
        tax_ids = rpc.search_ids(client, "account.tax", [], limit=40)
        mapping = rpc.xmlids_for_records(client, "account.tax", tax_ids)
        tax_xmlids = sorted(mapping.values())

    fiscal_position_names: list[str] = []
    if rpc.exists(client, "account.fiscal.position"):
        frows = rpc.search_read(client, "account.fiscal.position", [], ["name"], limit=20)
        fiscal_position_names = [str(r.get("name") or "") for r in frows if r.get("name")]

    reconcile_model_names: list[str] = []
    if rpc.exists(client, "account.reconcile.model"):
        rrows = rpc.search_read(client, "account.reconcile.model", [], ["name"], limit=20)
        reconcile_model_names = [str(r.get("name") or "") for r in rrows if r.get("name")]

    user_logins: list[str] = []
    if rpc.exists(client, "res.users"):
        rows = rpc.search_read(
            client,
            "res.users",
            [("share", "=", False)] if rpc.field_exists(client, "res.users", "share") else [],
            ["login"],
            limit=80,
            context={"active_test": False},
        )
        user_logins = [str(r.get("login") or "").lower() for r in rows if r.get("login")]

    account_count = 0
    if rpc.exists(client, "account.account"):
        try:
            account_count = int(client.execute_kw("account.account", "search_count", [[]]) or 0)
        except Exception:  # noqa: BLE001
            account_count = len(rpc.search_ids(client, "account.account", [], limit=5000))

    company_name = None
    currency = None
    country_code = None
    paperformat_name = None
    lock_dates = read_company_lock_dates(client)
    if rpc.exists(client, "res.company"):
        cfields = ["name", "currency_id", "country_id"]
        if rpc.field_exists(client, "res.company", "paperformat_id"):
            cfields.append("paperformat_id")
        rows = rpc.search_read(client, "res.company", [], cfields, limit=1)
        if rows:
            company_name = str(rows[0].get("name") or "") or None
            currency = rpc.m2o_name(rows[0].get("currency_id"))
            country = rpc.m2o_name(rows[0].get("country_id"))
            country_code = None
            cid = rpc.m2o_id(rows[0].get("country_id"))
            if cid and rpc.exists(client, "res.country"):
                crow = rpc.search_read(
                    client, "res.country", [("id", "=", cid)], ["code"], limit=1
                )
                if crow:
                    country_code = str(crow[0].get("code") or "") or None
            if not country_code and country:
                country_code = country
            paperformat_name = rpc.m2o_name(rows[0].get("paperformat_id"))

    major = None
    try:
        ver = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", "base")]],
            {"fields": ["latest_version"], "limit": 1},
        )
        if ver:
            latest = str(ver[0].get("latest_version") or "")
            if latest:
                major = int(latest.split(".", 1)[0])
    except Exception:  # noqa: BLE001
        warnings.append("Could not read Odoo major from base module.")

    mail = probe_mail_health(client)
    settings = capture_settings(client)
    fp = InstanceFingerprint(
        major=major,
        modules_installed=modules,
        journal_types=journal_types,
        journal_names=journal_names,
        warehouse_codes=warehouse_codes,
        warehouse_delivery_steps=delivery_steps,
        tax_xmlids=tax_xmlids,
        user_logins=user_logins,
        account_code_count=account_count,
        company_name=company_name,
        currency=currency,
        country_code=country_code,
        settings=settings,
        mail=mail,
        paperformat_name=paperformat_name,
        fiscal_position_names=fiscal_position_names,
        reconcile_model_names=reconcile_model_names,
        period_lock_date=lock_dates.get("period_lock_date"),
        fiscalyear_lock_date=lock_dates.get("fiscalyear_lock_date"),
        tax_lock_date=lock_dates.get("tax_lock_date"),
        warnings=warnings + list(mail.warnings),
    )
    dumped = fp.model_dump(mode="json")
    dumped.pop("sha256", None)
    fp.sha256 = _sha(dumped)
    return fp
