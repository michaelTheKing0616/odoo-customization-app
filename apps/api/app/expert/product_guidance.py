"""Rule-based product UI guidance for Odoo Expert (in-app how-to).

Expert does **not** read the live TypeScript/Python tree at ask time. Product
docs are RAG-ingested as ``source=project``. This module answers common
"how do I use X in this app?" questions deterministically from curated copy
aligned with ``docs/OPERATOR-FEATURE-DEMO-GUIDE.md``, so guidance stays correct
even when embeddings are cold or thin.
"""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import GroundingBundle, looks_like_rpc_error

_PRODUCT_QUESTION_RE = re.compile(
    r"(?i)\b("
    r"how\s+do\s+i|how\s+to|where\s+(?:do\s+i|can\s+i)|"
    r"use\s+(?:the\s+)?(?:app|platform|product)|"
    r"view\s+designer|visual\s+designer|form\s+designer|"
    r"models?\s*&\s*fields|models?\s+and\s+fields|builder|"
    r"draft\s+studio|app\s+wizard|"
    r"job\s+autopilot|autopilot|"
    r"module\s*spec|modulespec|"
    r"code\s+studio|"
    r"website\s+editor|website\s+page|"
    r"automation|approvals?|reports?|"
    r"projects?\s+(?:feature|page|screen)|"
    r"add\s+(?:a\s+)?field\s+(?:to|on)|"
    r"load\s+(?:account|sale|invoice)|"
    r"investor\s+demo|demo\s+script|"
    r"option\s+a|sandbox\s+(?:install|smoke)|"
    r"account\.move|technical\s+model|"
    r"field\s+propert(?:y|ies)|widget\s+barcode|required\s+when"
    r")\b"
)

_PRODUCT_TOOL_ROUTES: tuple[dict[str, Any], ...] = (
    {
        "id": "designer",
        "keywords": ("view designer", "visual designer", "form designer", "canvas"),
        "label": "View Designer",
        "web_path": "/connections/{connection_id}/designer",
        "hint": "Load a technical model (e.g. account.move), then Load form view. Edit in Form layout; drag near edges to auto-scroll.",
    },
    {
        "id": "builder",
        "keywords": ("models & fields", "models and fields", "builder", "create field"),
        "label": "Models & Fields",
        "web_path": "/connections/{connection_id}/builder",
        "hint": "Create x_* fields or custom models, then place them in View Designer.",
    },
    {
        "id": "wizard",
        "keywords": ("draft studio", "wizard", "natural language", "create draft"),
        "label": "Draft Studio",
        "web_path": "/connections/{connection_id}/wizard",
        "hint": "NL to ModuleSpec. Option A PDF/QR needs Sandbox install & smoke.",
    },
    {
        "id": "job",
        "keywords": ("job autopilot", "autopilot"),
        "label": "Job Autopilot",
        "web_path": "/connections/{connection_id}/job",
        "hint": "Sandbox-only stock-first delivery; promote stays human.",
    },
    {
        "id": "modulespec",
        "keywords": ("modulespec", "module spec", "json spec"),
        "label": "ModuleSpec",
        "web_path": "/connections/{connection_id}/modulespec",
        "hint": "Inspect/apply/export the ModuleSpec JSON contract.",
    },
    {
        "id": "code-studio",
        "keywords": ("code studio", "custom code", "option a"),
        "label": "Code Studio",
        "web_path": "/connections/{connection_id}/code-studio",
        "hint": "Lint and sandbox Option A Python/XML blocks.",
    },
    {
        "id": "website",
        "keywords": ("website",),
        "label": "Website",
        "web_path": "/connections/{connection_id}/website",
        "hint": "Requires the website module installed on Odoo.",
    },
    {
        "id": "automations",
        "keywords": ("automation", "automations"),
        "label": "Automations",
        "web_path": "/connections/{connection_id}/automations",
        "hint": "Safe base.automation triggers; Python stays Option A.",
    },
    {
        "id": "approvals",
        "keywords": ("approval", "approvals"),
        "label": "Approvals",
        "web_path": "/connections/{connection_id}/approvals",
        "hint": "Approval-style gates and confirm flows.",
    },
    {
        "id": "reports",
        "keywords": ("report", "reports", "pdf", "qweb"),
        "label": "Reports",
        "web_path": "/connections/{connection_id}/reports",
        "hint": "Report layout lite; Pay-now/QR on PDF is Draft Studio Option A.",
    },
    {
        "id": "projects",
        "keywords": ("project", "projects"),
        "label": "Projects",
        "web_path": "/connections/{connection_id}/projects",
        "hint": "Package multi-step customization work per connection.",
    },
)


