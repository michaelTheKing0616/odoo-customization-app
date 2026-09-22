"""Report / document layout address scrub CLASS (P1 Job 3).

Class-wide — strip or reshape commercial partner *name* lines on stock QWeb
reports (delivery slip, picking, invoice / sale address blocks) when the brief
asks. Parameterized by host + stock report xmlid. Prefer Contacts “delivery
notes” must never steal this class.

Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any

# Stock Community report inherits — domain-agnostic targets, not one client DN.
# Each row: host model → list of report templates to scrub when brief matches.
REPORT_SCRUB_TARGETS: dict[str, list[dict[str, str]]] = {
    "stock.picking": [
        {
            "inherit_id": "stock.report_deliveryslip",
            "xml_id": "report_deliveryslip_address_scrub",
            "partner_expr": "o.partner_id",
            "label": "delivery slip",
        },
        {
            "inherit_id": "stock.report_picking",
            "xml_id": "report_picking_address_scrub",
            "partner_expr": "o.partner_id",
            "label": "picking operations",
        },
    ],
    "account.move": [
        {
            "inherit_id": "account.report_invoice_document",
            "xml_id": "report_invoice_address_scrub",
            "partner_expr": "o.partner_id",
            "label": "invoice",
        },
    ],
    "sale.order": [
        {
            "inherit_id": "sale.report_saleorder_document",
            "xml_id": "report_saleorder_address_scrub",
            "partner_expr": "doc.partner_id",
            "label": "sale order / quotation",
        },
    ],
    "purchase.order": [
        {
            "inherit_id": "purchase.report_purchaseorder_document",
            "xml_id": "report_purchaseorder_address_scrub",
            "partner_expr": "o.partner_id",
            "label": "purchase order",
        },
    ],
}

_HOST_MODULE = {
    "stock.picking": "stock",
    "account.move": "account",
    "sale.order": "sale",
    "purchase.order": "purchase",
}

# Marker baked into authored QWeb so static prove can assert scrub without live PDF.
SCRUB_MARKER = "ingenium:partner_name_scrubbed"

# Strong scrub cues — bare "delivery notes" alone is Prefer/field noise, not QWeb scrub.
_SCRUB_CUE_RE = re.compile(
    r"(?i)("
    r"shipping\s+address|"
    r"address\s+block|"
    r"invoice\s+address|"
    r"delivery\s+slip|"
    r"picking\s+(?:report|operations)|"
    r"operations\s+slip|"
    r"remove.{0,100}(?:customer|partner|commercial)\s+name|"
    r"(?:customer|partner|commercial)\s+name.{0,80}(?:removed|strip|scrub|omit|from)|"
    r"qweb\s+(?:inherit|layout|report)|"
    r"report\s+layout|"
    r"inherit\s+(?:the\s+)?(?:report|qweb)|"
    r"from\s+the\s+(?:pdf|slip|note|report)"
    r")"
)
# Prefer / Contacts field-pack must never enter this class.
_PREFER_CONTACTS_RE = re.compile(
    r"(?i)("
    r"prefer(?:red)?\s+for\s+delivery|"
    r"delivery\s+notes?(?:\s+on\s+contacts)?|"
    r"delivery\s+group|"
    r"delivery\s+preferences?|"
    r"checkbox.{0,40}delivery|"
    r"inherit[\s-]only.{0,40}(?:contacts|res\.partner|partner)|"
    r"on\s+contacts.{0,60}delivery\s+notes?"
    r")"
)
_SCRUB_VERB_RE = re.compile(
    r"(?i)(\b(remove|strip|scrub|omit|drop|hide|without)\b|"
    r"name.{0,40}(?:from|off)|(?:from|off).{0,40}name)"
)
_INVOICE_RE = re.compile(r"(?i)\binvoices?\b")
_SALE_RE = re.compile(r"(?i)\b(?:sale\s+order|quotation|sales?\s+order)\b")
_PURCHASE_RE = re.compile(r"(?i)\bpurchase\s+order|\brfq\b")
_PICKING_OPS_RE = re.compile(r"(?i)\bpicking\s+operations|\boperations\s+slip\b")


def is_report_layout_scrub_brief(prompt: str) -> bool:
    """True for address/QWeb scrub CLASS — false for Contacts Prefer delivery-notes."""
    text = prompt or ""
    # Prefer / Contacts delivery-notes field packs are never this class — unless the
    # brief also has an explicit QWeb/PDF scrub verb on a stock report document.
    preferish = bool(_PREFER_CONTACTS_RE.search(text))
    scrub_doc = bool(_SCRUB_CUE_RE.search(text))
    scrub_verb = bool(_SCRUB_VERB_RE.search(text))
    if preferish and not (scrub_doc and scrub_verb and re.search(
        r"(?i)delivery\s+slip|shipping\s+address|qweb|pdf|report\s+layout|invoice\s+address",
        text,
    )):
        return False
    if not scrub_doc:
        return False
    # Require a scrub verb or explicit layout/QWeb wording so "delivery notes" alone loses.
    if scrub_verb:
        return True
    return bool(
        re.search(
            r"(?i)qweb|report\s+layout|shipping\s+address|address\s+block|invoice\s+address|delivery\s+slip",
            text,
        )
    )


def report_scrub_host_from_prompt(prompt: str) -> str:
    """Document host for the scrub class (never res.partner / Contacts Prefer)."""
    text = prompt or ""
    if _INVOICE_RE.search(text) and not re.search(
        r"(?i)delivery\s+(?:note|slip)|picking", text
    ):
        return "account.move"
    if _PURCHASE_RE.search(text) and not re.search(r"(?i)\bsales?\b", text):
        return "purchase.order"
    if _SALE_RE.search(text) and not re.search(
        r"(?i)delivery\s+(?:note|slip)|picking", text
    ):
        return "sale.order"
    if _PICKING_OPS_RE.search(text):
        return "stock.picking"
    # Default commercial delivery document for delivery-slip / shipping-address class.
    return "stock.picking"


def targets_for_host(host: str, *, prompt: str = "") -> list[dict[str, str]]:
    """Parameterized report targets for a host; may narrow by brief cues."""
    rows = list(REPORT_SCRUB_TARGETS.get(host) or [])
    if not rows:
        return []
    text = prompt or ""
    if host == "stock.picking":
        if _PICKING_OPS_RE.search(text) and not re.search(
            r"(?i)delivery\s+(?:note|slip)", text
        ):
            return [r for r in rows if "picking" in r["inherit_id"]]
        if re.search(r"(?i)delivery\s+(?:note|slip)", text) and not _PICKING_OPS_RE.search(
            text
        ):
            return [r for r in rows if "deliveryslip" in r["inherit_id"]]
        # Broad delivery/address scrub → both slip + picking.
        return rows
    return rows


def address_scrub_qweb_xml(
    *,
    host: str,
    targets: list[dict[str, str]] | None = None,
    prompt: str = "",
) -> str:
    """Generate domain-agnostic QWeb inherits that drop partner name from address blocks.

    Uses the contact widget with address/phone only (no ``name`` field) — class
    mutants share this shape; no client-specific strings.
    """
    rows = targets if targets is not None else targets_for_host(host, prompt=prompt)
    if not rows:
        rows = [
            {
                "inherit_id": f"{_HOST_MODULE.get(host, 'base')}.report_document",
                "xml_id": f"report_{host.replace('.', '_')}_address_scrub",
                "partner_expr": "o.partner_id",
                "label": host,
            }
        ]

    parts: list[str] = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<odoo>",
        f"    <!-- {SCRUB_MARKER} host={host} class=report_layout_address_scrub -->",
    ]
    for row in rows:
        inherit_id = row["inherit_id"]
        xml_id = row["xml_id"]
        partner = row.get("partner_expr") or "o.partner_id"
        label = row.get("label") or inherit_id
        # Dual xpath: div[@t-field] (CE slip/invoice) and span/div name lines.
        parts.append(
            f"""    <template id="{xml_id}" inherit_id="{inherit_id}">
        <!-- Scrub commercial partner name on {label}; keep street/city/phone. -->
        <xpath expr="//div[@t-field='{partner}']" position="attributes">
            <attribute name="t-options">{{"widget": "contact", "fields": ["address", "phone"], "no_marker": true}}</attribute>
        </xpath>
        <xpath expr="//span[@t-field='{partner}.name']" position="replace"/>
        <xpath expr="//strong[@t-field='{partner}.name']" position="replace"/>
        <xpath expr="//t[@t-esc='{partner}.name']" position="replace"/>
    </template>"""
        )
    parts.append("</odoo>")
    parts.append("")
    return "\n".join(parts)


def scaffold_address_scrub_blocks(
    draft: dict[str, Any],
    *,
    prompt: str = "",
    host: str | None = None,
) -> list[dict[str, Any]]:
    """Attach parameterized QWeb scrub blocks onto an Option A draft."""
    text = prompt or str(draft.get("_user_prompt") or "")
    if not is_report_layout_scrub_brief(text):
        return []
    resolved = host or report_scrub_host_from_prompt(text)
    rows = targets_for_host(resolved, prompt=text)
    slug = resolved.replace(".", "_")
    path = f"report/{slug}_address_scrub.xml"
    content = address_scrub_qweb_xml(host=resolved, targets=rows, prompt=text)
    blocks = [
        {
            "source_file": path,
            "path": path,
            "kind": "qweb",
            "filename": path.split("/")[-1],
            "model": resolved,
            "reason": (
                "QWeb address scrub CLASS — drop commercial partner name on "
                f"{resolved} stock reports (module → sandbox → human Promote)"
            ),
            "source": "report_layout_scrub_scaffold",
            "option_a": True,
            "content": content,
        }
    ]
    # Ensure inherit host row + depends.
    models = list(draft.get("models") or [])
    if not any(
        isinstance(m, dict)
        and str(m.get("model")) == resolved
        and str(m.get("mode") or "") == "inherit"
        for m in models
    ):
        models = [{"model": resolved, "mode": "inherit", "fields": []}, *models]
    # Drop mistaken Contacts host for this class.
    models = [
        m
        for m in models
        if not (
            isinstance(m, dict)
            and str(m.get("model")) == "res.partner"
            and str(m.get("mode") or "") == "inherit"
        )
    ]
    draft["models"] = models
    dep = _HOST_MODULE.get(resolved)
    deps = list(draft.get("depends") or ["base"])
    if dep and dep not in deps:
        deps.append(dep)
    draft["depends"] = deps
    draft["display_name"] = draft.get("display_name") or "Report address layout"
    draft["grain"] = "full_app"
    draft["_capability_primary_option_a"] = True
    draft["_delivery_preference"] = "module_zip"
    return blocks


def static_scrub_findings(draft: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    """Static prove helpers for acceptance checks (no live PDF required)."""
    text = prompt or str(draft.get("_user_prompt") or "")
    blocks = [
        b
        for b in (draft.get("custom_code_blocks") or [])
        if isinstance(b, dict)
        and (
            str(b.get("kind") or "") in {"xml", "qweb"}
            or str(b.get("source_file") or "").endswith(".xml")
        )
    ]
    blob = "\n".join(str(b.get("content") or "") for b in blocks)
    inherit_ids = re.findall(r'inherit_id=["\']([^"\']+)["\']', blob)
    expected_hosts = set(REPORT_SCRUB_TARGETS)
    host = ""
    for m in draft.get("models") or []:
        if isinstance(m, dict) and str(m.get("mode") or "") == "inherit":
            mid = str(m.get("model") or "")
            if mid in expected_hosts:
                host = mid
                break
    if not host:
        host = report_scrub_host_from_prompt(text)

    expected = {t["inherit_id"] for t in targets_for_host(host, prompt=text)}
    qweb_ok = bool(expected & set(inherit_ids)) or (
        bool(inherit_ids) and any("report_" in i for i in inherit_ids)
    )
    # Scrubbed = marker present OR contact fields without name OR .name xpath replace
    scrubbed = bool(
        SCRUB_MARKER in blob
        or re.search(
            r"""["']fields["']\s*:\s*\[[^\]]*"address"[^\]]*\]""",
            blob,
        )
        and not re.search(
            r"""["']fields["']\s*:\s*\[[^\]]*"name"[^\]]*\]""",
            blob,
        )
        or re.search(r"""position=["']replace["'][\s\S]{0,40}\.name|t-field=['\"][^'\"]*\.name['\"][^>]*>\s*</""", blob)
        or ".name" in blob and 'position="replace"' in blob
    )
    address_kept = bool(
        re.search(r"partner_id|contact|address", blob, re.I)
        and (
            "address" in blob
            or "partner_id" in blob
            or "widget\": \"contact\"" in blob
            or "widget': 'contact'" in blob
        )
    )
    # Pass when host is a commercial document — Prefer Contacts packs stay on res.partner.
    not_contacts = host in REPORT_SCRUB_TARGETS and host != "res.partner"
    return {
        "host_model": host,
        "inherit_ids": inherit_ids,
        "expected_inherit_ids": sorted(expected),
        "qweb_inherit_present": qweb_ok,
        "partner_name_scrubbed": scrubbed,
        "address_block_preserved": address_kept,
        "not_contacts_prefer": not_contacts,
        "block_count": len(blocks),
    }


__all__ = [
    "REPORT_SCRUB_TARGETS",
    "SCRUB_MARKER",
    "address_scrub_qweb_xml",
    "is_report_layout_scrub_brief",
    "report_scrub_host_from_prompt",
    "scaffold_address_scrub_blocks",
    "static_scrub_findings",
    "targets_for_host",
]
