"""CMP-3 CSS palette extraction parser."""

from __future__ import annotations

from app.palette_extract import parse_theme_from_css, theme_to_preview_vars


SAMPLE_CSS = """
:root {
  --o-brand-primary: #714B67;
  --o-brand-secondary: #017e84;
  --o-color-success: #28a745;
}
.o_form_view { color: var(--o-brand-primary); }
"""


def test_parse_theme_from_css_fixture() -> None:
    theme = parse_theme_from_css(SAMPLE_CSS)
    assert theme["primary"] == "#714B67"
    assert theme["accent"] == "#017e84"


def test_theme_to_preview_vars_maps_primary() -> None:
    vars_ = theme_to_preview_vars({"primary": "#714B67"})
    assert vars_["--odoo-primary"] == "#714B67"
    assert vars_["--odoo-statusbar"] == "#714B67"


def test_theme_to_preview_vars_empty_without_primary() -> None:
    assert theme_to_preview_vars({}) == {}
