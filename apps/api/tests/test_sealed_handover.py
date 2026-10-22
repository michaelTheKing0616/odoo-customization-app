from app.job_autopilot.report import render_sealed_pdf_bytes, sealed_pages


def test_cover_contents_seal_and_fingerprint():
    md = "# Summary\nAll good.\n## Checks\nok"
    pages, extra, fp = sealed_pages(md, title="UAT delivery report", prepared="Prepared today")
    assert "UAT delivery report" in pages[0]
    assert pages[1][0] == "Contents" and any("Summary" in l for l in pages[1])
    assert pages[-1][0] == "Seal" and fp[:32] in pages[-1]
    assert list(extra) == [len(pages) - 1]


def test_pdf_is_valid():
    pdf = render_sealed_pdf_bytes("# A\nb", title="T", prepared="P")
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert b"/Count 4" in pdf


def test_qr_encodes_the_fingerprint():
    import segno

    from app.job_autopilot.report import _qr_ops

    ops = _qr_ops("ingenium:sha256:abc", 0, 0)
    assert ops[0] == "q" and ops[-1] == "Q" and sum(o.endswith(" re") for o in ops) > 50
    assert segno.make("ingenium:sha256:abc").designator