def route_product_tools(question: str, *, connection_id: str | None) -> list[dict[str, Any]]:
    """Deep-links into Build / AI Studio surfaces for how-to questions."""
    q = (question or "").lower()
    if not q or not connection_id:
        return []
    if not _PRODUCT_QUESTION_RE.search(question or ""):
        return []
    routes: list[dict[str, Any]] = []
    for route in _PRODUCT_TOOL_ROUTES:
        if any(kw in q for kw in route["keywords"]):
            routes.append(
                {
                    "id": route["id"],
                    "label": route["label"],
                    "deep_link": route["web_path"].format(connection_id=connection_id),
                    "hint": route["hint"],
                }
            )
    if not routes and re.search(r"(?i)how\s+(?:do\s+i|to)\s+use", q):
        for rid in ("wizard", "designer", "builder"):
            route = next(r for r in _PRODUCT_TOOL_ROUTES if r["id"] == rid)
            routes.append(
                {
                    "id": route["id"],
                    "label": route["label"],
                    "deep_link": route["web_path"].format(connection_id=connection_id),
                    "hint": route["hint"],
                }
            )
    return routes[:6]


def _tools_md(tools: list[dict[str, Any]]) -> str:
    if not tools:
        return ""
    lines = ["", "### Open in this app", ""]
    for t in tools:
        link = t.get("deep_link") or ""
        label = t.get("label") or t.get("id")
        hint = t.get("hint") or ""
        lines.append(f"- **{label}** — `{link}`" + (f" — {hint}" if hint else ""))
    return "\n".join(lines)


