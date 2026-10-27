"""BOT-VERSION-CAPS: version-capability catalogue (fixtures, data sanity, live smoke)."""

from __future__ import annotations

import os

import pytest

from app.bots import versioncaps as vc
from app.bots.versioncaps import caps as C


def _fx(major: int, extra_field: bool) -> C.Caps:
    mods = {
        "base": {"depends": [], "category": "Hidden", "application": False},
        "product": {"depends": ["base"], "category": "Sales", "application": False},
        "stock": {"depends": ["product"], "category": "Inventory", "application": True},
        "mrp": {"depends": ["stock"], "category": "Manufacturing", "application": True},
        "broken": {"depends": ["base"], "category": "", "application": False},
    }
    f = {
        "name": ["char", "", True, ["base"]],
        "state": ["selection", "", False, ["mrp"], ["draft", "done"]],
    }
    if extra_field:
        f["new_f"] = ["float", "", False, ["mrp"]]
    models = {
        "res.partner": {"modules": ["base"], "fields": {"name": ["char", "", True, ["base"]]}},
        "mrp.bom": {"modules": ["mrp"], "fields": f},
        "stock.quant": {
            "modules": ["stock"],
            "fields": {
                "quantity": ["float", "", False, ["stock"]],
                "x_mrp": ["char", "", False, ["stock", "mrp"]],
            },
        },
        "broken.model": {"modules": ["broken"], "fields": {}},
    }
    if major == 17:
        models["old.model"] = {"modules": ["stock"], "fields": {}}
    return C.Caps(
        major,
        {"major": major, "modules": mods, "models": models, "not_introspectable": ["broken"]},
        {"ent_app": {"min_major": 17}},
    )


@pytest.fixture
def fx(monkeypatch):
    monkeypatch.setattr(C, "_OVERRIDE", {17: _fx(17, False), 18: None, 19: None, 20: _fx(20, True)})


def test_lookups(fx):
    assert vc.module_info(20, "mrp")["depends"] == ["stock"]
    assert vc.module_info(20, "ent_app")["edition"] == "enterprise"
    assert vc.module_info(20, "nope") is None and vc.module_info(99, "mrp") is None
    mi = vc.model_info(20, "mrp.bom")
    assert mi["defined_by_module"] == "mrp" and mi["installed_by_default"] is False
    assert vc.model_info(20, "res.partner")["installed_by_default"] is True
    fi = vc.field_info(20, "mrp.bom", "state")
    assert fi["module"] == "mrp" and fi["selection"] == ["draft", "done"]
    assert (
        vc.field_info(20, "stock.quant", "x_mrp")["module"] == "stock"
    )  # introducer, not redefiner
    assert vc.find_module_for(20, "mrp.bom") == "mrp"
    assert vc.find_module_for(20, "mrp.bom", "new_f") == "mrp"
    assert vc.find_module_for(17, "mrp.bom", "new_f") is None


def test_verdicts(fx):
    a = vc.availability
    assert (
        a(20, "community", ["mrp", "stock", "product"], "mrp.bom", ["state"]).status
        == "installed-ok"
    )
    v = a(20, "community", ["product"], "mrp.bom", ["state"])
    assert v.status == "available-needs-install" and v.module == "mrp"
    assert (
        v.missing_depends == ("mrp", "stock")
        and "Odoo 20 via module mrp; needs install" in v.reason
    )
    v = a(17, "community", [], "mrp.bom", ["new_f"])
    assert v.status == "not-in-this-version" and v.other_versions == (20,)
    v = a(20, "community", [], "old.model")  # blocked/Enterprise could provide it -> unknown
    assert v.status == "unknown" and v.other_versions == (17,)
    v = a(20, "community", [], "x.ent", module_hint="ent_app")
    assert v.status == "enterprise-only" and "not verifiable" in v.reason
    assert a(20, "enterprise", ["ent_app"], "x.ent", module_hint="ent_app").status == "unknown"
    assert a(20, "community", [], "broken.model").status == "unknown"


def test_fail_closed(fx, monkeypatch):
    for ver in (18, 99, None, "abc"):
        assert vc.availability(ver, "community", [], "mrp.bom").status == "unknown"
    assert vc.availability(20, "community", [], "zz.none").status == "unknown"  # ent overlay exists
    assert vc.install_reason(20, "community", [], "mrp.bom").startswith("available in Odoo 20")
    assert vc.install_reason(20, "community", ["mrp", "stock", "product"], "mrp.bom") is None
    monkeypatch.setattr(C, "DATA", C.DATA / "missing")
    C._load_file.cache_clear()
    assert C._load_file(20) is None
    C._load_file.cache_clear()


