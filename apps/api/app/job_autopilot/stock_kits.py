"""Phase B/C stock kits: fiscal capture, warehouse/routes, document layout, journals.

RPC only. Never invent tax codes. Never LLM ir.config_parameter.
"""

from __future__ import annotations

import re
from typing import Any

from app.config_packet import rpc
from app.config_packet.schema import ConfigCompany, ConfigDocuments, ConfigJournal, ConfigStock
from app.job_autopilot.packet import BootstrapReport, JobPacket, ProbeResult

_DELIVERY_NEEDLES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(three[-\s]?step|pick\s*pack\s*ship|pick.?pack.?ship)\b", re.I), "pick_pack_ship"),
    (re.compile(r"\b(two[-\s]?step|pick\s*\+?\s*ship|pick.?ship)\b", re.I), "pick_ship"),
    (re.compile(r"\b(one[-\s]?step|ship[-\s]?only|single[-\s]?step delivery)\b", re.I), "ship_only"),
)
_RECEIPT_NEEDLES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(three[-\s]?step receipt|three[-\s]?step reception)\b", re.I), "three_steps"),
    (re.compile(r"\b(two[-\s]?step receipt|two[-\s]?step reception)\b", re.I), "two_steps"),
    (re.compile(r"\b(one[-\s]?step receipt|one[-\s]?step reception)\b", re.I), "one_step"),
)
_LOT_RE = re.compile(r"\b(lot|serial|traceab)\b", re.I)
_MTO_RE = re.compile(r"\b(mto|make[-\s]?to[-\s]?order)\b", re.I)
_DROPSHIP_RE = re.compile(r"\bdrop\s*-?\s*ship\b", re.I)


def infer_warehouse_flags(prompt: str) -> dict[str, Any]:
    delivery = None
    for pat, value in _DELIVERY_NEEDLES:
        if pat.search(prompt):
            delivery = value
            break
    reception = None
    for pat, value in _RECEIPT_NEEDLES:
        if pat.search(prompt):
            reception = value
            break
    return {
        "delivery_steps": delivery,
        "reception_steps": reception,
        "lot_tracking": bool(_LOT_RE.search(prompt)),
        "mto": bool(_MTO_RE.search(prompt)),
        "dropship": bool(_DROPSHIP_RE.search(prompt)),
    }


def apply_named_journals(client: Any, journals: list[ConfigJournal]) -> list[str]:
    if not rpc.exists(client, "account.journal"):
        return []
    created: list[str] = []
    for journal in journals:
        hit = rpc.search_ids(client, "account.journal", [("name", "=", journal.name)], limit=1)
        if hit:
            continue
        # Never clone every sale/bank journal from the sandbox — only named extras
        # or missing type if the instance has none of that type.
        is_named = journal.name.lower() in {"trust", "payment clearing", "operating bank"} or journal.code in {
            "trust",
            "pay_c",
            "op_ba",
        }
        type_missing = not rpc.search_ids(
            client, "account.journal", [("type", "=", journal.type)], limit=1
        )
        if not is_named and not type_missing:
            continue
        vals = {"name": journal.name, "type": journal.type, "code": (journal.code or "X")[:5]}
        try:
            client.execute_kw("account.journal", "create", [vals])
            created.append(f"journal:{journal.name}")
        except Exception:  # noqa: BLE001
            continue
    return created