_ANSWERS: tuple[tuple[re.Pattern[str], str, tuple[str, ...]], ...] = (
    (
        re.compile(
            r"(?i)(field\s+propert(?:y|ies)|inspector|"
            r"required\s+when|readonly\s+when|invisible\s+domain|"
            r"widget\s+(?:barcode|email|phone|image)|change\s+(?:the\s+)?label\s+on\s+(?:the\s+)?form)"
        ),
        (
            "### Field properties (View Designer)\n\n"
            "1. **Build → View Designer** → load a form → select a field on "
            "**Form layout (primary)**.\n"
            "2. Use the right aside **Field properties**:\n"
            "   - **Label** — display string on this view\n"
            "   - **Required** / **Readonly** — Off, Always, or When… (domain)\n"
            "   - **Invisible** — domain builder (AND rules) or Edit raw\n"
            "   - **Widget** — curated list by field type, or Advanced…\n"
            "   - **Image size** — when widget is `image`\n"
            "3. **Save to Odoo** (Inherit on stock models) → **Open in Odoo** → hard-refresh.\n\n"
            "These are **view** attrs. To change type, selection keys, or relation, use "
            "**Models & Fields**.\n\n"
            "Full matrix (FP1–FP12): `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` § Field properties."
        ),
        ("designer", "builder"),
    ),
    (
        re.compile(
            r"(?i)(unlink\s+(?:a\s+|the\s+)?(?:inherit\s+)?view|"
            r"delete\s+(?:a\s+|the\s+)?(?:inherit\s+)?view|"
            r"remove\s+designer\s+inherit|how\s+do\s+i\s+unlink)"
        ),
        (
            "### Unlink a view (Designer inherit or Odoo UI)\n\n"
            "**In this app (preferred for Bills duplicates):**\n"
            "1. **Build → View Designer** → model e.g. `account.move` → form.\n"
            "2. Prefer **Fix duplicate chrome** (rewrites the bad full-form inherit to "
            "additive `x_*` and usually keeps TEST GROUP).\n"
            "3. Or **Unlink designer inherit** → type `I understand the risks` → confirm. "
            "That deletes `{model}.designer.form` only — not the stock primary form, and "
            "not `{model}.custom.x_*.form` field injects.\n"
            "4. Hard-refresh the Bill/Invoice in Odoo.\n\n"
            "**In Odoo (developer mode):**\n"
            "1. Settings → activate **Developer mode**.\n"
            "2. **Settings → Technical → User Interface → Views**.\n"
            "3. Search name `account.move.designer.form` (or your `{model}.designer.form`).\n"
            "4. Open the view → **Action → Delete** (unlink).\n"
            "5. Hard-refresh the form.\n\n"
            "Do **not** delete the primary stock view (e.g. Account's main move form) unless "
            "you know exactly what you are doing."
        ),
        ("designer",),
    ),
    (
        re.compile(
            r"(?i)(duplicate\s+(?:send|print|pay|other\s+info)|send\s*\|\s*send|"
            r"other\s+info.*other\s+info|fix\s+duplicate\s+chrome)"
        ),
        (
            "### Duplicate Send / Print / Pay / Other Info\n\n"
            "Root cause: an older Designer **Inherit** save wrote a full `//form` "
            "**replace** that re-emitted stock buttons and notebook pages; module "
            "inherits then inject them again.\n\n"
            "1. Restart the API if it is still on an old build.\n"
            "2. View Designer → `account.move` → **Fix duplicate chrome**.\n"
            "3. Hard-refresh the Bill/Invoice.\n"
            "4. If needed: **Unlink designer inherit** (confirm phrase) or delete "
            "`account.move.designer.form` under Odoo Technical → Views.\n\n"
            "TEST GROUP / `x_*` fields you added are yours — repair keeps them when "
            "possible; unlink removes layout that lived only in that inherit."
        ),
        ("designer",),
    ),
    (
        re.compile(
            r"(?i)(view\s+designer|visual\s+designer|form\s+designer|"
            r"load\s+(?:account|sale)|add\s+(?:a\s+)?field\s+(?:to|on)\s+"
            r"(?:invoice|account|stock)|account\.move|"
            r"technical\s+model|module\s+vs\s+model|model\s+vs\s+module)"
        ),
        (
            "### View Designer — stock or existing custom forms\n\n"
            "Use a **technical model name**, not an Apps module name.\n\n"
            "1. Open **Build → View Designer**.\n"
            "2. Enter the model, for example:\n"
            "   - Invoices / bills → **`account.move`** (not `account`)\n"
            "   - Sales orders → **`sale.order`**\n"
            "   - Custom residual → **`x_matter`**, **`x_booking`**, etc.\n"
            "3. Set view type to **form** (or list/search).\n"
            "4. **Load existing view** so **Form layout (primary)** shows the real Odoo "
            "structure (groups, notebook, buttons). Preview is optional.\n"
            "5. Drag an **`x_*`** field from the left field list onto a group "
            "(+ Group if needed — page auto-scrolls near the edge), then **Apply** "
            "(confirm phrase when prompted).\n"
            "6. Open Odoo on a real record and hard-refresh.\n\n"
            "**Why `account` looked wrong:** `account` is a **module**. The Designer "
            "loads an ORM **model** arch — for invoices that is `account.move`.\n\n"
            "**PDF / QR / click-to-pay on the invoice PDF** is not Designer — use "
            "**Draft Studio** Option A → **Sandbox install & smoke**.\n\n"
            "Full matrices: `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §2."
        ),
        ("designer", "builder"),
    ),
    (
        re.compile(r"(?i)(models?\s*&\s*fields|models?\s+and\s+fields|\bbuilder\b)"),
        (
            "### Models & Fields\n\n"
            "1. Open **Build → Models & Fields**.\n"
            "2. Select a model (`account.move` or `x_…`) or create a custom model.\n"
            "3. Add fields with names starting with **`x_`**.\n"
            "4. Save/Apply to the connected database.\n"
            "5. Place new fields on the UI in **View Designer** "
            "(creating a column alone may not show it on the form).\n\n"
            "Tier-1 Accounting still allows **additive** `x_*`; stock field mutation "
            "and O2M onto tier-1 hosts stay blocked.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §3."
        ),
        ("builder", "designer"),
    ),
    (
        re.compile(
            r"(?i)(draft\s+studio|create\s+draft|natural\s+language|"
            r"option\s+a|sandbox\s+(?:install|smoke)|qr.*pdf|click[\s-]?to[\s-]?pay)"
        ),
        (
            "### Draft Studio\n\n"
            "1. Open **AI Studio → Draft Studio**.\n"
            "2. Enter a prompt (e.g. “Add SLA due date on invoices”).\n"
            "3. **Create draft** → review scorecard, done-bar, and Option A callout.\n"
            "4. **Apply** for live metadata (fields/views/stubs).\n"
            "5. If the ask is **PDF / QR / click-to-pay / Python / OWL**, the draft is "
            "**Option A primary**: score is capped (~7.0) with `option_a_unproven` until "
            "you run **Sandbox install & smoke**. Then `go_live_ready` may flip — "
            "**promote to another connection stays human**.\n\n"
            "Completeness 10.0 is not Apps Store / go-live.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §9."
        ),
        ("wizard", "code-studio", "modulespec"),
    ),
    (
        re.compile(r"(?i)job\s+autopilot|autopilot"),
        (
            "### Job Autopilot\n\n"
            "Sandbox-only delivery: brief → stock install/config → custom `x_*` residual "
            "→ ingest → **RPC process smoke**.\n\n"
            "1. Use a **local sandbox** connection (e.g. `127.0.0.1:8069`).\n"
            "2. Paste a business brief → Run.\n"
            "3. Poll until terminal; read the Autopilot scorecard "
            "(separate from ModuleSpec 10.0).\n"
            "4. **Refuse production write mode.** Promote is a human confirm.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §10."
        ),
        ("job",),
    ),
    (
        re.compile(r"(?i)module\s*spec|modulespec"),
        (
            "### ModuleSpec\n\n"
            "The JSON contract between AI and Odoo: models, views, menus, automations, "
            "`custom_code_blocks`, scorecard, live-apply contract.\n\n"
            "1. Open **AI Studio → ModuleSpec**.\n"
            "2. Review `_scorecard` (completeness), `_certification` (ship bar), "
            "`_live_apply`, `_done_bar`, `_architecture_plan`, `_capability_gaps`.\n"
            "3. **Apply** live metadata, or **export zip** for sandbox / Code Studio.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §11."
        ),
        ("modulespec", "wizard"),
    ),
    (
        re.compile(r"(?i)code\s+studio"),
        (
            "### Code Studio\n\n"
            "Developer path for Option A Python/XML: lint → sandbox zip → promote.\n\n"
            "1. Open **Build → Code Studio** with a draft that has `custom_code_blocks`.\n"
            "2. Lint (relative Odoo imports OK; bare `import os` flagged).\n"
            "3. Export / sandbox install before any customer promote.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §8."
        ),
        ("code-studio", "wizard"),
    ),
    (
        re.compile(r"(?i)\bwebsite\b"),
        (
            "### Website\n\n"
            "Requires the Odoo **`website`** module installed on the connection.\n\n"
            "1. Open **Build → Website**.\n"
            "2. Pick a page → edit → save → verify on the public site URL.\n\n"
            "Portal pay / PDF QR is **Draft Studio Option A**, not the Website editor.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §4."
        ),
        ("website", "wizard"),
    ),
    (
        re.compile(r"(?i)\bautomations?\b"),
        (
            "### Automations\n\n"
            "Safe `base.automation` triggers (object_write, activities). "
            "**Python `state=code` is Option A** (module → sandbox → promote).\n\n"
            "1. Open **Build → Automations**.\n"
            "2. Pick model + trigger + safe action → Apply → test in Odoo.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §5."
        ),
        ("automations",),
    ),
    (
        re.compile(r"(?i)\bapprovals?\b"),
        (
            "### Approvals\n\n"
            "Approval-style gates aligned with confirm phrases "
            "(`I understand the risks`).\n\n"
            "Open **Build → Approvals** and walk request → approve/reject.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §6."
        ),
        ("approvals",),
    ),
    (
        re.compile(r"(?i)\breports?\b|\bqweb\b|\binvoice\s+pdf\b"),
        (
            "### Reports\n\n"
            "Report layout lite under **Build → Reports**.\n\n"
            "For **Pay now + QR on the invoice PDF**, prefer "
            "**Draft Studio** Option A scaffolds → **Sandbox install & smoke**, "
            "then Print in Odoo.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §7 and §9."
        ),
        ("reports", "wizard"),
    ),
    (
        re.compile(
            r"(?i)\bprojects?\b.*(feature|page|screen|how)|how.*(use|open).*projects?"
        ),
        (
            "### Projects\n\n"
            "Package multi-step work (Draft Studio + Designer + Autopilot) per connection.\n\n"
            "Open **AI Studio → Projects** → create a project → use it as the "
            "customer engagement spine.\n\n"
            "See `docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §12."
        ),
        ("projects",),
    ),
    (
        re.compile(
            r"(?i)investor\s+demo|demo\s+script|"
            r"how\s+(?:do\s+i|to)\s+use\s+(?:the\s+)?(?:app|platform)"
        ),
        (
            "### Using this app (quick map)\n\n"
            "| Goal | Where |\n|---|---|\n"
            "| Add a column | **Models & Fields** then **View Designer** |\n"
            "| Polish a stock form | **View Designer** with `account.move` / `sale.order` |\n"
            "| NL draft | **Draft Studio** |\n"
            "| PDF/QR/pay on invoice | Draft Studio **Option A** + sandbox smoke |\n"
            "| Unattended sandbox delivery | **Job Autopilot** |\n"
            "| Inspect JSON / zip | **ModuleSpec** / **Code Studio** |\n\n"
            "**Confirm phrase:** `I understand the risks`\n\n"
            "Full investor scripts (12–20 min): "
            "`docs/OPERATOR-FEATURE-DEMO-GUIDE.md` §13."
        ),
        ("wizard", "designer", "builder"),
    ),
)


