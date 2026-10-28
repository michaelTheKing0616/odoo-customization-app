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
