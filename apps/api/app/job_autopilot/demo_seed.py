"""Sandbox identity: leftover-vertical probe + brief sample master data.

Autopilot reuses the Docker DB. It does not wipe restaurant/hotel rows.
When the operator did not attach client files, seed named partners/products
from the brief so the sandbox is recognizable as this job — not go-live data.
"""

from __future__ import annotations

import re
from typing import Any

from app.job_autopilot.packet import JobPacket, ProbeResult

_LEFTOVER_MODELS: tuple[tuple[str, str], ...] = (
    ("pos.order", "Point of Sale orders"),
    ("mrp.bom", "Bills of Materials"),
    ("hotel.folio", "Hotel folios"),
    ("x_stay", "Stay records"),
    ("x_room", "Room records"),
    ("x_table", "Table records"),
)

_CLIENTS_RE = re.compile(
    r"Clients?:\s*(.+?)(?:\n|$)",
    re.I,
)
_PRODUCTS_RE = re.compile(
    r"(?:Products?\s*/\s*fee types?|Products?|Fee types?):\s*(.+?)(?:\n|$)",
    re.I,
)
_MATTERS_RE = re.compile(
    r"Matters?:\s*(.+?)(?:\n|$)",
    re.I,
)


def _count(client: Any, model: str) -> int | None:
    try:
        n = client.execute_kw(model, "search_count", [[]])
        return int(n)
    except Exception:  # noqa: BLE001
        return None


def _split_names(blob: str) -> list[str]:
    parts = re.split(r"[;\n]|,\s+(?=[A-Z])", blob)
    out: list[str] = []
    for raw in parts:
        name = re.sub(r"\s+", " ", raw).strip(" .")
        name = re.sub(r"^['\"]|['\"]$", "", name)
        if 2 < len(name) < 80:
            out.append(name)
    return out[:8]


def parse_brief_master_data(prompt: str) -> dict[str, list[str]]:
    """Pull sample clients / products / matter titles from the operator brief."""
    clients: list[str] = []
    products: list[str] = []
    matters: list[str] = []
    m = _CLIENTS_RE.search(prompt or "")
    if m:
        clients = _split_names(m.group(1))
    m = _PRODUCTS_RE.search(prompt or "")
    if m:
        products = _split_names(m.group(1))
    m = _MATTERS_RE.search(prompt or "")
    if m:
        quoted = re.findall(r"[“\"]([^”\"]+)[”\"]", m.group(1))
        matters = quoted or _split_names(m.group(1))
    return {"clients": clients, "products": products, "matters": matters}


_STOCK_FORM_HOSTS: tuple[str, ...] = ("account.move", "sale.order")


def probe_leftover_stock_form_fields(client: Any) -> list[ProbeResult]:
    """Warn when a reused sandbox still has custom x_* on stock invoice/SO forms."""
    rows: list[dict[str, Any]] = []
    try:
        found = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "in", list(_STOCK_FORM_HOSTS)), ("name", "=like", "x_%")]],
            {"fields": ["name", "model", "field_description"], "limit": 24},
        )
        if isinstance(found, list):
            rows = [r for r in found if isinstance(r, dict) and str(r.get("name") or "").startswith("x_")]
    except Exception as exc:  # noqa: BLE001
        return [
            ProbeResult(
                name="sandbox_form",
                ok=True,
                detail=f"Could not list leftover x_* on stock forms: {exc}",
            )
        ]
    if not rows:
        return [
            ProbeResult(
                name="sandbox_form",
                ok=True,
                detail="Stock invoice/quotation forms have no leftover x_* fields.",
            )
        ]
    labels = []
    for row in rows[:12]:
        mid = str(row.get("model") or "")
        name = str(row.get("name") or "")
        labels.append(f"{mid}.{name}")
    extra = f" (+{len(rows) - 12} more)" if len(rows) > 12 else ""
    return [
        ProbeResult(
            name="sandbox_form",
            ok=True,
            detail=(
                "Invoice/quotation form is not stock Community — leftover custom fields "
                f"from prior Apply jobs: {', '.join(labels)}{extra}. "
                "This Autopilot job did not add them. Use a fresh DB for a clean UAT. "
                "Due date “or Pay…” is stock payment terms (no label by design)."
            ),
        )
    ]