def try_rule_based_product_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Answer in-app how-to questions from curated product guide copy."""
    del client
    q = (question or "").strip()
    # Never steal Diagnose / Fault pastes — error_diagnosis owns those.
    if not q or looks_like_rpc_error(q):
        return None
    if not _PRODUCT_QUESTION_RE.search(q):
        return None

    for pattern, body, tool_ids in _ANSWERS:
        if not pattern.search(q):
            continue
        tools = route_product_tools(q, connection_id=connection_id)
        if connection_id:
            have = {t.get("id") for t in tools}
            for rid in tool_ids:
                if rid in have:
                    continue
                route = next((r for r in _PRODUCT_TOOL_ROUTES if r["id"] == rid), None)
                if not route:
                    continue
                tools.append(
                    {
                        "id": route["id"],
                        "label": route["label"],
                        "deep_link": route["web_path"].format(connection_id=connection_id),
                        "hint": route["hint"],
                    }
                )
            tools = tools[:6]
        elif bundle.suggested_tools:
            tools = list(bundle.suggested_tools)[:6]

        answer = body + _tools_md(tools)
        return {
            "answer_markdown": answer,
            "caution_flags": ["rule_based_product_guidance"],
            "suggested_tools": tools,
        }
    return None


__all__ = [
    "route_product_tools",
    "try_rule_based_product_guidance",
]
