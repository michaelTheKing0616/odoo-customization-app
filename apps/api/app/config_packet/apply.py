"""Apply a Config Packet delta onto a connection — never Autopilot-on-prod."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config_packet.diff import diff_packet
from app.config_packet.fingerprint import fingerprint_instance
from app.config_packet.schema import ConfigApplyReport, ConfigPacket
from app.config_packet.settings import apply_settings, sanitize_settings
from app.config_packet.users import provision_users
from app.job_autopilot.sandbox_gate import classify_connection
from app.snapshots import CONFIRM_PHRASE, require_advanced_confirmation, save_snapshot

APPLY_WARNING = (
    "This applies a sandbox-proven Config Packet onto THIS connection: missing "
    "Community modules, named journals, warehouse steps, allowlisted Settings, "
    "and user logins (no passwords). It is not Job Autopilot. Production Autopilot "
    "stays refused. Secrets (SMTP, Paystack) stay a paste-in-Odoo checklist."
)
APPLY_RISKS = [
    "May install Community modules on this database",
    "May create journals / users / warehouse writes / fiscal positions / rec models",
    "Does not clone or dump a production database",
    "Does not write API keys, SMTP passwords, or ir.config_parameter secrets",
    "Taxes are verified by xmlid only — never invented; cash basis writes existing taxes only",
    "Does not replace UAT sign-off",
]


def apply_config_packet(
    *,
    client: Any,
    connection: Any,
    packet: ConfigPacket,
    db: Session | None = None,
    confirm_advanced: bool = False,
    confirm_phrase: str | None = None,
) -> ConfigApplyReport:
    kind, _unattended = classify_connection(connection)
    if kind == "observer":
        return ConfigApplyReport(
            ok=False,
            refused=True,
            refuse_reason="Observer connections cannot apply configuration.",
            target_kind=kind,
            message="Observer refused.",
        )
    require_advanced_confirmation(
        confirm_advanced=confirm_advanced,
        confirm_phrase=confirm_phrase,
        warning=APPLY_WARNING + f" Target kind={kind}.",
        risks=APPLY_RISKS,
    )

    fingerprint = fingerprint_instance(client)
    delta = diff_packet(packet, fingerprint)
    snapshot_id = None
    if db is not None:
        connection_id = str(getattr(connection, "id", "") or "")
        snap = save_snapshot(
            db,
            connection_id=connection_id,
            resource_type="config_packet",
            resource_key=f"config_packet:{packet.sha256 or 'na'}",
            label="Config Packet apply (pre-write fingerprint)",
            payload={"fingerprint": fingerprint.model_dump(mode="json")},
            reversible="partial",
        )
        snapshot_id = str(snap.id)

    applied: list[str] = []
    skipped = list(delta.skipped)
    warnings = list(fingerprint.warnings)

    from app.job_autopilot.bootstrap import install_named_modules
    from app.job_autopilot.stock_kits import apply_stock_kit, apply_named_journals

    module_names = [
        op.target for op in delta.ops if op.op == "install_module"
    ]
    if module_names:
        boot = install_named_modules(client, module_names)
        applied.extend(f"install:{n}" for n in boot.installed)
        skipped.extend(f"already:{n}" for n in boot.already_installed)
        warnings.extend(boot.warnings)

    if any(op.op == "create_journal" for op in delta.ops):
        created = apply_named_journals(client, packet.accounting.journals)
        applied.extend(created)

    if any(op.op == "write_warehouse" for op in delta.ops):
        detail = apply_stock_kit(client, packet.stock)
        if detail:
            applied.append(detail)

    if any(op.op == "create_user" for op in delta.ops):
        created, existing, user_warn = provision_users(client, packet.users)
        if created:
            applied.append(f"users created={created}")
        if existing:
            skipped.append(f"users existing={existing}")
        warnings.extend(user_warn)

    if any(
        op.op in {"create_fiscal_position", "write_cash_basis", "create_reconcile_model"}
        for op in delta.ops
    ):
        from app.config_packet.fiscal import apply_fiscal_kit

        fiscal_applied = apply_fiscal_kit(client, packet.accounting)
        applied.extend(fiscal_applied)

    if any(op.op == "write_settings" for op in delta.ops):
        msg = apply_settings(client, sanitize_settings(packet.settings.values))
        if msg:
            applied.append(msg)

    if any(op.op == "write_company" for op in delta.ops):
        from app.job_autopilot.stock_kits import apply_company_identity

        msg = apply_company_identity(client, packet.company)
        if msg:
            applied.append(msg)

    if any(op.op == "write_layout" for op in delta.ops):
        from app.job_autopilot.stock_kits import apply_document_layout

        msg = apply_document_layout(client, packet.documents)
        if msg:
            applied.append(msg)

    for op in delta.ops:
        if op.op == "secret_handoff":
            skipped.append(f"secret {op.target}: paste in Odoo — {op.detail}")
        if op.op == "verify_tax" and op.target not in fingerprint.tax_xmlids:
            warnings.append(op.detail)

    blocked = list(delta.blocked)
    ok = not blocked or any(a.startswith("install:") for a in applied) or bool(applied)
    if blocked and not applied:
        ok = False
    return ConfigApplyReport(
        ok=ok,
        snapshot_id=snapshot_id,
        applied=applied,
        skipped=skipped + blocked,
        warnings=warnings,
        checklist=delta.checklist,
        target_kind=kind,
        message=(
            f"Config Packet apply on {kind}: {len(applied)} write(s). "
            f"Confirm phrase was {CONFIRM_PHRASE!r}. Autopilot was not run."
        ),
    )
