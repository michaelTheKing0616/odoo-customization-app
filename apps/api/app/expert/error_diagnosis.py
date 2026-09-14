"""Rule-based software-bug diagnosis for Odoo Expert (any connected instance).

Priority: match known Fault / view / ACL / schema patterns → structured remediation.
Never fall through to unrelated RAG for a pasted error log. Unknown faults still get
a grounded extraction of the fault body + instance-aware next steps.
"""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import (
    GroundingBundle,
    extract_model_field_refs,
    is_traceback_junk_ref,
    looks_like_conceptual_question,
    looks_like_rpc_error,
)

_MODEL_NOT_FOUND_RE = re.compile(
    r"(?i)(?:model not found|unknown model|no model named):\s*['\"]?([a-z][a-z0-9_.]*)"
)
_FIELD_NOT_FOUND_RE = re.compile(
    r"(?i)(?:field\s+['\"]?([a-z][a-z0-9_]*)['\"]?\s+(?:does not exist|is undefined|"
    r"not found)|invalid field['\"]?\s*['\"]?([a-z][a-z0-9_]*)|"
    r"keyerror:\s*['\"]([a-z][a-z0-9_]*)['\"])"
)
_VALIDATING_VIEW_RE = re.compile(
    r"(?i)error while (?:parsing or )?validating view"
)
_EMPTY_FIELD_NAME_RE = re.compile(
    r'(?i)field tag must have a ["\']?name["\']? attribute'
    r'|<\s*field\s+name\s*=\s*["\']["\']'
)
_DUPLICATE_CHROME_RE = re.compile(
    r"(?i)(duplicate\s+(?:send|print|pay|other\s+info)|send\s*\|\s*send|"
    r"other\s+info.*other\s+info|toolbar.*twice|buttons?\s+appear\s+twice)"
)
_UNKNOWN_FIELD_IN_VIEW_RE = re.compile(
    r"(?i)field\s+['\"]([a-z][a-z0-9_]*)['\"]\s+does not exist"
    r"|unknown field\s+['\"]([a-z][a-z0-9_]*)['\"]"
)
_XPATH_RE = re.compile(
    r"(?i)(cannot be located in parent view|invalid view architecture|"
    r"element\s+['\"]?<xpath|xpath expr)"
)
_XPATH_FIELD_RE = re.compile(
    r"""field\[@name=(?:['\"]|&#39;|&apos;)([a-z0-9_]+)"""
)
_XPATH_EXPR_RE = re.compile(
    r"""xpath expr=(?:['\"]|&#39;|&apos;)([^'\"&]+)"""
)
_ACCESS_ERROR_RE = re.compile(
    r"(?i)(access\s*error|accesserror|not allowed to (?:access|modify|create|delete))"
)
_USER_ERROR_RE = re.compile(r"(?i)\busererror\b|odoo\.exceptions\.UserError")
_VALIDATION_ERROR_RE = re.compile(
    r"(?i)\bvalidationerror\b|odoo\.exceptions\.ValidationError"
)
_MISSING_ERROR_RE = re.compile(r"(?i)\bmissingerror\b|record does not exist|missing record")
_INTEGRITY_RE = re.compile(
    r"(?i)(integrityerror|null value in column|foreign key|duplicate key|unique constraint)"
)
_PARSE_ERROR_RE = re.compile(r"(?i)(parseerror|xmlsyntaxerror|not well-formed|lxml)")
_SERIALIZATION_RE = re.compile(
    r"(?i)(cannot be serialized|jsonserializable|object of type .* is not json)"
)
_OWL_RE = re.compile(
    r"(?i)(owlerror|uncaughtpromise|assets?/web|missing template|component is not defined)"
)
_CONNECTION_RE = re.compile(
    r"(?i)(connection refused|failed to connect|xmlrpc\.client|protocolerror|"
    r"unauthorized|wrong login|401|403 forbidden|ssl|certificate)"
)
_CONFIRM_RE = re.compile(
    r"(?i)(i understand the risks|confirmation required|confirm_phrase|confirm advanced)"
)
_WRITE_MODE_RE = re.compile(
    r"(?i)(write_mode|observer mode|read-only connection|mutation blocked)"
)
_FAULT_RE = re.compile(r"(?i)(?:<fault\s*\d+:|fault\s+\d+:)")
_FAULT_BODY_RE = re.compile(
    r"(?is)<fault\s*\d+:\s*'([^']*)'|Fault\s+\d+:\s*(.+?)(?:\n\n|$)"
)
_NEAR_SNIPPET_RE = re.compile(
    r"(?is)error while validating view near:\s*(.+?)(?:Field tag must|Model not found|$)"
)
_REQUEST_FAILED_RE = re.compile(r"(?i)\brequest failed\b")


