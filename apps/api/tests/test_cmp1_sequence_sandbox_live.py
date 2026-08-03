"""CMP-1 live sandbox: workflow module assigns reference on create."""

from __future__ import annotations

import shutil

import pytest

from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip


@pytest.mark.integration
def test_cmp1_workflow_sequence_sandbox_install_populates_reference() -> None:
    if not shutil.which("docker"):
        pytest.skip("docker not available")

    from app.sandbox import (
        SANDBOX_DB,
        SANDBOX_PASSWORD,
        SANDBOX_USER,
        _sandbox_rpc,
        run_sandbox_install,
    )

    spec = ModuleSpec(
        technical_name="cmp1_seq_smoke",
        display_name="CMP1 Seq Smoke",
        models=[
            ModelSpec(
                model="x_cmp1_order",
                description="CMP1 Order",
                is_workflow=True,
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                ],
            )
        ],
    )
    zip_bytes = build_module_zip(spec)
    result = run_sandbox_install(zip_bytes, odoo_major=19)
    if not result.ok:
        pytest.skip(f"sandbox unavailable: {result.message}")

    uid, models = _sandbox_rpc(19)
    rec_id = models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        "x_cmp1_order",
        "create",
        [[{"x_name": "Smoke order"}]],
    )
    rows = models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        "x_cmp1_order",
        "read",
        [[rec_id]],
        {"fields": ["x_code", "x_name"]},
    )
    assert rows
    code = rows[0].get("x_code") or ""
    assert code.startswith("CMP1/")
    assert code != "/"
