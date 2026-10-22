from app.email_receipt import receipt_html


def test_one_button_escaped_and_dark_safe():
    h = receipt_html(title="Reset <you>", lead="Lead", button_label="Go", button_url="https://x.test/r?a=1&b=2", reference="REF-1")
    assert h.count("<a ") == 1
    assert "Reset &lt;you&gt;" in h and "a=1&amp;b=2" in h
    assert 'name="color-scheme" content="light dark"' in h
    assert "<img" not in h
    assert "ui-monospace" in h