def apply_stock_kit(client: Any, stock: ConfigStock) -> str | None:
    if not rpc.exists(client, "stock.warehouse"):
        return None
    fields = ["id", "code", "name"]
    for fname in ("delivery_steps", "reception_steps"):
        if rpc.field_exists(client, "stock.warehouse", fname):
            fields.append(fname)
    rows = rpc.search_read(client, "stock.warehouse", [], fields, limit=1)
    if not rows:
        return None
    wid = int(rows[0]["id"])
    vals: dict[str, Any] = {}
    if stock.delivery_steps and rpc.field_exists(client, "stock.warehouse", "delivery_steps"):
        vals["delivery_steps"] = stock.delivery_steps
    if stock.reception_steps and rpc.field_exists(client, "stock.warehouse", "reception_steps"):
        vals["reception_steps"] = stock.reception_steps
    wrote: list[str] = []
    if vals:
        try:
            client.execute_kw("stock.warehouse", "write", [[wid], vals])
            wrote.extend(vals.keys())
        except Exception as exc:  # noqa: BLE001
            return f"warehouse write skipped: {exc}"
    if stock.mto:
        _activate_route(client, needles=("mto", "make to order"), wrote=wrote)
    if stock.dropship:
        _activate_route(client, needles=("dropship", "drop ship"), wrote=wrote)
    if stock.lot_tracking and rpc.exists(client, "product.category"):
        _enable_lot_on_all_category(client, wrote)
    return f"warehouse id={wid} {wrote}" if wrote else None


def _activate_route(client: Any, *, needles: tuple[str, ...], wrote: list[str]) -> None:
    if not rpc.exists(client, "stock.route"):
        return
    for needle in needles:
        rows = rpc.search_read(
            client,
            "stock.route",
            [("name", "ilike", needle)],
            ["id", "name"],
            limit=1,
        )
        if not rows:
            continue
        rid = int(rows[0]["id"])
        payload: dict[str, Any] = {}
        if rpc.field_exists(client, "stock.route", "active"):
            payload["active"] = True
        try:
            if payload:
                client.execute_kw("stock.route", "write", [[rid], payload])
            wrote.append(f"route:{rows[0].get('name')}")
        except Exception:  # noqa: BLE001
            continue
        return


def _enable_lot_on_all_category(client: Any, wrote: list[str]) -> None:
    if not rpc.field_exists(client, "product.category", "tracking"):
        return
    rows = rpc.search_read(client, "product.category", [], ["id"], limit=1)
    if not rows:
        return
    try:
        client.execute_kw(
            "product.category",
            "write",
            [[int(rows[0]["id"])], {"tracking": "lot"}],
        )
        wrote.append("category.tracking=lot")
    except Exception:  # noqa: BLE001
        return


def apply_company_identity(client: Any, company: ConfigCompany) -> str | None:
    if not rpc.exists(client, "res.company"):
        return None
    rows = rpc.search_read(client, "res.company", [], ["id"], limit=1)
    if not rows:
        return None
    cid = int(rows[0]["id"])
    vals: dict[str, Any] = {}
    wrote: list[str] = []
    if company.name:
        vals["name"] = company.name
        wrote.append("name")
    if company.country_code:
        country = rpc.search_read(
            client, "res.country", [("code", "=", company.country_code)], ["id"], limit=1
        )
        if country:
            vals["country_id"] = int(country[0]["id"])
            wrote.append("country_id")
    if not vals:
        return None
    try:
        client.execute_kw("res.company", "write", [[cid], vals])
    except Exception as exc:  # noqa: BLE001
        return f"company skipped: {exc}"
    if company.currency:
        try:
            from app.job_autopilot.bootstrap import activate_currency

            cur_id, _detail = activate_currency(client, company.currency)
            if cur_id:
                try:
                    client.execute_kw("res.company", "write", [[cid], {"currency_id": cur_id}])
                    wrote.append("currency_id")
                except Exception as exc:  # noqa: BLE001
                    return f"company wrote {wrote}; currency blocked: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"company wrote {wrote}; currency skipped: {exc}"
    return f"company {wrote}"


