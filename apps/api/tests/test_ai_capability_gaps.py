"""Domain-agnostic capability gaps — PDF/QR/pay vs field packs."""

from __future__ import annotations

from app.ai_capability_gaps import assess_capability_gaps, stamp_capability_gaps
from app.ai_component_builder import draft_component_from_prompt
from app.ai_draft_scorecard import attach_scorecard
from app.ai_live_apply_contract import attach_live_apply_contract
from app.ai_senior_shape import infer_extension_fields


PDF_QR_PROMPT = (
    "Add dynamic QR codes or click-to-pay buttons directly on the PDF for Invoices"
)


def test_assess_pdf_qr_pay_is_primary_option_a() -> None:
    a = assess_capability_gaps(PDF_QR_PROMPT)
    assert a.primary_option_a is True
    ids = {g.id for g in a.gaps}
    assert "pdf_report" in ids
    assert "qr_on_document" in ids
    assert "click_to_pay" in ids


def test_infer_extension_fields_no_junk_for_pdf_qr() -> None:
    fields = infer_extension_fields(PDF_QR_PROMPT)
    names = {str(f.get("name")) for f in fields}
    assert "x_dynamic" not in names
    assert "x_notes" not in names
    assert "x_active" not in names
    assert "x_payment_url" in names
    assert "x_qr_payload" in names


def test_sla_still_infer_three_fields() -> None:
    fields = infer_extension_fields("Add SLA due date on invoices")
    names = {str(f.get("name")) for f in fields}
    assert "x_sla_due" in names
    assert "x_sla_status" in names
    assert "x_sla_hours" in names
    assert assess_capability_gaps("Add SLA due date on invoices").gaps == []


def test_single_sla_datetime_field_is_not_padded() -> None:
    prompt = (
        "Finance asked for a single extra field on customer invoices: "
        "SLA due date and time. Just inherit the stock invoice."
    )
    fields = infer_extension_fields(prompt)
    names = [str(f.get("name")) for f in fields]
    assert names == ["x_sla_due"]
    assert fields[0].get("ttype") == "datetime"


def test_mixed_sla_and_qr_keeps_sla_plus_stubs() -> None:
    prompt = "Add SLA due date and a QR code on the PDF for invoices"
    a = assess_capability_gaps(prompt)
    assert a.primary_option_a is False
    fields = infer_extension_fields(prompt)
    names = {str(f.get("name")) for f in fields}
    assert "x_sla_due" in names
    assert "x_qr_payload" in names


def test_component_draft_pdf_qr_stamps_option_a() -> None:
    draft, hosts, _ = draft_component_from_prompt(
        PDF_QR_PROMPT,
        available_models=["account.move", "sale.order"],
    )
    assert hosts[0].model == "account.move"
    assert draft.get("_capability_primary_option_a") is True
    inherit = next(m for m in draft["models"] if m.get("mode") == "inherit")
    names = {str(f.get("name")) for f in inherit.get("fields") or []}
    assert "x_dynamic" not in names
    assert "x_notes" not in names
    assert "x_payment_url" in names
    assert "x_qr_payload" in names
    attach_live_apply_contract(draft)
    attach_scorecard(draft, user_prompt=PDF_QR_PROMPT)
    option_a = (draft.get("_live_apply") or {}).get("option_a") or []
    assert option_a
    assert any("PDF" in str(x) or "QR" in str(x) or "pay" in str(x).lower() for x in option_a)
    findings = (draft.get("_scorecard") or {}).get("findings") or []
    assert not any(f.get("element") == "noun:code" for f in findings)
    assert not any(f.get("element") == "noun:click" for f in findings)
    assert not any(f.get("element") == "noun:directly" for f in findings)


def test_stamp_capability_gaps_idempotent() -> None:
    draft = {
        "models": [
            {
                "model": "account.move",
                "mode": "inherit",
                "fields": [
                    {"name": "x_dynamic", "ttype": "char"},
                    {"name": "x_notes", "ttype": "text"},
                ],
            }
        ],
        "views": [],
        "connect_points": {"sub_menu_name": "Pay / QR"},
    }
    notes = stamp_capability_gaps(draft, PDF_QR_PROMPT)
    assert notes
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_dynamic" not in names
    assert "x_payment_url" in names
    blocks = draft.get("custom_code_blocks") or []
    assert any(
        isinstance(b, dict)
        and str(b.get("source_file") or "").endswith("_document_extras.xml")
        and "account.report_invoice_document" in str(b.get("content") or "")
        for b in blocks
    )
    assert any(
        isinstance(b, dict)
        and str(b.get("source_file") or "").endswith("_document_extras.py")
        and "action_refresh_pay_qr_stubs" in str(b.get("content") or "")
        for b in blocks
    )
    count1 = len(blocks)
    stamp_capability_gaps(draft, PDF_QR_PROMPT)
    assert len(draft["custom_code_blocks"]) == count1


