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
    assert node == str(d / "bin" / "node")
