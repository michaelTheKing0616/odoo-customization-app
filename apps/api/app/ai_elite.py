"""Wave 18 ELITE passes — developer-grade draft enrichment."""

from __future__ import annotations

import re
from typing import Any

from app.custom_code_authoring import lint_custom_code_blocks
from app.module_spec_codec import merge_custom_code_blocks

from app.settings import settings

ELITE_SCORECARD_FLOOR = 9.0
ELITE_DIMENSION_FLOORS: dict[str, float] = {
    "domain_fit": 8.0,
    "structure": 8.5,
    "semantics": 8.5,
    "ux": 8.0,
    "hygiene": 8.0,
}

_BILLING_RE = re.compile(
    r"\b(invoice|invoic|billing|bill|accounting|account\.move|payment)\b",
    re.I,
)
_INVENTORY_RE = re.compile(
    r"\b(inventory|stock|warehouse|picking|delivery|procurement|purchase)\b",
    re.I,
)
_LIBRARY_RE = re.compile(
    r"\b(library|libraries|book|loan|isbn|reservation|overdue|fine)\b",
    re.I,
)


def _models_index(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(m["model"]): m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }


def _field_names(model: dict[str, Any]) -> set[str]:
    return {
        str(f.get("name"))
        for f in (model.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }


def _upsert_block(draft: dict[str, Any], block: dict[str, Any]) -> None:
    blocks = draft.setdefault("custom_code_blocks", [])
    if not isinstance(blocks, list):
        blocks = []
        draft["custom_code_blocks"] = blocks
    model = block.get("model")
    source = block.get("source_file")
    for i, existing in enumerate(blocks):
        if not isinstance(existing, dict):
            continue
        if model and existing.get("model") == model and existing.get("source_file") == source:
            blocks[i] = block
            return
    blocks.append(block)


def _model_class_name(model: str) -> str:
    return "".join(p.title() for p in model.replace(".", "_").split("_") if p)


def _loan_models(draft: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for mid, model in _models_index(draft).items():
        names = _field_names(model)
        if "x_due_date" in names and ("x_loan_date" in names or "x_book_id" in names):
            out.append((mid, model))
    return out


def run_elite_python_pass(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Add lint-clean Python blocks for constraints, computes, and cron hooks."""
    notes: list[str] = []
    tech = str(draft.get("technical_name") or "custom_module")

    for mid, model in _loan_models(draft):
        names = _field_names(model)
        constraint_lines: list[str] = []
        if "x_due_date" in names and "x_loan_date" in names:
            constraint_lines.append(
                "            if record.x_loan_date and record.x_due_date and record.x_due_date < record.x_loan_date:\n"
                "                raise ValidationError('Due date must be on or after loan date.')"
            )
        if "x_return_date" in names and "x_loan_date" in names:
            constraint_lines.append(
                "            if record.x_return_date and record.x_loan_date and record.x_return_date < record.x_loan_date:\n"
                "                raise ValidationError('Return date must be on or after loan date.')"
            )
        if constraint_lines:
            content = (
                "from odoo import api, models\n"
                "from odoo.exceptions import ValidationError\n\n\n"
                f"class {_model_class_name(mid)}(models.Model):\n"
                f"    _inherit = '{mid}'\n\n"
                "    @api.constrains('x_loan_date', 'x_due_date', 'x_return_date')\n"
                "    def _check_loan_dates(self):\n"
                "        for record in self:\n"
                + "\n".join(constraint_lines)
                + "\n"
            )
            _upsert_block(
                draft,
                {
                    "model": mid,
                    "source_file": f"models/{mid.replace('.', '_')}_constraints.py",
                    "kind": "python",
                    "reason": "elite: loan date constraints",
                    "content": content,
                },
            )
            notes.append(f"elite: constraints on {mid}")

        if {"x_fine_amount", "x_days_overdue", "x_book_id"}.issubset(names):
            compute_content = (
                "from odoo import api, fields, models\n\n\n"
                f"class {_model_class_name(mid)}Compute(models.Model):\n"
                f"    _inherit = '{mid}'\n\n"
                "    @api.depends('x_due_date', 'x_returned', 'x_book_id', 'x_book_id.x_fine_rate')\n"
                "    def _compute_overdue_fine(self):\n"
                "        today = fields.Date.context_today(self)\n"
                "        for record in self:\n"
                "            if record.x_returned or not record.x_due_date:\n"
                "                record.x_days_overdue = 0\n"
                "                record.x_fine_amount = 0.0\n"
                "                continue\n"
                "            days = max((today - record.x_due_date).days, 0)\n"
                "            rate = (record.x_book_id.x_fine_rate if record.x_book_id else 0.0) or 0.0\n"
                "            record.x_days_overdue = days\n"
                "            record.x_fine_amount = float(days) * float(rate)\n"
            )
            _upsert_block(
                draft,
                {
                    "model": mid,
                    "source_file": f"models/{mid.replace('.', '_')}_fine_compute.py",
                    "kind": "python",
                    "reason": "elite: overdue fine compute",
                    "content": compute_content,
                },
            )
            notes.append(f"elite: fine compute on {mid}")

        cron_content = (
            "from odoo import api, fields, models\n\n\n"
            f"class {_model_class_name(mid)}Cron(models.Model):\n"
            f"    _inherit = '{mid}'\n\n"
            "    @api.model\n"
            "    def cron_send_overdue_reminders(self):\n"
            "        today = fields.Date.context_today(self)\n"
            "        overdue = self.search([\n"
            "            ('x_returned', '=', False),\n"
            "            ('x_due_date', '<', today),\n"
            "        ])\n"
            "        tpl = self.env.ref(\n"
            f"            '{tech}.mail_template_loan_overdue', raise_if_not_found=False\n"
            "        )\n"
            "        if not tpl:\n"
            "            return True\n"
            "        for loan in overdue:\n"
            "            member = loan.x_member_id\n"
            "            if member and member.email:\n"
            "                tpl.send_mail(loan.id, force_send=False)\n"
            "        return True\n"
        )
        _upsert_block(
            draft,
            {
                "model": mid,
                "source_file": f"models/{mid.replace('.', '_')}_cron.py",
                "kind": "python",
                "reason": "elite: overdue reminder cron hook",
                "content": cron_content,
            },
        )
        notes.append(f"elite: cron hook on {mid}")

    lint = lint_custom_code_blocks(draft)
    if not lint.get("ok"):
        bad = [b.get("source_file") for b in (lint.get("blocks") or []) if b.get("issues")]
        notes.append(f"elite: lint warnings on blocks: {bad}")

    if user_prompt and _LIBRARY_RE.search(user_prompt):
        draft["_elite_python"] = {"library_patterns": True}
    return notes


def run_elite_artifacts_pass(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Add mail templates, cron jobs, and PDF reports for document models."""
    notes: list[str] = []
    tech = str(draft.get("technical_name") or "custom_module")
    by_id = _models_index(draft)

    loan_models = [mid for mid, _ in _loan_models(draft)]
    if loan_models:
        loan_model = loan_models[0]
        mail = draft.setdefault("mail_templates", [])
        if not isinstance(mail, list):
            mail = []
            draft["mail_templates"] = mail
        if not any(isinstance(m, dict) and m.get("xml_id") == "mail_template_loan_overdue" for m in mail):
            mail.append(
                {
                    "xml_id": "mail_template_loan_overdue",
                    "name": "Overdue Library Loan",
                    "model": loan_model,
                    "subject": "Overdue: {{ object.x_name }}",
                    "body_html": (
                        "<p>Dear {{ object.x_member_id.name }},</p>"
                        "<p>Your loan <strong>{{ object.x_name }}</strong> is overdue "
                        "(due {{ object.x_due_date }}).</p>"
                        "<p>Please return the book or contact the library.</p>"
                    ),
                    "email_to": "${object.x_member_id.email|safe}",
                }
            )
            notes.append("elite: mail_template_loan_overdue")

        crons = draft.setdefault("cron_jobs", [])
        if not isinstance(crons, list):
            crons = []
            draft["cron_jobs"] = crons
        if not any(isinstance(c, dict) and c.get("xml_id") == "ir_cron_library_overdue" for c in crons):
            crons.append(
                {
                    "xml_id": "ir_cron_library_overdue",
                    "name": "Library: send overdue reminders",
                    "model": loan_model,
                    "code": "model.cron_send_overdue_reminders()",
                    "interval_number": 1,
                    "interval_type": "days",
                }
            )
            notes.append("elite: ir_cron_library_overdue")

        reports = draft.setdefault("reports", [])
        if not isinstance(reports, list):
            reports = []
            draft["reports"] = reports
        if not any(isinstance(r, dict) and r.get("model") == loan_model for r in reports):
            reports.append(
                {
                    "name": "Loan Receipt",
                    "model": loan_model,
                    "report_name": "library_loan_receipt",
                    "template_xml_id": "report_loan_receipt",
                    "body_html": (
                        "<div class='page'>"
                        "<h2>Loan Receipt</h2>"
                        "<p>Reference: <span t-field='doc.x_name'/></p>"
                        "<p>Member: <span t-field='doc.x_member_id'/></p>"
                        "<p>Book: <span t-field='doc.x_book_id'/></p>"
                        "<p>Due: <span t-field='doc.x_due_date'/></p>"
                        "</div>"
                    ),
                    "print_report_name": "'Loan-%s' % (object.x_name or '')",
                    "technical_name": "report_loan_receipt",
                }
            )
            notes.append(f"elite: report on {loan_model}")

    for mid, model in by_id.items():
        if mid in loan_models:
            continue
        if not (model.get("is_workflow") or model.get("state_field")):
            continue
        reports = draft.setdefault("reports", [])
        if any(isinstance(r, dict) and r.get("model") == mid for r in reports):
            continue
            desc = str(model.get("description") or mid)
            reports.append(
                {
                    "name": f"{desc} Summary",
                    "model": mid,
                    "report_name": f"{mid.replace('.', '_')}_summary",
                    "template_xml_id": f"report_{mid.replace('.', '_')}",
                    "body_html": (
                        f"<div class='page'><h2>{desc}</h2>"
                        f"<p t-field='doc.x_name'/></div>"
                    ),
                    "technical_name": f"report_{mid.replace('.', '_')}",
                }
            )
            notes.append(f"elite: summary report on {mid}")

    if user_prompt:
        draft["_elite_artifacts"] = {"prompt_matched": True, "technical_name": tech}
    return notes


def run_elite_integration_pass(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """PCM-safe stock/account link-only integration when prompt implies billing/inventory."""
    notes: list[str] = []
    from app.ai_apply_readiness import (
        ensure_transaction_document_links,
        wire_reuse_stock_documents,
    )

    notes.extend(ensure_transaction_document_links(draft))
    notes.extend(wire_reuse_stock_documents(draft))

    prompt = user_prompt.lower()
    by_id = _models_index(draft)
    if _BILLING_RE.search(prompt):
        for mid, model in by_id.items():
            if not str(mid).startswith("x_"):
                continue
            names = _field_names(model)
            if "x_invoice_id" in names:
                continue
            if model.get("is_workflow") or "x_amount" in names or "x_total" in names:
                model.setdefault("fields", []).append(
                    {
                        "name": "x_invoice_id",
                        "ttype": "many2one",
                        "string": "Invoice",
                        "relation": "account.move",
                        "readonly": True,
                        "help": "Link-only — post invoices in Accounting, link here.",
                    }
                )
                deps = list(draft.get("depends") or ["base"])
                if "account" not in deps:
                    deps.append("account")
                draft["depends"] = deps
                notes.append(f"elite: x_invoice_id link on {mid}")
                smart = draft.setdefault("smart_buttons", [])
                if not any(
                    isinstance(b, dict)
                    and b.get("on_model") == mid
                    and b.get("related_model") == "account.move"
                    for b in smart
                ):
                    smart.append(
                        {
                            "on_model": mid,
                            "related_model": "account.move",
                            "relation_field": "x_invoice_id",
                            "label": "Invoice",
                        }
                    )

    if _INVENTORY_RE.search(prompt):
        deps = list(draft.get("depends") or ["base"])
        for dep in ("stock", "purchase"):
            if dep not in deps:
                deps.append(dep)
        draft["depends"] = deps
        notes.append("elite: stock/purchase depends for inventory prompt")

    return notes


def run_elite_quality_pass(draft: dict[str, Any]) -> list[str]:
    """Emit module tests + i18n pot as custom_code_blocks."""
    notes: list[str] = []
    tech = str(draft.get("technical_name") or "custom_module")
    models = [str(m.get("model")) for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]
    if not models:
        return notes

    test_content = (
        "# -*- coding: utf-8 -*-\n"
        "from odoo.tests import tagged\n"
        "from odoo.tests.common import TransactionCase\n\n\n"
        "@tagged('post_install', '-at_install')\n"
        f"class Test{tech.replace('_', ' ').title().replace(' ', '')}Smoke(TransactionCase):\n"
        "    def test_models_registered(self):\n"
        "        Model = self.env['ir.model']\n"
        + "".join(
            f"        self.assertTrue(Model.search([('model', '=', '{mid}')], limit=1))\n"
            for mid in models[:8]
        )
    )
    _upsert_block(
        draft,
        {
            "source_file": f"tests/test_{tech}_smoke.py",
            "kind": "test",
            "reason": "elite: generated smoke tests",
            "content": test_content,
        },
    )
    notes.append("elite: tests/test smoke")

    pot_lines = ['msgid ""', 'msgstr ""', '""', '"Content-Type: text/plain; charset=UTF-8\\n"', '""', ""]
    display = str(draft.get("display_name") or tech)
    pot_lines.append(f'msgid "{display}"')
    pot_lines.append(f'msgstr "{display}"')
    pot_lines.append("")
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        desc = str(m.get("description") or m.get("model") or "")
        if desc:
            pot_lines.append(f'msgid "{desc}"')
            pot_lines.append(f'msgstr "{desc}"')
            pot_lines.append("")

    _upsert_block(
        draft,
        {
            "source_file": f"i18n/{tech}.pot",
            "kind": "i18n",
            "reason": "elite: translation template",
            "content": "\n".join(pot_lines) + "\n",
        },
    )
    notes.append(f"elite: i18n/{tech}.pot")
    return notes


def check_elite_scorecard_floors(scorecard: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (passes, reasons)."""
    reasons: list[str] = []
    floor = float(settings.elite_scorecard_floor or ELITE_SCORECARD_FLOOR)
    overall = float(scorecard.get("score_0_10") or 0)
    if overall < floor:
        reasons.append(f"overall {overall} < {floor}")
    dims = scorecard.get("dimensions") if isinstance(scorecard.get("dimensions"), dict) else {}
    for dim, floor in ELITE_DIMENSION_FLOORS.items():
        val = float(dims.get(dim) or 0)
        if val < floor:
            reasons.append(f"{dim} {val} < {floor}")
    validators = scorecard.get("validators") if isinstance(scorecard.get("validators"), dict) else {}
    if validators.get("xml_findings"):
        reasons.append("xml validator findings present")
    consistency = validators.get("consistency_findings") or []
    if len(consistency) > 2:
        reasons.append(f"too many consistency findings ({len(consistency)})")
    return (len(reasons) == 0, reasons)


def elite_promote_gate(draft: dict[str, Any]) -> tuple[bool, list[str]]:
    """Scorecard + lint gate before sandbox/promote autopilot."""
    reasons: list[str] = []
    sc = draft.get("_scorecard") if isinstance(draft.get("_scorecard"), dict) else {}
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    if not sc:
        reasons.append("missing _scorecard — run draft generation first")
    else:
        ok, floor_reasons = check_elite_scorecard_floors(sc)
        meta_score = meta.get("score_0_10")
        validators = sc.get("validators") if isinstance(sc.get("validators"), dict) else {}
        if not ok and meta_score is not None:
            if float(meta_score) >= float(settings.elite_scorecard_floor or ELITE_SCORECARD_FLOOR):
                if validators.get("all_green") or not validators.get("xml_findings"):
                    ok = True
                    floor_reasons = [
                        r for r in floor_reasons if not r.startswith("overall")
                    ]
        if not ok:
            reasons.extend(floor_reasons)
    lint = lint_custom_code_blocks(draft)
    lint_ok = bool(lint.get("ok"))
    if not lint_ok:
        failing = [
            b
            for b in (lint.get("blocks") or [])
            if b.get("issues")
            and not str(b.get("source_file") or "").startswith("tests/")
            and not str(b.get("source_file") or "").endswith(".pot")
        ]
        lint_ok = len(failing) == 0
    if not lint_ok:
        reasons.append("custom_code_blocks lint failed")
    blocks = merge_custom_code_blocks(draft)
    for block in blocks:
        kind = str(block.get("kind") or "")
        if kind in ("test", "i18n"):
            continue
        content = str(block.get("content") or "")
        if content and ("import os" in content or "import subprocess" in content):
            reasons.append("forbidden import in custom code")
    status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    mode = str(status.get("mode") or "")
    ambition = str((draft.get("_meta") or {}).get("ambition") or draft.get("ambition") or "")
    if ambition == "comprehensive" and mode == "pack_fallback":
        reasons.append("comprehensive prompt fell back to pack only")
    return (len(reasons) == 0, reasons)


def run_elite_ux_finish_pass(draft: dict[str, Any]) -> list[str]:
    """Ensure search views exist after late action/view synthesis (post-critique)."""
    from app.ai_production_shape import ensure_search_views

    return ensure_search_views(draft)


def run_elite_passes(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
) -> list[str]:
    """Run all ELITE enrichment passes in order."""
    notes: list[str] = []
    notes.extend(run_elite_python_pass(draft, user_prompt=user_prompt))
    notes.extend(run_elite_artifacts_pass(draft, user_prompt=user_prompt))
    notes.extend(run_elite_integration_pass(draft, user_prompt=user_prompt))
    notes.extend(run_elite_quality_pass(draft))
    notes.extend(run_elite_ux_finish_pass(draft))
    from app.ai_apply_readiness import sanitize_empty_field_tags

    notes.extend(sanitize_empty_field_tags(draft))
    draft["_elite"] = {
        "passes_applied": True,
        "notes_count": len(notes),
    }
    return notes


__all__ = [
    "ELITE_DIMENSION_FLOORS",
    "ELITE_SCORECARD_FLOOR",
    "check_elite_scorecard_floors",
    "elite_promote_gate",
    "run_elite_artifacts_pass",
    "run_elite_integration_pass",
    "run_elite_passes",
    "run_elite_python_pass",
    "run_elite_quality_pass",
    "run_elite_ux_finish_pass",
]