def test_pdf_qr_option_a_zip_contains_report_inherit() -> None:
    from app.custom_code_authoring import lint_custom_code_blocks
    from app.module_spec_codec import export_draft_module_zip
    from module_generator import render_module_files
    from app.module_spec_codec import draft_dict_to_module_spec
    import zipfile
    import io

    draft, _hosts, _w = draft_component_from_prompt(
        PDF_QR_PROMPT,
        available_models=["account.move", "sale.order"],
    )
    stamp_capability_gaps(draft, PDF_QR_PROMPT)
    lint = lint_custom_code_blocks(draft)
    # OWL/js blocks are skipped by lint kind; python/xml must be clean.
    py_xml = [
        b
        for b in lint["blocks"]
        if str(b.get("source_file") or "").endswith((".py", ".xml"))
    ]
    assert all(not b.get("issues") for b in py_xml), lint

    spec = draft_dict_to_module_spec(draft)
    files = render_module_files(spec)
    root = spec.technical_name
    report_key = next(k for k in files if k.endswith("_document_extras.xml"))
    assert "account.report_invoice_document" in files[report_key]
    assert "Pay now" in files[report_key]
    assert "QR" in files[report_key]
    py_key = next(k for k in files if k.endswith("_document_extras.py"))
    assert "_sync_pay_qr_stubs" in files[py_key]
    assert "from . import" in files[f"{root}/models/__init__.py"]
    assert "account_move_document_extras" in files[f"{root}/models/__init__.py"]
    manifest = files[f"{root}/__manifest__.py"]
    assert "report/account_move_document_extras.xml" in manifest
    assert "account" in (draft.get("depends") or [])

    zbytes = export_draft_module_zip(draft)
    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        names = zf.namelist()
        assert any(n.endswith("_document_extras.xml") for n in names)
        assert any(n.endswith("_document_extras.py") for n in names)


def test_website_owl_email_gaps_are_option_a() -> None:
    a = assess_capability_gaps("Add a website controller for public booking confirmation")
    assert any(g.id == "website_controller" for g in a.gaps)
    assert a.primary_option_a is True
    assert infer_extension_fields(
        "Add a website controller for public booking confirmation"
    ) == []

    a = assess_capability_gaps("Add an OWL widget dashboard on the project task form")
    assert any(g.id == "owl_widget" for g in a.gaps)
    assert a.primary_option_a is True
    names = {f["name"] for f in infer_extension_fields(
        "Add an OWL widget dashboard on the project task form"
    )}
    assert "x_owl" not in names
    assert "x_widget" not in names

    # QR-in-mail still hits reportish gaps → primary Option A (not a field pack).
    a = assess_capability_gaps("Add an HTML mail template with a QR on the invoice email")
    assert any(g.id == "email_template_html" for g in a.gaps)
    assert any(g.id == "qr_on_document" for g in a.gaps)
    assert a.primary_option_a is True


def test_python_compute_prompt_is_option_a_not_primary_report() -> None:
    a = assess_capability_gaps("Add a python compute for line totals on sale orders")
    assert any(g.id == "python_logic" for g in a.gaps)
    assert a.primary_option_a is True
    assert "x_python" not in {
        f["name"] for f in infer_extension_fields(
            "Add a python compute for line totals on sale orders"
        )
    }

    # Warranty + python → live fields win; still stamp python gap, no x_python.
    prompt = "Add a python compute for warranty expiry on sale orders"
    a = assess_capability_gaps(prompt)
    assert any(g.id == "python_logic" for g in a.gaps)
    assert a.primary_option_a is False
    names = {f["name"] for f in infer_extension_fields(prompt)}
    assert "x_warranty_end" in names or "x_compliance_expiry" in names
    assert "x_python" not in names


def test_markup_stays_primary_option_a_even_after_field_clarify() -> None:
    prompt = (
        'The Client wants a "Mark-up" line added to every Sale they make. '
        "A Witholding Tax on the markup only, and only for Sales, NOT Purchases.\n"
        "Add fields on an existing Odoo form people already use."
    )
    a = assess_capability_gaps(prompt)
    assert any(g.id == "python_logic" for g in a.gaps)
    assert a.primary_option_a is True
