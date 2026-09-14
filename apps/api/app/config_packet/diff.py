"""Diff a Config Packet against a client fingerprint (dry-run, no writes)."""

from __future__ import annotations

from app.config_packet.checklist import build_checklist
from app.config_packet.schema import (
    ConfigDiff,
    ConfigDiffOp,
    ConfigPacket,
    InstanceFingerprint,
)
from app.config_packet.settings import sanitize_settings


def diff_packet(packet: ConfigPacket, fingerprint: InstanceFingerprint) -> ConfigDiff:
    ops: list[ConfigDiffOp] = []
    skipped: list[str] = []
    blocked: list[str] = []
    installed = set(fingerprint.modules_installed)
    for name in packet.modules:
        if name in installed or name in {"base", "web"}:
            skipped.append(f"module {name} already installed")
            continue
        ops.append(
            ConfigDiffOp(
                op="install_module",
                target=name,
                detail=f"Install Community module {name}",
                risky=True,
            )
        )

    names = {n.lower() for n in fingerprint.journal_names}
    for journal in packet.accounting.journals:
        if journal.name.lower() in names:
            skipped.append(f"journal {journal.name} exists")
            continue
        if journal.type in {"sale", "general", "bank", "cash"} or journal.name.lower() in {
            "trust",
            "payment clearing",
            "operating bank",
        }:
            ops.append(
                ConfigDiffOp(
                    op="create_journal",
                    target=journal.code or journal.name,
                    detail=f"Create journal {journal.name!r} type={journal.type}",
                    risky=True,
                )
            )

    have_tax = set(fingerprint.tax_xmlids)
    tax_xmlids = list(packet.accounting.tax_xmlids) or [t.xmlid for t in packet.accounting.taxes]
    for xmlid in tax_xmlids:
        if xmlid in have_tax:
            skipped.append(f"tax {xmlid} present")
        else:
            blocked.append(
                f"tax {xmlid} missing — install matching l10n; never invent tax codes"
            )
            ops.append(
                ConfigDiffOp(
                    op="verify_tax",
                    target=xmlid,
                    detail="Skip create — taxes come from l10n xmlids only",
                    risky=False,
                )
            )

    have_fp = {n.lower() for n in fingerprint.fiscal_position_names}
    for pos in packet.accounting.fiscal_positions:
        if pos.name.lower() in have_fp:
            skipped.append(f"fiscal position {pos.name} exists")
            continue
        ops.append(
            ConfigDiffOp(
                op="create_fiscal_position",
                target=pos.name,
                detail=f"Create fiscal position {pos.name!r} (tax map xmlids only)",
                risky=True,
            )
        )

    for tax in packet.accounting.taxes:
        if not tax.tax_exigibility and not tax.cash_basis_account_xmlid:
            continue
        if tax.xmlid not in have_tax:
            continue
        ops.append(
            ConfigDiffOp(
                op="write_cash_basis",
                target=tax.xmlid,
                detail=(
                    f"tax_exigibility={tax.tax_exigibility} "
                    f"cash_basis={tax.cash_basis_account_xmlid}"
                ),
                risky=True,
            )
        )

    have_rec = {n.lower() for n in fingerprint.reconcile_model_names}
    for rec in packet.accounting.reconcile_models:
        if rec.name.lower() in have_rec:
            skipped.append(f"reconcile model {rec.name} exists")
            continue
        ops.append(
            ConfigDiffOp(
                op="create_reconcile_model",
                target=rec.name,
                detail=f"Create reconcile model {rec.name!r} rule_type={rec.rule_type}",
                risky=True,
            )
        )

    if packet.stock.delivery_steps or packet.stock.warehouse_code:
        if fingerprint.warehouse_codes and (
            not packet.stock.delivery_steps
            or fingerprint.warehouse_delivery_steps == packet.stock.delivery_steps
        ):
            skipped.append("warehouse already matches")
        else:
            ops.append(
                ConfigDiffOp(
                    op="write_warehouse",
                    target=packet.stock.warehouse_code or "MAIN",
                    detail=(
                        f"delivery_steps={packet.stock.delivery_steps} "
                        f"reception_steps={packet.stock.reception_steps} "
                        f"mto={packet.stock.mto} dropship={packet.stock.dropship}"
                    ),
                    risky=True,
                )
            )

    have_users = {u.lower() for u in fingerprint.user_logins}
    for user in packet.users:
        if user.login.lower() in have_users:
            skipped.append(f"user {user.login} exists")
            continue
        ops.append(
            ConfigDiffOp(
                op="create_user",
                target=user.login,
                detail="Create login without password; operator sends reset in Odoo",
                risky=True,
            )
        )

    wanted = sanitize_settings(packet.settings.values)
    current = fingerprint.settings or {}
    delta = {k: v for k, v in wanted.items() if current.get(k) != v}
    if delta:
        ops.append(
            ConfigDiffOp(
                op="write_settings",
                target="res.config.settings",
                detail=f"Allowlisted keys: {sorted(delta)}",
                risky=True,
            )
        )

    if packet.company.name or packet.company.currency:
        ops.append(
            ConfigDiffOp(
                op="write_company",
                target="res.company",
                detail=(
                    f"name={packet.company.name} currency={packet.company.currency} "
                    f"country={packet.company.country_code}"
                ),
                risky=True,
            )
        )

    if (
        packet.documents.paperformat_name
        or packet.documents.primary_color
        or packet.documents.font
        or packet.documents.layout_background
        or packet.documents.external_report_layout_xmlid
        or packet.documents.report_header
        or packet.documents.report_footer
    ):
        ops.append(
            ConfigDiffOp(
                op="write_layout",
                target="res.company",
                detail=(
                    "Paperformat / colors / stock report_header+footer "
                    "(logo stays a human upload; custom QWeb is Option A)"
                ),
                risky=False,
            )
        )

    for conn in packet.connectors:
        if conn.needs_secret:
            ops.append(
                ConfigDiffOp(
                    op="secret_handoff",
                    target=conn.id,
                    detail=conn.open_hint or f"Paste keys on {conn.odoo_model} in Odoo",
                    risky=False,
                )
            )

    checklist = build_checklist(packet, fingerprint)
    n_write = sum(
        1
        for o in ops
        if o.op
        not in {
            "skip",
            "secret_handoff",
            "verify_tax",
        }
    )
    return ConfigDiff(
        ops=ops,
        skipped=skipped,
        blocked=blocked,
        checklist=checklist,
        message=(
            f"{n_write} write op(s), {len(skipped)} skip(s), {len(blocked)} block(s). "
            "Autopilot is not run. Secrets stay out of the packet."
        ),
    )
