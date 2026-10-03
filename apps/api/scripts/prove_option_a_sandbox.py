#!/usr/bin/env python3
"""T1-F3: prove a minimal option_a_authored module on the Odoo 19 sandbox.

Depends only on ``base``. Includes a trivial x_* model and a passing test.
Calls ``prove_option_a_in_sandbox(..., odoo_major=19, run_tests=True)``.
Does not promote. Does not write a customer database.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TECHNICAL_NAME = "option_a_prove_note"
DEFAULT_LOG = REPO / ".cache" / "t1_f3_option_a_prove_19.log"
DEFAULT_JSON = REPO / ".cache" / "t1_f3_option_a_prove_19.json"


def _minimal_authored_draft() -> dict:
    return {
        "technical_name": TECHNICAL_NAME,
        "display_name": "Option A Prove Note",
        "depends": ["base"],
        "grain": "full_app",
        "models": [
            {
                "model": "x_prove_note",
                "description": "Prove Note",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                    {"name": "x_body", "ttype": "char", "string": "Body"},
                ],
            }
        ],
        "custom_code_blocks": [
            {
                "option_a": True,
                "source_file": "models/prove_note_logic.py",
                "kind": "python",
                "reason": "option_a_authored: inherit Seen flag + mark-seen",
                "content": (
                    "from odoo import fields, models\n\n\n"
                    "class ProveNoteLogic(models.Model):\n"
                    "    _inherit = 'x_prove_note'\n\n"
                    "    x_seen = fields.Boolean(string='Seen', default=False)\n\n"
                    "    def action_mark_seen(self):\n"
                    "        self.x_seen = True\n"
                    "        return True\n"
                ),
            },
            {
                "source_file": "models/__init__.py",
                "kind": "python",
                "reason": "import option_a inherit file",
                "content": "from . import prove_note_logic\n",
            },
            {
                "source_file": "tests/__init__.py",
                "kind": "test",
                "reason": "tests package",
                "content": "from . import test_prove_note\n",
            },
            {
                "source_file": "tests/test_prove_note.py",
                "kind": "test",
                "reason": "trivial passing TransactionCase",
                "content": (
                    "# -*- coding: utf-8 -*-\n"
                    "from odoo.tests import tagged\n"
                    "from odoo.tests.common import TransactionCase\n\n\n"
                    "@tagged('post_install', '-at_install')\n"
                    "class TestProveNote(TransactionCase):\n"
                    "    def test_note_create_and_mark_seen(self):\n"
                    "        note = self.env['x_prove_note'].create({\n"
                    "            'x_name': 'T1-F3 prove',\n"
                    "            'x_body': 'trivial',\n"
                    "        })\n"
                    "        self.assertTrue(note.id)\n"
                    "        self.assertIn('x_seen', note._fields)\n"
                    "        note.action_mark_seen()\n"
                    "        self.assertTrue(note.x_seen)\n"
                ),
            },
        ],
        "_generation_engine": {
            "capability": "option_a_authored",
            "artifact_kind": "option_a_module",
            "delivery_lane": "module_sh_or_self",
            "prove_status": "pending",
        },
        "_user_prompt": (
            "Option A module: a trivial Prove Note model on base with a Seen flag. "
            "Zip then sandbox with tests. Do not promote."
        ),
    }


def _public_result(out: dict) -> dict:
    sandbox = out.get("sandbox") if isinstance(out.get("sandbox"), dict) else {}
    smoke = out.get("smoke") if isinstance(out.get("smoke"), dict) else {}
    return {
        "ok": out.get("ok"),
        "prove_status": out.get("prove_status"),
        "tests_ran": sandbox.get("tests_ran", smoke.get("tests_ran")),
        "test_failures": sandbox.get("test_failures") or smoke.get("test_failures") or [],
        "promote_eligible": out.get("promote_eligible"),
        "run_tests": out.get("run_tests"),
        "message": out.get("message") or sandbox.get("message") or smoke.get("message"),
        "module": sandbox.get("module"),
        "install_attempts": out.get("install_attempts"),
        "repairs_used": out.get("repairs_used"),
        "log_tail": sandbox.get("log_tail") or smoke.get("log_tail") or "",
    }


def main() -> int:
    from app.ai_generation_engine import is_option_a_authored_draft
    from app.ai_option_a_quality import prove_option_a_in_sandbox, structural_option_a_smoke
    from app.ai_structural_zip_gate import structural_zip_gate
    from app.module_spec_codec import export_draft_module_zip

    draft = _minimal_authored_draft()
    if not is_option_a_authored_draft(draft):
        print("draft is not option_a_authored", file=sys.stderr)
        return 2

    zip_bytes = export_draft_module_zip(draft, odoo_major=19)
    gate = structural_zip_gate(zip_bytes)
    structural = structural_option_a_smoke(draft)
    if not gate.get("ok") or not structural.get("structural_ok"):
        payload = {
            "ok": False,
            "prove_status": "failed",
            "tests_ran": False,
            "preflight": {"structural_zip_gate": gate, "structural_option_a_smoke": structural},
        }
        print(json.dumps(payload, indent=2))
        return 1

    started = datetime.now(UTC).isoformat()
    out = prove_option_a_in_sandbox(
        draft, odoo_major=19, run_tests=True, auto_repair=False
    )
    public = _public_result(out)
    public["started_at"] = started
    public["finished_at"] = datetime.now(UTC).isoformat()
    public["capability"] = "option_a_authored"
    public["odoo_major"] = 19
    public["technical_name"] = TECHNICAL_NAME
    public["promoted"] = False

    DEFAULT_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_text = (
        f"T1-F3 option_a_authored prove odoo_major=19 run_tests=True\n"
        f"started={public['started_at']} finished={public['finished_at']}\n"
        f"ok={public['ok']} prove_status={public['prove_status']} "
        f"tests_ran={public['tests_ran']} promote_eligible={public['promote_eligible']}\n"
        f"message={public.get('message') or ''}\n"
        f"test_failures={public.get('test_failures')}\n\n"
        f"--- sandbox log_tail ---\n"
        f"{public.get('log_tail') or ''}\n"
    )
    DEFAULT_LOG.write_text(log_text)
    DEFAULT_JSON.write_text(json.dumps({**public, "log_path": str(DEFAULT_LOG)}, indent=2) + "\n")
    public["log_path"] = str(DEFAULT_LOG)
    print(json.dumps({k: v for k, v in public.items() if k != "log_tail"}, indent=2))
    print(f"log_path={DEFAULT_LOG}")
    if public.get("ok") and public.get("prove_status") == "proved" and public.get("tests_ran"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
