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


# ---------------------------------------------------------------- H2 JS string / URL mutation folded
@pytest.mark.parametrize("src", [
    "fetch('/web/dataset/call_kw/res.XXXX/write'.replace('XXXX','users'),{method:'POST'});",
    "const u=new URL(location.origin); u.pathname='/web/dataset/call_kw/res.users/write'; fetch(u,{method:'POST'});",
    "const u=new URL(location.origin); u.href='/web/dataset/call_kw/res.users/unlink'; fetch(u,{method:'POST'});",
    "fetch('/WEB/DATASET/CALL_KW/RES.USERS/WRITE'.toLowerCase(),{method:'POST'});",
    "fetch('/web/dataset/call_kw/res.users/write/xx'.slice(0, -3),{method:'POST'});",
    "fetch('/web/dataset/call_kw/res.U/write'.replaceAll('U','users'),{method:'POST'});",
    "const u=new URL('/', location.origin); Object.assign(u, {pathname: '/web/dataset/call_kw/res.users/write'}); fetch(u,{method:'POST'});",
    "function f(p){ const u=new URL(location.origin); u.pathname=p; fetch(u,{method:'POST'}); }",
    "function f(m){ const u=new URL(location.origin); u.pathname='/web/dataset/call_kw/' + m + '/write'; fetch(u,{method:'POST'}); }",
    "function f(m){ fetch('/web/dataset/call_kw/' + m + '/write', {method:'POST'}); }",
])
def test_h2_mutated_url_sensitive_high(src):
    assert "high" in _sev(_js(src), "js-sensitive-model")


@pytest.mark.parametrize("src", [
    "const u=new URL(location.origin); u.pathname='/shop/cart'; fetch(u,{method:'POST'});",
    "fetch('/web/image/XX'.replace('XX','1'));",
    "const u=new URL('/web/dataset/call_kw/res.partner/read', location.origin); u.search='?a=1'; fetch(u,{method:'POST'});",
])
def test_h2_benign_mutation_silent(src):
    assert "high" not in _sev(_js(src), "js-sensitive-model")


# ---------------------------------------------------------------- H3 + L2 in-place / aliased state domain
_DEL = "await this.orm.unlink('res.partner', await this.orm.search('res.partner', {d}));"


def _comp(body, d="this.state.domain"):
    return "class C extends Component {\n setup(){ this.state = useState({domain: [['id','=',1]]}); }\n" + body + "\n async go(){ " + _DEL.format(d=d) + " }\n}"


@pytest.mark.parametrize("src", [
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ Object.assign(this.state, {domain: []}); }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ const s = this.state; s.domain = []; }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ const s = this; s.state.domain = []; }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ this.state.domain.splice(0); }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ this.state.domain.length = 0; }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ this.state.domain.push('|', ['id','!=',0]); }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(x){ Object.assign(this.state, x); }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ this.state.domain.pop(); }"),
    _comp("onSearch(d){ this.state.domain = d; } wipe(){ this.state.domain[0] = '|'; }"),
])
def test_h3_inplace_state_domain_high(src):
    assert "high" in _sev(_js(src), "js-mass-change")


def test_h3_user_selection_still_bounded():
    src = _comp("onSearch(d){ this.state.domain = d; }")
    assert "high" not in _sev(_js(src), "js-mass-change")


def test_l2_props_and_this_domain_agree():
    a = "class C extends Component {\n async go(){ " + _DEL.format(d="this.props.domain") + " }\n}"
    b = "class C extends Component {\n setup(){ this.domain = this.props.domain; }\n async go(){ " + _DEL.format(d="this.domain") + " }\n}"
    va, vb = _sev(_js(a), "js-mass-change"), _sev(_js(b), "js-mass-change")
    assert ("high" in va) == ("high" in vb)
    xml = '<templates><t t-name="m.P"><C domain="[]"/></t></templates>'
    for s in (a, b):
        assert "high" in _sev({**_js(s), "static/src/p.xml": xml}, "js-mass-change")
    js2 = "this.dialog.add(C, {domain: []});"
    assert "high" in _sev(_js(a + "\n" + js2), "js-mass-change")


# ---------------------------------------------------------------- M1 exec sinks / network keep rank in tests/
_TH = "from odoo.tests.common import TransactionCase\n\n\nclass T(TransactionCase):\n    def test_a(self):\n"


@pytest.mark.parametrize("line,code,sev", [
    ("eval(self.env.context.get('x', ''))", "eval-exec", "high"),
    ("exec(self.env.context.get('x', ''))", "eval-exec", "high"),
    ("compile(self.env.context.get('x', ''), 'f', 'exec')", "compile-code", "high"),
    ("compile('1', 'f', 'eval')", "compile-code", "medium"),
])
def test_m1_exec_sinks_keep_rank_in_tests(line, code, sev):
    for path in ("tests/test_a.py", "tests/sub/test_b.py"):
        assert sev in _sev({path: _TH + "        " + line + "\n"}, code)


def test_m1_outbound_network_keeps_rank_in_tests():
    src = "import requests\n" + _TH + "        requests.get('http://x')\n"
    prod = _sev({"models/a.py": src}, "outbound-network")
    assert prod and _sev({"tests/test_a.py": src}, "outbound-network") == prod
