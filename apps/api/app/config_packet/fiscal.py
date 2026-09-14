"""Fiscal kit: positions, cash-basis writes, reconcile models.

Never create ``account.tax`` rows. Taxes stay l10n xmlids.
"""

from __future__ import annotations

from typing import Any

from app.config_packet import rpc
from app.config_packet.schema import (
    ConfigAccounting,
    ConfigFiscalPosition,
    ConfigFiscalTaxMap,
    ConfigReconcileModel,
    ConfigTax,
)


def capture_taxes(client: Any) -> list[ConfigTax]:
    if not rpc.exists(client, "account.tax"):
        return []
    fields = ["id", "name", "amount", "type_tax_use"]
    for fname in ("tax_exigibility", "cash_basis_transition_account_id"):
        if rpc.field_exists(client, "account.tax", fname):
            fields.append(fname)
    rows = rpc.search_read(client, "account.tax", [], fields, limit=40)
    if not rows:
        ids = rpc.search_ids(client, "account.tax", [], limit=40)
        rows = [{"id": i} for i in ids]
    ids = [int(r["id"]) for r in rows if r.get("id")]
    xmlids = rpc.xmlids_for_records(client, "account.tax", ids)
    acc_xml: dict[int, str] = {}
    acc_ids = []
    for row in rows:
        aid = rpc.m2o_id(row.get("cash_basis_transition_account_id"))
        if aid:
            acc_ids.append(aid)
    if acc_ids and rpc.exists(client, "account.account"):
        acc_xml = rpc.xmlids_for_records(client, "account.account", acc_ids)
    out: list[ConfigTax] = []
    for row in rows:
        xid = xmlids.get(int(row["id"]))
        if not xid:
            continue
        tax = ConfigTax(
            xmlid=xid,
            name=str(row.get("name") or "") or None,
            amount=float(row["amount"]) if row.get("amount") is not None else None,
            type_tax_use=str(row.get("type_tax_use") or "") or None,
        )
        exig = str(row.get("tax_exigibility") or "") or None
        if exig:
            tax.tax_exigibility = exig
        aid = rpc.m2o_id(row.get("cash_basis_transition_account_id"))
        if aid and acc_xml.get(aid):
            tax.cash_basis_account_xmlid = acc_xml[aid]
        out.append(tax)
    return out


def capture_fiscal_positions(client: Any) -> list[ConfigFiscalPosition]:
    if not rpc.exists(client, "account.fiscal.position"):
        return []
    fields = ["id", "name"]
    if rpc.field_exists(client, "account.fiscal.position", "auto_apply"):
        fields.append("auto_apply")
    rows = rpc.search_read(client, "account.fiscal.position", [], fields, limit=20)
    tax_xml: dict[int, str] = {}
    if rpc.exists(client, "account.tax"):
        tax_ids = rpc.search_ids(client, "account.tax", [], limit=80)
        tax_xml = rpc.xmlids_for_records(client, "account.tax", tax_ids)
    out: list[ConfigFiscalPosition] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        pos = ConfigFiscalPosition(
            name=name,
            auto_apply=bool(row.get("auto_apply")),
        )
        fid = int(row["id"])
        maps = _tax_maps_for_position(client, fid, tax_xml)
        pos.tax_map = maps
        out.append(pos)
    return out


def _tax_maps_for_position(
    client: Any, position_id: int, tax_xml: dict[int, str]
) -> list[ConfigFiscalTaxMap]:
    if not rpc.exists(client, "account.fiscal.position.tax"):
        return []
    rows = rpc.search_read(
        client,
        "account.fiscal.position.tax",
        [("position_id", "=", position_id)],
        ["tax_src_id", "tax_dest_id"],
        limit=40,
    )
    maps: list[ConfigFiscalTaxMap] = []
    for row in rows:
        src = rpc.m2o_id(row.get("tax_src_id"))
        dest = rpc.m2o_id(row.get("tax_dest_id"))
        src_xml = tax_xml.get(src) if src else None
        if not src_xml:
            continue
        dest_xml = tax_xml.get(dest) if dest else None
        maps.append(ConfigFiscalTaxMap(src_xmlid=src_xml, dest_xmlid=dest_xml))
    return maps