def _format_ref(model: str, field: str | None) -> str:
    return f"`{model}.{field}`" if field else f"`{model}`"


def _version_note(bundle: GroundingBundle) -> str:
    summary = bundle.instance_summary or {}
    ver = str(summary.get("server_version") or summary.get("version") or "").strip()
    edition = str(summary.get("edition") or "").strip()
    if ver and edition:
        return f"Connected instance: **{ver}** ({edition})."
    if ver:
        return f"Connected instance: **{ver}**."
    return ""


def _tool(
    tool_id: str,
    label: str,
    path: str,
    hint: str,
    connection_id: str | None,
) -> dict[str, Any]:
    deep = path.format(connection_id=connection_id) if connection_id else path
    return {
        "id": tool_id,
        "label": label,
        "deep_link": deep if connection_id else None,
        "hint": hint,
    }


def _extract_fault_message(question: str) -> str:
    m = _FAULT_BODY_RE.search(question)
    if m:
        return (m.group(1) or m.group(2) or "").strip()
    near = _NEAR_SNIPPET_RE.search(question)
    if near:
        return near.group(0).strip()[:800]
    # Strip "Diagnose…" preface; keep the densest error block
    lines = [ln.strip() for ln in question.splitlines() if ln.strip()]
    keep: list[str] = []
    for ln in lines:
        if re.search(
            r"(?i)(error|fault|traceback|exception|failed|invalid|denied)",
            ln,
        ):
            keep.append(ln)
    return "\n".join(keep[:12]) if keep else question.strip()[:600]