def probe_leftover_verticals(client: Any) -> list[ProbeResult]:
    """Warn when this sandbox still holds another vertical's operational docs."""
    hits: list[str] = []
    for model, label in _LEFTOVER_MODELS:
        n = _count(client, model)
        if n and n > 0:
            hits.append(f"{label}={n}")
    if not hits:
        return [
            ProbeResult(
                name="sandbox_identity",
                ok=True,
                detail="No leftover POS/hotel/kitchen documents detected.",
            )
        ]
    return [
        ProbeResult(
            name="sandbox_identity",
            ok=True,
            detail=(
                "This sandbox DB was reused and still has "
                + ", ".join(hits)
                + ". Autopilot does not wipe other verticals. "
                "Open the smoke invoice by id — do not treat leftover invoices as this job. "
                "Use a fresh DB for a clean UAT."
            ),
        )
    ]


def _search_name(client: Any, model: str, name: str) -> int | None:
    try:
        ids = client.execute_kw(model, "search", [[("name", "=", name)]], {"limit": 1})
        if ids:
            return int(ids[0])
    except Exception:  # noqa: BLE001
        return None
    return None


def _create(client: Any, model: str, vals: dict[str, Any]) -> int | None:
    try:
        rid = client.execute_kw(model, "create", [vals])
        return int(rid)
    except Exception:  # noqa: BLE001
        return None


def seed_brief_master_data(client: Any, packet: JobPacket) -> list[ProbeResult]:
    """Named partners/products/matters from the brief when no client files exist."""
    parsed = parse_brief_master_data(packet.prompt)
    steps: list[ProbeResult] = []
    partner_ids: list[int] = []
    for name in parsed["clients"]:
        existing = _search_name(client, "res.partner", name)
        pid = existing or _create(client, "res.partner", {"name": name, "is_company": True})
        if pid:
            partner_ids.append(pid)
    if parsed["clients"]:
        steps.append(
            ProbeResult(
                name="brief.partners",
                ok=bool(partner_ids),
                detail=f"seeded {len(partner_ids)}/{len(parsed['clients'])} named clients",
            )
        )
    product_ok = 0
    for name in parsed["products"]:
        existing = _search_name(client, "product.template", name)
        if existing:
            product_ok += 1
            continue
        vals: dict[str, Any] = {
            "name": name,
            "type": "service",
            "invoice_policy": "order",
        }
        if _create(client, "product.template", vals):
            product_ok += 1
    if parsed["products"]:
        steps.append(
            ProbeResult(
                name="brief.products",
                ok=product_ok > 0,
                detail=f"seeded {product_ok}/{len(parsed['products'])} fee types",
            )
        )
    if parsed["matters"] and partner_ids:
        try:
            client.execute_kw("x_matter", "fields_get", [], {"attributes": ["string"]})
        except Exception:  # noqa: BLE001
            return steps
        employee_ids: list[int] = []
        try:
            rows = client.execute_kw("hr.employee", "search", [[]], {"limit": 8})
            employee_ids = [int(x) for x in (rows or [])]
        except Exception:  # noqa: BLE001
            employee_ids = []
        if not employee_ids:
            # Minimal fee earner so required x_employee_id does not block seed
            eid = _create(client, "hr.employee", {"name": "Autopilot Lawyer"})
            if eid:
                employee_ids = [eid]
        created = 0
        last_err = ""
        for i, title in enumerate(parsed["matters"]):
            existing = _search_name(client, "x_matter", title)
            if existing:
                created += 1
                continue
            # Matters use x_name, not stock name
            try:
                found = client.execute_kw(
                    "x_matter",
                    "search",
                    [[("x_name", "=", title)]],
                    {"limit": 1},
                )
                if found:
                    created += 1
                    continue
            except Exception:  # noqa: BLE001
                pass
            vals: dict[str, Any] = {
                "x_name": title,
                "x_partner_id": partner_ids[i % len(partner_ids)],
            }
            if employee_ids:
                vals["x_employee_id"] = employee_ids[i % len(employee_ids)]
            # Prefer intake when the live selection still has it (reused DBs may differ)
            for status in ("intake", "draft", "new", "open"):
                vals["x_status"] = status
                rid = _create(client, "x_matter", vals)
                if rid:
                    created += 1
                    last_err = ""
                    break
                last_err = f"create failed with x_status={status}"
            else:
                # Last attempt without status — let Odoo default
                vals.pop("x_status", None)
                if _create(client, "x_matter", vals):
                    created += 1
                    last_err = ""
                elif not last_err:
                    last_err = "create failed"
        detail = f"seeded {created}/{len(parsed['matters'])} sample matters"
        if created == 0 and last_err:
            detail = f"{detail} ({last_err})"
        steps.append(
            ProbeResult(
                name="brief.matters",
                ok=created > 0,
                detail=detail,
            )
        )
    return steps


__all__ = [
    "parse_brief_master_data",
    "probe_leftover_stock_form_fields",
    "probe_leftover_verticals",
    "seed_brief_master_data",
]
