"""Connection-scoped planner tools + curated pattern snippets (not full OCA).

Used by Architecture Plan / Expert closer — deterministic helpers, not LLM tools API.
"""

from __future__ import annotations

from typing import Any, Callable

# Curated pattern library — short XML/Python snippets for common CE tasks
PATTERN_LIBRARY: dict[str, dict[str, Any]] = {
    "inherit_field": {
        "id": "inherit_field",
        "title": "Inherit form: add field after partner_id",
        "tags": ["xpath", "inherit", "field"],
        "snippet": """
<record id="view_form_inherit_x" model="ir.ui.view">
  <field name="name">model.form.inherit.x</field>
  <field name="model">TARGET.MODEL</field>
  <field name="inherit_id" ref="MODULE.view_form"/>
  <field name="arch" type="xml">
    <xpath expr="//field[@name='partner_id']" position="after">
      <field name="x_custom_flag"/>
    </xpath>
  </field>
</record>
""".strip(),
    },
    "approval_state": {
        "id": "approval_state",
        "title": "Selection state + Confirm button pattern",
        "tags": ["workflow", "button", "state"],
        "snippet": """
<field name="x_state" widget="statusbar"
       statusbar_visible="draft,confirmed,done"/>
<!-- server action / button: write x_state='confirmed' -->
""".strip(),
    },
    "qweb_invoice_block": {
        "id": "qweb_invoice_block",
        "title": "QWeb inherit: block after totals on invoice PDF",
        "tags": ["qweb", "account", "report"],
        "snippet": """
<template id="report_invoice_document_inherit_x" inherit_id="account.report_invoice_document">
  <xpath expr="//div[@id='total']" position="after">
    <div t-if="o.x_payment_url" class="mt-3">
      <a t-att-href="o.x_payment_url">Pay now</a>
    </div>
  </xpath>
</template>
""".strip(),
    },
    "access_rights_x": {
        "id": "access_rights_x",
        "title": "ir.model.access CSV row for new x_* model",
        "tags": ["security", "acl"],
        "snippet": "access_x_model_user,x.model.user,model_x_model,base.group_user,1,1,1,0",
    },
    "join_table_party": {
        "id": "join_table_party",
        "title": "Party/role join is list+form, never a workflow kanban",
        "tags": ["party", "role", "join", "workflow"],
        "snippet": (
            "x_*_party: many2one parent + res.partner + role selection. "
            "is_workflow=False. No generic x_status. No kanban."
        ),
    },
    "qweb_commercial_host": {
        "id": "qweb_commercial_host",
        "title": "Pay/QR QWeb on invoice/order/picking — never calendar",
        "tags": ["qweb", "invoice", "pay", "qr", "account.move"],
        "snippet": (
            "inherit_id=account.report_invoice_document (or sale/purchase/picking). "
            "_inherit the same commercial host. No form group for PDF extras."
        ),
    },
    "sudo_justified_icp": {
        "id": "sudo_justified_icp",
        "title": "sudo() only for admin-only ICP, with SUDO-JUSTIFIED",
        "tags": ["sudo", "security", "icp"],
        "snippet": (
            "# SUDO-JUSTIFIED: ir.config_parameter is admin-only; public web.base.url.\n"
            'return self.env["ir.config_parameter"].sudo().get_param("web.base.url")'
        ),
    },
    "single_company_offices": {
        "id": "single_company_offices",
        "title": "Two offices of one company are not multi-company ir.rule",
        "tags": ["multi_company", "office", "record_rule"],
        "snippet": (
            "multi_company=false. Optional x_company_id is tagging. "
            "Do not emit Multi-company (x_*) record rules."
        ),
    },
}


def find_pattern(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    q = (query or "").lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for pat in PATTERN_LIBRARY.values():
        score = 0
        blob = f"{pat['id']} {pat['title']} {' '.join(pat.get('tags') or [])}".lower()
        for token in q.split():
            if token and token in blob:
                score += 1
        if score:
            scored.append((score, pat))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]


