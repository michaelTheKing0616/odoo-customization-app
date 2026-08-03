"""DEPLOY_ODOO_SH.md zip injection."""

from __future__ import annotations

import zipfile
from io import BytesIO

from app.deploy_odoo_sh import deploy_odoo_sh_markdown, inject_file_into_zip


def test_deploy_markdown_contains_module_name() -> None:
    md = deploy_odoo_sh_markdown(
        technical_name="my_mod", display_name="My Mod", odoo_major=19
    )
    assert "my_mod" in md
    assert "19" in md


def test_inject_file_into_zip() -> None:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("my_mod/__manifest__.py", "{}")
    out = inject_file_into_zip(buf.getvalue(), "my_mod/DEPLOY_ODOO_SH.md", "# Deploy")
    with zipfile.ZipFile(BytesIO(out)) as zf:
        names = zf.namelist()
    assert "my_mod/DEPLOY_ODOO_SH.md" in names
