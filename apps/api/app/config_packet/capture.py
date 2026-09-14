"""Serialize a proven sandbox Autopilot run into a Config Packet."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.config_packet.checklist import build_checklist
from app.config_packet.fingerprint import fingerprint_instance, probe_mail_health
from app.config_packet.fiscal import (
    capture_fiscal_positions,
    capture_reconcile_models,
    capture_taxes,
)
from app.config_packet.schema import (
    COA_THRESHOLD,
    ConfigAccounting,
    ConfigCompany,
    ConfigConnector,
    ConfigDocuments,
    ConfigJournal,
    ConfigOpening,
    ConfigPacket,
    ConfigSales,
    ConfigSettings,
    ConfigSmoke,
    ConfigStock,
    ConfigUser,
)
from app.config_packet.settings import capture_settings, sanitize_settings
from app.config_packet.users import parse_roster_csv, users_from_emails
from app.job_autopilot.connectors.catalog import CONNECTOR_ORDER, SPECS, detected_brands
from app.job_autopilot.packet import AutopilotResult, JobPacket
from app.job_autopilot.recipes import RECIPE_VERSION

_CONNECTOR_MODELS: dict[str, str] = {
    "payments": "payment.provider",
    "inbound_orders": "sale.order",
    "messaging": "mail.channel",
    "hardware": "pos.config",
    "statutory_payroll": "hr.employee",
}

_CONNECTOR_ACTION_XMLIDS: dict[str, tuple[str, ...]] = {
    "payments": ("payment.action_payment_provider", "payment.action_payment_acquirer"),
    "inbound_orders": ("sale.action_orders",),
    "messaging": ("mail.action_discuss", "discuss.action_discuss"),
    "hardware": ("point_of_sale.action_pos_config_pos",),
}

_CONNECTOR_HINTS: dict[str, str] = {
    "payments": "/web#action=payment.action_payment_provider&model=payment.provider",
    "inbound_orders": "/web#model=sale.order&view_type=list",
    "messaging": "/web#model=discuss.channel&view_type=list",
    "hardware": "/web#model=pos.config&view_type=list",
    "statutory_payroll": "Statutory is compute-only — no partner keys to paste",
}


def _sha(packet: ConfigPacket) -> str:
    data = packet.model_dump(mode="json")
    data.pop("sha256", None)
    blob = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _journals_from_result(result: AutopilotResult, client: Any) -> list[ConfigJournal]:
    from app.config_packet import rpc

    if not rpc.exists(client, "account.journal"):
        return []
    rows = rpc.search_read(
        client,
        "account.journal",
        [],
        ["name", "type", "code"],
        limit=40,
    )
    named = []
    for r in rows:
        name = str(r.get("name") or "")
        if name:
            named.append(
                ConfigJournal(
                    name=name,
                    type=str(r.get("type") or "general"),
                    code=str(r.get("code") or "")[:5],
                )
            )
    # Prefer brief-created named journals when probes mention them.
    return named


def _tax_xmlids(client: Any) -> list[str]:
    from app.config_packet.fiscal import capture_taxes

    return [t.xmlid for t in capture_taxes(client)]


def _stock_from_client(client: Any, packet: JobPacket) -> ConfigStock:
    from app.config_packet import rpc
    from app.job_autopilot.stock_kits import infer_warehouse_flags

    flags = infer_warehouse_flags(packet.prompt or "")
    stock = ConfigStock(
        delivery_steps=flags.get("delivery_steps"),
        reception_steps=flags.get("reception_steps"),
        lot_tracking=bool(flags.get("lot_tracking")),
        mto=bool(flags.get("mto")),
        dropship=bool(flags.get("dropship")),
    )
    if rpc.exists(client, "stock.warehouse"):
        fields = ["code", "name"]
        if rpc.field_exists(client, "stock.warehouse", "delivery_steps"):
            fields.append("delivery_steps")
        if rpc.field_exists(client, "stock.warehouse", "reception_steps"):
            fields.append("reception_steps")
        rows = rpc.search_read(client, "stock.warehouse", [], fields, limit=1)
        if rows:
            stock.warehouse_code = str(rows[0].get("code") or "") or None
            stock.warehouse_name = str(rows[0].get("name") or "") or None
            stock.delivery_steps = str(rows[0].get("delivery_steps") or stock.delivery_steps) or None
            stock.reception_steps = (
                str(rows[0].get("reception_steps") or stock.reception_steps) or None
            )
    return stock


def _documents_from_client(client: Any) -> ConfigDocuments:
    from app.config_packet import rpc

    docs = ConfigDocuments(logo_upload_needed=True)
    if not rpc.exists(client, "res.company"):
        return docs
    fields = ["name"]
    for fname in (
        "paperformat_id",
        "primary_color",
        "secondary_color",
        "external_report_layout_id",
        "layout_background",
        "font",
        "report_header",
        "report_footer",
    ):
        if rpc.field_exists(client, "res.company", fname):
            fields.append(fname)
    rows = rpc.search_read(client, "res.company", [], fields, limit=1)
    if not rows:
        return docs
    row = rows[0]
    docs.paperformat_name = rpc.m2o_name(row.get("paperformat_id"))
    if isinstance(row.get("primary_color"), str):
        docs.primary_color = row.get("primary_color")
    if isinstance(row.get("secondary_color"), str):
        docs.secondary_color = row.get("secondary_color")
    if isinstance(row.get("font"), str) and row.get("font"):
        docs.font = str(row.get("font"))
    if isinstance(row.get("layout_background"), str) and row.get("layout_background"):
        docs.layout_background = str(row.get("layout_background"))
    header = row.get("report_header")
    if isinstance(header, str) and header.strip():
        docs.report_header = header.strip()[:4000]
    footer = row.get("report_footer")
    if isinstance(footer, str) and footer.strip():
        docs.report_footer = footer.strip()[:4000]
    layout_id = rpc.m2o_id(row.get("external_report_layout_id"))
    docs.layout_xmlid = rpc.m2o_name(row.get("external_report_layout_id"))
    if layout_id and rpc.exists(client, "ir.ui.view"):
        xmlmap = rpc.xmlids_for_records(client, "ir.ui.view", [layout_id])
        docs.external_report_layout_xmlid = xmlmap.get(layout_id)
    docs.option_a_qweb_needed = False
    return docs


def _users_from_packet(job: JobPacket) -> list[ConfigUser]:
    roster: list[ConfigUser] = []
    seen: set[str] = set()
    for data in job.data_files:
        if data.doc_type in {"user_roster", "employee_roster"} or "user" in (data.filename or "").lower():
            parsed = parse_roster_csv(data.excerpt or "")
            for user in parsed:
                if user.login not in seen:
                    seen.add(user.login)
                    roster.append(user)
    for user in users_from_emails(job.org_emails, roles=job.roles or job.actors):
        if user.login not in seen:
            seen.add(user.login)
            roster.append(user)
    return roster


def _connectors(job: JobPacket, client: Any) -> list[ConfigConnector]:
    from app.config_packet import rpc

    by_id = {s.id: s for s in SPECS}
    out: list[ConfigConnector] = []
    for cid in CONNECTOR_ORDER:
        if cid not in job.connectors:
            continue
        spec = by_id.get(cid)
        brands = detected_brands(job.prompt, cid) if spec else []
        model = _CONNECTOR_MODELS.get(cid, "ir.model")
        action_id, action_xmlid = rpc.action_id_for_xmlids(
            client, _CONNECTOR_ACTION_XMLIDS.get(cid, ())
        )
        if action_id is None:
            action_id = rpc.action_id_for_model(client, model)
        out.append(
            ConfigConnector(
                id=cid,
                title=spec.title if spec else cid,
                needs_secret=cid != "statutory_payroll",
                odoo_model=model,
                brands=list(brands),
                open_hint=_CONNECTOR_HINTS.get(cid, ""),
                action_id=action_id,
                action_xmlid=action_xmlid,
            )
        )
    return out


def _smoke(result: AutopilotResult) -> ConfigSmoke:
    report = result.smoke
    if report is None:
        return ConfigSmoke()
    passed = [s.name for s in report.steps if s.ok]
    failed = [s.name for s in report.steps if not s.ok]
    processes = []
    if report.named_process:
        processes.append(report.named_process)
    for name in (
        "purchase.order",
        "purchase.order.receipt",
        "pos.config",
        "pos.session",
        "crm.lead",
        "crm.lead.won",
    ):
        if any(name in s.name for s in report.steps):
            processes.append(name)
    return ConfigSmoke(
        processes=list(dict.fromkeys(processes)),
        passed=passed,
        failed=failed,
    )


def capture_config_packet(client: Any, result: AutopilotResult) -> ConfigPacket:
    """Build a replayable packet from the sandbox after Autopilot finishes."""
    job = result.packet
    fp = fingerprint_instance(client)
    boot = result.bootstrap
    installed = list(
        dict.fromkeys(
            list(getattr(boot, "installed", None) or [])
            + list(getattr(boot, "already_installed", None) or [])
            + list(job.stock_apps)
        )
    )
    if job.l10n_module and job.l10n_module not in installed:
        installed.append(job.l10n_module)

    taxes = capture_taxes(client)
    fiscal_positions = capture_fiscal_positions(client)
    reconcile_models = capture_reconcile_models(client)
    account_count = fp.account_code_count
    tb_present = any(f.doc_type == "opening_trial_balance" for f in job.data_files)
    lock_blocked = bool(
        fp.period_lock_date or fp.fiscalyear_lock_date or fp.tax_lock_date
    )
    packet = ConfigPacket(
        recipe_version=int(
            getattr(boot, "recipe_version", RECIPE_VERSION) or RECIPE_VERSION
        ),
        source_kind=result.connection_kind or "sandbox",
        modules=installed,
        company=ConfigCompany(
            name=job.company_name or fp.company_name,
            currency=job.currency or fp.currency,
            country_code=job.country_code or fp.country_code,
        ),
        accounting=ConfigAccounting(
            journals=_journals_from_result(result, client),
            tax_xmlids=[t.xmlid for t in taxes] or _tax_xmlids(client),
            taxes=taxes,
            fiscal_position_names=[p.name for p in fiscal_positions],
            fiscal_positions=fiscal_positions,
            reconcile_models=reconcile_models,
            account_code_count=account_count,
            taxes_invented=False,
        ),
        stock=_stock_from_client(client, job),
        sales=ConfigSales(
            pricelist_name="Autopilot Public" if "sale" in job.stock_apps else None,
            pricelist_currency=job.currency or fp.currency,
        ),
        documents=_documents_from_client(client),
        users=_users_from_packet(job),
        connectors=_connectors(job, client),
        settings=ConfigSettings(values=sanitize_settings(capture_settings(client))),
        mail=probe_mail_health(client),
        ingest_plan=[f.doc_type for f in job.data_files],
        smoke=_smoke(result),
        opening=ConfigOpening(
            tb_present=tb_present,
            tb_allowed=account_count >= COA_THRESHOLD,
            account_code_count=account_count,
            lock_date_blocked=lock_blocked,
            period_lock_date=fp.period_lock_date,
            fiscalyear_lock_date=fp.fiscalyear_lock_date,
            tax_lock_date=fp.tax_lock_date,
            message=(
                f"{account_count} account codes (threshold {COA_THRESHOLD})"
                if account_count
                else "CoA not probed"
            ),
        ),
        fingerprint=fp,
        custom_zip_present=bool(
            result.custom and (result.custom.zip_base64 or getattr(result.custom, "zip_omitted", False))
        ),
        residual_models=[r.model for r in job.custom_residuals],
        secrets_excluded=True,
    )
    packet.documents.option_a_qweb_needed = bool(
        packet.custom_zip_present or packet.residual_models
    )
    packet.checklist = build_checklist(packet, fp)
    packet.sha256 = _sha(packet)
    return packet