def find_model(
    catalog: list[dict[str, Any]] | None,
    needle: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search catalog rows ``{model, name?, modules?}``."""
    n = (needle or "").lower().strip()
    if not n:
        return []
    hits: list[dict[str, Any]] = []
    for row in catalog or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or row.get("model_id") or "")
        name = str(row.get("name") or row.get("display_name") or "")
        if n in mid.lower() or n in name.lower():
            hits.append(
                {
                    "model": mid,
                    "name": name or mid,
                    "modules": row.get("modules") or row.get("modules_installed") or [],
                }
            )
        if len(hits) >= limit:
            break
    return hits


def fields_get_summary(
    fields_get: dict[str, Any] | None,
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, meta in (fields_get or {}).items():
        if not isinstance(meta, dict):
            continue
        out.append(
            {
                "name": name,
                "type": meta.get("type"),
                "string": meta.get("string"),
                "required": bool(meta.get("required")),
                "relation": meta.get("relation"),
            }
        )
        if len(out) >= limit:
            break
    return out


def module_installed(installed: set[str] | list[str] | None, name: str) -> bool:
    return str(name or "").strip() in {str(x) for x in (installed or [])}


def find_views(
    views: list[dict[str, Any]] | None,
    model: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Summarize view rows for a model (id, type, inherit, field names best-effort)."""
    import re

    mid = (model or "").strip()
    if not mid:
        return []
    out: list[dict[str, Any]] = []
    for row in views or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("model") or "") != mid:
            continue
        arch = str(row.get("arch") or "")
        fields = sorted(set(re.findall(r"""name=['\"]([a-zA-Z0-9_.]+)['\"]""", arch)))
        out.append(
            {
                "id": row.get("id") or row.get("xml_id") or row.get("name"),
                "type": row.get("type") or row.get("view_type"),
                "inherit_id": row.get("inherit_id"),
                "field_names": fields[:40],
            }
        )
        if len(out) >= limit:
            break
    return out


def planner_toolbelt(
    *,
    catalog: list[dict[str, Any]] | None = None,
    installed_modules: set[str] | list[str] | None = None,
    fields_get_fn: Callable[[str], dict[str, Any]] | None = None,
    views: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return bound helpers for Architecture Plan / Expert (serializable summaries)."""

    def _find_model(needle: str) -> list[dict[str, Any]]:
        return find_model(catalog, needle)

    def _fields(model: str) -> list[dict[str, Any]]:
        if not fields_get_fn:
            return []
        try:
            return fields_get_summary(fields_get_fn(model))
        except Exception:  # noqa: BLE001
            return []

    def _installed(name: str) -> bool:
        return module_installed(installed_modules, name)

    def _views(model: str) -> list[dict[str, Any]]:
        return find_views(views, model)

    return {
        "find_model": _find_model,
        "fields_get_summary": _fields,
        "module_installed": _installed,
        "find_views": _views,
        "find_pattern": find_pattern,
        "patterns": list(PATTERN_LIBRARY.keys()),
    }


def stamp_planner_grounding(
    draft: dict[str, Any],
    *,
    catalog: list[dict[str, Any]] | None = None,
    installed_modules: list[str] | None = None,
    views: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Light stamp: available pattern ids + sample model hits from prompt nouns."""
    prompt = str(draft.get("_user_prompt") or "")
    patterns = find_pattern(prompt, limit=3)
    grounding = {
        "patterns": [{"id": p["id"], "title": p["title"]} for p in patterns],
        "pattern_library_size": len(PATTERN_LIBRARY),
        "catalog_size": len(catalog or []),
        "installed_module_count": len(installed_modules or []),
    }
    # Sample find_model for first token-ish word > 3 chars
    tokens = [t for t in re_split_tokens(prompt) if len(t) > 3][:3]
    model_hits: list[dict[str, Any]] = []
    for t in tokens:
        model_hits.extend(find_model(catalog, t, limit=2))
    grounding["model_hints"] = model_hits[:6]
    # Primary form field names from draft views (connection-scoped when views passed)
    host = None
    try:
        from app.ai_capability_option_a_scaffold import host_model_from_draft

        host = host_model_from_draft(draft, prompt=prompt)
    except Exception:  # noqa: BLE001
        host = None
    if not host:
        for m in draft.get("models") or []:
            if isinstance(m, dict) and str(m.get("mode")) == "inherit":
                host = str(m.get("model") or "")
                break
    if host:
        grounding["primary_form_fields"] = find_views(
            list(draft.get("views") or []) + list(views or []),
            host,
            limit=3,
        )
    draft["_planner_grounding"] = grounding
    return grounding


def re_split_tokens(text: str) -> list[str]:
    import re

    return re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text or "")


__all__ = [
    "PATTERN_LIBRARY",
    "fields_get_summary",
    "find_model",
    "find_pattern",
    "find_views",
    "module_installed",
    "planner_toolbelt",
    "stamp_planner_grounding",
]
