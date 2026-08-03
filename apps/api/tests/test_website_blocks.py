"""Website block parser tests (UIX-7)."""

from app.website_blocks import parse_website_arch, render_website_arch

SAMPLE_ARCH = """
<section>
  <h2>Welcome</h2>
  <p>Hello world</p>
  <a href="/contact">Contact us</a>
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
    assert "image" in child_kinds


def test_locked_block_round_trip_byte_identical() -> None:
    locked = '<t t-foreach="items" t-as="item"/>'
    arch = f"<section><p>Hi</p>{locked}</section>"
    blocks = parse_website_arch(arch)
    out = render_website_arch(blocks)
    assert locked in out
    assert "<p>Hi</p>" in out


def test_round_trip_simple_paragraph() -> None:
    arch = "<p>Alpha</p>"
    blocks = parse_website_arch(arch)
    out = render_website_arch(blocks)
    assert "Alpha" in out
    assert "<p>" in out