def _match_catalog(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None,
) -> tuple[list[str], list[str], list[dict[str, Any]]] | None:
    """Return (lines, caution_flags, suggested_tools) or None if no specific match."""
    lines: list[str] = []
    caution: list[str] = ["rule_based_diagnosis"]
    tools: list[dict[str, Any]] = []
    ui_model = str((bundle.ui_context or {}).get("model") or "").strip()

    def _xpath_miss() -> tuple[list[str], list[str], list[dict[str, Any]]] | None:
        if not (
            _XPATH_RE.search(question)
            or re.search(r"(?i)cannot be located in parent view", question)
        ):
            return None
        if not (
            _VALIDATING_VIEW_RE.search(question)
            or _PARSE_ERROR_RE.search(question)
            or _FAULT_RE.search(question)
        ):
            return None
        expr_m = _XPATH_EXPR_RE.search(question)
        field_m = _XPATH_FIELD_RE.search(question)
        expr = (expr_m.group(1) if expr_m else "").strip()
        ghost = (field_m.group(1) if field_m else "").strip()
        host = ""
        host_m = re.search(r"(?i)view\.model['\"]?\s*:\s*['\"]([a-z0-9_.]+)['\"]", question)
        if host_m:
            host = host_m.group(1)
        elif re.search(r"(?i)sale\.order", question):
            host = "sale.order"
        elif ui_model:
            host = ui_model
        loc = f" on **`{host}`**" if host else ""
        ghost_note = f"`{ghost}`" if ghost else "the target node"
        expr_note = f"`{expr}`" if expr else "the inherit xpath"
        extra = ""
        if ghost in {"amount_tax", "amount_untaxed"} or host == "sale.order":
            extra = (
                " Community 17–19 Sales form totals use **`tax_totals`**, not "
                f"{ghost_note} as a form field. `xmlrpc.py` in the traceback is the RPC "
                "controller — not an `ir.model`."
            )
        lines.extend(
            [
                f"**Root cause:** Inherit xpath {expr_note} cannot be located in the parent view"
                f"{loc}. Odoo raised **ParseError** while installing/loading the view.{extra}",
                "",
                "**Fix:**",
                "1. Retarget the xpath to a node that exists on **this** parent arch "
                "(Sales: `//field[@name='tax_totals']`, not `amount_tax`).",
                "2. If this was **Sandbox Install** of an Option A zip: retry sandbox after "
                "the zip rewrite — do **not** Live Install. Zip → sandbox → human **Promote**.",
                "3. Designer is for live metadata inherits, not this module zip.",
            ]
        )
        if connection_id:
            tools.append(
                _tool(
                    "studio",
                    "App Studio",
                    "/connections/{connection_id}/studio",
                    "Retry Sandbox Install after xpath rewrite. Promote stays human.",
                    connection_id,
                )
            )
        tools.append(
            _tool(
                "designer",
                "View Designer",
                "/connections/{connection_id}/designer",
                "Only for live inherit edits — not Option A zip install.",
                connection_id,
            )
        )
        caution.append("xpath_miss")
        return lines, caution, tools

    xpath_hit = _xpath_miss()
    if xpath_hit:
        return xpath_hit

    # --- Live schema diagnostics from grounding ---
    for diag in bundle.error_diagnostics or []:
        status = diag.get("status")
        model = str(diag.get("model") or "").strip()
        fld = diag.get("field")
        field = str(fld).strip() if fld else None
        suggestion = str(diag.get("suggestion") or "").strip()

        if status == "model_missing" and model:
            if is_traceback_junk_ref(model, field):
                continue
            lines.append(
                f"**Root cause:** {_format_ref(model, None)} does not exist on this connection "
                f"(`ir.model` has no record)."
            )
            if model.startswith("x_"):
                lines.extend(
                    [
                        "",
                        "**Fix:**",
                        f"1. Create the custom model `{model}` in **Models & Fields**, or save from "
                        "**Designer** with standard write mode (missing `x_*` models auto-create).",
                        "2. Re-save the view or retry after the model exists.",
                    ]
                )
            else:
                lines.extend(
                    [
                        "",
                        "**Fix:**",
                        f"1. Install the module that provides `{model}`, or fix a typo in the model name.",
                        "2. Retry after the model is on this database.",
                    ]
                )
            if suggestion:
                lines.append(f"3. {suggestion}")
            tools.append(
                _tool(
                    "builder",
                    "Models & Fields",
                    "/connections/{connection_id}/builder",
                    f"Create or verify `{model}`.",
                    connection_id,
                )
            )
            caution.append("live_model_missing")
            return lines, caution, tools

        if status == "field_missing" and model and field:
            lines.append(
                f"**Root cause:** Field {_format_ref(model, field)} does not exist on this connection."
            )
            lines.append(
                suggestion
                and f"**Likely fix:** {suggestion}"
                or f"**Fix:** Add `{field}` on `{model}` in Models & Fields, or correct the typo in the view/automation."
            )
            tools.append(
                _tool(
                    "builder",
                    "Models & Fields",
                    "/connections/{connection_id}/builder",
                    f"Add `{field}` on `{model}`.",
                    connection_id,
                )
            )
            caution.append("live_field_missing")
            return lines, caution, tools

    # --- Empty <field name=""/> (Designer / arch emit) ---
    if _EMPTY_FIELD_NAME_RE.search(question):
        lines.extend(
            [
                "**Root cause:** The view arch contains empty "
                '`<field name=""/>` tags. Odoo requires every `<field>` to have a non-empty `name`.',
                "",
                "**Why (this app):** Loading a stock form (e.g. `account.move`) can turn nested "
                "`<group>` nodes into blank field rows in Designer; Save then emits invalid XML.",
                "",
                "**Fix:**",
                "1. **View Designer → Form layout** — remove rows with a blank technical name "
                "(or hard-refresh and **Load existing view** after the empty-name fix).",
                "2. Keep only real fields (`x_my_test`, `partner_id`, …).",
                "3. **Save to Odoo** again — prefer **inherit** on stock models.",
            ]
        )
        tools.append(
            _tool(
                "designer",
                "View Designer",
                "/connections/{connection_id}/designer",
                "Reload form layout; remove blank field rows; Save with inherit.",
                connection_id,
            )
        )
        caution.append("empty_field_name_in_arch")
        return lines, caution, tools

    # --- Duplicate Bill/Invoice chrome from full form replace inherit ---
    if _DUPLICATE_CHROME_RE.search(question):
        lines.extend(
            [
                "**Root cause:** A Designer **Inherit** save previously wrote a full "
                "`//form` **replace** that re-emitted stock header buttons and notebook "
                "pages. Module inherits then inject **Send / Print / Pay** and **Other Info** "
                "again → visible duplicates. This is view configuration, not duplicate "
                "accounting rows.",
                "",
                "**Fix:**",
                "1. Restart the API (additive stock saves + repair endpoints).",
                "2. View Designer → model `account.move` → **Fix duplicate chrome** "
                "(rewrites `account.move.designer.form` to additive `x_*`; keeps TEST GROUP "
                "when possible).",
                "3. Or **Load existing view** → **Save Inherit** after API restart.",
                "4. Hard-refresh Odoo on the Bill/Invoice — one Send, one Print, one Pay, "
                "one Other Info.",
                "5. Nuclear: **Unlink designer inherit** (confirm phrase) or in Odoo "
                "debug delete view `account.move.designer.form`, then re-save from Designer "
                "if you still need custom fields.",
            ]
        )
        tools.append(
            _tool(
                "designer",
                "View Designer",
                "/connections/{connection_id}/designer",
                "Re-save or Fix duplicate chrome on account.move.",
                connection_id,
            )
        )
        caution.append("duplicate_view_chrome")
        return lines, caution, tools

    # --- Model not found (text) ---
    model_match = _MODEL_NOT_FOUND_RE.search(question)
    if model_match:
        model = model_match.group(1).lower()
        if _VALIDATING_VIEW_RE.search(question) or "view" in question.lower():
            lines.append(
                f"**Root cause:** Odoo could not validate the view because model `{model}` "
                "is not registered in `ir.model`."
            )
        else:
            lines.append(f"**Root cause:** Model `{model}` was not found on this connection.")
        if model.startswith("x_"):
            lines.extend(
                [
                    "",
                    "**Fix:**",
                    f"1. Create `{model}` in **Models & Fields** before saving the view.",
                    "2. Or **Designer → Save to Odoo** with standard write mode — missing `x_*` "
                    "models are auto-created on save.",
                    "3. Re-save after the model exists.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "**Fix:**",
                    f"1. Install the module that provides `{model}` on this database.",
                    "2. Confirm the technical model name (not the Apps module name).",
                ]
            )
        tools.append(
            _tool(
                "builder",
                "Models & Fields",
                "/connections/{connection_id}/builder",
                f"Ensure `{model}` exists.",
                connection_id,
            )
        )
        caution.append("model_not_found")
        return lines, caution, tools

    # --- Unknown field in view / KeyError ---
    field_match = _UNKNOWN_FIELD_IN_VIEW_RE.search(question) or _FIELD_NOT_FOUND_RE.search(
        question
    )
    if field_match:
        field = next((g for g in field_match.groups() if g), None)
        field = (field or "").lower()
        model = ui_model or "the target model"
        lines.extend(
            [
                f"**Root cause:** Field `{field}` is referenced but does not exist on "
                f"**`{model}`** (or the name is wrong).",
                "",
                "**Fix:**",
                f"1. In **Models & Fields**, confirm `{field}` exists on `{model}` "
                "(custom fields must start with `x_`).",
                "2. In **View Designer**, remove or rename the bad field node, then Save.",
                "3. If you just created the field, wait for the field list refresh before Save.",
            ]
        )
        tools.extend(
            [
                _tool(
                    "builder",
                    "Models & Fields",
                    "/connections/{connection_id}/builder",
                    f"Verify `{field}`.",
                    connection_id,
                ),
                _tool(
                    "designer",
                    "View Designer",
                    "/connections/{connection_id}/designer",
                    "Fix the arch field node.",
                    connection_id,
                ),
            ]
        )
        caution.append("field_not_found")
        return lines, caution, tools

    # --- AccessError ---
    if _ACCESS_ERROR_RE.search(question):
        model_from_error = re.search(r"['\"]([a-z][a-z0-9_.]*)['\"]", question, re.I)
        target = (
            model_from_error.group(1)
            if model_from_error
            else (bundle.ui_context or {}).get("model")
        )
        lines.append(
            "**Root cause:** **AccessError** — the Odoo user lacks model ACL or record-rule "
            "permission for this operation."
        )
        fix_lines = [
            "",
            "**Fix:**",
            "1. In Odoo: **Settings → Users & Companies → Groups** — grant the needed access.",
            "2. In this app: **Access Matrix** for the group on the model.",
        ]
        if target:
            fix_lines.append(
                f"3. Error references `{target}` — check `ir.model.access` and record rules."
            )
        if connection_id:
            fix_lines.append(
                f"4. Open `/connections/{connection_id}/access-matrix`."
            )
        lines.extend(fix_lines)
        tools.append(
            _tool(
                "access-matrix",
                "Access Matrix",
                "/connections/{connection_id}/access-matrix",
                "Grant read/write for the failing model.",
                connection_id,
            )
        )
        caution.append("access_error")
        return lines, caution, tools

    # --- Confirm phrase / advanced gate ---
    if _CONFIRM_RE.search(question):
        lines.extend(
            [
                "**Root cause:** This action is gated behind the advanced confirmation phrase "
                '(`I understand the risks`).',
                "",
                "**Fix:**",
                "1. Type the exact phrase when prompted.",
                "2. Prefer safer paths (inherit, sandbox) when available.",
                "3. Snapshot before overwrite / mutate when offered.",
            ]
        )
        caution.append("confirm_required")
        return lines, caution, tools

    if _WRITE_MODE_RE.search(question):
        lines.extend(
            [
                "**Root cause:** The connection is in a mode that blocks live writes "
                "(observer / restricted write_mode).",
                "",
                "**Fix:**",
                "1. Open the connection settings and enable a write-capable mode for sandbox/dev.",
                "2. Never point write_mode=production Autopilot at a customer DB.",
                "3. Retry the mutation after mode change.",
            ]
        )
        caution.append("write_mode_blocked")
        return lines, caution, tools

    # --- DB integrity ---
    if _INTEGRITY_RE.search(question):
        lines.extend(
            [
                "**Root cause:** Database integrity constraint failed (NULL, FK, or unique).",
                "",
                "**Fix:**",
                "1. If adding a **required** field on a model with existing rows — supply a default "
                "or backfill before `NOT NULL`.",
                "2. Check Many2one relations point at existing comodel records.",
                "3. For unique constraints — find the duplicate value before retry.",
            ]
        )
        tools.append(
            _tool(
                "builder",
                "Models & Fields",
                "/connections/{connection_id}/builder",
                "Adjust required/default on the field.",
                connection_id,
            )
        )
        caution.append("integrity_error")
        return lines, caution, tools

    # --- Parse / XML ---
    if _PARSE_ERROR_RE.search(question):
        lines.extend(
            [
                "**Root cause:** View/XML could not be parsed (malformed arch).",
                "",
                "**Fix:**",
                "1. Preview arch in Designer before Save; look for unclosed tags.",
                "2. Clear any raw **arch override** that may be broken.",
                "3. Reload the parent view and re-apply changes with inherit.",
            ]
        )
        tools.append(
            _tool(
                "designer",
                "View Designer",
                "/connections/{connection_id}/designer",
                "Fix or clear arch override.",
                connection_id,
            )
        )
        caution.append("parse_error")
        return lines, caution, tools

    if _VALIDATION_ERROR_RE.search(question) or _USER_ERROR_RE.search(question):
        body = _extract_fault_message(question)
        lines.extend(
            [
                "**Root cause:** Odoo raised a **UserError/ValidationError** (business rule, not ACL).",
                "",
                f"**Message:** {body[:500]}" if body else "**Message:** (see pasted log)",
                "",
                "**Fix:**",
                "1. Read the message literally — it usually names the blocking constraint.",
                "2. Fix the record/domain/required field called out, then retry.",
                "3. If this came from a server action / automation — open Automations and inspect the domain.",
            ]
        )
        caution.append("user_validation_error")
        return lines, caution, tools

    if _MISSING_ERROR_RE.search(question):
        lines.extend(
            [
                "**Root cause:** **MissingError** — a referenced record id no longer exists.",
                "",
                "**Fix:**",
                "1. Refresh the UI and reload the record.",
                "2. Check Many2one / One2many links for deleted targets.",
                "3. Re-open the action from the menu (stale action id).",
            ]
        )
        caution.append("missing_error")
        return lines, caution, tools

    if _CONNECTION_RE.search(question):
        lines.extend(
            [
                "**Root cause:** Connection / auth to the Odoo instance failed.",
                "",
                "**Fix:**",
                "1. Verify URL, database name, and API key/password on the connection.",
                "2. Confirm the Odoo process is up and reachable from this API host.",
                "3. Re-probe the connection; check TLS if using HTTPS.",
            ]
        )
        caution.append("connection_error")
        return lines, caution, tools

    if _OWL_RE.search(question) or _SERIALIZATION_RE.search(question):
        lines.extend(
            [
                "**Root cause:** Client/assets or serialization error (often after a bad view or JS asset).",
                "",
                "**Fix:**",
                "1. Hard-refresh Odoo; try an incognito window.",
                "2. **Open in Odoo** after reverting the last view change (inherit uninstall / snapshot rollback).",
                "3. OWL/template crashes after custom JS need **Option A** modules — not live `state=code` hacks.",
            ]
        )
        caution.append("client_assets_error")
        return lines, caution, tools

    # --- Generic view validation with snippet ---
    if _VALIDATING_VIEW_RE.search(question):
        near = _NEAR_SNIPPET_RE.search(question)
        snippet = (near.group(1).strip()[:400] if near else "")
        lines.extend(
            [
                "**Root cause:** Odoo rejected the view during validation "
                "(`Error while validating view`).",
            ]
        )
        if snippet:
            lines.extend(["", f"**Near:**\n```xml\n{snippet}\n```"])
        lines.extend(
            [
                "",
                "**Fix:**",
                "1. Inspect the snippet — blank `name=\"\"`, unknown fields, or bad structure.",
                "2. In Designer, remove invalid nodes; prefer **inherit** on stock models.",
                "3. Confirm every field exists on the model in Models & Fields.",
            ]
        )
        tools.append(
            _tool(
                "designer",
                "View Designer",
                "/connections/{connection_id}/designer",
                "Fix arch near the cited snippet.",
                connection_id,
            )
        )
        caution.append("view_validation")
        return lines, caution, tools

    return None


