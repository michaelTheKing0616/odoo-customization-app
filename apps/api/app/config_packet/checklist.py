"""Day-1 checklist from packet + optional client fingerprint."""

from __future__ import annotations

from app.config_packet.schema import (
    COA_THRESHOLD,
    ChecklistItem,
    ConfigPacket,
    InstanceFingerprint,
)
from app.config_packet.settings import SETTINGS_ALLOWLIST


def build_checklist(
    packet: ConfigPacket,
    fingerprint: InstanceFingerprint | None = None,
) -> list[ChecklistItem]:
    fp = fingerprint or packet.fingerprint
    items: list[ChecklistItem] = []

    installed = set(fp.modules_installed) if fp else set()
    for name in packet.modules:
        done = name in installed
        items.append(
            ChecklistItem(
                id=f"mod:{name}",
                label=f"Community app {name} installed",
                status="done" if done else "todo",
                surface="job_autopilot",
                href_hint="AI Studio → Job Autopilot (sandbox) then Apply config packet",
            )
        )

    if packet.accounting.journals:
        names = {n.lower() for n in (fp.journal_names if fp else [])}
        missing = [j.name for j in packet.accounting.journals if j.name.lower() not in names]
        items.append(
            ChecklistItem(
                id="journals",
                label=(
                    "Named journals present"
                    if not missing
                    else f"Create journals: {', '.join(missing)}"
                ),
                status="done" if not missing else "todo",
                surface="job_autopilot",
            )
        )

    if packet.accounting.tax_xmlids:
        have = set(fp.tax_xmlids if fp else [])
        missing_tax = [x for x in packet.accounting.tax_xmlids if x not in have]
        items.append(
            ChecklistItem(
                id="taxes",
                label=(
                    "l10n tax xmlids present on client"
                    if not missing_tax
                    else "Install matching l10n — taxes are never invented"
                ),
                status="done" if not missing_tax else "blocked",
                surface="odoo",
                href_hint="Settings → Apps → l10n pack for the company country",
            )
        )

    if packet.accounting.fiscal_positions:
        have_fp = {n.lower() for n in (fp.fiscal_position_names if fp else [])}
        missing_fp = [p.name for p in packet.accounting.fiscal_positions if p.name.lower() not in have_fp]
        items.append(
            ChecklistItem(
                id="fiscal_positions",
                label=(
                    "Fiscal positions present"
                    if not missing_fp
                    else f"Create fiscal positions: {', '.join(missing_fp)}"
                ),
                status="done" if not missing_fp else "todo",
                surface="job_autopilot",
            )
        )

    coa_ok = (fp.account_code_count if fp else packet.opening.account_code_count) >= COA_THRESHOLD
    items.append(
        ChecklistItem(
            id="coa",
            label=f"Chart of accounts ≥ {COA_THRESHOLD} codes",
            status="done" if coa_ok else "blocked",
            surface="job_autopilot",
        )
    )
    if packet.opening.tb_present:
        items.append(
            ChecklistItem(
                id="tb",
                label=(
                    "Opening trial balance ready to import (draft entry, never auto-posted)"
                    if coa_ok
                    else "Hold TB until CoA threshold — do not guess accounts"
                ),
                status="todo" if coa_ok else "blocked",
                surface="ingest",
                href_hint="Data → Import / Autopilot files (opening_trial_balance)",
            )
        )
        if packet.opening.period_lock_date or packet.opening.fiscalyear_lock_date or (
            fp and (fp.period_lock_date or fp.fiscalyear_lock_date or fp.tax_lock_date)
        ):
            items.append(
                ChecklistItem(
                    id="tb_lock",
                    label="Company lock dates set — ingest gaps if TB date is on or before the lock",
                    status="todo",
                    surface="ingest",
                    href_hint="Accounting → Settings → Lock dates (draft JE still never auto-posted)",
                )
            )

    if packet.stock.delivery_steps or packet.stock.warehouse_code:
        steps_ok = bool(fp and fp.warehouse_codes)
        items.append(
            ChecklistItem(
                id="warehouse",
                label=(
                    f"Warehouse {packet.stock.delivery_steps or packet.stock.warehouse_code or 'MAIN'}"
                ),
                status="done" if steps_ok else "todo",
                surface="job_autopilot",
            )
        )

    for user in packet.users:
        have_user = bool(fp and user.login.lower() in {u.lower() for u in fp.user_logins})
        items.append(
            ChecklistItem(
                id=f"user:{user.login}",
                label=f"User {user.login} (reset mail — no password in packet)",
                status="done" if have_user else "todo",
                surface="ingest",
                href_hint="Attach users.csv on Job Autopilot or Data → Import",
            )
        )

    for conn in packet.connectors:
        if not conn.needs_secret:
            continue
        items.append(
            ChecklistItem(
                id=f"secret:{conn.id}",
                label=f"Paste {conn.title} keys in Odoo ({', '.join(conn.brands) or conn.id})",
                status="secret",
                surface="odoo",
                href_hint=conn.open_hint or f"Open {conn.odoo_model} in Odoo — never store keys here",
                action_id=conn.action_id,
                odoo_model=conn.odoo_model,
            )
        )

    if packet.mail.warnings or not packet.mail.ok:
        items.append(
            ChecklistItem(
                id="smtp",
                label="Outgoing mail / alias domain on the client",
                status="secret",
                surface="odoo",
                href_hint="Settings → Technical → Outgoing Mail Servers (password stays in Odoo)",
                action_id=packet.mail.action_id,
                odoo_model=packet.mail.odoo_model or "ir.mail_server",
            )
        )
    else:
        items.append(
            ChecklistItem(
                id="smtp",
                label="Outgoing mail server present",
                status="done",
                surface="odoo",
                action_id=packet.mail.action_id,
                odoo_model=packet.mail.odoo_model or "ir.mail_server",
            )
        )

    if packet.documents.report_header or packet.documents.report_footer:
        items.append(
            ChecklistItem(
                id="letterhead",
                label="Stock document header/footer (report_header / report_footer) replayed",
                status="todo",
                surface="job_autopilot",
                href_hint="Odoo Settings → General Settings → Document Layout (text, not custom QWeb)",
                odoo_model="res.company",
            )
        )

    if packet.documents.logo_upload_needed or packet.documents.option_a_qweb_needed:
        items.append(
            ChecklistItem(
                id="brand",
                label=(
                    "Upload company logo; custom invoice/POS QWeb is Option A module zip"
                    if packet.documents.option_a_qweb_needed
                    else "Upload company logo in Odoo; stock letterhead is in the packet"
                ),
                status="todo",
                surface="instance_config",
                href_hint="Safety → Instance Config + Odoo Settings → General Settings → Document Layout",
                odoo_model="res.company",
            )
        )

    if packet.settings.values:
        items.append(
            ChecklistItem(
                id="settings",
                label=f"Allowlisted Settings ({len(packet.settings.values)} keys) replay",
                status="todo",
                surface="job_autopilot",
                href_hint=f"Allowlist: {', '.join(sorted(SETTINGS_ALLOWLIST)[:6])}…",
            )
        )

    if packet.custom_zip_present or packet.residual_models:
        items.append(
            ChecklistItem(
                id="residual",
                label=(
                    "Human Promote of residual module zip"
                    if packet.custom_zip_present
                    else f"Live Apply residual {', '.join(packet.residual_models)}"
                ),
                status="todo",
                surface="job_autopilot",
                href_hint="Job Autopilot → Promote to target (zip) or App Studio → Install",
            )
        )

    items.append(
        ChecklistItem(
            id="promote_lock",
            label="Autopilot was not run on production; this checklist is the client hop",
            status="done",
            surface="job_autopilot",
        )
    )
    return items