def apply_document_layout(client: Any, docs: ConfigDocuments) -> str | None:
    if not rpc.exists(client, "res.company"):
        return None
    rows = rpc.search_read(client, "res.company", [], ["id"], limit=1)
    if not rows:
        return None
    cid = int(rows[0]["id"])
    vals: dict[str, Any] = {}
    if docs.primary_color and rpc.field_exists(client, "res.company", "primary_color"):
        vals["primary_color"] = docs.primary_color
    if docs.secondary_color and rpc.field_exists(client, "res.company", "secondary_color"):
        vals["secondary_color"] = docs.secondary_color
    if docs.paperformat_name and rpc.exists(client, "report.paperformat"):
        pf = rpc.search_read(
            client,
            "report.paperformat",
            [("name", "=", docs.paperformat_name)],
            ["id"],
            limit=1,
        )
        if pf and rpc.field_exists(client, "res.company", "paperformat_id"):
            vals["paperformat_id"] = int(pf[0]["id"])
    if docs.font and rpc.field_exists(client, "res.company", "font"):
        vals["font"] = docs.font
    if docs.layout_background and rpc.field_exists(client, "res.company", "layout_background"):
        vals["layout_background"] = docs.layout_background
    layout_id = None
    if docs.external_report_layout_xmlid:
        layout_id = rpc.xml_id(client, docs.external_report_layout_xmlid)
    if layout_id is None and docs.layout_xmlid and rpc.exists(client, "ir.ui.view"):
        hit = rpc.search_read(
            client,
            "ir.ui.view",
            [("name", "=", docs.layout_xmlid)],
            ["id"],
            limit=1,
        )
        if hit:
            layout_id = int(hit[0]["id"])
    if layout_id and rpc.field_exists(client, "res.company", "external_report_layout_id"):
        vals["external_report_layout_id"] = layout_id
    if docs.report_header and rpc.field_exists(client, "res.company", "report_header"):
        vals["report_header"] = docs.report_header[:4000]
    if docs.report_footer and rpc.field_exists(client, "res.company", "report_footer"):
        vals["report_footer"] = docs.report_footer[:4000]
    if not vals:
        return "layout: logo/QWeb remain human / Option A"
    try:
        client.execute_kw("res.company", "write", [[cid], vals])
        return f"layout {sorted(vals)}"
    except Exception as exc:  # noqa: BLE001
        return f"layout skipped: {exc}"


def run_phase_bc_kits(client: Any, packet: JobPacket, report: BootstrapReport) -> None:
    """Mutate sandbox stock after RECIPE_VERSION 2 probes: fiscal capture, warehouse, layout."""
    flags = infer_warehouse_flags(packet.prompt or "")
    stock = ConfigStock(
        delivery_steps=flags.get("delivery_steps"),
        reception_steps=flags.get("reception_steps"),
        lot_tracking=bool(flags.get("lot_tracking")),
        mto=bool(flags.get("mto")),
        dropship=bool(flags.get("dropship")),
    )
    if packet.warehouse_needed or "stock" in packet.stock_apps:
        detail = apply_stock_kit(client, stock)
        report.probes.append(
            ProbeResult(
                name="warehouse_kit",
                ok=True,
                detail=detail or f"flags={flags} (no warehouse write)",
            )
        )

    if rpc.exists(client, "account.tax"):
        ids = rpc.search_ids(client, "account.tax", [], limit=20)
        mapping = rpc.xmlids_for_records(client, "account.tax", ids)
        report.probes.append(
            ProbeResult(
                name="fiscal_taxes",
                ok=bool(mapping),
                detail=f"{len(mapping)} tax xmlid(s) captured — none invented",
            )
        )
    if rpc.exists(client, "account.fiscal.position"):
        fps = rpc.search_read(client, "account.fiscal.position", [], ["name"], limit=12)
        report.probes.append(
            ProbeResult(
                name="fiscal_positions",
                ok=True,
                detail=f"{len(fps)} fiscal position(s) on instance",
            )
        )

    from app.config_packet.settings import capture_settings, apply_settings

    captured = capture_settings(client)
    if captured:
        msg = apply_settings(client, captured)
        report.probes.append(
            ProbeResult(name="settings_allowlist", ok=True, detail=msg or str(sorted(captured)))
        )

    from app.config_packet.fingerprint import probe_mail_health

    mail = probe_mail_health(client)
    report.probes.append(
        ProbeResult(
            name="mail_health",
            ok=mail.ok,
            detail=f"smtp={mail.smtp_servers} alias_domains={mail.alias_domains}",
        )
    )
    report.warnings.extend(mail.warnings)
