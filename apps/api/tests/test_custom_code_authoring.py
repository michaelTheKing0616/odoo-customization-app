"""DEV-2 — custom code authoring tests."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.custom_code_authoring import (  # noqa: E402
    lint_custom_code_blocks,
    lint_python,
    lint_xml,
    model_class_skeleton,
    normalize_block,
)
from app.module_spec_codec import export_draft_module_zip, merge_custom_code_blocks  # noqa: E402
from app.module_import import import_module_archive  # noqa: E402


def test_lint_python_syntax_error() -> None:
    issues = lint_python("def broken(")
    assert issues and issues[0]["code"] == "syntax_error"


def test_lint_python_import_warning() -> None:
    issues = lint_python("import os\nx = 1")
    assert any(i["code"] == "import_forbidden" for i in issues)


def test_lint_xml_malformed() -> None:
    issues = lint_xml("<odoo><record></odoo>")
    assert issues and issues[0]["code"] == "xml_malformed"


def test_lint_blocks_on_spec() -> None:
    spec = {
        "custom_code_blocks": [
            {"source_file": "models/x.py", "kind": "python", "content": "x = 1\n"},
            {"source_file": "data/x.xml", "kind": "xml", "content": "<odoo/>"},
        ]
    }
    out = lint_custom_code_blocks(spec)
    assert out["ok"] is True


def test_model_skeleton_includes_fields() -> None:
    spec = {
        "models": [
            {
                "model": "x_book",
                "description": "Book",
                "fields": [{"name": "x_title", "ttype": "char", "string": "Title"}],
            }
        ]
    }
    code = model_class_skeleton(spec, "x_book")
    assert "_name = 'x_book'" in code
    assert "x_title = fields.Char" in code


def test_round_trip_write_path_byte_identical() -> None:
    py = b'''from odoo import fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    x_dev_score = fields.Integer(string="Score")

    def _compute_x_dev_score(self):
        for rec in self:
            rec.x_dev_score = 1
'''
    raw = b"""<?xml version='1.0'?>
<odoo><record id="view_partner_dev" model="ir.ui.view"><field name="name">dev</field></record></odoo>"""
    import zipfile
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dev_test/__init__.py", "")
        zf.writestr("dev_test/__manifest__.py", "{'name':'dev','depends':['base'],'data':[]}")
        zf.writestr("dev_test/models/__init__.py", "from . import res_partner")
        zf.writestr("dev_test/models/res_partner.py", py)
        zf.writestr("dev_test/views/partner.xml", raw)
    imported = import_module_archive(buf.getvalue(), filename="dev_test.zip")
    spec = imported.as_dict()
    blocks = merge_custom_code_blocks(spec)
    assert blocks
    edited = dict(spec)
    blocks_copy = [dict(b) for b in blocks]
    blocks_copy[0]["content"] = blocks_copy[0]["content"] + "\n# edited\n"
    edited["custom_code_blocks"] = blocks_copy
    zip_bytes = export_draft_module_zip(edited, odoo_major=19)
    reimport = import_module_archive(zip_bytes, filename="dev_test.zip")
    round_blocks = merge_custom_code_blocks(reimport.as_dict())
    assert round_blocks[0]["content"].endswith("# edited\n")


def test_normalize_block() -> None:
    b = normalize_block({"path": "models/x.py", "source": "x=1"})
    assert b["source_file"] == "models/x.py"
    assert b["content"] == "x=1"