def test_process_design_uses_caps(fx):
    from app.bots.process_design import design as D

    inv = D.Inventory(20, frozenset({"base"}), frozenset(), {"res.partner": frozenset({"name"})})
    it = D.Item("record", "mrp.bom", {"state": 1}, {})
    D._ground(it, inv)
    assert it.verdict == "stock-install" and "via module mrp" in it.reason and "stock" in it.reason
    gone = D.Item("record", "old.model", {}, {})
    D._ground(gone, inv)
    assert gone.verdict == "needs review"  # catalogue has blocked/Enterprise modules: no demotion
    unk = D.Item("record", "zz.none", {}, {})
    D._ground(unk, inv)
    assert unk.verdict == "needs review"


# ------------------------------------------------------------ data sanity (generated files)
REAL = [v for v in C.MAJORS if (C.DATA / f"caps_{v}.json.gz").exists()]


@pytest.mark.skipif(not {17, 20} <= set(REAL), reason="catalogue 17/20 not generated")
def test_data_sanity():
    C._load_file.cache_clear()
    for v in REAL:
        c = C._load_file(v)
        assert c and c.major == v and len(c.modules) > 300 and len(c.models) > 500
        for m in ("mrp.bom", "stock.quant", "account.move", "res.partner", "stock.move"):
            assert m in c.models, (v, m)
        assert vc.model_info(v, "mrp.bom")["defined_by_module"] == "mrp"
        assert (
            vc.availability(v, "community", ["base"], "mrp.bom").status == "available-needs-install"
        )
    for v in REAL:  # quantity_done was already renamed to quantity in 17
        assert "quantity" in C._load_file(v).models["stock.move"]["fields"]
        assert "quantity_done" not in C._load_file(v).models["stock.move"]["fields"]
    assert "group_id" in C._load_file(17).models["stock.move"]["fields"]
    assert "group_id" not in C._load_file(20).models["stock.move"]["fields"]
    assert "category_id" in C._load_file(17).models["uom.uom"]["fields"]
    assert "category_id" not in C._load_file(20).models["uom.uom"]["fields"]
    if 19 in REAL:
        assert "category_id" not in C._load_file(19).models["uom.uom"]["fields"]
    v = vc.availability(20, "community", [], "stock.move", ["group_id"])
    assert v.status == "not-in-this-version" and v.other_versions[:1] == (17,)
    g = vc.availability(20, "community", [], "account.group")  # Enterprise could add it: unknown
    assert g.status == "unknown" and 17 in g.other_versions


@pytest.mark.skipif(os.environ.get("ODOO_LIVE") != "1", reason="live: needs docker sandbox")
def test_generator_smoke(tmp_path):
    import importlib.util
    import pathlib

    p = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "gen_versioncaps.py"
    spec = importlib.util.spec_from_file_location("gen_vc", p)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    b = g.Box(20, 18399)
    try:
        b.up()
        caps = g.read_caps(b, [])
        assert "res.partner" in caps["models"] and caps["modules"]["base"]["state"] == "installed"
    finally:
        b.down()


