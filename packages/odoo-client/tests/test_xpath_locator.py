"""Upgrade-safe xpath locator scoring, rewrite, and issue classification."""

from odoo_client.xpath_locator import (
    classify_locator,
    classify_xpath_arch,
    count_xpath_matches,
    is_positional,
    rewrite_locator,
    score_locator,
    semantic_field_candidates,
    semantic_inject_expr,
)
from odoo_client.view_arch import render_inherit_xpath_arch, validate_xpath_arch

PARTNER_ARCH = """
<form>
  <sheet>
    <group id="header_left_group">
      <field name="partner_id"/>
    </group>
    <group string="Other">
      <field name="ref"/>
    </group>
    <notebook>
      <page string="Lines">
        <field name="line_ids">
          <list>
            <field name="partner_id"/>
          </list>
        </field>
      </page>
    </notebook>
  </sheet>
</form>
"""


def test_score_prefers_named_over_positional() -> None:
    named = score_locator("//field[@name='partner_id']")
    scoped = score_locator("//group[@id='header_left_group']//field[@name='partner_id']")
    positional = score_locator("//sheet/group[2]/field[1]")
    assert named > positional
    assert scoped >= named
    assert is_positional("//group[1]")
    assert not is_positional("//field[@name='email']")


def test_count_matches_evaluates_odoo_double_slash() -> None:
    assert count_xpath_matches(PARTNER_ARCH, "//field[@name='partner_id']") == 2
    assert count_xpath_matches(PARTNER_ARCH, "//group[@id='header_left_group']") == 1
    assert count_xpath_matches(PARTNER_ARCH, "//field[@name='missing']") == 0


def test_rewrite_group_index_to_named_id() -> None:
    rewritten = rewrite_locator("//group[1]", PARTNER_ARCH)
    assert rewritten == "//group[@id='header_left_group']"
    assert "[1]" not in rewritten


def test_semantic_inject_prefers_named_group() -> None:
    assert semantic_inject_expr(None, "form") == "//sheet"
    assert semantic_inject_expr(PARTNER_ARCH, "form") == "//group[@id='header_left_group']"
    single = '<form><sheet><group><field name="x"/></group></sheet></form>'
    assert semantic_inject_expr(single, "form") == "//group"


def test_partner_id_candidates_are_unique_named() -> None:
    cands = semantic_field_candidates(PARTNER_ARCH, "partner_id")
    assert len(cands) >= 2
    assert cands[0].xpath == "//group[@id='header_left_group']//field[@name='partner_id']"
    assert cands[0].match_count == 1
    assert not cands[0].fragile


def test_classify_missing_and_ambiguous() -> None:
    missing = classify_locator("//field[@name='nope']", parent_arch=PARTNER_ARCH)
    assert any(i.code == "missing_node" and i.severity == "error" for i in missing)
    amb = classify_locator("//field[@name='partner_id']", parent_arch=PARTNER_ARCH)
    assert any(i.code == "ambiguous_match" and i.severity == "error" for i in amb)
    ok = classify_locator(
        "//group[@id='header_left_group']//field[@name='partner_id']",
        parent_arch=PARTNER_ARCH,
    )
    assert not any(i.severity == "error" for i in ok)


def test_classify_positional_warning_and_invalid_body() -> None:
    issues = classify_locator(
        "//group[2]", parent_arch=PARTNER_ARCH, body_xml="<field name='x'/>"
    )
    assert any(i.code == "positional_fragility" and i.severity == "warning" for i in issues)
    assert any(i.suggestion == "//group[@string='Other']" for i in issues if i.suggestion)
    bad_body = classify_locator("//sheet", parent_arch=PARTNER_ARCH, body_xml="<field")
    assert any(i.code == "invalid_body_xml" and i.severity == "error" for i in bad_body)


def test_validate_xpath_arch_parent_missing() -> None:
    arch = render_inherit_xpath_arch(
        expr="//field[@name='missing']",
        position="inside",
        body_xml="<field name='x_extra'/>",
    )
    issues = validate_xpath_arch(arch, parent_arch=PARTNER_ARCH)
    assert any("matches no node" in i for i in issues)
    assert not any("matches no node" in i for i in validate_xpath_arch(arch))


def test_classify_xpath_arch_invalid_xml() -> None:
    issues = classify_xpath_arch("<data><xpath")
    assert issues[0].code == "invalid_xml"
    assert issues[0].severity == "error"