def _universal_fault_fallback(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Always-on structured diagnosis when a Fault/traceback is present but unmatched."""
    body = _extract_fault_message(question)
    refs = extract_model_field_refs(question)
    caution = ["rule_based_diagnosis", "generic_fault_fallback"]
    lines = [
        "**Root cause:** An Odoo RPC / validation fault was pasted. "
        "No more-specific catalog rule matched — diagnosing from the fault text.",
        "",
        f"**Fault excerpt:**\n```\n{body[:900]}\n```",
    ]
    if refs:
        ref_text = ", ".join(_format_ref(m, f) for m, f in refs)
        lines.extend(["", f"**Detected model/field refs:** {ref_text}"])
    lines.extend(
        [
            "",
            "**Next steps (instance-safe):**",
            "1. Fix the exact message above — do not ignore the fault body.",
            "2. Confirm models/fields on **this** connection in Models & Fields.",
            "3. For view faults: Designer → Load existing view → remove bad nodes → Save **inherit**.",
            "4. For ACL faults: Access Matrix / Odoo groups.",
            "5. Re-probe the connection if auth or version looks wrong.",
        ]
    )
    tools: list[dict[str, Any]] = []
    if connection_id:
        tools.append(
            _tool(
                "designer",
                "View Designer",
                "/connections/{connection_id}/designer",
                "If this was a view save, reload and fix the arch.",
                connection_id,
            )
        )
        tools.append(
            _tool(
                "builder",
                "Models & Fields",
                "/connections/{connection_id}/builder",
                "Verify schema on this instance.",
                connection_id,
            )
        )
    return lines, caution, tools


def try_rule_based_error_diagnosis(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Return answer fields when the paste looks like a software/RPC bug."""
    del client
    if not looks_like_rpc_error(question) and not _REQUEST_FAILED_RE.search(question):
        # Confirmation / write-mode gates are operator bugs without classic Fault markers.
        if not (
            _CONFIRM_RE.search(question)
            or _WRITE_MODE_RE.search(question)
            or _DUPLICATE_CHROME_RE.search(question)
        ):
            if not (_FAULT_RE.search(question) or _VALIDATING_VIEW_RE.search(question)):
                return None
    if looks_like_conceptual_question(question) and not looks_like_rpc_error(question):
        if not (
            _CONFIRM_RE.search(question)
            or _WRITE_MODE_RE.search(question)
            or _DUPLICATE_CHROME_RE.search(question)
        ):
            return None

    matched = _match_catalog(question, bundle, connection_id=connection_id)
    if matched is None and (
        looks_like_rpc_error(question)
        or _FAULT_RE.search(question)
        or _REQUEST_FAILED_RE.search(question)
    ):
        matched = _universal_fault_fallback(question, bundle, connection_id=connection_id)

    if matched is None:
        return None

    lines, caution, tools = matched
    ver = _version_note(bundle)
    if ver:
        lines.append("")
        lines.append(ver)

    answer = "\n".join(lines)
    if "xpath_miss" in caution:
        answer += (
            "\n\n*Diagnosis from the ParseError / parent-view xpath — "
            "not traceback filenames like xmlrpc.py.*"
        )
    elif connection_id and bundle.error_diagnostics:
        answer += "\n\n*Live schema cross-check ran against this connection.*"
    elif connection_id:
        answer += "\n\n*Diagnosis from the error text and this connection’s context — not unrelated docs.*"
    else:
        answer += (
            "\n\n*Connect an Odoo instance for live schema cross-checks and version-aware fixes.*"
        )

    return {
        "answer_markdown": answer,
        # Grounded in the pasted fault / live schema — never "ungrounded parametric guess".
        "grounded": True,
        "declined": False,
        "caution_flags": caution,
        "suggested_tools": tools,
    }
