"""Versioned stock config recipes. RPC only — never LLM ir.config_parameter."""

from __future__ import annotations

import re
from typing import Any

from app.job_autopilot.packet import BootstrapReport, JobPacket, ProbeResult

RECIPE_VERSION = 4

_SKIP_USER_LOGINS = frozenset({"admin", "admin@example.com", "odoo", "demo"})

# Brief needles → named journals (domain-agnostic trust / clearing / operating).
_JOURNAL_NEEDLES: tuple[tuple[re.Pattern[str], str, str, str], ...] = (
    (
        re.compile(r"\b(trust\s+account|client\s+money|client\s+trust|trust\s+receipt)\b", re.I),
        "Trust",
        "general",
        "trust",
    ),
    (
        re.compile(
            r"\b(paystack\s+clearing|payment\s+clearing|stripe\s+clearing|"
            r"acquirer\s+clearing|clearing\s+journal)\b",
            re.I,
        ),
        "Payment Clearing",
        "bank",
        "pay_clear",
    ),
    (
        re.compile(r"\b(operating\s+bank|operating\s+cash)\b", re.I),
        "Operating Bank",
        "bank",
        "op_bank",
    ),
)

# Role needle → xml id. Missing groups are skipped, not invented.
_ROLE_GROUPS: tuple[tuple[str, str], ...] = (
    ("sales", "sales_team.group_sale_salesman"),
    ("accountant", "account.group_account_invoice"),
    ("warehouse", "stock.group_stock_user"),
    ("hr", "hr.group_hr_user"),
    ("purchase", "purchase.group_purchase_user"),
    ("project", "project.group_project_user"),
)


def _search(client: Any, model: str, domain: list[Any], *, limit: int = 1) -> list[int]:
    try:
        ids = client.execute_kw(model, "search", [domain], {"limit": limit})
    except Exception:  # noqa: BLE001
        return []
    if not ids:
        return []
    return [int(i) for i in ids]