def capture_reconcile_models(client: Any) -> list[ConfigReconcileModel]:
    if not rpc.exists(client, "account.reconcile.model"):
        return []
    fields = ["name"]
    if rpc.field_exists(client, "account.reconcile.model", "rule_type"):
        fields.append("rule_type")
    rows = rpc.search_read(client, "account.reconcile.model", [], fields, limit=20)
    out: list[ConfigReconcileModel] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        out.append(
            ConfigReconcileModel(
                name=name,
                rule_type=str(row.get("rule_type") or "writeoff_button"),
            )
        )
    return out


def apply_fiscal_kit(client: Any, accounting: ConfigAccounting) -> list[str]:
    """Create missing positions / rec models; write cash basis on existing taxes.

    Never creates ``account.tax``.
    """
    applied: list[str] = []
    applied.extend(_write_cash_basis(client, accounting.taxes))
    applied.extend(_create_fiscal_positions(client, accounting.fiscal_positions))
    applied.extend(_create_reconcile_models(client, accounting.reconcile_models))
    return applied


def _write_cash_basis(client: Any, taxes: list[ConfigTax]) -> list[str]:
    if not rpc.exists(client, "account.tax"):
        return []
    wrote: list[str] = []
    for tax in taxes:
        if not tax.tax_exigibility and not tax.cash_basis_account_xmlid:
            continue
        tid = rpc.xml_id(client, tax.xmlid)
        if not tid:
            continue
        vals: dict[str, Any] = {}
        if tax.tax_exigibility and rpc.field_exists(client, "account.tax", "tax_exigibility"):
            vals["tax_exigibility"] = tax.tax_exigibility
        if tax.cash_basis_account_xmlid and rpc.field_exists(
            client, "account.tax", "cash_basis_transition_account_id"
        ):
            acc = rpc.xml_id(client, tax.cash_basis_account_xmlid)
            if acc:
                vals["cash_basis_transition_account_id"] = acc
        if not vals:
            continue
        try:
            client.execute_kw("account.tax", "write", [[tid], vals])
            wrote.append(f"cash_basis:{tax.xmlid}")
        except Exception:  # noqa: BLE001
            continue
    return wrote


def _create_fiscal_positions(client: Any, positions: list[ConfigFiscalPosition]) -> list[str]:
    if not rpc.exists(client, "account.fiscal.position"):
        return []
    created: list[str] = []
    for pos in positions:
        hit = rpc.search_ids(client, "account.fiscal.position", [("name", "=", pos.name)], limit=1)
        if hit:
            continue
        vals: dict[str, Any] = {"name": pos.name}
        if rpc.field_exists(client, "account.fiscal.position", "auto_apply"):
            vals["auto_apply"] = bool(pos.auto_apply)
        tax_cmds: list[tuple[int, int, dict[str, Any]]] = []
        for mapping in pos.tax_map:
            src = rpc.xml_id(client, mapping.src_xmlid)
            if not src:
                continue
            dest = rpc.xml_id(client, mapping.dest_xmlid) if mapping.dest_xmlid else False
            # Skip dest-missing maps rather than inventing a tax.
            if mapping.dest_xmlid and not dest:
                continue
            tax_cmds.append((0, 0, {"tax_src_id": src, "tax_dest_id": dest or False}))
        if tax_cmds and rpc.field_exists(client, "account.fiscal.position", "tax_ids"):
            vals["tax_ids"] = tax_cmds
        try:
            client.execute_kw("account.fiscal.position", "create", [vals])
            created.append(f"fiscal_position:{pos.name}")
        except Exception:  # noqa: BLE001
            continue
    return created


def _create_reconcile_models(client: Any, models: list[ConfigReconcileModel]) -> list[str]:
    if not rpc.exists(client, "account.reconcile.model"):
        return []
    created: list[str] = []
    for rec in models:
        hit = rpc.search_ids(client, "account.reconcile.model", [("name", "=", rec.name)], limit=1)
        if hit:
            continue
        vals: dict[str, Any] = {"name": rec.name}
        if rpc.field_exists(client, "account.reconcile.model", "rule_type"):
            vals["rule_type"] = rec.rule_type or "writeoff_button"
        try:
            client.execute_kw("account.reconcile.model", "create", [vals])
            created.append(f"reconcile_model:{rec.name}")
        except Exception:  # noqa: BLE001
            continue
    return created


__all__ = [
    "apply_fiscal_kit",
    "capture_fiscal_positions",
    "capture_reconcile_models",
    "capture_taxes",
]
