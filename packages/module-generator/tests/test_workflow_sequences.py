"""CMP-1 workflow ir.sequence emission in generated modules."""

from __future__ import annotations

from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip, render_module_files


def test_workflow_model_emits_sequence_and_create_hook() -> None:
    spec = ModuleSpec(
        technical_name="wf_seq",
        display_name="Workflow Seq",
        models=[
            ModelSpec(
                model="x_work_order",
                description="Work Order",
                is_workflow=True,
                state_field={"field": "x_status", "transitions": [["draft", "done"]]},
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                    FieldSpec(
                        name="x_status",
                        ttype="selection",
                        string="Status",
                        selection="[('draft','Draft'),('done','Done')]",
                    ),
                ],
            )
        ],
    )
    files = render_module_files(spec)
    seq_xml = files["wf_seq/data/sequences.xml"]
    assert 'model="ir.sequence"' in seq_xml
    assert "x_work_order.ref" in seq_xml
    assert "WORK/" in seq_xml

    model_py = files["wf_seq/models/x_work_order.py"]
    assert "next_by_code" in model_py
    assert "x_code" in model_py

    manifest = files["wf_seq/__manifest__.py"]
    assert "data/sequences.xml" in manifest
    seq_pos = manifest.index("data/sequences.xml")
    views_pos = manifest.index("views/views.xml") if "views/views.xml" in manifest else len(manifest)
    assert seq_pos < views_pos or "views/views.xml" not in manifest


def test_existing_x_reference_field_reused() -> None:
    spec = ModuleSpec(
        technical_name="wf_ref",
        display_name="Workflow Ref",
        models=[
            ModelSpec(
                model="x_lease",
                description="Lease",
                state_field={"field": "x_status", "transitions": []},
                fields=[
                    FieldSpec(name="x_name", ttype="char", string="Name"),
                    FieldSpec(name="x_reference", ttype="char", string="Ref"),
                ],
            )
        ],
    )
    files = render_module_files(spec)
    assert "x_reference" in files["wf_ref/models/x_lease.py"]
    assert "x_code" not in files["wf_ref/models/x_lease.py"].split("create")[0]


def test_zip_contains_sequences_xml() -> None:
    raw = build_module_zip(
        ModuleSpec(
            technical_name="wf_zip",
            display_name="WF Zip",
            models=[
                ModelSpec(
                    model="x_order",
                    description="Order",
                    is_workflow=True,
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )
    import zipfile
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(raw)) as zf:
        names = zf.namelist()
    assert any(n.endswith("data/sequences.xml") for n in names)
