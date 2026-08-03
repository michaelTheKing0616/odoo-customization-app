"""Website block parser tests (UIX-7 / REM-7)."""

from app.website_blocks import blocks_from_dicts, parse_website_arch, render_website_arch

SAMPLE_ARCH = """
<section>
  <h2>Welcome</h2>
  <p>Hello world</p>
  <a href="/contact">Contact us</a>
  <button formaction="/signup">Sign up</button>
  <img src="/web/image/1"/>
  <t t-foreach="items" t-as="item"/>
</section>
"""


def test_parser_recognized_blocks() -> None:
    blocks = parse_website_arch(SAMPLE_ARCH)
    kinds = [b.kind for b in blocks]
    assert "section" in kinds
    sec = next(b for b in blocks if b.kind == "section")
    child_kinds = [c.kind for c in sec.children]
    assert "heading" in child_kinds
    assert "paragraph" in child_kinds
    assert "link" in child_kinds
    assert "button" in child_kinds
    assert "image" in child_kinds


def test_locked_block_round_trip_byte_identical() -> None:
    locked = '<t t-foreach="items" t-as="item"/>'
    arch = f"<section><p>Hi</p>{locked}</section>"
    blocks = parse_website_arch(arch)
    out = render_website_arch(blocks)
    assert out == arch


def test_full_arch_round_trip_with_locked_snippet() -> None:
    arch = (
        "<section><h2>Title</h2><p>Body</p>"
        '<t t-call="website.layout"/>'
        '<img src="/web/image/42"/>'
        "</section>"
    )
    blocks = parse_website_arch(arch)
    out = render_website_arch(blocks)
    assert out == arch


def test_button_href_label_round_trip() -> None:
    arch = '<button formaction="/go">Click me</button>'
    blocks = parse_website_arch(arch)
    btn = blocks[0]
    assert btn.kind == "button"
    assert btn.href == "/go"
    assert btn.text == "Click me"
    out = render_website_arch(blocks)
    assert out == arch


def test_round_trip_simple_paragraph() -> None:
    arch = "<p>Alpha</p>"
    blocks = parse_website_arch(arch)
    out = render_website_arch(blocks)
    assert out == arch


def test_blocks_from_dicts_nested_children() -> None:
    raw = [
        {
            "id": "sec-1",
            "kind": "section",
            "children": [
                {"id": "p-1", "kind": "paragraph", "text": "Nested"},
            ],
        }
    ]
    blocks = blocks_from_dicts(raw)
    assert blocks[0].children[0].text == "Nested"
    out = render_website_arch(blocks)
    assert out == "<section><p>Nested</p></section>"
