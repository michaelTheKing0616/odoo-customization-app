"""CODE-AUDIT-13: REVIEW-CODE-AUDIT-10 probes and neighbour variants."""
import pytest

from tests.test_nf_bot_code_audit_11 import _m, _sev, _js, P, O

SA = ("<odoo><record id='s' model='ir.actions.server'><field name='name'>s</field>"
      "<field name='model_id' ref='base.model_res_partner'/><field name='state'>code</field>"
      "<field name='code'>{}</field></record></odoo>")


# ---------------------------------------------------------------- H1 exact match on a non-unique field
@pytest.mark.parametrize("body", [
    f"{P}.search([('company_id', '=', self.env.company.id)]).unlink()",
    f"{P}.search([('active', '=', self.active)]).unlink()",
    f"t = self.env.context.get('t', 'contact')\n{P}.search([('type', '=', t)]).unlink()",
    f"{P}.search([('user_id', '=', self.env.uid)]).write({{'active': False}})",
    f"{P}.search([('parent_id', '=', self.parent_id.id)]).unlink()",
    f"{P}.search([('id', 'child_of', self.env.context.get('x', 1))]).unlink()",
    f"{P}.sudo().search([('create_uid', '=', self.env.user.id)]).unlink()",
    f"{P}.search([('state', '=', 'draft')]).unlink()",
    f"{P}.search([('name', '=', self.name)]).unlink()",
    f"{P}.search([('id', 'child_of', 1)]).unlink()",
    f"{P}.search([('parent_id', '=', False)]).unlink()",
    f"{P}.search([('name', 'ilike', 'abc')]).unlink()",
])
def test_h1_non_unique_exact_match_mass(body):
    assert "high" in _sev(_m(body), "mass-change")


@pytest.mark.parametrize("body", [
    f"{P}.search([('id', '=', self.id)]).unlink()",
    f"{P}.search([('id', 'in', self.ids)]).unlink()",
    f"{P}.search([('id', '=', 7)]).unlink()",
    f"self.env['res.users'].search([('login', '=', 'bob')]).write({{'active': False}})",
    f"{P}.search([('partner_id', '=', self.id)]).unlink()",
    f"{P}.search([('state', '=', 'draft')], limit=1).unlink()",
])
def test_h1_unique_key_silent(body):
    assert not _sev(_m(body), "mass-change")


def test_h1_module_declared_unique_silent():
    pre = ""
    body = f"self.env['x.t'].search([('code', '=', self.code)]).unlink()"
    files = _m(body, pre)
    files["models/t.py"] = ("from odoo import models, fields\nclass T(models.Model):\n    _name = 'x.t'\n"
                            "    code = fields.Char()\n    _sql_constraints = [('c_uniq', 'unique(code)', 'x')]\n")
    assert not _sev(files, "mass-change")


@pytest.mark.parametrize("code", [
    "env['res.partner'].search([('company_id', '=', env.company.id)]).unlink()",
    "env['res.partner'].search([('user_id', '=', env.uid)]).write({'active': False})",
    "env['res.partner'].search([('id', 'child_of', env.context.get('x', 1))]).unlink()",
])
def test_h1_server_action_mass(code):
    assert "high" in _sev({"views/v.xml": SA.format(code)}, "server-mass-change")