def _search_read(
    client: Any,
    model: str,
    domain: list[Any],
    fields: list[str],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    try:
        rows = client.execute_kw(
            model,
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )
    except Exception:  # noqa: BLE001
        return []
    return [r for r in (rows or []) if isinstance(r, dict)]


def _exists(client: Any, model: str) -> bool:
    fn = getattr(client, "model_exists", None)
    if callable(fn):
        try:
            return bool(fn(model))
        except Exception:  # noqa: BLE001
            return False
    try:
        client.execute_kw(model, "fields_get", [], {"attributes": ["string"]})
        return True
    except Exception:  # noqa: BLE001
        return False


def _xml_id(client: Any, xml_id: str) -> int | None:
    if "." not in xml_id:
        return None
    module, name = xml_id.split(".", 1)
    rows = _search_read(
        client,
        "ir.model.data",
        [("module", "=", module), ("name", "=", name)],
        ["res_id"],
        limit=1,
    )
    if not rows:
        return None
    rid = rows[0].get("res_id")
    return int(rid) if rid else None


def _probe_coa(client: Any, report: BootstrapReport) -> None:
    if not _exists(client, "account.account"):
        report.probes.append(ProbeResult(name="coa_align", ok=False, detail="account.account missing"))
        return
    try:
        from app.ingest.coa_align import load_instance_account_codes

        codes = load_instance_account_codes(client)
    except Exception:  # noqa: BLE001
        codes = {}
        rows = _search_read(client, "account.account", [], ["code"], limit=5000)
        for r in rows:
            code = str(r.get("code") or "").strip()
            if code:
                codes[code] = r
    ok = len(codes) >= 8
    report.probes.append(
        ProbeResult(
            name="coa_align",
            ok=ok,
            detail=f"{len(codes)} account codes on instance",
        )
    )
    if not ok:
        report.warnings.append("Chart of accounts is thin — install l10n before ingesting CoA/TB.")


def _probe_journals(client: Any, report: BootstrapReport) -> None:
    if not _exists(client, "account.journal"):
        report.probes.append(ProbeResult(name="journals", ok=False, detail="account.journal missing"))
        return
    needed = ("sale", "general", "bank")
    found: list[str] = []
    for kind in needed:
        if _search(client, "account.journal", [("type", "=", kind)]):
            found.append(kind)
    ok = "sale" in found and "general" in found
    report.probes.append(
        ProbeResult(
            name="journals",
            ok=ok,
            detail=f"types present: {', '.join(found) or '(none)'}",
        )
    )
    if not ok:
        report.warnings.append("Opening journals incomplete (need sale + general at minimum).")


def _ensure_brief_journals(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    """Soft-create named journals from brief needles (trust / clearing / operating).

    Domain-agnostic — lawyers, agencies, and any vertical that says client trust.
    Never writes API keys. Skips when account.journal missing or create fails.
    """
    if not _exists(client, "account.journal"):
        return
    prompt = packet.prompt or ""
    created: list[str] = []
    existing: list[str] = []
    for pattern, name, jtype, code in _JOURNAL_NEEDLES:
        if not pattern.search(prompt):
            continue
        hit = _search(client, "account.journal", [("name", "=", name)], limit=1)
        if hit:
            existing.append(name)
            continue
        vals: dict[str, Any] = {
            "name": name,
            "type": jtype,
            "code": code[:5],
        }
        try:
            client.execute_kw("account.journal", "create", [vals])
            created.append(name)
        except Exception as exc:  # noqa: BLE001
            report.warnings.append(f"Journal {name!r} create skipped: {exc}")
    if created or existing:
        report.probes.append(
            ProbeResult(
                name="journals_named",
                ok=True,
                detail=f"created={created or []} existing={existing or []}",
            )
        )


def _probe_locations(client: Any, report: BootstrapReport) -> None:
    if not _exists(client, "stock.location"):
        report.probes.append(
            ProbeResult(name="locations", ok=False, detail="stock.location missing")
        )
        return
    ids = _search(client, "stock.location", [], limit=20)
    ok = len(ids) >= 1
    report.probes.append(
        ProbeResult(name="locations", ok=ok, detail=f"{len(ids)} location(s) visible")
    )


def _probe_uom(client: Any, report: BootstrapReport) -> None:
    model = "uom.uom" if _exists(client, "uom.uom") else None
    if model is None and _exists(client, "product.uom"):
        model = "product.uom"
    if model is None:
        report.probes.append(ProbeResult(name="uom", ok=False, detail="uom model missing"))
        return
    ids = _search(client, model, [], limit=5)
    report.probes.append(
        ProbeResult(name="uom", ok=bool(ids), detail=f"{model} count probe={len(ids)}")
    )


def _probe_pricelist(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    if not _exists(client, "product.pricelist"):
        report.probes.append(
            ProbeResult(name="pricelist", ok=False, detail="product.pricelist missing")
        )
        return
    currency_id = report.currency_id
    rows = _search_read(client, "product.pricelist", [], ["id", "name", "currency_id"], limit=1)
    if rows:
        pid = int(rows[0]["id"])
        if currency_id:
            try:
                client.execute_kw("product.pricelist", "write", [[pid], {"currency_id": currency_id}])
            except Exception as exc:  # noqa: BLE001
                report.warnings.append(f"Pricelist currency write skipped: {exc}")
        report.probes.append(
            ProbeResult(
                name="pricelist",
                ok=True,
                detail=f"exists id={pid} name={rows[0].get('name')} "
                f"currency={packet.currency or 'unchanged'}",
            )
        )
        return
    payload: dict[str, Any] = {"name": "Autopilot Public"}
    if currency_id:
        payload["currency_id"] = currency_id
    try:
        pid = client.execute_kw("product.pricelist", "create", [payload])
    except Exception as exc:  # noqa: BLE001
        report.probes.append(ProbeResult(name="pricelist", ok=False, detail=str(exc)))
        report.warnings.append(f"Pricelist create failed: {exc}")
        return
    report.probes.append(
        ProbeResult(name="pricelist", ok=True, detail=f"created id={pid} currency_id={currency_id}")
    )


def _group_ids_for_roles(client: Any, roles: list[str]) -> list[int]:
    blob = " ".join(roles).lower()
    ids: list[int] = []
    for needle, xml_id in _ROLE_GROUPS:
        if needle not in blob:
            continue
        gid = _xml_id(client, xml_id)
        if gid:
            ids.append(gid)
    user_gid = _xml_id(client, "base.group_user")
    if user_gid:
        ids.append(user_gid)
    return list(dict.fromkeys(ids))


def _probe_users(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    from app.config_packet.users import parse_roster_csv, provision_users

    roster = []
    for data in packet.data_files:
        name = (data.filename or "").lower()
        if data.doc_type == "user_roster" or "user" in name:
            roster.extend(parse_roster_csv(data.excerpt or ""))
    if roster:
        created, existing, warnings = provision_users(client, roster)
        report.warnings.extend(warnings)
        report.probes.append(
            ProbeResult(
                name="users_roster",
                ok=created + existing > 0 or not warnings,
                detail=f"roster created={created} existing={existing}",
            )
        )
    emails = [e.strip().lower() for e in packet.org_emails if e and "@" in e]
    emails = [e for e in emails if e not in _SKIP_USER_LOGINS][:8]
    if not emails and not roster:
        report.probes.append(
            ProbeResult(name="users", ok=True, detail="no org emails in packet — skipped create")
        )
        return
    if not _exists(client, "res.users"):
        report.probes.append(ProbeResult(name="users", ok=False, detail="res.users missing"))
        return
    group_ids = _group_ids_for_roles(client, packet.roles or packet.actors)
    created = 0
    existing = 0
    for email in emails:
        found = _search(client, "res.users", [("login", "=", email)])
        if found:
            existing += 1
            continue
        vals: dict[str, Any] = {
            "name": email.split("@")[0],
            "login": email,
            "email": email,
        }
        if group_ids:
            from app.config_packet.rpc import user_groups_field

            vals[user_groups_field(client)] = [(6, 0, group_ids)]
        try:
            client.execute_kw("res.users", "create", [vals])
            created += 1
        except Exception as exc:  # noqa: BLE001
            report.warnings.append(f"User {email} skipped: {exc}")
    ok = created + existing > 0 or not emails
    report.probes.append(
        ProbeResult(
            name="users",
            ok=ok,
            detail=f"created={created} existing={existing} groups={len(group_ids)}",
        )
    )


def run_stock_recipes(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    """Config probes after module install. RECIPE_VERSION is stamped on the report."""
    report.recipe_version = RECIPE_VERSION
    if "account" in packet.stock_apps or packet.l10n_module:
        _probe_coa(client, report)
        _probe_journals(client, report)
        _ensure_brief_journals(client, packet, report)
    if packet.warehouse_needed or "stock" in packet.stock_apps:
        _probe_locations(client, report)
    if any(m in packet.stock_apps for m in ("sale", "stock", "purchase", "product")):
        _probe_uom(client, report)
    if "sale" in packet.stock_apps:
        _probe_pricelist(client, packet, report)
    _probe_users(client, packet, report)
    from app.job_autopilot.stock_kits import run_phase_bc_kits

    run_phase_bc_kits(client, packet, report)


__all__ = ["RECIPE_VERSION", "run_stock_recipes"]