def test_configverify_hint(fx):
    from app.bots import configverify as CV

    def call(model, method, args, kw):
        if model == "ir.module.module":
            return [{"name": "base"}, {"name": "product"}]
        if model == "res.partner" and method == "fields_get":
            return {"name": {"type": "char"}}
        raise RuntimeError("no such model")

    v = CV.Verifier(call)
    v.major = 20
    r = v.check(
        {"ref": "a", "kind": "record", "model": "mrp.bom", "key": {"state": "x"}, "expected": {}}
    )
    assert (
        r["status"] == "cannot-read"
        and "available in Odoo 20 via module mrp; needs install" in r["reason"]
    )
    v2 = CV.Verifier(lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    v2.major = 20
    r2 = v2.check(
        {"ref": "b", "kind": "record", "model": "mrp.bom", "key": {"state": "x"}, "expected": {}}
    )
    assert (
        r2["status"] == "cannot-read" and "needs install" not in r2["reason"]
    )  # installed set unknown


def _metric_fields(m):
    out = []
    for side in ("actual", "expected"):
        f = (m.get(side) or {}).get("field")
        if isinstance(f, str):
            out.append([f])
    for k in ("uom_field", "group_by", "date_field"):
        v = m.get(k)
        if isinstance(v, str):
            out.append([v])
        elif isinstance(v, list) and k == "uom_field":
            out.append([x for x in v if isinstance(x, str)])  # candidates: one must exist
        elif isinstance(v, list):
            out.extend([x] for x in v if isinstance(x, str))
    return out


@pytest.mark.skipif(not {17, 20} <= set(REAL), reason="catalogue 17/20 not generated")
def test_variance_fields_exist_per_version():
    import json

    from app.bots.variance import variance as V

    C._load_file.cache_clear()
    bad = []
    for m in json.loads(V.METRICS.read_text())["metrics"]:
        for v in REAL:
            mm = C._load_file(v).models.get(m["model"])
            if mm is None:
                bad.append((v, m["id"], m["model"]))
                continue
            for cands in _metric_fields(m):
                if cands and not any(c.split(".")[0] in mm["fields"] for c in cands):
                    bad.append((v, m["id"], cands))
    assert not bad, bad


def test_blocked_and_uninstallable(fx):
    assert vc.module_info(20, "broken")["introspected"] is False
    c = C.Caps(
        20,
        {"major": 20, "modules": {"stub": {"state": "uninstallable", "depends": []}}, "models": {}},
    )
    assert "stub" in c.blocked and "stub" not in c.modules


def _clean(major, with_old):
    c = _fx(major, False)
    d = dict(c.data, not_introspectable=[])
    d["modules"] = {k: v for k, v in d["modules"].items() if k != "broken"}
    d["models"] = {k: v for k, v in d["models"].items() if k != "broken.model"}
    if not with_old:
        d["models"].pop("old.model", None)
    return C.Caps(major, d, {})


def test_not_in_version_only_when_nothing_unread(monkeypatch):
    from app.bots.process_design import design as D

    monkeypatch.setattr(
        C, "_OVERRIDE", {17: _clean(17, True), 18: None, 19: None, 20: _clean(20, False)}
    )
    v = vc.availability(20, "community", [], "old.model")
    assert v.status == "not-in-this-version" and v.other_versions == (17,)
    inv = D.Inventory(20, frozenset({"base"}), frozenset(), {})
    it = D.Item("record", "old.model", {}, {})
    D._ground(it, inv)
    assert it.verdict == "needs-custom" and "exists in 17" in it.reason


def test_odd_inputs_unknown(fx):
    a = vc.availability
    for args in (
        (20, "community", None, "mrp.bom"),
        (20, "community", [], ["mrp.bom"]),
        (20, "community", [], "mrp.bom", [1, 2]),
        (20, "community", [], "mrp.bom", "state"),
        (20, None, [], "mrp.bom"),
        (20, "community", [], "mrp.bom", (), 5),
        (20, "community", [3], "mrp.bom"),
    ):
        assert a(*args).status == "unknown", args


def test_catalogue_fault_unknown_and_integrations_survive(monkeypatch):
    from app.bots import configverify as CV
    from app.bots.process_design import design as D

    class Boom(C.Caps):
        @property
        def models(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(C, "_OVERRIDE", {20: Boom(20, {"major": 20, "modules": {}, "models": {}})})
    assert vc.availability(20, "community", [], "mrp.bom").status == "unknown"
    monkeypatch.setattr(vc, "availability", lambda *a, **k: 1 / 0)
    monkeypatch.setattr(C, "availability", lambda *a, **k: 1 / 0)
    inv = D.Inventory(20, frozenset({"base"}), frozenset(), {})
    it = D.Item("record", "mrp.bom", {"state": 1}, {})
    D._ground(it, inv)
    assert it.verdict == "needs review"
    v = CV.Verifier(lambda m, *a: [{"name": "base"}] if m == "ir.module.module" else 1 / 0)
    v.major = 20
    r = v.check(
        {"ref": "a", "kind": "record", "model": "mrp.bom", "key": {"state": "x"}, "expected": {}}
    )
    assert r["status"] == "cannot-read" and r["reason"] == "model mrp.bom not readable or absent"


def test_custom_fields_no_claim(fx):
    v = vc.availability(
        20, "community", ["mrp", "stock", "product"], "mrp.bom", ["x_studio_f", "state"]
    )
    assert v.status == "installed-ok"


def test_enterprise_on_community_db_stays_enterprise_only(fx):
    v = vc.availability(20, "community", ["ent_app"], "x.ent", module_hint="ent_app")
    assert v.status == "enterprise-only"


def test_installed_by_default_order_free(fx, monkeypatch):
    c = _fx(20, False)
    c.data["models"]["res.partner"]["modules"] = ["mrp", "base"]
    monkeypatch.setattr(C, "_OVERRIDE", {20: c})
    assert vc.model_info(20, "res.partner")["installed_by_default"] is True


def _write(p, raw):
    import gzip as G

    p.write_bytes(G.compress(raw))


@pytest.mark.parametrize(
    "raw",
    [
        None,  # truncated gzip
        b"[1, 2]",
        b'{"major": 20, "modules": [], "models": {}}',
        b'{"major": 20, "modules": {}, "models": {"m": {"fields": {"f": ["char"]}}}}',
        b'{"major": 20, "modules": {"a": {"depends": "x"}}, "models": {"m": {"fields": {}}}}',  # noqa: E501
        b'{"major": 17, "modules": {}, "models": {"m": {"fields": {}}}}',  # major mismatch
    ],
)
def test_corrupt_data_fails_closed(tmp_path, monkeypatch, raw):
    import gzip as G

    p = tmp_path / "caps_20.json.gz"
    if raw is None:
        p.write_bytes(G.compress(b'{"major": 20}' * 50)[:20])
    else:
        _write(p, raw)
    monkeypatch.setattr(C, "DATA", tmp_path)
    monkeypatch.setattr(C, "_OVERRIDE", {})
    C._load_file.cache_clear()
    try:
        assert C._load_file(20) is None
        assert vc.availability(20, "community", [], "m").status == "unknown"
    finally:
        C._load_file.cache_clear()


@pytest.mark.skipif(set(REAL) != set(C.MAJORS), reason="catalogue not generated")
def test_real_dependency_facts():
    C._load_file.cache_clear()
    for v in C.MAJORS:
        assert "stock" in vc.module_info(v, "mrp")["depends"]
        assert vc.model_info(v, "stock.move")["defined_by_module"] == "stock"
        assert vc.model_info(v, "res.partner")["defined_by_module"] == "base"
        chain = vc.availability(v, "community", [], "mrp.bom").missing_depends
        assert {"mrp", "stock", "product"} <= set(chain)
        c = C._load_file(v)
        assert sum(1 for m in c.listed.values() if m["depends"]) >= 0.8 * (len(c.listed) - 1)


# ------------------------------------------------------------ provenance (fail closed)
@pytest.mark.skipif(not REAL, reason="catalogue not generated")
def test_provenance_present_and_matches():
    C._load_file.cache_clear()
    for v in REAL:
        p = vc.provenance(v)
        assert p["major"] == v and p["source_image"] == f"odoo:{v}" and p["edition"] == "community"
        assert p["image_id"].startswith("sha256:") and p["generated"] >= "2026-10-26"
        assert "ir.model.fields" in p["sources"]
    assert vc.provenance(99) is None and vc.provenance("x") is None


def _write_caps(path, d):
    import gzip
    import json

    path.write_bytes(gzip.compress(json.dumps(d).encode()))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("provenance"),
        lambda d: d["provenance"].update(major=18),
        lambda d: d["provenance"].update(source_image="odoo:18"),
        lambda d: d["provenance"].update(generated="yesterday"),
        lambda d: d["provenance"].update(image_id=""),
        lambda d: d["provenance"].pop("sources"),
    ],
)
@pytest.mark.skipif(17 not in REAL, reason="catalogue 17 not generated")
def test_bad_provenance_refused(tmp_path, monkeypatch, mutate):
    import copy

    d = copy.deepcopy(dict(C._load_file(17).data))
    mutate(d)
    _write_caps(tmp_path / "caps_17.json.gz", d)
    monkeypatch.setattr(C, "DATA", tmp_path)
    C._load_file.cache_clear()
    try:
        assert C._load_file(17) is None
        assert vc.availability(17, "community", [], "mrp.bom").status == "unknown"
    finally:
        C._load_file.cache_clear()


@pytest.mark.parametrize("raw", [b"", b"not gzip", b"\x1f\x8b\x08\x00garbage"])
def test_corrupt_catalogue_refused(tmp_path, monkeypatch, raw):
    (tmp_path / "caps_17.json.gz").write_bytes(raw)
    monkeypatch.setattr(C, "DATA", tmp_path)
    C._load_file.cache_clear()
    try:
        assert C._load_file(17) is None and vc.provenance(17) is None
    finally:
        C._load_file.cache_clear()
