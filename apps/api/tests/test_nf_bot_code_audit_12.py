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


# ---------------------------------------------------------------- H2 URL objects / dynamic URLs to the ORM
@pytest.mark.parametrize("src", [
    "const u=new URL('/web/dataset/call_kw/res.users/write', location.origin); fetch(u,{method:'POST', body: JSON.stringify({params: {model: 'res.users', method: 'write', args: [[1], {login: 'x'}]}})});",
    "const u=new URL('/web/dataset/call_kw/res.users/write', location.origin); fetch(u,{method:'POST'}); fetch(u.href,{method:'POST', body: JSON.stringify({params: {args: [[2], {}]}})});",
    "const b=location.origin; fetch(b + '/web/dataset/call_kw/res.users/write', {method:'POST', body: JSON.stringify({params: {args: [[1], {}]}})});",
    "const q=new Request(new URL('/web/dataset/call_kw/res.users/write', location.origin), {method:'POST', body: JSON.stringify({params: {args: [[1], {}]}})}); fetch(q);",
    "const u=new URL('/web/dataset/call_kw/res.users/write', location.origin); u.search = new URLSearchParams({a: 1}); fetch(String(u), {method: 'POST', body: JSON.stringify({params: {args: [[1], {}]}})});",
])
def test_h2_url_object_orm_high(src):
    assert "high" in _sev(_js(src), "js-sensitive-model")


@pytest.mark.parametrize("src", [
    "function f(url, payload) { return fetch(url, {method: 'POST', body: JSON.stringify(payload)}); }",
    "function f(base, m) { return fetch(base + '/' + m, {method: 'POST', body: JSON.stringify({params: {model: m, method: 'unlink', args: [[1]]}})}); }",
    "function f(u, data) { const x = new XMLHttpRequest(); x.open('POST', u); x.send(data); }",
])
def test_h2_dynamic_url_unprovable_high(src):
    assert "high" in _sev(_js(src), "js-raw-orm-request")


@pytest.mark.parametrize("src", [
    "function f(id, fd) { const d = new FormData(); return fetch('/web/binary/upload_attachment/' + id, {method: 'POST', body: d}); }",
    "function f(url) { const d = new FormData(); return fetch(url, {method: 'POST', body: d}); }",
    "function f(url) { return fetch(url); }",
    "function f(url) { return fetch(url, {method: 'POST', body: JSON.stringify({csrf_token: 'x', name: 'y'})}); }",
])
def test_h2_benign_silent(src):
    files = _js(src)
    assert not {s for s in _sev(files, "js-raw-orm-request") if s == "high"}
    assert not _sev(files, "js-sensitive-model")


def test_h2_review_probe_url_object_no_body():
    src = "const u=new URL('/web/dataset/call_kw/res.users/write', location.origin); fetch(u,{method:'POST'});"
    assert "high" in _sev(_js(src), "js-sensitive-model")


# ---------------------------------------------------------------- H3 view-state domains judged on their merits
_DEL = f"async del() {{ const ids = await {O}.search(this.resModel, %s); await {O}.unlink(this.resModel, ids); }}"


@pytest.mark.parametrize("cls", [
    "class L { setup() { this.domain = []; } " + _DEL % "this.domain" + " }",
    "class L { setup() { this.state = useState({domain: [['id', '!=', 0]]}); } " + _DEL % "this.state.domain" + " }",
    "class L { setup() { this.domain = JSON.parse(this.props.cfg); } " + _DEL % "this.domain" + " }",
    "class L { domain = [['active', 'in', [true, false]]]; " + _DEL % "this.domain" + " }",
    "class L { static defaultProps = {domain: []}; " + _DEL % "this.props.domain" + " }",
    "class L { setup() { this.state = useState({domain: []}); } load() { this.state.domain = this.props.cfg.domain; } " + _DEL % "this.state.domain" + " }",
])
def test_h3_module_assigned_state_domain_high(cls):
    assert "high" in _sev(_js(cls), "js-mass-change")


@pytest.mark.parametrize("cls", [
    "class L { " + _DEL % "this.domain" + " }",
    "class L { setup() { this.state = useState({domain: [['id', '=', this.props.resId]]}); } " + _DEL % "this.state.domain" + " }",
    "class L { onSearch(domain) { this.domain = domain; } " + _DEL % "this.domain" + " }",
    "class L { setup() { this.domain = this.env.searchModel.domain; } " + _DEL % "this.domain" + " }",
    "class L { " + _DEL % "this.props.domain" + " }",
])
def test_h3_user_selection_silent(cls):
    assert not _sev(_js(cls), "js-mass-change")


# ---------------------------------------------------------------- M1 exec sinks in tests/ keep their rank
_TH = "from odoo.tests.common import TransactionCase\n"


@pytest.mark.parametrize("body", [
    'import os\nos.system("x")\n',
    'import subprocess\nsubprocess.run(["id"])\n',
    'import os\nos.popen("id").read()\n',
    'import subprocess\nclass T(TransactionCase):\n    def test_a(self):\n        subprocess.check_output("id", shell=True)\n',
])
def test_m1_tests_exec_sink_high(body):
    assert "high" in _sev({"tests/test_x.py": _TH + body}, "dangerous-call")


def test_m1_non_test_same_severity():
    body = 'import os\nos.system("x")\n'
    assert _sev({"tests/test_x.py": _TH + body}, "dangerous-call") == _sev({"models/x.py": _TH + body}, "dangerous-call")


def test_m1_benign_test_silent():
    body = "class T(TransactionCase):\n    def test_a(self):\n        self.assertTrue(self.env['res.partner'].search([('id', '=', 1)]))\n"
    assert not _sev({"tests/test_x.py": _TH + body}, "dangerous-call")


# ---------------------------------------------------------------- M2 QWeb list/dict pop() on render values
def _qw(expr):
    return {"report/r.xml": f"<odoo><template id='r'><t t-foreach='range(2)' t-as='i'><t t-set='x' t-value=\"{expr}\"/><span t-out='x'/></t></template></odoo>"}


@pytest.mark.parametrize("expr", [
    "current_data[1].pop()",
    "quantity.popitem()",
    "rows.pop(0)",
    "vals.setdefault('a', 1)",
])
def test_m2_local_container_pop_silent(expr):
    assert not _sev(_qw(expr), "unsafe-expression")


@pytest.mark.parametrize("expr", [
    "request.session.pop('uid')",
    "request.session.clear()",
    "env.context.pop('x')",
    "user.sudo().write({'active': False})",
    "doc.update({'name': 'x'})",
])
def test_m2_shared_state_mutation_high(expr):
    assert "high" in _sev(_qw(expr), "unsafe-expression")
