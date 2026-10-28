"""CODE-AUDIT-12: REVIEW-CODE-AUDIT-9 (3H/3M/1L) root causes. Each: probe, >=3 variants, benign twin."""
import pytest

from tests.test_nf_bot_code_audit_5 import codes
from tests.test_nf_bot_code_audit_11 import _m, _sev, _js, P, O

# ---------------------------------------------------------------- H1 open ranges are non-selective
@pytest.mark.parametrize("body", [
    f"{P}.search([('create_date', '<', fields.Date.today())]).unlink()",  # probe
    f"{P}.search([('write_date', '<=', fields.Datetime.now())]).write({{'active': False}})",
    f"{P}.search([('id', '<', 10**9)]).unlink()",
    f"big = 10**9\n{P}.search([('id', '<', big)]).unlink()",
    f"{P}.search([('id', '>', self.env.context.get('x', 0))]).unlink()",
    f"n = {P}.search_count([])\n{P}.search([('id', '<=', n)]).action_archive()",
    f"{P}.search([('name', 'ilike', self.env.context.get('q'))]).unlink()",
])
def test_h1_open_range_mass_change(body):
    assert "high" in _sev(_m(body), "mass-change")


@pytest.mark.parametrize("body", [
    f"{P}.search([('id', '=', self.env.context.get('active_id'))]).unlink()",
    f"{P}.search([('parent_id', '=', self.id), ('create_date', '<', fields.Date.today())]).unlink()",
    f"{P}.search([('id', 'in', self.ids)]).write({{'active': False}})",
    f"{P}.search([('create_date', '<', fields.Date.today())], limit=100).unlink()",
])
def test_h1_bounded_silent(body):
    assert not _sev(_m(body), "mass-change")


@pytest.mark.parametrize("code", [
    "env['res.partner'].search([('create_date', '&lt;', datetime.datetime.now())]).unlink()",
    "env['res.partner'].search([('id', '&lt;', 10**9)]).unlink()",
    "env['res.partner'].search([('id', '>', env.context.get('x', 0))]).write({'active': False})",
])
def test_h1_server_action_mass(code):
    from tests.test_nf_bot_code_audit_11 import test_h12_server_mass_change_high as h12
    h12(code)
